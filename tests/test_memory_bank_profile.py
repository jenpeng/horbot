import tempfile
import unittest
from pathlib import Path
from unittest.mock import AsyncMock, patch

import httpx

from horbot.agent.context import ContextBuilder
from horbot.agent.manager import get_agent_manager
from horbot.config.normalizer import normalize_config
from horbot.config.schema import AgentConfig, Config
from horbot.web.main import app


class MemoryBankProfileTests(unittest.IsolatedAsyncioTestCase):
    async def test_update_agent_persists_memory_bank_profile(self):
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
            reset_mock = AsyncMock()

            with (
                patch("horbot.web.security.get_cached_config", return_value=config),
                patch("horbot.web.api.get_cached_config", return_value=config),
                patch("horbot.agent.manager.get_cached_config", return_value=config),
                patch("horbot.config.loader.get_cached_config", return_value=config),
                patch("horbot.config.loader.load_config", return_value=config),
                patch("horbot.config.loader.save_config"),
                patch("horbot.web.api.reset_agent_loop", reset_mock),
            ):
                manager.reload(config)
                transport = httpx.ASGITransport(app=app, client=("127.0.0.1", 43123))
                async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
                    update_response = await client.put(
                        "/api/agents/writer",
                        json={
                            "id": "writer",
                            "name": "Writer",
                            "description": "memory profile test",
                            "profile": "builder",
                            "permission_profile": "balanced",
                            "model": "gpt-5.4",
                            "provider": "mycc",
                            "system_prompt": "",
                            "capabilities": ["code"],
                            "tools": [],
                            "skills": [],
                            "workspace": str(workspace_root / "writer"),
                            "teams": [],
                            "personality": "",
                            "avatar": "",
                            "evolution_enabled": True,
                            "learning_enabled": True,
                            "memory_bank_profile": {
                                "mission": "优先保留与前端交互优化和用户反馈相关的长期记忆。",
                                "directives": [
                                    "优先召回较新的约束和回归结论",
                                    "反思时记录可复用的排障策略",
                                ],
                                "reasoning_style": "structured",
                            },
                        },
                    )
                    self.assertEqual(update_response.status_code, 200)

                    get_response = await client.get("/api/agents/writer")
                    list_response = await client.get("/api/agents")

                reset_mock.assert_awaited_once()

            self.assertEqual(get_response.status_code, 200)
            payload = get_response.json()
            self.assertEqual(
                payload["memory_bank_profile"]["mission"],
                "优先保留与前端交互优化和用户反馈相关的长期记忆。",
            )
            self.assertEqual(
                payload["memory_bank_profile"]["directives"],
                ["优先召回较新的约束和回归结论", "反思时记录可复用的排障策略"],
            )
            self.assertEqual(payload["memory_bank_profile"]["reasoning_style"], "structured")

            self.assertEqual(list_response.status_code, 200)
            listed = next(item for item in list_response.json()["agents"] if item["id"] == "writer")
            self.assertEqual(listed["memory_bank_profile"]["reasoning_style"], "structured")

    async def test_context_builder_embeds_memory_bank_profile(self):
        with tempfile.TemporaryDirectory() as tempdir:
            workspace = Path(tempdir) / "writer"
            workspace.mkdir(parents=True, exist_ok=True)
            config = Config()
            config.agents.instances = {
                "writer": AgentConfig(
                    id="writer",
                    name="Writer",
                    workspace=str(workspace),
                    memory_bank_profile={
                        "mission": "优先服务复杂排障与回归验证。",
                        "directives": [
                            "召回时优先看决策与约束",
                            "反思时记录稳定策略和失效经验",
                        ],
                        "reasoning_style": "strict",
                    },
                )
            }
            config = normalize_config(config)

            with patch("horbot.config.loader.get_cached_config", return_value=config):
                builder = ContextBuilder(workspace=workspace, use_hierarchical=False, agent_id="writer", agent_name="Writer")
                prompt = builder.build_system_prompt(include_memory=False)

            self.assertIn("# Memory Bank Profile", prompt)
            self.assertIn("优先服务复杂排障与回归验证", prompt)
            self.assertIn("召回时优先看决策与约束", prompt)
            self.assertIn("严格约束", prompt)


if __name__ == "__main__":
    unittest.main()
