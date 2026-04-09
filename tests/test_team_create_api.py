import tempfile
import unittest
from pathlib import Path
from unittest.mock import AsyncMock, patch

import httpx

from horbot.config.normalizer import normalize_config
from horbot.config.schema import Config, TeamConfig
from horbot.web.main import app


class TeamCreateApiTests(unittest.IsolatedAsyncioTestCase):
    async def test_create_team_rejects_exact_duplicate_id(self):
        response, save_config_mock, reset_mock = await self._post_create_request(
            existing_team_id="delivery",
            request_id="delivery",
        )

        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json()["detail"], "Team ID 'delivery' already exists")
        save_config_mock.assert_not_called()
        reset_mock.assert_not_awaited()

    async def test_create_team_rejects_duplicate_id_after_normalization(self):
        response, save_config_mock, reset_mock = await self._post_create_request(
            existing_team_id="Delivery",
            request_id=" delivery ",
        )

        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json()["detail"], "Team ID 'delivery' already exists")
        save_config_mock.assert_not_called()
        reset_mock.assert_not_awaited()

    async def _post_create_request(self, existing_team_id: str, request_id: str):
        with tempfile.TemporaryDirectory() as tempdir:
            workspace_root = Path(tempdir) / "workspace"
            config = Config()
            config.teams.instances = {
                existing_team_id: TeamConfig(
                    id=existing_team_id,
                    name="Existing Team",
                    workspace=str(workspace_root / existing_team_id),
                ),
            }
            config = normalize_config(config)
            reset_mock = AsyncMock()

            with (
                patch("horbot.web.security.get_cached_config", return_value=config),
                patch("horbot.web.api.get_cached_config", return_value=config),
                patch("horbot.team.manager.get_cached_config", return_value=config),
                patch("horbot.config.loader.get_cached_config", return_value=config),
                patch("horbot.config.loader.load_config", return_value=config),
                patch("horbot.config.loader.save_config") as save_config_mock,
                patch("horbot.web.api.reset_agent_loop", reset_mock),
            ):
                transport = httpx.ASGITransport(app=app, client=("127.0.0.1", 43123))
                async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
                    response = await client.post(
                        "/api/teams",
                        json={
                            "id": request_id,
                            "name": "Delivery Clone",
                            "description": "duplicate id test",
                            "members": [],
                            "member_profiles": {},
                            "workspace": "",
                        },
                    )

        return response, save_config_mock, reset_mock


if __name__ == "__main__":
    unittest.main()
