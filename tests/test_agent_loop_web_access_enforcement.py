import copy
import tempfile
import unittest
from pathlib import Path

from horbot.agent.loop import AgentLoop
from horbot.agent.tools.base import Tool, ToolCategory, ToolMetadata
from horbot.bus.queue import MessageBus
from horbot.config.schema import Config
from horbot.providers.base import LLMProvider, LLMResponse, ToolCallRequest
from horbot.session.manager import SessionManager


class SequencedProvider(LLMProvider):
    def __init__(self, responses: list[LLMResponse]) -> None:
        super().__init__(api_key="stub", api_base="stub://sequence")
        self._responses = list(responses)
        self.calls = 0
        self.seen_messages: list[list[dict]] = []

    async def chat(self, messages, **kwargs):
        self.calls += 1
        self.seen_messages.append(copy.deepcopy(messages))
        if not self._responses:
            raise AssertionError("provider received more calls than expected")
        return self._responses.pop(0)

    def get_default_model(self) -> str:
        return "stub-model"


class StubWebAccessTool(Tool):
    def __init__(self, outputs: list[str] | None = None) -> None:
        self._outputs = list(outputs or [])

    @property
    def name(self) -> str:
        return "web_access"

    @property
    def description(self) -> str:
        return "stub web access"

    @property
    def parameters(self) -> dict:
        return {
            "type": "object",
            "properties": {
                "action": {"type": "string"},
                "query": {"type": "string"},
            },
            "required": ["action"],
        }

    @property
    def metadata(self) -> ToolMetadata:
        return ToolMetadata(
            name=self.name,
            description=self.description,
            category=ToolCategory.WEB,
        )

    async def execute(self, **kwargs):
        if self._outputs:
            return self._outputs.pop(0)
        action = kwargs.get("action", "")
        query = kwargs.get("query", "")
        return f"stub-web-access:{action}:{query}"


def _build_loop(provider: LLMProvider, tempdir: str, web_outputs: list[str] | None = None) -> AgentLoop:
    config = Config()
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
    loop.tools.unregister("web_access")
    loop.tools.register(StubWebAccessTool(outputs=web_outputs))
    return loop


class AgentLoopWebAccessEnforcementTests(unittest.IsolatedAsyncioTestCase):
    async def test_run_agent_loop_retries_until_web_access_used_for_fresh_knowledge(self):
        provider = SequencedProvider([
            LLMResponse(content="我先直接总结一下最新局势。"),
            LLMResponse(tool_calls=[
                ToolCallRequest(
                    id="call-web-1",
                    name="web_access",
                    arguments={"action": "search", "query": "当前美伊局势 最新"},
                )
            ], content=None),
            LLMResponse(content="基于联网检索结果，这是最新简报。"),
        ])

        with tempfile.TemporaryDirectory() as tempdir:
            loop = _build_loop(provider, tempdir)
            final_content, tools_used, messages, _, _ = await loop._run_agent_loop(
                [
                    {"role": "system", "content": "You are a helpful assistant."},
                    {"role": "user", "content": "帮我整理一下当前美伊局势的最新动态"},
                ],
                session_key="web:dm_main",
            )

            self.assertEqual(final_content, "基于联网检索结果，这是最新简报。")
            self.assertEqual(provider.calls, 3)
            self.assertIn("web_access", tools_used)
            self.assertTrue(any(m.get("role") == "tool" and m.get("name") == "web_access" for m in messages))
            self.assertTrue(
                any(
                    m.get("role") == "user"
                    and "请先调用 `web_access` 获取外部信息" in str(m.get("content", ""))
                    for m in provider.seen_messages[1]
                )
            )

    async def test_run_agent_loop_blocks_message_tool_until_web_access_succeeds(self):
        provider = SequencedProvider([
            LLMResponse(tool_calls=[
                ToolCallRequest(
                    id="call-msg-1",
                    name="message",
                    arguments={"content": "这是我直接给你的最新结论。"},
                )
            ], content=None),
            LLMResponse(tool_calls=[
                ToolCallRequest(
                    id="call-web-1",
                    name="web_access",
                    arguments={"action": "search", "query": "OpenAI Responses API 官方文档"},
                )
            ], content=None),
            LLMResponse(content="我已经联网核实，下面是结论。"),
        ])

        with tempfile.TemporaryDirectory() as tempdir:
            loop = _build_loop(provider, tempdir)
            final_content, tools_used, messages, _, _ = await loop._run_agent_loop(
                [
                    {"role": "system", "content": "You are a helpful assistant."},
                    {"role": "user", "content": "帮我看一下 OpenAI Responses API 官方文档怎么用"},
                ],
                session_key="web:dm_main",
            )

            self.assertEqual(final_content, "我已经联网核实，下面是结论。")
            self.assertEqual(provider.calls, 3)
            self.assertIn("web_access", tools_used)
            self.assertFalse(any("Message sent to" in str(m.get("content", "")) for m in messages if m.get("role") == "tool"))
            self.assertTrue(
                any(
                    m.get("role") == "tool"
                    and m.get("name") == "message"
                    and "requires a successful web_access call" in str(m.get("content", ""))
                    for m in provider.seen_messages[1]
                )
            )

    async def test_security_notice_web_access_result_does_not_count_as_success(self):
        provider = SequencedProvider([
            LLMResponse(tool_calls=[
                ToolCallRequest(
                    id="call-web-1",
                    name="web_access",
                    arguments={"action": "search", "query": "OpenAI Responses API official docs"},
                )
            ], content=None),
            LLMResponse(tool_calls=[
                ToolCallRequest(
                    id="call-msg-1",
                    name="message",
                    arguments={"content": "我已经查完了，下面直接给结论。"},
                )
            ], content=None),
            LLMResponse(tool_calls=[
                ToolCallRequest(
                    id="call-web-2",
                    name="web_access",
                    arguments={"action": "search", "query": "OpenAI Responses API docs overview"},
                )
            ], content=None),
            LLMResponse(content="这次基于可用联网结果给出总结。"),
        ])

        with tempfile.TemporaryDirectory() as tempdir:
            loop = _build_loop(
                provider,
                tempdir,
                web_outputs=[
                    "[Security notice] Tool output from 'web_access' was withheld because it appears to contain unsafe instructions or sensitive data (embedded credentials).",
                    "stub-web-access:search:OpenAI Responses API docs overview",
                ],
            )
            final_content, tools_used, _, _, _ = await loop._run_agent_loop(
                [
                    {"role": "system", "content": "You are a helpful assistant."},
                    {"role": "user", "content": "帮我看一下 OpenAI Responses API 官方文档怎么用"},
                ],
                session_key="web:dm_main",
            )

            self.assertEqual(final_content, "这次基于可用联网结果给出总结。")
            self.assertEqual(provider.calls, 4)
            self.assertGreaterEqual(tools_used.count("web_access"), 2)
            self.assertTrue(
                any(
                    m.get("role") == "tool"
                    and m.get("name") == "message"
                    and "requires a successful web_access call" in str(m.get("content", ""))
                    for m in provider.seen_messages[2]
                )
            )

    async def test_no_results_web_access_result_falls_back_to_failure_message(self):
        provider = SequencedProvider([
            LLMResponse(tool_calls=[
                ToolCallRequest(
                    id="call-web-1",
                    name="web_access",
                    arguments={"action": "search", "query": "OpenAI Responses API docs"},
                )
            ], content=None),
            LLMResponse(tool_calls=[
                ToolCallRequest(
                    id="call-web-2",
                    name="web_access",
                    arguments={"action": "search", "query": "OpenAI Responses API official docs"},
                )
            ], content=None),
            LLMResponse(tool_calls=[
                ToolCallRequest(
                    id="call-web-3",
                    name="web_access",
                    arguments={"action": "search", "query": "OpenAI Responses API guide"},
                )
            ], content=None),
        ])

        with tempfile.TemporaryDirectory() as tempdir:
            loop = _build_loop(
                provider,
                tempdir,
                web_outputs=[
                    "No results for: OpenAI Responses API docs",
                    "No results for: OpenAI Responses API official docs",
                    "[Security notice] Tool output from 'web_access' was withheld because it appears to contain unsafe instructions or sensitive data (embedded credentials).",
                ],
            )
            final_content, tools_used, _, _, _ = await loop._run_agent_loop(
                [
                    {"role": "system", "content": "You are a helpful assistant."},
                    {"role": "user", "content": "帮我看一下 OpenAI Responses API 官方文档怎么用"},
                ],
                session_key="web:dm_main",
            )

            self.assertEqual(final_content, loop.WEB_ACCESS_ENFORCEMENT_FAILURE)
            self.assertEqual(provider.calls, 3)
            self.assertEqual(tools_used.count("web_access"), 3)


if __name__ == "__main__":
    unittest.main()
