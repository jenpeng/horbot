import unittest

from horbot.utils.error_messages import (
    friendly_provider_error_message,
    is_retryable_provider_error,
    public_error_message,
)


class ErrorMessageTests(unittest.TestCase):
    def test_friendly_provider_error_message_sanitizes_invalid_response_trace(self):
        message = friendly_provider_error_message(
            error=Exception(
                "litellm.InternalServerError: OpenAIException - Invalid response object "
                "Traceback ... received_args={'response_object': {'choices': None}}"
            )
        )
        self.assertEqual(message, "模型服务返回异常，请稍后重试。")

    def test_public_error_message_returns_generic_message_for_non_provider_exception(self):
        message = public_error_message(RuntimeError("database locked"))
        self.assertEqual(message, "服务处理失败，请稍后重试。")

    def test_public_error_message_preserves_provider_safe_message(self):
        message = public_error_message(
            "Error calling LLM: litellm.InternalServerError: Invalid response object"
        )
        self.assertEqual(message, "模型服务返回异常，请稍后重试。")

    def test_retryable_provider_error_detects_invalid_response(self):
        self.assertTrue(
            is_retryable_provider_error(
                "litellm.InternalServerError: Invalid response object Traceback ... received_args={...}"
            )
        )

    def test_friendly_provider_error_message_detects_missing_model_channel(self):
        message = friendly_provider_error_message(
            error=Exception(
                "Error code: 400 - {'error': {'code': 'model_not_found', "
                "'message': 'No available channel for model MiniMax-M2.7 under group codex'}}"
            )
        )
        self.assertEqual(message, "当前模型或接口不存在，请检查配置。")

    def test_missing_model_channel_is_not_retryable(self):
        self.assertFalse(
            is_retryable_provider_error(
                "No available channel for model MiniMax-M2.7 under group codex"
            )
        )
