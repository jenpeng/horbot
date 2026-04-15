import copy
import tempfile
import unittest
from pathlib import Path

from horbot.agent.context_compact import estimate_tokens
from horbot.agent.loop import AgentLoop
from horbot.bus.queue import MessageBus
from horbot.config.schema import Config
from horbot.providers.base import LLMProvider, LLMResponse
from horbot.session.manager import SessionManager


class CaptureMessagesProvider(LLMProvider):
    def __init__(self) -> None:
        super().__init__(api_key="stub", api_base="stub://capture")
        self.seen_messages: list[dict] = []

    async def chat(self, messages, **kwargs):
        self.seen_messages = copy.deepcopy(messages)
        return LLMResponse(content="压缩完成", finish_reason="stop")

    def get_default_model(self) -> str:
        return "stub-model"


class LengthContinuationProvider(LLMProvider):
    def __init__(self) -> None:
        super().__init__(api_key="stub", api_base="stub://length")
        self.calls = 0
        self.seen_messages: list[list[dict]] = []

    async def chat(self, messages, on_content_delta=None, **kwargs):
        self.calls += 1
        self.seen_messages.append(copy.deepcopy(messages))
        if self.calls == 1:
            if on_content_delta:
                await on_content_delta("第一段")
            return LLMResponse(content="第一段", finish_reason="length")

        if on_content_delta:
            await on_content_delta("第二段")
        return LLMResponse(content="第二段", finish_reason="stop")

    def get_default_model(self) -> str:
        return "stub-model"


class AgentLoopAutoCompactionTests(unittest.IsolatedAsyncioTestCase):
    async def test_run_agent_loop_compacts_oversized_recent_context_before_provider_call(self):
        provider = CaptureMessagesProvider()
        config = Config()
        config.agents.defaults.context_compact.max_tokens = 1200
        config.agents.defaults.context_compact.preserve_recent = 10

        with tempfile.TemporaryDirectory() as tempdir:
            workspace = Path(tempdir) / "workspace"
            workspace.mkdir(parents=True, exist_ok=True)
            loop = AgentLoop(
                bus=MessageBus(),
                provider=provider,
                workspace=workspace,
                model="stub-model",
                max_iterations=config.agents.defaults.max_tool_iterations,
                temperature=config.agents.defaults.temperature,
                max_tokens=config.agents.defaults.max_tokens,
                memory_window=config.agents.defaults.memory_window,
                brave_api_key=config.tools.web.search.api_key,
                restrict_to_workspace=config.tools.restrict_to_workspace,
                mcp_servers={},
                channels_config=config.channels,
                exec_config=config.tools.exec,
                session_manager=SessionManager(workspace=Path(tempdir) / "sessions"),
                use_hierarchical_context=False,
                enable_hot_reload=False,
                agent_id="agent-01",
                agent_name="Agent 01",
                team_ids=[],
            )
            loop._get_config = lambda: config

            huge_block = "A" * 8000
            initial_messages = [{"role": "system", "content": "You are a helpful assistant."}]
            for index in range(6):
                initial_messages.append({"role": "user", "content": f"问题 {index}"})
                initial_messages.append({"role": "assistant", "content": f"回答 {index}\n{huge_block}"})
            initial_messages.append({"role": "user", "content": "请继续排查超时根因。"})

            final_content, _, _, _, _ = await loop._run_agent_loop(
                initial_messages,
                session_key="web:dm_main",
            )

            self.assertEqual(final_content, "压缩完成")
            self.assertLessEqual(estimate_tokens(provider.seen_messages), 1200)
            self.assertTrue(
                any("[Compressed assistant" in str(message.get("content", "")) for message in provider.seen_messages),
                "expected oversized recent assistant messages to be clipped",
            )

    async def test_run_agent_loop_auto_continues_length_truncated_response(self):
        provider = LengthContinuationProvider()
        config = Config()
        config.agents.defaults.context_compact.max_tokens = 4000

        with tempfile.TemporaryDirectory() as tempdir:
            workspace = Path(tempdir) / "workspace"
            workspace.mkdir(parents=True, exist_ok=True)
            loop = AgentLoop(
                bus=MessageBus(),
                provider=provider,
                workspace=workspace,
                model="stub-model",
                max_iterations=config.agents.defaults.max_tool_iterations,
                temperature=config.agents.defaults.temperature,
                max_tokens=config.agents.defaults.max_tokens,
                memory_window=config.agents.defaults.memory_window,
                brave_api_key=config.tools.web.search.api_key,
                restrict_to_workspace=config.tools.restrict_to_workspace,
                mcp_servers={},
                channels_config=config.channels,
                exec_config=config.tools.exec,
                session_manager=SessionManager(workspace=Path(tempdir) / "sessions"),
                use_hierarchical_context=False,
                enable_hot_reload=False,
                agent_id="agent-01",
                agent_name="Agent 01",
                team_ids=[],
            )
            loop._get_config = lambda: config

            progress_updates: list[str] = []

            async def _on_progress(content: str, **kwargs):
                progress_updates.append(content)

            final_content, _, messages, _, _ = await loop._run_agent_loop(
                [
                    {"role": "system", "content": "You are a helpful assistant."},
                    {"role": "user", "content": "请输出完整排查结论。"},
                ],
                session_key="web:dm_main",
                on_progress=_on_progress,
            )

            self.assertEqual(final_content, "第一段第二段")
            self.assertEqual(provider.calls, 2)
            self.assertEqual(progress_updates[-1], "第一段第二段")
            self.assertFalse(any(message.get("_ephemeral") for message in messages))
            self.assertEqual(messages[-1]["role"], "assistant")
            self.assertEqual(messages[-1]["content"], "第一段第二段")

