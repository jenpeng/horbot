import unittest

from horbot.bus.queue import MessageBus
from horbot.channels.sharecrm import ShareCrmChannel
from horbot.config.schema import ShareCrmConfig


class ShareCrmChannelTests(unittest.IsolatedAsyncioTestCase):
    async def test_inbound_message_preserves_endpoint_and_agent_binding(self):
        bus = MessageBus()
        channel = ShareCrmChannel(
            ShareCrmConfig(
                enabled=True,
                app_id="app",
                app_secret="secret",
            ),
            bus,
            endpoint_id="sharecrm-sales",
            target_agent_id="horbot-02",
            endpoint_name="销售纷享销客",
        )

        await channel._on_message({
            "data": {
                "chat_id": "chat-123",
                "chat_type": "direct",
                "from": {"id": "user-1", "name": "Alice"},
                "message_id": "msg-1",
                "text": "hello from sharecrm",
                "date": 1710000000,
            },
        })

        self.assertEqual(bus.inbound_size, 1)
        message = await bus.consume_inbound()
        self.assertEqual(message.channel, "sharecrm")
        self.assertEqual(message.channel_instance_id, "sharecrm-sales")
        self.assertEqual(message.target_agent_id, "horbot-02")
        self.assertEqual(message.session_key, "sharecrm-sales:chat-123")
        self.assertEqual(message.metadata["channel_instance_id"], "sharecrm-sales")
        self.assertEqual(message.metadata["target_agent_id"], "horbot-02")
        self.assertEqual(message.metadata["channel_endpoint_name"], "销售纷享销客")


if __name__ == "__main__":
    unittest.main()
