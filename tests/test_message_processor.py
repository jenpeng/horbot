import asyncio
import unittest
from unittest.mock import MagicMock, AsyncMock

from horbot.agent.message_processor import MessageProcessor
from horbot.bus.events import InboundMessage, OutboundMessage


class MockSession:
    def __init__(self, key):
        self.key = key
        self.history = []
        self.messages = []
        self.last_consolidated = 0
        self._pending_confirmations = {}
        
    def get_history(self, max_messages=10):
        return self.history
        
    def clear(self):
        self.history = []


class MockSessionManager:
    def __init__(self):
        self.sessions = {}
        
    def get_or_create(self, key):
        if key not in self.sessions:
            self.sessions[key] = MockSession(key)
        return self.sessions[key]
        
    def save(self, session):
        self.sessions[session.key] = session

    def invalidate(self, key):
        self.sessions.pop(key, None)


class MockAgentLoop:
    def __init__(self):
        self.bus = MagicMock()
        self.bus.publish_outbound = AsyncMock()
        self.sessions = MockSessionManager()
        self.memory_window = 10
        self.context = MagicMock()
        self.context.build_messages.return_value = [{"role": "user", "content": "hello"}]
        self.context.build_fast_messages.return_value = [{"role": "user", "content": "hello"}]
        self.context.clear_session_context = MagicMock()
        self.context.should_use_fast_reply.return_value = False
        self._run_agent_loop = AsyncMock(
            return_value=(
                "Mock response",
                None,
                [{"role": "user", "content": "hello"}, {"role": "assistant", "content": "Mock response"}],
                None,
                None,
            )
        )
        self._save_turn = MagicMock()
        self._set_tool_context = MagicMock()
        self._active_plans = {}
        self._consolidating = set()
        self._consolidation_tasks = set()
        self._message_locks = {}
        self.use_hierarchical_context = False
        self._planning_enabled = True
        self._build_bound_channel_runtime_hints = MagicMock(return_value=[])

        self.tools = MagicMock()
        self.tools.get.return_value = None
        
        self._agent_id = "agent_1"
        self._agent_name = "test_agent"
        
    def _is_new_task(self, content, session):
        return False

    def _get_message_lock(self, key):
        return self._message_locks.setdefault(key, asyncio.Lock())

    def _prune_message_lock(self, key, lock):
        if self._message_locks.get(key) is lock and not lock.locked():
            self._message_locks.pop(key, None)

    def _get_consolidation_lock(self, key):
        return asyncio.Lock()

    def _prune_consolidation_lock(self, key, lock):
        return None

    def _resolve_planning_mode(self, msg):
        return False, False


class TestMessageProcessor(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.mock_agent = MockAgentLoop()
        self.processor = MessageProcessor(agent_loop=self.mock_agent)

    async def test_dispatch_normal_message(self):
        msg = InboundMessage(
            channel="cli",
            sender_id="user_1",
            chat_id="chat_1",
            content="hello world"
        )
        
        await self.processor.dispatch(msg)
        
        # Verify publish_outbound was called
        self.mock_agent.bus.publish_outbound.assert_called_once()
        outbound_msg = self.mock_agent.bus.publish_outbound.call_args[0][0]
        self.assertIsInstance(outbound_msg, OutboundMessage)
        self.assertEqual(outbound_msg.channel, "cli")
        self.assertEqual(outbound_msg.chat_id, "chat_1")
        self.assertEqual(outbound_msg.content, "Mock response")
        
        # Verify run_agent_loop was called
        self.mock_agent._run_agent_loop.assert_called_once()
        self.mock_agent._save_turn.assert_called_once()

    async def test_dispatch_system_message(self):
        msg = InboundMessage(
            channel="system",
            sender_id="sys",
            chat_id="telegram:chat_123",
            content="Background task completed"
        )
        
        await self.processor.dispatch(msg)
        
        self.mock_agent.bus.publish_outbound.assert_called_once()
        outbound_msg = self.mock_agent.bus.publish_outbound.call_args[0][0]
        self.assertIsInstance(outbound_msg, OutboundMessage)
        self.assertEqual(outbound_msg.channel, "telegram")
        self.assertEqual(outbound_msg.chat_id, "chat_123")
        self.assertEqual(outbound_msg.content, "Mock response")

    async def test_dispatch_system_message_with_legacy_endpoint_id(self):
        msg = InboundMessage(
            channel="system",
            sender_id="sys",
            chat_id="legacy:sharecrm:0:fs:b21ddfcd6a074e0abef44266b19c32ee:",
            content="Background task completed"
        )

        await self.processor.dispatch(msg)

        self.mock_agent.bus.publish_outbound.assert_called_once()
        outbound_msg = self.mock_agent.bus.publish_outbound.call_args[0][0]
        self.assertIsInstance(outbound_msg, OutboundMessage)
        self.assertEqual(outbound_msg.channel, "legacy:sharecrm")
        self.assertEqual(outbound_msg.chat_id, "0:fs:b21ddfcd6a074e0abef44266b19c32ee:")
        self.assertEqual(outbound_msg.content, "Mock response")

    async def test_dispatch_exception(self):
        # Make process_message raise an exception
        self.mock_agent._run_agent_loop.side_effect = Exception("Test error")
        
        msg = InboundMessage(
            channel="cli",
            sender_id="user_1",
            chat_id="chat_1",
            content="trigger error"
        )
        
        await self.processor.dispatch(msg)
        
        self.mock_agent.bus.publish_outbound.assert_called_once()
        outbound_msg = self.mock_agent.bus.publish_outbound.call_args[0][0]
        self.assertIsInstance(outbound_msg, OutboundMessage)
        self.assertEqual(outbound_msg.content, "Sorry, I encountered an error.")

    async def test_process_message_new_task(self):
        self.mock_agent._is_new_task = MagicMock(return_value=True)
        
        msg = InboundMessage(
            channel="cli",
            sender_id="user_1",
            chat_id="chat_1",
            content="start fresh"
        )
        
        response = await self.processor.process_message(msg)
        
        self.assertIsNotNone(response)
        self.assertEqual(response.content, "Mock response")
        # Ensure context clearing might have been called
        self.mock_agent._is_new_task.assert_called_once()


if __name__ == "__main__":
    unittest.main()
