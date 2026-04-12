"""WeCom AI Bot channel using the WebSocket gateway."""

from __future__ import annotations

import asyncio
import base64
import hashlib
import json
import mimetypes
import uuid
from collections import OrderedDict
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import httpx
from cryptography.hazmat.primitives import padding
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
from loguru import logger

from horbot.bus.events import OutboundMessage
from horbot.bus.queue import MessageBus
from horbot.channels.base import BaseChannel
from horbot.config.schema import WeComConfig
from horbot.utils.helpers import get_data_path, safe_filename

try:
    import websockets

    WECOM_WEBSOCKETS_AVAILABLE = True
except ImportError:  # pragma: no cover - dependency is declared in pyproject
    websockets = None
    WECOM_WEBSOCKETS_AVAILABLE = False

_IMAGE_EXTS = {".jpg", ".jpeg", ".png", ".gif", ".bmp", ".webp"}
_AUDIO_EXTS = {".mp3", ".wav", ".ogg", ".opus", ".m4a", ".aac"}
_VIDEO_EXTS = {".mp4", ".mov", ".avi", ".mkv", ".webm"}
_UPLOAD_CHUNK_SIZE = 512 * 1024
_MEDIA_CACHE_LIMIT = 1024


@dataclass
class WeComStreamState:
    key: str
    reply_req_id: str
    chat_id: str
    stream_id: str
    content: str = ""
    last_sent_len: int = 0
    last_flush_at: float = 0.0


def _first_str(*values: Any) -> str:
    for value in values:
        if isinstance(value, str) and value.strip():
            return value.strip()
    return ""


def _normalize_identifier(value: str) -> str:
    cleaned = str(value or "").strip()
    if ":" in cleaned:
        cleaned = cleaned.split(":")[-1].strip()
    return cleaned.lower()


def _matches_allowlist(value: str, allowlist: list[str]) -> bool:
    if not allowlist:
        return True
    normalized = _normalize_identifier(value)
    for candidate in allowlist:
        candidate_normalized = _normalize_identifier(candidate)
        if candidate_normalized in {"*", "all"} or candidate_normalized == normalized:
            return True
    return False


def _frame_req_id(frame: dict[str, Any]) -> str:
    headers = frame.get("headers")
    if isinstance(headers, dict):
        value = _first_str(headers.get("req_id"), headers.get("request_id"))
        if value:
            return value
    return _first_str(frame.get("req_id"), frame.get("request_id"))


def _frame_body(frame: dict[str, Any]) -> dict[str, Any]:
    body = frame.get("body")
    return body if isinstance(body, dict) else {}


def _make_frame(cmd: str, body: dict[str, Any], *, req_id: str | None = None) -> dict[str, Any]:
    return {
        "cmd": cmd,
        "headers": {
            "req_id": req_id or uuid.uuid4().hex,
        },
        "body": body,
    }


def build_wecom_subscribe_frame(bot_id: str, secret: str) -> dict[str, Any]:
    return _make_frame("aibot_subscribe", {"bot_id": bot_id, "secret": secret})


def build_wecom_send_frame(chat_id: str, msg_item: dict[str, Any]) -> dict[str, Any]:
    return _make_frame("aibot_send_msg", {"chatid": chat_id, "msg_item": msg_item})


def build_wecom_reply_frame(reply_req_id: str, msg_item: dict[str, Any]) -> dict[str, Any]:
    return _make_frame("aibot_reply_msg", {"req_id": reply_req_id, "msg_item": msg_item})


def build_wecom_reply_stream_frame(
    reply_req_id: str,
    stream_id: str,
    content: str,
    *,
    finish: bool,
) -> dict[str, Any]:
    return _make_frame(
        "aibot_reply_stream",
        {
            "req_id": reply_req_id,
            "stream_id": stream_id,
            "content": content,
            "finish": finish,
        },
    )


def build_wecom_upload_init_frame(
    *,
    filename: str,
    media_type: str,
    file_size: int,
    file_md5: str,
) -> dict[str, Any]:
    return _make_frame(
        "aibot_upload_media_init",
        {
            "filename": filename,
            "media_type": media_type,
            "file_size": file_size,
            "file_md5": file_md5,
        },
    )


def build_wecom_upload_chunk_frame(upload_id: str, index: int, content_b64: str) -> dict[str, Any]:
    return _make_frame(
        "aibot_upload_media_chunk",
        {
            "upload_id": upload_id,
            "index": index,
            "content": content_b64,
        },
    )


def build_wecom_upload_finish_frame(upload_id: str) -> dict[str, Any]:
    return _make_frame("aibot_upload_media_finish", {"upload_id": upload_id})


def build_wecom_text_msg_item(content: str) -> dict[str, Any]:
    return {
        "msgtype": "markdown",
        "markdown": {"content": content},
    }


def build_wecom_media_msg_item(media_type: str, media_id: str) -> dict[str, Any]:
    return {
        "msgtype": media_type,
        media_type: {"media_id": media_id},
    }


def is_wecom_subscribe_success(frame: dict[str, Any]) -> bool:
    cmd = str(frame.get("cmd") or "").strip().lower()
    code = frame.get("errcode", frame.get("code"))
    if not cmd.startswith("aibot_subscribe"):
        return False
    return code in (None, 0, "0", True) and not extract_wecom_error(frame)


def extract_wecom_error(frame: dict[str, Any]) -> str:
    for container in (frame, _frame_body(frame)):
        if not isinstance(container, dict):
            continue
        for key in ("errmsg", "message", "error", "detail"):
            value = container.get(key)
            if isinstance(value, str) and value.strip():
                return value.strip()
    return ""


def is_wecom_message_callback(frame: dict[str, Any]) -> bool:
    cmd = str(frame.get("cmd") or frame.get("action") or frame.get("type") or "").strip().lower()
    return cmd in {"aibot_msg_callback", "aibot_message_callback"}


def _message_payload(body: dict[str, Any]) -> dict[str, Any]:
    msg_item = body.get("msg_item")
    if isinstance(msg_item, dict):
        return msg_item
    return body


def _extract_message_text(payload: dict[str, Any]) -> str:
    text_payload = payload.get("text")
    if isinstance(text_payload, dict):
        content = _first_str(text_payload.get("content"), text_payload.get("text"))
        if content:
            return content

    markdown_payload = payload.get("markdown")
    if isinstance(markdown_payload, dict):
        content = _first_str(markdown_payload.get("content"), markdown_payload.get("text"))
        if content:
            return content

    mixed_payload = payload.get("mixed")
    if isinstance(mixed_payload, dict):
        parts: list[str] = []
        for item in mixed_payload.get("items", []) if isinstance(mixed_payload.get("items"), list) else []:
            if isinstance(item, dict):
                part = _first_str(
                    item.get("content"),
                    ((item.get("text") or {}).get("content") if isinstance(item.get("text"), dict) else item.get("text")),
                )
                if part:
                    parts.append(part)
        if parts:
            return "\n".join(parts)

    voice_payload = payload.get("voice")
    if isinstance(voice_payload, dict):
        content = _first_str(
            voice_payload.get("recognized_text"),
            voice_payload.get("transcript"),
            voice_payload.get("content"),
        )
        if content:
            return content
        return "[Voice Message]"

    file_payload = payload.get("file")
    if isinstance(file_payload, dict):
        name = _first_str(file_payload.get("filename"), file_payload.get("name"))
        return f"[File] {name}".strip()

    image_payload = payload.get("image")
    if isinstance(image_payload, dict):
        alt = _first_str(image_payload.get("alt"), image_payload.get("name"))
        return f"[Image] {alt}".strip()

    return _first_str(payload.get("content"), payload.get("msg"), payload.get("message"))


def _extract_media_entries(payload: dict[str, Any]) -> list[dict[str, Any]]:
    entries: list[dict[str, Any]] = []
    for media_type in ("image", "file", "voice", "video"):
        info = payload.get(media_type)
        if not isinstance(info, dict):
            continue
        url = _first_str(info.get("url"), info.get("download_url"))
        aeskey = _first_str(info.get("aeskey"), info.get("aes_key"))
        if not url:
            continue
        entries.append({
            "type": media_type,
            "url": url,
            "aeskey": aeskey,
            "filename": _first_str(
                info.get("filename"),
                info.get("name"),
                info.get("title"),
                f"{media_type}-{hashlib.md5(url.encode()).hexdigest()[:8]}",
            ),
            "mime": _first_str(info.get("mime_type"), info.get("content_type")),
            "size": info.get("size"),
        })
    return entries


def parse_wecom_inbound(frame: dict[str, Any]) -> dict[str, Any] | None:
    body = _frame_body(frame)
    if not body:
        return None

    payload = _message_payload(body)
    content = _extract_message_text(payload)
    media_entries = _extract_media_entries(payload)
    if not content and not media_entries:
        return None

    sender_info = body.get("from") if isinstance(body.get("from"), dict) else {}
    sender_id = _first_str(
        body.get("from_userid"),
        body.get("from_user_id"),
        body.get("userid"),
        body.get("user_id"),
        body.get("external_userid"),
        body.get("senderid"),
        sender_info.get("userid"),
        sender_info.get("user_id"),
        sender_info.get("external_userid"),
        sender_info.get("id"),
    )
    chat_id = _first_str(
        body.get("chatid"),
        body.get("chat_id"),
        body.get("conversation_id"),
        body.get("roomid"),
        body.get("group_id"),
        body.get("session_id"),
        sender_id,
    )
    if not sender_id or not chat_id:
        return None

    sender_name = _first_str(
        body.get("from_name"),
        body.get("sender_name"),
        sender_info.get("name"),
        sender_info.get("nickname"),
    )
    message_id = _first_str(body.get("msgid"), body.get("message_id"), _frame_req_id(frame))
    chat_type = _first_str(body.get("chat_type"), body.get("conversation_type"), body.get("scene"))
    is_group = bool(
        body.get("is_group")
        or body.get("group_id")
        or body.get("roomid")
        or chat_type.lower() in {"group", "room", "chatroom"}
    )

    return {
        "sender_id": sender_id,
        "sender_name": sender_name,
        "chat_id": chat_id,
        "content": content,
        "is_group": is_group,
        "message_id": message_id,
        "chat_type": chat_type or ("group" if is_group else "direct"),
        "reply_req_id": _frame_req_id(frame),
        "raw_body": body,
        "media_entries": media_entries,
    }


def decrypt_wecom_media(ciphertext: bytes, aeskey: str) -> bytes:
    padding_needed = (-len(aeskey)) % 4
    key = base64.b64decode(aeskey + ("=" * padding_needed))
    cipher = Cipher(algorithms.AES(key), modes.CBC(key[:16]))
    decryptor = cipher.decryptor()
    padded = decryptor.update(ciphertext) + decryptor.finalize()
    unpadder = padding.PKCS7(128).unpadder()
    return unpadder.update(padded) + unpadder.finalize()


def detect_wecom_media_type(path: str | Path) -> str:
    suffix = Path(path).suffix.lower()
    if suffix in _IMAGE_EXTS:
        return "image"
    if suffix in _AUDIO_EXTS:
        return "voice"
    if suffix in _VIDEO_EXTS:
        return "video"
    mime, _ = mimetypes.guess_type(str(path), strict=False)
    if mime and mime.startswith("image/"):
        return "image"
    if mime and mime.startswith("audio/"):
        return "voice"
    if mime and mime.startswith("video/"):
        return "video"
    return "file"


class WeComChannel(BaseChannel):
    """WeCom AI Bot channel over WebSocket."""

    name = "wecom"

    def __init__(self, config: WeComConfig, bus: MessageBus, **channel_kwargs):
        super().__init__(config, bus, **channel_kwargs)
        self.config: WeComConfig = config
        self._ws: Any = None
        self._connected = False
        self._heartbeat_task: asyncio.Task | None = None
        self._send_lock = asyncio.Lock()
        self._request_futures: dict[str, asyncio.Future[dict[str, Any]]] = {}
        self._seen_message_ids: OrderedDict[str, None] = OrderedDict()
        self._active_streams: dict[str, WeComStreamState] = {}
        self._http: httpx.AsyncClient | None = None

    async def start(self) -> None:
        if not WECOM_WEBSOCKETS_AVAILABLE:
            logger.error("websockets is not installed, WeCom channel unavailable")
            return
        if not self.config.bot_id or not self.config.secret:
            logger.error("WeCom bot_id and secret are not configured")
            return

        self._running = True
        reconnect_delay = 5
        websocket_url = (self.config.websocket_url or "wss://openws.work.weixin.qq.com").strip()

        while self._running:
            try:
                logger.info("Connecting to WeCom gateway at {}...", websocket_url)
                async with websockets.connect(websocket_url, ping_interval=None, open_timeout=10) as ws:
                    self._ws = ws
                    await self._authenticate()
                    self._connected = True
                    reconnect_delay = 5
                    logger.info("Connected to WeCom gateway")
                    self._heartbeat_task = asyncio.create_task(self._heartbeat())

                    async for raw in ws:
                        await self._handle_raw_frame(raw)
            except asyncio.CancelledError:
                break
            except Exception as exc:
                logger.warning("WeCom connection error: {}", exc)
            finally:
                self._connected = False
                self._ws = None
                self._active_streams.clear()
                for future in self._request_futures.values():
                    if not future.done():
                        future.cancel()
                self._request_futures.clear()
                if self._heartbeat_task:
                    self._heartbeat_task.cancel()
                    try:
                        await self._heartbeat_task
                    except asyncio.CancelledError:
                        pass
                    self._heartbeat_task = None

            if self._running:
                logger.info("Reconnecting to WeCom in {} seconds...", reconnect_delay)
                await asyncio.sleep(reconnect_delay)
                reconnect_delay = min(reconnect_delay * 2, 30)

    async def stop(self) -> None:
        self._running = False
        self._connected = False
        self._active_streams.clear()
        if self._heartbeat_task:
            self._heartbeat_task.cancel()
            try:
                await self._heartbeat_task
            except asyncio.CancelledError:
                pass
            self._heartbeat_task = None
        if self._ws:
            await self._ws.close()
            self._ws = None
        if self._http:
            await self._http.aclose()
            self._http = None

    async def send(self, msg: OutboundMessage) -> None:
        if not self._connected or not self._ws:
            logger.warning("WeCom gateway not connected")
            return

        is_progress = bool((msg.metadata or {}).get("_progress"))
        wecom_meta = (msg.metadata or {}).get("wecom", {}) if isinstance(msg.metadata, dict) else {}
        reply_req_id = _first_str(wecom_meta.get("reply_req_id"))

        if is_progress and self.config.stream_replies and reply_req_id:
            await self._send_progress_update(msg, reply_req_id)
            return

        stream_key = self._stream_key(msg, reply_req_id)
        active_stream = self._active_streams.pop(stream_key, None)
        finalized_stream = active_stream is not None
        if active_stream:
            final_text = str(msg.content or "").strip() or active_stream.content
            active_stream.content = final_text
            await self._flush_stream(active_stream, finish=True)

        for media_path in msg.media or []:
            await self._send_media_message(msg.chat_id, media_path, reply_req_id=reply_req_id)

        content = str(msg.content or "").strip()
        if content and not finalized_stream:
            await self._send_text_message(msg.chat_id, content, reply_req_id=reply_req_id)

    async def _authenticate(self) -> None:
        frame = build_wecom_subscribe_frame(self.config.bot_id, self.config.secret)
        response = await self._send_request(frame, timeout=10)
        if not is_wecom_subscribe_success(response):
            raise RuntimeError(extract_wecom_error(response) or "WeCom subscribe failed")

    async def _heartbeat(self) -> None:
        while self._running and self._ws:
            try:
                pong = await self._ws.ping()
                await asyncio.wait_for(pong, timeout=10)
            except asyncio.CancelledError:
                raise
            except Exception as exc:
                logger.debug("WeCom heartbeat failed: {}", exc)
                return
            await asyncio.sleep(30)

    async def _send_request(self, frame: dict[str, Any], timeout: float = 20.0) -> dict[str, Any]:
        if not self._ws:
            raise RuntimeError("WeCom gateway is not connected")
        req_id = _frame_req_id(frame)
        if not req_id:
            raise RuntimeError("WeCom frame missing req_id")
        loop = asyncio.get_running_loop()
        future: asyncio.Future[dict[str, Any]] = loop.create_future()
        self._request_futures[req_id] = future
        try:
            async with self._send_lock:
                await self._ws.send(json.dumps(frame, ensure_ascii=False))
            response = await asyncio.wait_for(future, timeout=timeout)
        finally:
            self._request_futures.pop(req_id, None)
        error = extract_wecom_error(response)
        if error:
            raise RuntimeError(error)
        return response

    async def _handle_raw_frame(self, raw: str) -> None:
        try:
            frame = json.loads(raw)
        except json.JSONDecodeError:
            logger.warning("Invalid JSON from WeCom gateway: {}", raw[:200])
            return
        await self._handle_frame_dict(frame)

    async def _handle_frame_dict(self, frame: dict[str, Any]) -> None:
        if not isinstance(frame, dict):
            return

        req_id = _frame_req_id(frame)
        if req_id:
            future = self._request_futures.get(req_id)
            if future and not future.done() and not is_wecom_message_callback(frame):
                future.set_result(frame)
                return

        if not is_wecom_message_callback(frame):
            error = extract_wecom_error(frame)
            if error:
                logger.warning("WeCom gateway error: {}", error)
            return

        inbound = parse_wecom_inbound(frame)
        if inbound is None:
            return

        message_id = inbound["message_id"]
        if message_id and self._is_duplicate_message(message_id):
            logger.debug("Skipping duplicate WeCom message {}", message_id)
            return

        if not self._is_message_allowed(
            sender_id=inbound["sender_id"],
            chat_id=inbound["chat_id"],
            is_group=inbound["is_group"],
        ):
            logger.debug(
                "Ignoring WeCom message due to policy: sender={}, chat_id={}, is_group={}",
                inbound["sender_id"],
                inbound["chat_id"],
                inbound["is_group"],
            )
            return

        media_paths, markers = await self._materialize_inbound_media(inbound["media_entries"])
        content_parts = [part for part in [inbound["content"], *markers] if isinstance(part, str) and part.strip()]

        await self._handle_message(
            sender_id=inbound["sender_id"],
            chat_id=inbound["chat_id"],
            content="\n".join(content_parts).strip(),
            media=media_paths,
            metadata={
                "message_id": message_id,
                "is_group": inbound["is_group"],
                "chat_type": inbound["chat_type"],
                "sender_name": inbound["sender_name"],
                "raw": inbound["raw_body"],
                "wecom": {
                    "reply_req_id": inbound["reply_req_id"],
                    "message_id": message_id,
                    "media_entries": inbound["media_entries"],
                },
            },
        )

    async def _get_http_client(self) -> httpx.AsyncClient:
        if self._http is None:
            self._http = httpx.AsyncClient(timeout=30.0)
        return self._http

    async def _materialize_inbound_media(self, media_entries: list[dict[str, Any]]) -> tuple[list[str], list[str]]:
        if not media_entries:
            return [], []

        if not self.config.download_media:
            markers = [f"[{entry['type']}: {entry['filename']}]" for entry in media_entries]
            return [], markers

        media_dir = get_data_path() / "media" / "wecom"
        media_dir.mkdir(parents=True, exist_ok=True)
        client = await self._get_http_client()
        paths: list[str] = []
        markers: list[str] = []

        for entry in media_entries[:_MEDIA_CACHE_LIMIT]:
            filename = safe_filename(entry["filename"]) or f"{entry['type']}-{uuid.uuid4().hex[:8]}"
            try:
                response = await client.get(entry["url"])
                response.raise_for_status()
                data = response.content
                aeskey = _first_str(entry.get("aeskey"))
                if aeskey:
                    data = decrypt_wecom_media(data, aeskey)
                file_path = media_dir / filename
                file_path.write_bytes(data)
                paths.append(str(file_path))
                markers.append(f"[{entry['type']}: {file_path}]")
            except Exception as exc:
                logger.warning("Failed to download WeCom {} {}: {}", entry["type"], filename, exc)
                markers.append(f"[{entry['type']}: {filename} - download failed]")

        return paths, markers

    async def _send_text_message(self, chat_id: str, content: str, *, reply_req_id: str | None = None) -> None:
        msg_item = build_wecom_text_msg_item(content)
        frame = build_wecom_reply_frame(reply_req_id, msg_item) if reply_req_id else build_wecom_send_frame(chat_id, msg_item)
        await self._send_request(frame)

    async def _send_media_message(self, chat_id: str, media_path: str, *, reply_req_id: str | None = None) -> None:
        path = Path(media_path).expanduser()
        if not path.is_file():
            logger.warning("WeCom media file not found: {}", media_path)
            return

        media_type = detect_wecom_media_type(path)
        media_id = await self._upload_media(path, media_type)
        msg_item = build_wecom_media_msg_item(media_type, media_id)
        frame = build_wecom_reply_frame(reply_req_id, msg_item) if reply_req_id else build_wecom_send_frame(chat_id, msg_item)
        await self._send_request(frame)

    async def _upload_media(self, path: Path, media_type: str) -> str:
        data = path.read_bytes()
        init_frame = build_wecom_upload_init_frame(
            filename=safe_filename(path.name) or path.name,
            media_type=media_type,
            file_size=len(data),
            file_md5=hashlib.md5(data).hexdigest(),
        )
        init_response = await self._send_request(init_frame)
        init_body = _frame_body(init_response)

        media_id = _first_str(init_body.get("media_id"), init_response.get("media_id"))
        if media_id:
            return media_id

        upload_id = _first_str(init_body.get("upload_id"), init_response.get("upload_id"))
        if not upload_id:
            raise RuntimeError("WeCom upload init did not return upload_id")

        for index, start in enumerate(range(0, len(data), _UPLOAD_CHUNK_SIZE), start=1):
            chunk = data[start:start + _UPLOAD_CHUNK_SIZE]
            chunk_frame = build_wecom_upload_chunk_frame(
                upload_id,
                index,
                base64.b64encode(chunk).decode("ascii"),
            )
            await self._send_request(chunk_frame)

        finish_response = await self._send_request(build_wecom_upload_finish_frame(upload_id))
        finish_body = _frame_body(finish_response)
        media_id = _first_str(finish_body.get("media_id"), finish_response.get("media_id"))
        if not media_id:
            raise RuntimeError("WeCom upload finish did not return media_id")
        return media_id

    async def _send_progress_update(self, msg: OutboundMessage, reply_req_id: str) -> None:
        delta = str(msg.content or "")
        if not delta:
            return

        key = self._stream_key(msg, reply_req_id)
        state = self._active_streams.get(key)
        if state is None:
            state = WeComStreamState(
                key=key,
                reply_req_id=reply_req_id,
                chat_id=msg.chat_id,
                stream_id=uuid.uuid4().hex,
            )
            self._active_streams[key] = state

        if not state.content:
            state.content = delta
        elif delta.startswith(state.content):
            state.content = delta
        elif state.content.endswith(delta):
            pass
        else:
            state.content += delta
        now = asyncio.get_running_loop().time()
        should_flush = (
            state.last_sent_len == 0
            or len(state.content) - state.last_sent_len >= max(int(self.config.stream_buffer_threshold), 1)
            or (now - state.last_flush_at) * 1000 >= max(int(self.config.stream_edit_interval_ms), 100)
        )
        if should_flush:
            await self._flush_stream(state, finish=False)

    async def _flush_stream(self, state: WeComStreamState, *, finish: bool) -> None:
        content = state.content
        if self.config.stream_cursor and not finish:
            content = f"{content}\n▌"
        frame = build_wecom_reply_stream_frame(
            state.reply_req_id,
            state.stream_id,
            content,
            finish=finish,
        )
        await self._send_request(frame)
        state.last_flush_at = asyncio.get_running_loop().time()
        state.last_sent_len = len(state.content)

    def _stream_key(self, msg: OutboundMessage, reply_req_id: str | None) -> str:
        identity = _first_str(
            reply_req_id,
            msg.reply_to,
            ((msg.metadata or {}).get("message_id") if isinstance(msg.metadata, dict) else None),
            msg.chat_id,
        )
        route = msg.channel_instance_id or self.endpoint_id
        return f"{route}:{msg.chat_id}:{identity}"

    def _is_duplicate_message(self, message_id: str) -> bool:
        if message_id in self._seen_message_ids:
            return True
        self._seen_message_ids[message_id] = None
        while len(self._seen_message_ids) > 1024:
            self._seen_message_ids.popitem(last=False)
        return False

    def _is_message_allowed(self, sender_id: str, chat_id: str, is_group: bool) -> bool:
        sender_allowed = _matches_allowlist(sender_id, list(self.config.allow_from or []))
        if not is_group:
            policy = self.config.dm_policy
            if policy == "disabled":
                return False
            if policy in {"allowlist", "pairing"}:
                return sender_allowed
            return True

        policy = self.config.group_policy
        if policy == "disabled":
            return False
        if policy == "allowlist":
            group_allowed = _matches_allowlist(chat_id, list(self.config.group_allow_from or []))
            if not group_allowed:
                return False

        group_rule = (self.config.groups or {}).get(chat_id)
        if group_rule and getattr(group_rule, "allow_from", None):
            return _matches_allowlist(sender_id, list(group_rule.allow_from))
        return True
