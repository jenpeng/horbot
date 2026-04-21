import asyncio
import unittest
from unittest.mock import MagicMock, AsyncMock

from horbot.agent.loop import AgentLoop
from horbot.agent.message_processor import MessageProcessor
from horbot.agent.tools.registry import WebRequirement
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
        self._run_planning_mode = AsyncMock(return_value=None)

        self.tools = MagicMock()
        self.tools.get.return_value = None
        self.tools.classify_web_requirement.return_value = WebRequirement()
        
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

    async def test_dispatch_system_exception_routes_back_to_source_channel(self):
        self.mock_agent._run_agent_loop.side_effect = Exception("Test error")

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
        self.assertEqual(outbound_msg.content, "Sorry, I encountered an error.")

    def test_agent_to_agent_turn_skips_planning(self):
        loop = AgentLoop.__new__(AgentLoop)
        msg = InboundMessage(
            channel="web",
            sender_id="web_user",
            chat_id="team_team-001",
            content="请从风险角度补充",
            metadata={
                "conversation_context": {
                    "conversation_type": "agent_to_agent",
                    "source": "alpha",
                    "source_name": "Alpha",
                    "target": "beta",
                    "target_name": "Beta",
                }
            },
        )

        self.assertTrue(AgentLoop._should_skip_planning_for_message(loop, msg))

    def test_group_chat_summary_return_turn_skips_planning(self):
        loop = AgentLoop.__new__(AgentLoop)
        msg = InboundMessage(
            channel="web",
            sender_id="web_user",
            chat_id="team_team-001",
            content="请基于当前团队对话历史，吸收其他 agent 已经给出的分析。",
            metadata={
                "group_chat": True,
                "conversation_context": {
                    "conversation_type": "user_to_agent",
                    "source": "user",
                    "source_name": "用户",
                    "target": "main",
                    "target_name": "小项 🐎",
                    "trigger_message": "请基于当前团队对话历史，吸收其他 agent 已经给出的分析，现在直接面向用户输出最终总结。",
                },
            },
        )

        self.assertTrue(AgentLoop._should_skip_planning_for_message(loop, msg))

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

    async def test_process_message_disables_fast_reply_when_web_tools_required(self):
        self.mock_agent.context.should_use_fast_reply.return_value = True
        self.mock_agent.tools.classify_web_requirement.return_value = WebRequirement(
            category="direct_web",
            requires_web_access=True,
            reason="explicit webpage interaction requested",
        )

        msg = InboundMessage(
            channel="web",
            sender_id="web_user",
            chat_id="dm_main",
            content="在当前浏览器上打开新浪首页",
        )

        response = await self.processor.process_message(msg)

        self.assertIsNotNone(response)
        self.mock_agent.context.build_messages.assert_called_once()
        self.mock_agent.context.build_fast_messages.assert_not_called()
        self.mock_agent._run_agent_loop.assert_awaited_once()
        self.assertEqual(self.mock_agent._run_agent_loop.await_args.kwargs["tool_mode"], "smart")
        self.assertIsNone(self.mock_agent._run_agent_loop.await_args.kwargs["max_tokens_override"])

    async def test_process_message_falls_back_to_direct_execution_when_planning_is_skipped(self):
        self.mock_agent._resolve_planning_mode = MagicMock(return_value=(True, False))
        self.mock_agent._run_planning_mode = AsyncMock(
            return_value=OutboundMessage(
                channel="cli",
                chat_id="chat_1",
                content="",
                metadata={"_skip_planning_execute_direct": True},
            )
        )

        msg = InboundMessage(
            channel="cli",
            sender_id="user_1",
            chat_id="chat_1",
            content="请直接创建一个简单 PPT",
        )

        response = await self.processor.process_message(msg)

        self.assertIsNotNone(response)
        self.assertEqual(response.content, "Mock response")
        self.mock_agent._run_planning_mode.assert_awaited_once()
        self.mock_agent._run_agent_loop.assert_awaited_once()


if __name__ == "__main__":
    unittest.main()
