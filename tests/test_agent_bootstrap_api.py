import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import httpx

from horbot.agent.manager import get_agent_manager
from horbot.config.normalizer import normalize_config
from horbot.config.schema import AgentConfig, Config
from horbot.web.main import app


class AgentBootstrapApiTests(unittest.IsolatedAsyncioTestCase):
    async def test_can_read_and_update_agent_bootstrap_files(self):
        with tempfile.TemporaryDirectory() as tempdir:
            workspace_root = Path(tempdir) / "workspace"
            config = Config()
            config.agents.defaults.workspace = str(workspace_root)
            config.agents.instances = {
                "main": AgentConfig(id="main", name="Main", is_main=True, workspace=str(workspace_root / "main")),
                "writer": AgentConfig(
                    id="writer",
                    name="Writer",
                    workspace=str(workspace_root / "writer"),
                    profile="builder",
                    permission_profile="readonly",
                ),
            }
            config = normalize_config(config)

            manager = get_agent_manager()
            with (
                patch("horbot.web.security.get_cached_config", return_value=config),
                patch("horbot.web.api.get_cached_config", return_value=config),
                patch("horbot.agent.manager.get_cached_config", return_value=config),
                patch("horbot.config.loader.get_cached_config", return_value=config),
            ):
                manager.reload(config)
                writer = manager.get_agent("writer")
                self.assertIsNotNone(writer)
                workspace = writer.get_workspace()
                (workspace / "SOUL.md").write_text("# Writer Soul\n", encoding="utf-8")

                transport = httpx.ASGITransport(app=app, client=("127.0.0.1", 43123))
                async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
                    response = await client.get("/api/agents/writer/bootstrap-files")
                    self.assertEqual(response.status_code, 200)
                    payload = response.json()
                    self.assertEqual(payload["agent_id"], "writer")
                    self.assertEqual(payload["files"]["soul"]["content"], "# Writer Soul\n")
                    self.assertIn("HORBOT_SETUP_PENDING", payload["files"]["user"]["content"])
                    self.assertIn("工程实现者", payload["files"]["user"]["content"])
                    self.assertIn("只读模式", payload["files"]["user"]["content"])
                    self.assertIn("Agent 名称：Writer Soul", payload["summary"]["identity"])
                    self.assertIn("协作画像：工程实现者", payload["summary"]["role_focus"])
                    self.assertTrue(payload["summary"]["is_structured"])

                    agents_response = await client.get("/api/agents")
                    self.assertEqual(agents_response.status_code, 200)
                    agents_payload = agents_response.json()["agents"]
                    main_payload = next(item for item in agents_payload if item["id"] == "main")
                    writer_payload = next(item for item in agents_response.json()["agents"] if item["id"] == "writer")
                    self.assertTrue(main_payload["is_main"])
                    self.assertFalse(writer_payload["is_main"])
                    self.assertTrue(writer_payload["bootstrap_setup_pending"])
                    self.assertEqual(writer_payload["tool_permission_profile"], "readonly")

                    summary_update = await client.put(
                        "/api/agents/writer/bootstrap-summary",
                        json={
                            "identity": ["Agent 名称：Writer Soul", "定位：负责文档整理与输出"],
                            "role_focus": ["负责需求梳理", "输出可执行方案"],
                            "communication_style": ["先结论后细节", "必要时补充风险提示"],
                            "boundaries": ["未经确认不修改生产配置"],
                            "user_preferences": ["默认使用中文", "优先给出简洁结论"],
                        },
                    )
                    self.assertEqual(summary_update.status_code, 200)
                    summary_payload = summary_update.json()
                    self.assertEqual(summary_payload["status"], "updated")
                    self.assertIn("定位：负责文档整理与输出", summary_payload["summary"]["identity"])
                    self.assertIn("负责需求梳理", summary_payload["summary"]["role_focus"])
                    self.assertIn("默认使用中文", summary_payload["summary"]["user_preferences"])
                    self.assertNotIn("HORBOT_SETUP_PENDING", summary_payload["files"]["soul"]["content"])
                    self.assertNotIn("HORBOT_SETUP_PENDING", summary_payload["files"]["user"]["content"])

                    soul_content = (workspace / "SOUL.md").read_text(encoding="utf-8")
                    user_content = (workspace / "USER.md").read_text(encoding="utf-8")
                    self.assertIn("## 身份定位", soul_content)
                    self.assertIn("- 定位：负责文档整理与输出", soul_content)
                    self.assertIn("## 职责重点", soul_content)
                    self.assertIn("- 负责需求梳理", soul_content)
                    self.assertIn("## 沟通风格", soul_content)
                    self.assertIn("## 边界约束", soul_content)
                    self.assertIn("## 用户偏好", user_content)
                    self.assertIn("- 默认使用中文", user_content)

                    agents_after_summary = await client.get("/api/agents")
                    self.assertEqual(agents_after_summary.status_code, 200)
                    writer_after_summary = next(item for item in agents_after_summary.json()["agents"] if item["id"] == "writer")
                    self.assertFalse(writer_after_summary["bootstrap_setup_pending"])

                    update = await client.put(
                        "/api/agents/writer/bootstrap-files/user",
                        json={"content": "# User Profile\nname: Test\n"},
                    )
                    self.assertEqual(update.status_code, 200)
                    updated_payload = update.json()
                    self.assertEqual(updated_payload["file"], "USER.md")

                    refreshed = await client.get("/api/agents/writer/bootstrap-files")
                    self.assertEqual(refreshed.status_code, 200)
                    refreshed_payload = refreshed.json()
                    self.assertEqual(
                        refreshed_payload["files"]["user"]["content"],
                        "# User Profile\nname: Test\n",
                    )

    async def test_custom_bootstrap_files_are_not_misclassified_as_pending(self):
        with tempfile.TemporaryDirectory() as tempdir:
            workspace_root = Path(tempdir) / "workspace"
            config = Config()
            config.agents.defaults.workspace = str(workspace_root)
            config.agents.instances = {
                "writer": AgentConfig(
                    id="writer",
                    name="Writer",
                    model="gpt-5.4",
                    provider="mycc",
                    workspace=str(workspace_root / "writer"),
                ),
            }
            config = normalize_config(config)

            manager = get_agent_manager()
            with (
                patch("horbot.web.security.get_cached_config", return_value=config),
                patch("horbot.web.api.get_cached_config", return_value=config),
                patch("horbot.agent.manager.get_cached_config", return_value=config),
                patch("horbot.config.loader.get_cached_config", return_value=config),
            ):
                manager.reload(config)
                writer = manager.get_agent("writer")
                self.assertIsNotNone(writer)
                workspace = writer.get_workspace()
                (workspace / "SOUL.md").write_text(
                    "# 灵魂\n\n我是 horbot，但现在专注于多 agent 协作与前端回归。\n\n## 工作方式\n- 先结论后细节\n",
                    encoding="utf-8",
                )
                (workspace / "USER.md").write_text(
                    "# 用户档案\n\n## 基本信息\n- 姓名：彭老师\n- 语言：中文\n\n## 协作偏好\n- 默认先给结论\n",
                    encoding="utf-8",
                )

                transport = httpx.ASGITransport(app=app, client=("127.0.0.1", 43123))
                async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
                    response = await client.get("/api/agents/writer")

            self.assertEqual(response.status_code, 200)
            payload = response.json()
            self.assertFalse(payload["setup_required"])
            self.assertFalse(payload["bootstrap_setup_pending"])

    async def test_single_file_update_auto_reconciles_peer_bootstrap_file(self):
        with tempfile.TemporaryDirectory() as tempdir:
            workspace_root = Path(tempdir) / "workspace"
            config = Config()
            config.agents.defaults.workspace = str(workspace_root)
            config.agents.instances = {
                "writer": AgentConfig(
                    id="writer",
                    name="Writer",
                    workspace=str(workspace_root / "writer"),
                ),
            }
            config = normalize_config(config)

            manager = get_agent_manager()
            with (
                patch("horbot.web.security.get_cached_config", return_value=config),
                patch("horbot.web.api.get_cached_config", return_value=config),
                patch("horbot.agent.manager.get_cached_config", return_value=config),
                patch("horbot.config.loader.get_cached_config", return_value=config),
            ):
                manager.reload(config)
                writer = manager.get_agent("writer")
                self.assertIsNotNone(writer)

                transport = httpx.ASGITransport(app=app, client=("127.0.0.1", 43123))
                async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
                    update = await client.put(
                        "/api/agents/writer/bootstrap-files/soul",
                        json={
                            "content": "# 小项\n\n我是小项，负责工程实现与回归验证。\n\n## 职责重点\n- 修复问题\n- 跑回归\n\n## 沟通风格\n- 先结论后细节\n",
                        },
                    )
                    self.assertEqual(update.status_code, 200)

                    bootstrap = await client.get("/api/agents/writer/bootstrap-files")
                    self.assertEqual(bootstrap.status_code, 200)
                    payload = bootstrap.json()
                    self.assertIn("这份 USER.md 记录用户与 小项 的当前协作约定", payload["files"]["user"]["content"])
                    self.assertNotIn("HORBOT_SETUP_PENDING", payload["files"]["user"]["content"])

                    agent_response = await client.get("/api/agents/writer")
                    self.assertEqual(agent_response.status_code, 200)
                    agent_payload = agent_response.json()
                    self.assertFalse(agent_payload["bootstrap_setup_pending"])


if __name__ == "__main__":
    unittest.main()
