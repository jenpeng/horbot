import tempfile
import unittest
from pathlib import Path
from unittest.mock import AsyncMock, patch

import httpx

from horbot.config.normalizer import normalize_config
from horbot.config.schema import AgentConfig, Config
from horbot.web.main import app


class AgentCreateApiTests(unittest.IsolatedAsyncioTestCase):
    async def test_create_agent_rejects_exact_duplicate_id(self):
        response, save_config_mock, reset_mock = await self._post_create_request(
            existing_agent_id="writer",
            request_id="writer",
        )

        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json()["detail"], "Agent ID 'writer' already exists")
        save_config_mock.assert_not_called()
        reset_mock.assert_not_awaited()

    async def test_create_agent_rejects_duplicate_id_after_normalization(self):
        response, save_config_mock, reset_mock = await self._post_create_request(
            existing_agent_id="Writer",
            request_id=" writer ",
        )

        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json()["detail"], "Agent ID 'writer' already exists")
        save_config_mock.assert_not_called()
        reset_mock.assert_not_awaited()

    async def _post_create_request(self, existing_agent_id: str, request_id: str):
        with tempfile.TemporaryDirectory() as tempdir:
            workspace_root = Path(tempdir) / "workspace"
            config = Config()
            config.agents.defaults.workspace = str(workspace_root)
            config.agents.instances = {
                existing_agent_id: AgentConfig(
                    id=existing_agent_id,
                    name="Existing Agent",
                    workspace=str(workspace_root / existing_agent_id),
                ),
            }
            config = normalize_config(config)
            reset_mock = AsyncMock()

            with (
                patch("horbot.web.security.get_cached_config", return_value=config),
                patch("horbot.web.api.get_cached_config", return_value=config),
                patch("horbot.agent.manager.get_cached_config", return_value=config),
                patch("horbot.config.loader.get_cached_config", return_value=config),
                patch("horbot.config.loader.load_config", return_value=config),
                patch("horbot.config.loader.save_config") as save_config_mock,
                patch("horbot.web.api.reset_agent_loop", reset_mock),
            ):
                transport = httpx.ASGITransport(app=app, client=("127.0.0.1", 43123))
                async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
                    response = await client.post(
                        "/api/agents",
                        json={
                            "id": request_id,
                            "name": "Writer Clone",
                            "description": "duplicate id test",
                            "profile": "",
                            "permission_profile": "",
                            "model": "",
                            "provider": "auto",
                            "system_prompt": "",
                            "capabilities": [],
                            "tools": [],
                            "skills": [],
                            "workspace": "",
                            "teams": [],
                            "personality": "",
                            "avatar": "",
                            "evolution_enabled": True,
                            "learning_enabled": True,
                            "memory_bank_profile": {},
                        },
                    )

        return response, save_config_mock, reset_mock


if __name__ == "__main__":
    unittest.main()
