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

    async def test_patch_web_search_persists_false_langsearch_flag_in_config_response(self):
        app = FastAPI()
        app.include_router(api_router, prefix="/api")
        transport = httpx.ASGITransport(app=app)
        config = Config()
        config.tools.web.search.provider = "langsearch"
        config.tools.web.search.langsearch_enabled = True

        with patch("horbot.web.api.get_cached_config", return_value=config), \
             patch("horbot.web.api.save_config", return_value=Path("/tmp/config.json")), \
             patch("horbot.web.api.reset_agent_loop", new=AsyncMock()):
            async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
                patch_response = await client.patch(
                    "/api/config/web-search",
                    json={"provider": "langsearch", "langsearchEnabled": False, "maxResults": 5},
                )
                get_response = await client.get("/api/config")

        self.assertEqual(patch_response.status_code, 200)
        self.assertEqual(get_response.status_code, 200)
        payload = get_response.json()
        self.assertEqual(payload["tools"]["web"]["search"]["provider"], "langsearch")
        self.assertIs(payload["tools"]["web"]["search"]["langsearchEnabled"], False)

    async def test_patch_web_search_persists_global_enabled_flag_in_config_response(self):
        app = FastAPI()
        app.include_router(api_router, prefix="/api")
        transport = httpx.ASGITransport(app=app)
        config = Config()
        config.tools.web.search.enabled = True

        with patch("horbot.web.api.get_cached_config", return_value=config), \
             patch("horbot.web.api.save_config", return_value=Path("/tmp/config.json")), \
             patch("horbot.web.api.reset_agent_loop", new=AsyncMock()):
            async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
                patch_response = await client.patch(
                    "/api/config/web-search",
                    json={"enabled": False, "maxResults": 5},
                )
                get_response = await client.get("/api/config")

        self.assertEqual(patch_response.status_code, 200)
        self.assertEqual(get_response.status_code, 200)
        payload = get_response.json()
        self.assertIs(payload["tools"]["web"]["search"]["enabled"], False)

    async def test_web_search_providers_include_langsearch_toggle_metadata(self):
        app = FastAPI()
        app.include_router(api_router, prefix="/api")
        transport = httpx.ASGITransport(app=app)

        async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
            response = await client.get("/api/web-search-providers")

        self.assertEqual(response.status_code, 200)
        providers = response.json()["providers"]
        langsearch = next((provider for provider in providers if provider["id"] == "langsearch"), None)
        self.assertIsNotNone(langsearch)
        self.assertTrue(langsearch["requires_api_key"])
        self.assertEqual(langsearch["enabled_config_key"], "langsearchEnabled")

    async def test_patch_web_search_stores_provider_specific_keys_without_overwriting_others(self):
        app = FastAPI()
        app.include_router(api_router, prefix="/api")
        transport = httpx.ASGITransport(app=app)
        config = Config()
        config.tools.web.search.provider = "tavily"
        config.tools.web.search.provider_api_keys = {"tavily": "tv-key", "langsearch": "ls-key"}
        config.tools.web.search.api_key = "tv-key"

        with patch("horbot.web.api.get_cached_config", return_value=config), \
             patch("horbot.web.api.save_config", return_value=Path("/tmp/config.json")), \
             patch("horbot.web.api.reset_agent_loop", new=AsyncMock()):
            async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
                response = await client.patch(
                    "/api/config/web-search",
                    json={"provider": "langsearch", "apiKey": "ls-key-updated", "maxResults": 5},
                )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(config.tools.web.search.provider, "langsearch")
        self.assertEqual(config.tools.web.search.provider_api_keys["tavily"], "tv-key")
        self.assertEqual(config.tools.web.search.provider_api_keys["langsearch"], "ls-key-updated")
        self.assertEqual(config.tools.web.search.api_key, "ls-key-updated")

    async def test_patch_web_search_switching_provider_without_saved_key_clears_effective_api_key(self):
        app = FastAPI()
        app.include_router(api_router, prefix="/api")
        transport = httpx.ASGITransport(app=app)
        config = Config()
        config.tools.web.search.provider = "tavily"
        config.tools.web.search.provider_api_keys = {"tavily": "tv-key"}
        config.tools.web.search.api_key = "tv-key"

        with patch("horbot.web.api.get_cached_config", return_value=config), \
             patch("horbot.web.api.save_config", return_value=Path("/tmp/config.json")), \
             patch("horbot.web.api.reset_agent_loop", new=AsyncMock()):
            async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
                response = await client.patch(
                    "/api/config/web-search",
                    json={"provider": "langsearch", "maxResults": 5},
                )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(config.tools.web.search.provider, "langsearch")
        self.assertEqual(config.tools.web.search.provider_api_keys["tavily"], "tv-key")
        self.assertEqual(config.tools.web.search.api_key, "")

    async def test_get_config_exposes_provider_specific_web_search_key_status(self):
        app = FastAPI()
        app.include_router(api_router, prefix="/api")
        transport = httpx.ASGITransport(app=app)
        config = Config()
        config.tools.web.search.provider = "langsearch"
        config.tools.web.search.provider_api_keys = {"tavily": "tv-secret", "langsearch": "ls-secret"}
        config.tools.web.search.api_key = "ls-secret"

        with patch("horbot.web.api.get_cached_config", return_value=config):
            async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
                response = await client.get("/api/config")

        self.assertEqual(response.status_code, 200)
        search = response.json()["tools"]["web"]["search"]
        self.assertTrue(search["providerApiKeyStatus"]["tavily"]["hasApiKey"])
        self.assertEqual(search["providerApiKeyStatus"]["tavily"]["apiKeyMasked"], "tv-s...cret")
        self.assertTrue(search["providerApiKeyStatus"]["langsearch"]["hasApiKey"])
        self.assertEqual(search["providerApiKeyStatus"]["langsearch"]["apiKeyMasked"], "ls-s...cret")


if __name__ == "__main__":
    unittest.main()
