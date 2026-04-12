import unittest

from horbot.channels.diagnostics import test_channel_connection as run_channel_connection
from horbot.config.schema import EmailConfig, FeishuConfig, WeComConfig


class ChannelDiagnosticsTests(unittest.IsolatedAsyncioTestCase):
    async def test_feishu_missing_credentials_returns_structured_diagnostics(self):
        result = await run_channel_connection(
            "feishu",
            FeishuConfig(enabled=True, app_id="", app_secret=""),
        )

        self.assertEqual(result["status"], "error")
        self.assertEqual(result["error_code"], "MISSING_REQUIRED_CONFIG")
        self.assertEqual(result["error_kind"], "missing")
        self.assertTrue(result["remediation"])
        self.assertTrue(any("飞书" in item or "App ID" in item for item in result["remediation"]))

    async def test_email_missing_config_returns_structured_diagnostics(self):
        result = await run_channel_connection(
            "email",
            EmailConfig(enabled=True, imap_host="", imap_username=""),
        )

        self.assertEqual(result["status"], "error")
        self.assertEqual(result["error_code"], "MISSING_REQUIRED_CONFIG")
        self.assertEqual(result["error_kind"], "missing")
        self.assertTrue(any("IMAP/SMTP" in item for item in result["remediation"]))

    async def test_wecom_missing_credentials_returns_structured_diagnostics(self):
        result = await run_channel_connection(
            "wecom",
            WeComConfig(enabled=True, bot_id="", secret=""),
        )

        self.assertEqual(result["status"], "error")
        self.assertEqual(result["error_code"], "MISSING_REQUIRED_CONFIG")
        self.assertEqual(result["error_kind"], "missing")
        self.assertTrue(any("Bot ID" in item or "企业微信" in item for item in result["remediation"]))


if __name__ == "__main__":
    unittest.main()
