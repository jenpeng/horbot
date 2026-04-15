import unittest
from pathlib import Path
from unittest.mock import AsyncMock, patch

import httpx
from fastapi import FastAPI

from horbot.config.schema import Config
from horbot.web.api import router as api_router


class WebSearchConfigApiTests(unittest.IsolatedAsyncioTestCase):
    async def test_patch_web_search_persists_false_tavily_flag_in_config_response(self):
        app = FastAPI()
        app.include_router(api_router, prefix="/api")
        transport = httpx.ASGITransport(app=app)
        config = Config()
        config.tools.web.search.provider = "tavily"
        config.tools.web.search.tavily_enabled = True

        with patch("horbot.web.api.get_cached_config", return_value=config), \
             patch("horbot.web.api.save_config", return_value=Path("/tmp/config.json")), \
             patch("horbot.web.api.reset_agent_loop", new=AsyncMock()):
            async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
                patch_response = await client.patch(
                    "/api/config/web-search",
                    json={"provider": "tavily", "tavilyEnabled": False, "maxResults": 5},
                )
                get_response = await client.get("/api/config")

        self.assertEqual(patch_response.status_code, 200)
        self.assertEqual(get_response.status_code, 200)
        payload = get_response.json()
        self.assertEqual(payload["tools"]["web"]["search"]["provider"], "tavily")
        self.assertIs(payload["tools"]["web"]["search"]["tavilyEnabled"], False)


if __name__ == "__main__":
    unittest.main()
