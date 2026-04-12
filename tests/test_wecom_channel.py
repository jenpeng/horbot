import unittest

from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import AsyncMock, patch

from horbot.bus.queue import MessageBus
from horbot.channels.wecom import (
    WeComChannel,
    build_wecom_subscribe_frame,
    decrypt_wecom_media,
    parse_wecom_inbound,
)
from horbot.config.schema import WeComConfig, WeComGroupRule


class WeComChannelTests(unittest.TestCase):
    def test_subscribe_frame_uses_header_req_id(self):
        frame = build_wecom_subscribe_frame("bot-id", "secret")

        self.assertEqual(frame["cmd"], "aibot_subscribe")
        self.assertEqual(frame["body"]["bot_id"], "bot-id")
        self.assertTrue(frame["headers"]["req_id"])

    def test_parse_wecom_inbound_text_message(self):
        parsed = parse_wecom_inbound({
            "cmd": "aibot_msg_callback",
            "headers": {"req_id": "req-123"},
            "body": {
                "msgid": "msg-1",
                "msgtype": "text",
                "chatid": "chat-123",
                "from_userid": "user-123",
                "text": {"content": "hello from wecom"},
            },
        })

        self.assertIsNotNone(parsed)
        assert parsed is not None
        self.assertEqual(parsed["sender_id"], "user-123")
        self.assertEqual(parsed["chat_id"], "chat-123")
        self.assertEqual(parsed["content"], "hello from wecom")
        self.assertFalse(parsed["is_group"])
        self.assertEqual(parsed["reply_req_id"], "req-123")

    def test_decrypt_wecom_media_roundtrip(self):
        from cryptography.hazmat.primitives import padding
        from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
        import base64

        key = b"1234567890abcdef1234567890abcdef"
        plain = b"hello wecom media"
        padder = padding.PKCS7(128).padder()
        padded = padder.update(plain) + padder.finalize()
        cipher = Cipher(algorithms.AES(key), modes.CBC(key[:16]))
        encryptor = cipher.encryptor()
        ciphertext = encryptor.update(padded) + encryptor.finalize()
        aeskey = base64.b64encode(key).decode("ascii")

        self.assertEqual(decrypt_wecom_media(ciphertext, aeskey), plain)

    def test_group_policy_and_group_sender_allowlist_are_enforced(self):
        channel = WeComChannel(
            WeComConfig(
                enabled=True,
                bot_id="bot-id",
                secret="secret",
                group_policy="allowlist",
                group_allow_from=["chat-123"],
                groups={"chat-123": WeComGroupRule(allow_from=["user-1"])},
            ),
            MessageBus(),
        )

        self.assertTrue(channel._is_message_allowed("user-1", "chat-123", is_group=True))
        self.assertFalse(channel._is_message_allowed("user-2", "chat-123", is_group=True))
        self.assertFalse(channel._is_message_allowed("user-1", "chat-999", is_group=True))


class WeComChannelAsyncTests(unittest.IsolatedAsyncioTestCase):
    async def test_progress_messages_are_coalesced_into_stream_updates(self):
        channel = WeComChannel(
            WeComConfig(
                enabled=True,
                bot_id="bot-id",
                secret="secret",
                stream_replies=True,
                stream_buffer_threshold=1,
                stream_edit_interval_ms=0,
            ),
            MessageBus(),
            endpoint_id="wecom-sales",
        )
        channel._connected = True
        channel._ws = object()
        channel._send_request = AsyncMock(return_value={"cmd": "ok", "headers": {"req_id": "ack"}})  # type: ignore[method-assign]

        await channel.send(type("Msg", (), {
            "chat_id": "chat-1",
            "content": "Hel",
            "metadata": {"_progress": True, "wecom": {"reply_req_id": "req-1"}},
            "reply_to": None,
            "media": [],
            "channel_instance_id": "wecom-sales",
        })())
        await channel.send(type("Msg", (), {
            "chat_id": "chat-1",
            "content": "lo",
            "metadata": {"_progress": True, "wecom": {"reply_req_id": "req-1"}},
            "reply_to": None,
            "media": [],
            "channel_instance_id": "wecom-sales",
        })())
        await channel.send(type("Msg", (), {
            "chat_id": "chat-1",
            "content": "Hello world",
            "metadata": {"wecom": {"reply_req_id": "req-1"}},
            "reply_to": None,
            "media": [],
            "channel_instance_id": "wecom-sales",
        })())

        sent_frames = [call.args[0] for call in channel._send_request.await_args_list]  # type: ignore[attr-defined]
        self.assertEqual(sent_frames[0]["cmd"], "aibot_reply_stream")
        self.assertEqual(sent_frames[1]["cmd"], "aibot_reply_stream")
        self.assertEqual(sent_frames[2]["cmd"], "aibot_reply_stream")
        self.assertTrue(sent_frames[2]["body"]["finish"])
        self.assertEqual(sent_frames[2]["body"]["content"], "Hello world")

    async def test_send_media_uses_upload_and_reply_frame(self):
        channel = WeComChannel(
            WeComConfig(enabled=True, bot_id="bot-id", secret="secret"),
            MessageBus(),
        )
        channel._connected = True
        channel._ws = object()
        channel._upload_media = AsyncMock(return_value="media-1")  # type: ignore[method-assign]
        channel._send_request = AsyncMock(return_value={"cmd": "ok", "headers": {"req_id": "ack"}})  # type: ignore[method-assign]

        with TemporaryDirectory() as tmpdir:
            media_path = Path(tmpdir) / "image.png"
            media_path.write_bytes(b"fake-image")
            await channel._send_media_message("chat-1", str(media_path), reply_req_id="req-1")

        frame = channel._send_request.await_args.args[0]  # type: ignore[attr-defined]
        self.assertEqual(frame["cmd"], "aibot_reply_msg")
        self.assertEqual(frame["body"]["msg_item"]["msgtype"], "image")
        self.assertEqual(frame["body"]["msg_item"]["image"]["media_id"], "media-1")

    async def test_inbound_media_is_materialized_when_enabled(self):
        channel = WeComChannel(
            WeComConfig(enabled=True, bot_id="bot-id", secret="secret", download_media=True),
            MessageBus(),
        )

        with TemporaryDirectory() as tmpdir:
            with patch("horbot.channels.wecom.get_data_path", return_value=Path(tmpdir)):
                class Response:
                    content = b"payload-bytes"

                    def raise_for_status(self) -> None:
                        return None

                class Client:
                    get = AsyncMock(return_value=Response())

                channel._get_http_client = AsyncMock(return_value=Client())  # type: ignore[method-assign]
                with patch("horbot.channels.wecom.decrypt_wecom_media", return_value=b"decrypted"):
                    paths, markers = await channel._materialize_inbound_media([{
                        "type": "image",
                        "url": "https://example.com/file",
                        "aeskey": "abc",
                        "filename": "image.png",
                    }])

        self.assertEqual(len(paths), 1)
        self.assertIn("[image:", markers[0].lower())


if __name__ == "__main__":
    unittest.main()
