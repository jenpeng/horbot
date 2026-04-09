import unittest

from horbot.providers.diagnostics import diagnose_provider_error


class ProviderDiagnosticsTests(unittest.TestCase):
    def test_auth_error_is_structured(self):
        result = diagnose_provider_error(
            status_code=401,
            error_text="Unauthorized",
            provider_name="mycc",
            model="gpt-5.4",
        )

        self.assertEqual(result["error_code"], "PROVIDER_AUTH_FAILED")
        self.assertEqual(result["error_kind"], "auth")
        self.assertIn("鉴权失败", result["message"])
        self.assertFalse(result["retryable"])

    def test_model_not_found_has_actionable_remediation(self):
        result = diagnose_provider_error(
            error_text="model_not_found: MiniMax-M2.7",
            provider_name="mycc",
            model="MiniMax-M2.7",
        )

        self.assertEqual(result["error_code"], "PROVIDER_MODEL_NOT_FOUND")
        self.assertIn("MiniMax-M2.7", result["remediation"][0])

    def test_invalid_response_is_retryable(self):
        result = diagnose_provider_error(
            error_text="Invalid response object: received_args={...}",
            provider_name="openrouter",
            model="gpt-4o",
        )

        self.assertEqual(result["error_kind"], "invalid_response")
        self.assertTrue(result["retryable"])


if __name__ == "__main__":
    unittest.main()
