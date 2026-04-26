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


class FakeMemoryStore:
    def __init__(self) -> None:
        self.reflection_calls: list[dict[str, list[str]]] = []
        self.history_entries: list[str] = []

    def merge_reflection_entries(self, **kwargs) -> bool:
        self.reflection_calls.append(kwargs)
        return True

    def append_history(self, entry: str) -> None:
        self.history_entries.append(entry)


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
                            "skill_name": "shell troubleshooting",
                            "description": "Capture reusable shell troubleshooting techniques and recovery checklists.",
                            "reference_name": "shell retry checklist",
                            "reference_title": "Shell Retry Checklist",
                            "trigger_cues": [
                                "A shell command fails and needs a repeatable recovery flow.",
                                "The task needs a CLI troubleshooting checklist before retrying.",
                            ],
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


class MergeSkillProvider(LLMProvider):
    def __init__(self) -> None:
        super().__init__(api_key="stub", api_base="stub://merge-skill-evolution")

    async def chat(self, messages, tools=None, **kwargs):
        return LLMResponse(
            content="",
            tool_calls=[
                ToolCallRequest(
                    id="merge_skill",
                    name="save_skill_review",
                    arguments={
                        "action": "update",
                        "skill_name": "shell troubleshooting",
                        "description": "Capture reusable shell troubleshooting techniques and recovery checklists.",
                        "reference_name": "timeout diagnosis",
                        "reference_title": "Timeout Diagnosis Checklist",
                        "trigger_cues": [
                            "A shell or tool execution fails because of timeout symptoms.",
                        ],
                        "body_markdown": (
                            "# Timeout Diagnosis Checklist\n\n"
                            "## When to use\n"
                            "- When a command hangs or times out.\n\n"
                            "## Steps\n"
                            "1. Confirm whether the timeout happens before connection, during execution, or while waiting for output.\n"
                            "2. Check network, credentials, and remote service health separately.\n"
                            "3. Capture the exact timeout boundary before retrying.\n"
                        ),
                        "reason": "This is another technique in the same shell troubleshooting family.",
                        "confidence": 0.83,
                    },
                )
            ],
            finish_reason="tool_calls",
        )

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
                            "skill_name": "workspace inspection",
                            "description": "Document repeatable workspace inspection workflows and checklists.",
                            "reference_name": "workspace inspection checklist",
                            "reference_title": "Workspace Inspection Checklist",
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
            memory_store = FakeMemoryStore()
            engine = SkillEvolutionEngine(
                workspace=workspace,
                provider=CreateSkillProvider(),
                model="stub-model",
                agent_id="writer",
                memory_store=memory_store,
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
            self.assertEqual(result.skill_name, "auto-shell-troubleshooting")
            skill_path = workspace / ".horbot-agent" / "skills" / "auto-shell-troubleshooting" / "SKILL.md"
            reference_path = workspace / ".horbot-agent" / "skills" / "auto-shell-troubleshooting" / "references" / "shell-retry-checklist.md"
            self.assertTrue(skill_path.exists())
            self.assertTrue(reference_path.exists())
            content = skill_path.read_text(encoding="utf-8")
            self.assertIn("generated_by: skill-evolution", content)
            self.assertIn("## Reference Library", content)
            self.assertIn("references/shell-retry-checklist.md", content)
            self.assertIn("## Trigger Cues", content)
            reference_content = reference_path.read_text(encoding="utf-8")
            self.assertIn("# Shell Retry Checklist", reference_content)
            self.assertEqual(len(memory_store.reflection_calls), 1)
            self.assertIn("auto-shell-troubleshooting", memory_store.reflection_calls[0]["reusable_strategies"][0])
            self.assertEqual(len(memory_store.history_entries), 1)
            self.assertIn("Skill evolution created", memory_store.history_entries[0])

    async def test_skill_evolution_merges_related_references_into_one_skill_family(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            workspace = Path(tmpdir)

            create_engine = SkillEvolutionEngine(
                workspace=workspace,
                provider=CreateSkillProvider(),
                model="stub-model",
                agent_id="writer",
            )
            merge_engine = SkillEvolutionEngine(
                workspace=workspace,
                provider=MergeSkillProvider(),
                model="stub-model",
                agent_id="writer",
            )

            await create_engine.review_execution(
                {
                    "task": "Debug a flaky shell command and summarize the recovery steps.",
                    "result": "Captured a stable recovery checklist after reproducing and fixing the failure.",
                    "tools_used": ["exec"],
                },
            )
            result = await merge_engine.review_execution(
                {
                    "task": "Diagnose a command timeout and summarize the checks.",
                    "result": "Captured a repeatable timeout diagnosis checklist for shell failures.",
                    "tools_used": ["exec"],
                },
            )

            self.assertIsNotNone(result)
            self.assertEqual(result.skill_name, "auto-shell-troubleshooting")
            skill_dir = workspace / ".horbot-agent" / "skills" / "auto-shell-troubleshooting"
            self.assertTrue((skill_dir / "SKILL.md").exists())
            self.assertTrue((skill_dir / "references" / "shell-retry-checklist.md").exists())
            self.assertTrue((skill_dir / "references" / "timeout-diagnosis.md").exists())
            skill_content = (skill_dir / "SKILL.md").read_text(encoding="utf-8")
            self.assertIn("references/shell-retry-checklist.md", skill_content)
            self.assertIn("references/timeout-diagnosis.md", skill_content)

    async def test_skill_evolution_consolidates_old_generated_skill_directories(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            workspace = Path(tmpdir)
            skills_dir = workspace / "skills"

            old_retry_dir = skills_dir / "auto-shell-retry-checklist"
            old_retry_dir.mkdir(parents=True, exist_ok=True)
            (old_retry_dir / "SKILL.md").write_text(
                "---\n"
                "name: auto-shell-retry-checklist\n"
                "description: Capture reusable shell troubleshooting techniques and recovery checklists.\n"
                "generated_by: skill-evolution\n"
                "generated_at: 2026-04-26T00:00:00+00:00\n"
                "metadata: {\"horbot\":{\"enabled\":true}}\n"
                "---\n\n"
                "# Shell Retry Checklist\n\n"
                "## When to use\n"
                "- When a shell command fails unexpectedly.\n",
                encoding="utf-8",
            )

            old_timeout_dir = skills_dir / "auto-shell-timeout-diagnosis"
            (old_timeout_dir / "references").mkdir(parents=True, exist_ok=True)
            (old_timeout_dir / "SKILL.md").write_text(
                "---\n"
                "name: auto-shell-timeout-diagnosis\n"
                "description: Capture reusable shell troubleshooting techniques for timeout failures.\n"
                "generated_by: skill-evolution\n"
                "generated_at: 2026-04-26T00:00:00+00:00\n"
                "metadata: {\"horbot\":{\"enabled\":true}}\n"
                "---\n\n"
                "# Shell Timeout Diagnosis\n\n"
                "## When to use\n"
                "- When a shell command times out.\n",
                encoding="utf-8",
            )
            (old_timeout_dir / "references" / "network-timeout.md").write_text(
                "# Network Timeout Checks\n\n"
                "Check DNS, remote health, and timeout boundary.\n",
                encoding="utf-8",
            )

            engine = SkillEvolutionEngine(
                workspace=workspace,
                provider=MergeSkillProvider(),
                model="stub-model",
                agent_id="writer",
            )

            result = await engine.review_execution(
                {
                    "task": "Diagnose a command timeout and summarize the checks.",
                    "result": "Captured a repeatable timeout diagnosis checklist for shell failures.",
                    "tools_used": ["exec"],
                },
            )

            self.assertIsNotNone(result)
            skill_dir = workspace / "skills" / "auto-shell-troubleshooting"
            self.assertTrue((skill_dir / "SKILL.md").exists())
            self.assertFalse(old_retry_dir.exists())
            self.assertFalse(old_timeout_dir.exists())
            self.assertTrue((skill_dir / "references" / "shell-retry-checklist.md").exists())
            self.assertTrue((skill_dir / "references" / "network-timeout.md").exists())
            self.assertTrue((skill_dir / "references" / "timeout-diagnosis.md").exists())

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

    async def test_manual_consolidation_groups_shared_domain_skills_into_family(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            workspace = Path(tmpdir)
            skills_dir = workspace / "skills"

            cases = {
                "auto-officecli-ppt-highlight-xml-debug": (
                    "Diagnose PowerPoint text highlighting by inspecting XML for proper highlight tags.",
                    "# Highlight XML Debug\n\nInspect run-level XML highlight tags.\n",
                ),
                "auto-officecli-ppt-xml-patch-script-generation": (
                    "Generate a standalone Python script to patch PowerPoint XML for precise run-level formatting.",
                    "# XML Patch Script Generation\n\nGenerate and run a standalone XML patch script.\n",
                ),
                "auto-officecli-ppt-text-overflow-debug": (
                    "Diagnose and resolve persistent text overflow in OfficeCLI-generated PowerPoint slides.",
                    "# Text Overflow Debug\n\nCheck overflow and autofit interactions.\n",
                ),
            }

            for skill_name, (description, body) in cases.items():
                skill_dir = skills_dir / skill_name
                skill_dir.mkdir(parents=True, exist_ok=True)
                (skill_dir / "SKILL.md").write_text(
                    "---\n"
                    f"name: {skill_name}\n"
                    f"description: {description}\n"
                    "generated_by: skill-evolution\n"
                    "generated_at: 2026-04-26T00:00:00+00:00\n"
                    "metadata: {\"horbot\":{\"enabled\":true}}\n"
                    "---\n\n"
                    f"{body}",
                    encoding="utf-8",
                )

            engine = SkillEvolutionEngine(
                workspace=workspace,
                provider=MergeSkillProvider(),
                model="stub-model",
                agent_id="writer",
            )

            result = engine.consolidate_generated_skills()

            family_dir = skills_dir / "auto-officecli-ppt"
            self.assertEqual(result["family_count_before"], 3)
            self.assertEqual(result["family_count_after"], 1)
            self.assertEqual(result["merged_skill_count"], 3)
            self.assertTrue(family_dir.exists())
            self.assertTrue((family_dir / "SKILL.md").exists())
            self.assertTrue((family_dir / "references" / "officecli-ppt-highlight-xml-debug.md").exists())
            self.assertTrue((family_dir / "references" / "officecli-ppt-xml-patch-script-generation.md").exists())
            self.assertTrue((family_dir / "references" / "officecli-ppt-text-overflow-debug.md").exists())
            self.assertFalse((skills_dir / "auto-officecli-ppt-highlight-xml-debug").exists())
            self.assertFalse((skills_dir / "auto-officecli-ppt-xml-patch-script-generation").exists())
            self.assertFalse((skills_dir / "auto-officecli-ppt-text-overflow-debug").exists())

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
                    content="List the current workspace files and summarize the local structure.",
                )
            )

            self.assertIsNotNone(response)
            if loop._skill_review_tasks:
                await asyncio.gather(*list(loop._skill_review_tasks))

            skill_path = workspace / ".horbot-agent" / "skills" / "auto-workspace-inspection" / "SKILL.md"
            reference_path = workspace / ".horbot-agent" / "skills" / "auto-workspace-inspection" / "references" / "workspace-inspection-checklist.md"
            self.assertTrue(skill_path.exists())
            self.assertTrue(reference_path.exists())


if __name__ == "__main__":
    unittest.main()
