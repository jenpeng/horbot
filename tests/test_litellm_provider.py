import unittest
from unittest.mock import patch
from types import SimpleNamespace

from horbot.providers.litellm_provider import LiteLLMProvider


class LiteLLMProviderTests(unittest.IsolatedAsyncioTestCase):
    async def test_chat_returns_friendly_message_for_invalid_response_error(self):
        provider = LiteLLMProvider(default_model="openai/gpt-4o")

        with patch(
            "horbot.providers.litellm_provider.acompletion",
            side_effect=Exception("Invalid response object: {'received_args': {...}}"),
        ):
            response = await provider.chat(
                messages=[{"role": "user", "content": "hello"}],
                model="openai/gpt-4o",
            )

        self.assertEqual(response.finish_reason, "error")
        self.assertEqual(response.content, "模型服务返回异常，请稍后重试。")
        self.assertEqual(response.error_info["error_code"], "PROVIDER_INVALID_RESPONSE")

    def test_friendly_provider_error_message_classifies_overload(self):
        message = LiteLLMProvider._friendly_provider_error_message(
            error=Exception("当前服务集群负载较高，请稍后重试"),
        )
        self.assertEqual(message, "模型服务当前负载较高，请稍后重试。")

    def test_friendly_provider_error_message_classifies_auth_failures(self):
        message = LiteLLMProvider._friendly_provider_error_message(
            status_code=401,
            error_text="Unauthorized",
        )
        self.assertEqual(message, "模型服务鉴权失败，请检查配置。")

    async def test_chat_returns_structured_error_info_for_auth_failure(self):
        provider = LiteLLMProvider(default_model="openai/gpt-4o", provider_name="mycc")

        with patch(
            "horbot.providers.litellm_provider.acompletion",
            side_effect=Exception("Unauthorized"),
        ):
            response = await provider.chat(
                messages=[{"role": "user", "content": "hello"}],
                model="gpt-5.4",
            )

        self.assertEqual(response.finish_reason, "error")
        self.assertEqual(response.error_info["error_code"], "PROVIDER_AUTH_FAILED")
        self.assertFalse(response.error_info["retryable"])

    async def test_chat_retries_once_for_retryable_provider_error(self):
        provider = LiteLLMProvider(default_model="openai/gpt-4o")
        response_obj = SimpleNamespace(
            choices=[
                SimpleNamespace(
                    finish_reason="stop",
                    message=SimpleNamespace(content="retry ok", tool_calls=None, reasoning_content=None),
                )
            ],
            usage=None,
        )

        with (
            patch(
                "horbot.providers.litellm_provider.acompletion",
                side_effect=[
                    Exception("Invalid response object: {'received_args': {...}}"),
                    response_obj,
                ],
            ) as mocked_completion,
            patch("horbot.providers.litellm_provider.asyncio.sleep") as mocked_sleep,
        ):
            response = await provider.chat(
                messages=[{"role": "user", "content": "hello"}],
                model="openai/gpt-4o",
            )

        self.assertEqual(response.finish_reason, "stop")
        self.assertEqual(response.content, "retry ok")
        self.assertEqual(mocked_completion.call_count, 2)
        mocked_sleep.assert_awaited_once()


if __name__ == "__main__":
    unittest.main()
