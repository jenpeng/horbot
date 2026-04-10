import asyncio
import tempfile
import unittest
from pathlib import Path

from horbot.agent.loop import AgentLoop
from horbot.agent.skill_evolution import SkillEvolutionEngine
from horbot.bus.events import InboundMessage
from horbot.bus.queue import MessageBus
from horbot.providers.base import LLMProvider, LLMResponse, ToolCallRequest
from horbot.session.manager import SessionManager


class CreateSkillProvider(LLMProvider):
    def __init__(self) -> None:
        super().__init__(api_key="stub", api_base="stub://skill-evolution")

    async def chat(self, messages, tools=None, **kwargs):
        tool_names = {item["function"]["name"] for item in (tools or [])}
        if "save_skill_review" in tool_names:
            return LLMResponse(
                content="",
                tool_calls=[
                    ToolCallRequest(
                        id="save_skill",
                        name="save_skill_review",
                        arguments={
                            "action": "create",
                            "skill_name": "shell retry checklist",
                            "description": "Capture a reusable shell troubleshooting checklist.",
                            "body_markdown": (
                                "# Shell Retry Checklist\n\n"
                                "## When to use\n"
                                "- When a shell-based task fails unexpectedly.\n\n"
                                "## Steps\n"
                                "1. Re-run the command with the exact failing arguments.\n"
                                "2. Inspect stderr and environment assumptions.\n"
                                "3. Verify the target path or dependency before retrying.\n\n"
                                "## Checks\n"
                                "- Confirm the failure is reproducible.\n"
                                "- Record the fix that resolved it.\n"
                            ),
                            "reason": "The execution produced a repeatable debugging checklist.",
                            "confidence": 0.91,
                        },
                    )
                ],
                finish_reason="tool_calls",
            )
        return LLMResponse(content="No-op")

    def get_default_model(self) -> str:
        return "stub-model"


class SkipSkillProvider(LLMProvider):
    def __init__(self) -> None:
        super().__init__(api_key="stub", api_base="stub://skill-evolution")

    async def chat(self, messages, tools=None, **kwargs):
        return LLMResponse(
            content="",
            tool_calls=[
                ToolCallRequest(
                    id="skip_skill",
                    name="save_skill_review",
                    arguments={
                        "action": "skip",
                        "reason": "This was a one-off answer without reusable procedure.",
                    },
                )
            ],
            finish_reason="tool_calls",
        )

    def get_default_model(self) -> str:
        return "stub-model"


class LoopSkillProvider(LLMProvider):
    def __init__(self) -> None:
        super().__init__(api_key="stub", api_base="stub://loop-skill-evolution")

    async def chat(self, messages, tools=None, **kwargs):
        tool_names = {item["function"]["name"] for item in (tools or [])}
        if "save_skill_review" in tool_names:
            return LLMResponse(
                content="",
                tool_calls=[
                    ToolCallRequest(
                        id="skill_review",
                        name="save_skill_review",
                        arguments={
                            "action": "create",
                            "skill_name": "workspace inspection checklist",
                            "description": "Document a repeatable workspace inspection workflow.",
                            "body_markdown": (
                                "# Workspace Inspection Checklist\n\n"
                                "## When to use\n"
                                "- When you need to quickly inspect the current workspace before editing.\n\n"
                                "## Steps\n"
                                "1. List the target directory.\n"
                                "2. Identify the key files involved in the task.\n"
                                "3. Summarize the findings before making changes.\n"
                            ),
                            "reason": "The agent used a reusable inspection workflow.",
                            "confidence": 0.88,
                        },
                    )
                ],
                finish_reason="tool_calls",
            )
        if any(message.get("role") == "tool" for message in messages):
            return LLMResponse(
                content=(
                    "I inspected the workspace with list_dir, identified the relevant files, "
                    "and summarized the result as a repeatable checklist for future tasks."
                )
            )
        return LLMResponse(
            content="",
            tool_calls=[
                ToolCallRequest(
                    id="list_dir_call",
                    name="list_dir",
                    arguments={"path": "."},
                )
            ],
            finish_reason="tool_calls",
        )

    def get_default_model(self) -> str:
        return "stub-model"


class SkillEvolutionTests(unittest.IsolatedAsyncioTestCase):
    async def test_skill_evolution_creates_skill_file(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            workspace = Path(tmpdir)
            engine = SkillEvolutionEngine(
                workspace=workspace,
                provider=CreateSkillProvider(),
                model="stub-model",
                agent_id="writer",
            )

            result = await engine.review_execution(
                {
                    "task": "Debug a flaky shell command and summarize the recovery steps.",
                    "result": "Captured a stable recovery checklist after reproducing and fixing the failure.",
                    "tools_used": ["exec"],
                },
                recent_messages=[
                    {"role": "user", "content": "Please debug the shell failure."},
                    {"role": "assistant", "content": "I found a reusable checklist."},
                ],
            )

            self.assertIsNotNone(result)
            self.assertEqual(result.skill_name, "auto-shell-retry-checklist")
            skill_path = workspace / "skills" / "auto-shell-retry-checklist" / "SKILL.md"
            self.assertTrue(skill_path.exists())
            content = skill_path.read_text(encoding="utf-8")
            self.assertIn("generated_by: skill-evolution", content)
            self.assertIn("# Shell Retry Checklist", content)

    async def test_skill_evolution_skips_one_off_work(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            workspace = Path(tmpdir)
            engine = SkillEvolutionEngine(
                workspace=workspace,
                provider=SkipSkillProvider(),
                model="stub-model",
                agent_id="writer",
            )

            result = await engine.review_execution(
                {
                    "task": "Answer a one-off greeting.",
                    "result": "Said hello back.",
                    "tools_used": [],
                },
            )

            self.assertIsNotNone(result)
            self.assertEqual(result.action, "skip")
            self.assertFalse((workspace / "skills").exists())

    async def test_agent_loop_runs_background_skill_review_after_tool_execution(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            workspace = root / "workspace"
            workspace.mkdir(parents=True, exist_ok=True)

            loop = AgentLoop(
                bus=MessageBus(),
                provider=LoopSkillProvider(),
                workspace=workspace,
                model="stub-model",
                session_manager=SessionManager(workspace=root / "sessions"),
                use_hierarchical_context=False,
                enable_hot_reload=False,
                agent_id="agent-01",
                agent_name="Agent 01",
            )
            loop._planning_enabled = False

            response = await loop.process_message(
                InboundMessage(
                    channel="web",
                    sender_id="tester",
                    chat_id="dm_agent-01",
                    content="Inspect the workspace and tell me what you find.",
                )
            )

            self.assertIsNotNone(response)
            if loop._skill_review_tasks:
                await asyncio.gather(*list(loop._skill_review_tasks))

            skill_path = workspace / "skills" / "auto-workspace-inspection-checklist" / "SKILL.md"
            self.assertTrue(skill_path.exists())


if __name__ == "__main__":
    unittest.main()
