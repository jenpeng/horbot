import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import httpx

from horbot.agent.manager import get_agent_manager
from horbot.config.normalizer import normalize_config
from horbot.config.schema import AgentConfig, Config
from horbot.providers.custom_provider import CustomProvider
from horbot.providers.registry import create_provider
from horbot.web.main import app


class _FakeStream:
    def __init__(self, chunks):
        self._chunks = list(chunks)

    def __aiter__(self):
        return self

    async def __anext__(self):
        if not self._chunks:
            raise StopAsyncIteration
        return self._chunks.pop(0)


class DynamicProviderHotReloadTests(unittest.IsolatedAsyncioTestCase):
    async def test_list_providers_includes_dynamic_provider(self):
        config = Config.model_validate(
            {
                "providers": {
                    "mycc": {
                        "apiKey": "sk-test",
                        "apiBase": "https://example.test/v1",
                    }
                }
            }
        )

        transport = httpx.ASGITransport(app=app, client=("127.0.0.1", 43123))
        async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
            with patch("horbot.config.loader.load_config", return_value=config):
                response = await client.get("/api/providers")

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        mycc = next((provider for provider in payload["providers"] if provider["id"] == "mycc"), None)
        self.assertIsNotNone(mycc)
        self.assertTrue(mycc["configured"])
        self.assertEqual(mycc["models"][0]["id"], "gpt-5.4")

    async def test_update_agent_hot_reloads_model_without_restart(self):
        with tempfile.TemporaryDirectory() as tempdir:
            workspace_root = Path(tempdir) / "workspace"
            config = Config()
            config.agents.defaults.workspace = str(workspace_root)
            config.agents.instances = {
                "main": AgentConfig(
                    id="main",
                    name="Main",
                    model="gpt-5.4",
                    provider="mycc",
                    workspace=str(workspace_root / "main"),
                ),
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
                        "/api/agents/main",
                        json={
                            "id": "main",
                            "name": "Main",
                            "description": "",
                            "model": "MiniMax-M2.7",
                            "provider": "mycc",
                            "system_prompt": "",
                            "capabilities": [],
                            "tools": [],
                            "skills": [],
                            "workspace": str(workspace_root / "main"),
                            "teams": [],
                            "personality": "",
                            "avatar": "",
                            "evolution_enabled": True,
                            "learning_enabled": True,
                        },
                    )
                    self.assertEqual(update_response.status_code, 200)

                    list_response = await client.get("/api/agents")

                reset_mock.assert_awaited_once()

            self.assertEqual(list_response.status_code, 200)
            agents = {agent["id"]: agent for agent in list_response.json()["agents"]}
            self.assertEqual(agents["main"]["model"], "MiniMax-M2.7")
            self.assertEqual(agents["main"]["provider"], "mycc")
            self.assertEqual(agents["writer"]["model"], "gpt-5.4")

    def test_dynamic_provider_with_api_base_uses_custom_provider(self):
        provider = create_provider(
            "mycc",
            api_key="sk-test",
            api_base="https://example.test/v1",
            default_model="gpt-5.4",
        )
        self.assertIsInstance(provider, CustomProvider)
        self.assertEqual(provider.get_default_model(), "gpt-5.4")

    async def test_custom_provider_supports_stream_only_openai_compatible_endpoints(self):
        provider = CustomProvider(
            api_key="sk-test",
            api_base="https://example.test/v1",
            default_model="gpt-5.4",
        )

        async def fake_create(**kwargs):
            if not kwargs.get("stream"):
                raise Exception("Stream must be set to true")
            return _FakeStream(
                [
                    SimpleNamespace(
                        choices=[
                            SimpleNamespace(
                                finish_reason=None,
                                delta=SimpleNamespace(
                                    content="STREAM-",
                                    reasoning_content=None,
                                    reasoning=None,
                                    tool_calls=None,
                                ),
                            )
                        ],
                        usage=None,
                    ),
                    SimpleNamespace(
                        choices=[
                            SimpleNamespace(
                                finish_reason="stop",
                                delta=SimpleNamespace(
                                    content="OK",
                                    reasoning_content=None,
                                    reasoning=None,
                                    tool_calls=None,
                                ),
                            )
                        ],
                        usage=SimpleNamespace(prompt_tokens=3, completion_tokens=2, total_tokens=5),
                    ),
                ]
            )

        provider._client = SimpleNamespace(
            chat=SimpleNamespace(
                completions=SimpleNamespace(create=fake_create),
            )
        )

        response = await provider.chat(
            messages=[{"role": "user", "content": "hello"}],
            model="gpt-5.4",
            file_ids=[],
            files=[],
        )

        self.assertEqual(response.content, "STREAM-OK")
        self.assertEqual(response.finish_reason, "stop")
        self.assertEqual(response.usage["total_tokens"], 5)

    async def test_custom_provider_parses_structured_content_blocks(self):
        provider = CustomProvider(
            api_key="sk-test",
            api_base="https://example.test/v1",
            default_model="gpt-5.4",
        )

        async def fake_create(**kwargs):
            return SimpleNamespace(
                choices=[
                    SimpleNamespace(
                        finish_reason="stop",
                        message=SimpleNamespace(
                            content=[{"type": "output_text", "text": "BLOCK-OK"}],
                            output_text=None,
                            tool_calls=None,
                            reasoning_content=None,
                            reasoning=None,
                        ),
                    )
                ],
                usage=SimpleNamespace(prompt_tokens=1, completion_tokens=1, total_tokens=2),
            )

        provider._client = SimpleNamespace(
            chat=SimpleNamespace(
                completions=SimpleNamespace(create=fake_create),
            )
        )

        response = await provider.chat(
            messages=[{"role": "user", "content": "hello"}],
            model="gpt-5.4",
        )

        self.assertEqual(response.content, "BLOCK-OK")
        self.assertEqual(response.usage["total_tokens"], 2)


if __name__ == "__main__":
    unittest.main()
