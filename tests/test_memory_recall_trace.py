import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from horbot.agent.context import ContextBuilder
from horbot.agent.context_manager import HierarchicalContextManager
from horbot.team.shared_memory import SharedMemoryManager


class TestMemoryRecallTrace(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp_dir.cleanup)

        self.root = Path(self.temp_dir.name) / ".horbot"
        self.workspace = Path(self.temp_dir.name) / "workspace"
        self.root.mkdir(parents=True, exist_ok=True)
        self.workspace.mkdir(parents=True, exist_ok=True)

        self.env = patch.dict(os.environ, {"HORBOT_ROOT": str(self.root)}, clear=False)
        self.env.start()
        self.addCleanup(self.env.stop)

    def test_search_context_returns_hybrid_recall_metadata(self):
        manager = HierarchicalContextManager(self.workspace)
        manager.add_memory(
            "## Prompt Injection Incident\n2026-04-01 14:09 MiniMax-M2 model returned empty choices during prompt injection replay.",
            level="L2",
            metadata={"Topic": "security incident", "Tag": "prompt-injection"},
        )
        manager.add_memory(
            "## Older Security Note\nPrompt injection happened in April and required manual inspection.",
            level="L2",
            metadata={"Topic": "security"},
        )

        results = manager.search_context(
            "MiniMax-M2 prompt injection 2026-04-01",
            levels=["L2"],
            max_results=5,
        )

        self.assertGreaterEqual(len(results), 1)
        top = results[0]
        self.assertIn("score_breakdown", top)
        self.assertGreater(top["score_breakdown"]["rrf"], 0)
        self.assertIn("时间信息命中", top["reasons"])
        self.assertIn("minimax", top["matched_terms"])
        self.assertEqual(top["level"], "L2")
        search_stats = manager.get_last_search_stats()
        self.assertGreaterEqual(search_stats["scanned_sections"], 2)
        self.assertGreaterEqual(search_stats["matched_count"], 1)
        self.assertEqual(search_stats["returned_count"], len(results))

    def test_context_builder_exposes_last_memory_trace(self):
        builder = ContextBuilder(workspace=self.workspace, use_hierarchical=True)
        assert builder._hierarchical_context is not None

        builder._hierarchical_context.add_memory(
            "## Browser Smoke\nBrowser smoke timeout was fixed by retrying transient Playwright failures.",
            level="L1",
            metadata={"Topic": "browser smoke"},
        )

        builder.build_messages(
            history=[],
            current_message="browser smoke timeout",
            channel="web",
            chat_id="dm_test",
            session_key="web:dm_test",
        )
        trace = builder.get_last_memory_trace()

        self.assertGreaterEqual(len(trace), 1)
        self.assertEqual(trace[0]["category"], "recent")
        self.assertEqual(trace[0]["level"], "L1")
        self.assertIn("Browser smoke timeout", trace[0]["snippet"])
        self.assertTrue(trace[0]["reasons"])
        metrics = builder.memory.get_metrics_summary()
        self.assertGreaterEqual(metrics["recall"]["count"], 1)
        self.assertGreater(metrics["recall"]["avg_latency_ms"], 0)
        self.assertGreaterEqual(len(metrics["recall"]["last_selected_memory_ids"]), 1)
        latest = builder.memory.get_last_recall_metrics()
        self.assertGreater(latest.get("latency_ms", 0), 0)
        self.assertGreaterEqual(latest.get("selected_count", 0), 1)

    def test_context_builder_includes_reflection_trace(self):
        builder = ContextBuilder(workspace=self.workspace, use_hierarchical=True)
        builder.memory.write_reflection(
            "# Reflection\n\n"
            "## Stable Observations\n"
            "- 用户倾向先做 smoke，再做深度回归。\n\n"
            "## Reusable Strategies\n"
            "- Playwright 超时先重试一次，再看浏览器上下文是否卡住。\n"
            "- 修改聊天链路后，要同时核对 SSE 事件和历史消息落盘。\n\n"
            "## Invalidated Observations\n"
            "- 旧的 /plan 显式触发限制已不再适用。\n"
        )

        builder.build_messages(
            history=[],
            current_message="playwright timeout 怎么处理",
            channel="web",
            chat_id="dm_reflection",
            session_key="web:dm_reflection",
        )
        trace = builder.get_last_memory_trace()
        reflection_items = [item for item in trace if item.get("category") == "reflection"]

        self.assertGreaterEqual(len(reflection_items), 1)
        self.assertEqual(reflection_items[0]["level"], "Reflect")
        self.assertEqual(reflection_items[0]["file"], "REFLECTION.md")
        self.assertIn("策略", "".join(reflection_items[0].get("reasons", [])))
        latest = builder.memory.get_last_recall_metrics()
        self.assertGreaterEqual(latest.get("selected_count", 0), 1)

    def test_context_builder_includes_team_memory_trace(self):
        team_id = "team-alpha"
        manager = SharedMemoryManager(team_id)
        manager.write_scope(
            "active_handoff",
            "# Active Handoff\n\n## Browser Handoff\nPlaywright timeout 已经通过一次重试和上下文清理规避，下一步继续核对浏览器页面状态。",
            agent_id="horbot-02",
        )

        builder = ContextBuilder(
            workspace=self.workspace,
            use_hierarchical=True,
            team_ids=[team_id],
        )

        builder.build_messages(
            history=[],
            current_message="playwright timeout 接力状态如何",
            channel="web",
            chat_id="team_trace",
            session_key="web:team_trace",
        )
        trace = builder.get_last_memory_trace()
        team_items = [item for item in trace if item.get("category") == "team"]

        self.assertGreaterEqual(len(team_items), 1)
        self.assertEqual(team_items[0]["level"], "Team")
        self.assertEqual(team_items[0]["origin"], "team_shared")
        self.assertEqual(team_items[0]["owner_id"], team_id)
        self.assertEqual(team_items[0]["scope"], "active_handoff")
        self.assertEqual(team_items[0]["scope_label"], "Active Handoff")
        self.assertIn("团队", "".join(team_items[0].get("reasons", [])))


if __name__ == "__main__":
    unittest.main()
