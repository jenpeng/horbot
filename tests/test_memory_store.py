import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from horbot.agent.context import ContextBuilder
from horbot.agent.memory import MemoryStore
from horbot.agent.tools.safe_editor import SafeWriteFileTool
from horbot.team.shared_memory import SharedMemoryManager
from horbot.utils.bootstrap import materialize_bootstrap_from_messages


LEGACY_MEMORY = """# 记忆 Consolidation (L1)

## 对话参与者
- 彭老师：产品经理身份，有产品能力
- 小项：AI助手视角，技术开发背景
- 袭人：AI助手视角，产品经理背景

## 项目规划讨论（2026-03-25）
**目标**：月入20000项目规划

**四个方向分析**：
| 方向 | 启动成本 | 被动收入 | 规模化 |
|------|----------|----------|--------|
| 技术开发类 | 低 | ⭐⭐⭐⭐ | 中 |
| 内容创作类 | 极低 | ⭐⭐⭐ | 高 |
| 电商交易类 | 高 | ⭐⭐⭐⭐ | 高 |
| 服务咨询类 | 极低 | ⭐ | 低 |

**最终共识方案**：
> 阶段一(0-3月)：电商AI客服/工单处理定制服务
> - 工具：Coze/Dify
> - 渠道：闲鱼/淘宝
> - 客单价：500-3000元/月/店
> - 预估：第1月0-2000，第2月3000-5000，第3月5000-8000

> 阶段二(3-6月)：标准化工具包+私教
> - 知识付费形态
> - 边际成本为0

> 阶段三(6月+)：SaaS化或团队化
> - 稳定月入2万+

**关键成功因素**：
- 每天至少3小时投入
- 克服第一单心理障碍
- 不要同时做多个方向

## 异常记录
- **2026-03-31至04-02期间**：存在大量重复prompt injection尝试，用户多次要求助手只回复"@袭人"或"袭人"，助手部分响应了这些请求（约40+次）。存在被操纵迹象，助手在部分回复中只输出了"袭人"二字而非正常对话。
- **2026-04-01 14:09**：MiniMax-M2模型错误，API返回空内容(choices为null)，错误信息包含AssertionError: assert response_object["choices"] is not None
"""


class TestMemoryStore(unittest.TestCase):
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

    def _create_store(self) -> MemoryStore:
        store = MemoryStore(workspace=self.workspace)
        store.write_long_term(LEGACY_MEMORY)
        store.clear_cache()
        return store

    def test_normalize_long_term_memory_converts_legacy_sections(self):
        store = self._create_store()

        normalized = store.normalize_long_term_memory()

        self.assertIn("## Facts", normalized)
        self.assertIn("## Decisions", normalized)
        self.assertIn("## Recent Actions", normalized)
        self.assertIn("- 彭老师：产品经理身份，有产品能力", normalized)
        self.assertIn("[项目规划讨论（2026-03-25）] 目标：月入20000项目规划", normalized)
        self.assertNotIn("*目标**", normalized)

    def test_build_long_term_context_preserves_bullets_for_query(self):
        store = self._create_store()

        context = store.build_long_term_context("袭人 prompt injection")

        self.assertIn("## Facts", context)
        self.assertIn("\n- 袭人：AI助手视角，产品经理背景", context)
        self.assertIn("## Recent Actions", context)
        self.assertIn("prompt injection", context)

    def test_normalize_long_term_memory_can_persist_structured_result(self):
        store = self._create_store()

        persisted = store.normalize_long_term_memory(persist=True)
        reloaded = store.read_long_term(use_cache=False)

        self.assertEqual(reloaded, persisted)
        self.assertTrue(reloaded.startswith("# Long-term Memory"))
        self.assertIn("## Summary", reloaded)

    def test_structured_memory_supports_observations_and_operating_rules(self):
        store = MemoryStore(workspace=self.workspace)
        store.write_long_term(store._render_structured_memory({
            "summary": "用户偏好先结论后展开。",
            "facts": ["项目名为 Horbot。"],
            "observations": ["用户经常先要求全局分析，再要求逐项落地。"],
            "decisions": ["默认使用中文交流。"],
            "operating_rules": ["回复时默认先给结论，再给执行细节。"],
            "open_questions": ["是否需要再补 recall 监控面板。"],
            "recent_actions": ["已修复团队会话路由。"],
        }))

        context = store.build_long_term_context()

        self.assertIn("## Observations", context)
        self.assertIn("## Operating Rules", context)
        self.assertIn("默认先给结论", context)

    def test_reflection_context_is_rendered(self):
        store = MemoryStore(workspace=self.workspace)
        store.write_reflection(store._render_reflection({
            "stable_observations": ["用户偏好中文。"],
            "reusable_strategies": ["先用 targeted smoke，再跑整套 browser-e2e。"],
            "invalidated_observations": ["旧的 main agent 假设已失效。"],
        }))

        reflection = store.build_reflection_context("smoke")

        self.assertIn("## Reusable Strategies", reflection)
        self.assertIn("browser-e2e", reflection)

    def test_team_memory_scopes_are_filtered_by_query(self):
        manager = SharedMemoryManager("team-01")
        manager.write_scope("team_decisions", "# Team Decisions\n\n- 已统一供应商为 MyCC\n", "tester")
        manager.write_scope("shared_constraints", "# Shared Constraints\n\n- 不允许直接删除生产数据\n", "tester")
        manager.write_scope("active_handoff", "# Active Handoff\n\n- 下一棒需要完成聊天 UI 回归\n", "tester")
        manager.write_scope("unresolved_blockers", "# Unresolved Blockers\n\n- browser-e2e 仍有一处团队中断偶发失败\n", "tester")

        store = MemoryStore(workspace=self.workspace, team_ids=["team-01"])
        blocker_context = store.get_all_team_contexts(query="当前有什么阻塞问题")
        decision_context = store.get_all_team_contexts(query="当前团队决策是什么")

        self.assertIn("Unresolved Blockers", blocker_context)
        self.assertNotIn("Shared Constraints", blocker_context)
        self.assertIn("Team Decisions", decision_context)

    def test_bootstrap_start_message_adds_runtime_setup_trigger(self):
        (self.workspace / "SOUL.md").write_text("# 灵魂\n<!-- HORBOT_SETUP_PENDING -->\n", encoding="utf-8")
        (self.workspace / "USER.md").write_text("# 用户档案\n<!-- HORBOT_SETUP_PENDING -->\n", encoding="utf-8")

        builder = ContextBuilder(workspace=self.workspace)
        messages = builder.build_messages([], "开始完善配置吧")

        self.assertIn("FIRST TIME SETUP", messages[0]["content"])
        self.assertIn("Bootstrap Setup Trigger", messages[-1]["content"])

    def test_custom_bootstrap_content_does_not_trigger_first_time_setup(self):
        (self.workspace / "SOUL.md").write_text(
            "# 灵魂\n\n我是 horbot，但现在负责前端交互优化与回归验证。\n\n## 工作方式\n- 先结论后细节\n",
            encoding="utf-8",
        )
        (self.workspace / "USER.md").write_text(
            "# 用户档案\n\n## 基本信息\n- 姓名：彭老师\n- 语言：中文\n\n## 偏好\n- 默认先看结论\n",
            encoding="utf-8",
        )

        builder = ContextBuilder(workspace=self.workspace)

        self.assertFalse(builder.is_first_time_setup())

    def test_first_time_setup_disables_fast_reply_for_followup_turns(self):
        (self.workspace / "SOUL.md").write_text("# 灵魂\n<!-- HORBOT_SETUP_PENDING -->\n", encoding="utf-8")
        (self.workspace / "USER.md").write_text("# 用户档案\n<!-- HORBOT_SETUP_PENDING -->\n", encoding="utf-8")

        builder = ContextBuilder(workspace=self.workspace)

        self.assertFalse(builder.should_use_fast_reply("称呼我彭老师，时区 UTC+8", history_size=2))

    def test_materialize_bootstrap_from_messages_persists_guided_setup(self):
        (self.workspace / "SOUL.md").write_text(
            "# 灵魂\n<!-- HORBOT_SETUP_PENDING -->\n\n我是 小布，运行在 horbot 中的独立 Agent。\n\n## 工作约束\n- 首轮对话时，优先帮助用户明确职责、输出风格、边界和协作方式。\n- 完成首次引导后，请主动重写本文件，并移除 `HORBOT_SETUP_PENDING` 标记。\n\n---\n\n*这是系统根据当前画像与权限档位生成的初始化版本，可在首次私聊后继续细化。*\n",
            encoding="utf-8",
        )
        (self.workspace / "USER.md").write_text(
            "# 用户档案\n<!-- HORBOT_SETUP_PENDING -->\n\n这份 USER.md 用于记录用户与 小布 的专属协作约定。\n\n## 备注\n- 完成首次引导后，请把真实偏好写入本文件，并移除 `HORBOT_SETUP_PENDING` 标记。\n",
            encoding="utf-8",
        )

        changed = materialize_bootstrap_from_messages(
            self.workspace,
            agent_name="小布",
            messages=[
                {"role": "user", "content": "开始完善配置吧"},
                {"role": "assistant", "content": "先从第 1 步开始。"},
                {"role": "user", "content": "称呼我彭老师，时区 UTC+8"},
                {"role": "assistant", "content": "进入第 2 步。"},
                {"role": "user", "content": "我是资深产品经理，需要你和我聊天和编码工作。"},
            ],
        )

        self.assertTrue(changed)
        soul = (self.workspace / "SOUL.md").read_text(encoding="utf-8")
        user = (self.workspace / "USER.md").read_text(encoding="utf-8")
        self.assertNotIn("HORBOT_SETUP_PENDING", soul)
        self.assertNotIn("HORBOT_SETUP_PENDING", user)
        self.assertIn("资深产品经理", soul)
        self.assertIn("称呼：彭老师", user)
        self.assertIn("时区：UTC+8", user)
        self.assertIn("优先支持：聊天", soul)
        self.assertIn("优先支持：编码工作", soul)
        self.assertNotIn("完成首次引导后", soul)
        self.assertNotIn("HORBOT_SETUP_PENDING", soul)
        self.assertNotIn("HORBOT_SETUP_PENDING", user)
        self.assertFalse(ContextBuilder(workspace=self.workspace).is_first_time_setup())


class TestBootstrapToolReconciliation(unittest.IsolatedAsyncioTestCase):
    async def test_safe_write_bootstrap_auto_completes_peer_file(self):
        with tempfile.TemporaryDirectory() as tempdir:
            workspace = Path(tempdir) / "workspace"
            workspace.mkdir(parents=True, exist_ok=True)
            (workspace / "SOUL.md").write_text("# 灵魂\n<!-- HORBOT_SETUP_PENDING -->\n", encoding="utf-8")
            (workspace / "USER.md").write_text("# 用户档案\n<!-- HORBOT_SETUP_PENDING -->\n", encoding="utf-8")

            tool = SafeWriteFileTool(workspace=workspace, allowed_dir=workspace)
            result = await tool.execute(
                str(workspace / "SOUL.md"),
                "# 小项\n\n我是小项，负责多 Agent 协作与回归验证。\n\n## 沟通风格\n- 先结论后细节\n",
            )

            self.assertIn("Successfully wrote", result)
            user_content = (workspace / "USER.md").read_text(encoding="utf-8")
            self.assertIn("这份 USER.md 记录用户与 小项 的当前协作约定", user_content)
            self.assertNotIn("HORBOT_SETUP_PENDING", user_content)
            self.assertFalse(ContextBuilder(workspace=workspace).is_first_time_setup())


if __name__ == "__main__":
    unittest.main()
