import unittest

from horbot.config.schema import Config
from horbot.web.api import _build_dashboard_channel_summary


class DashboardChannelSummaryTests(unittest.TestCase):
    def test_enabled_alias_backed_channels_are_not_marked_missing(self):
        config = Config.model_validate({
            "channels": {
                "feishu": {
                    "enabled": True,
                    "appId": "cli_test",
                    "appSecret": "secret_test",
                },
                "sharecrm": {
                    "enabled": True,
                    "appId": "sharecrm_app",
                    "appSecret": "sharecrm_secret",
                },
            },
        })

        summary = _build_dashboard_channel_summary(config)
        items = {item["name"]: item for item in summary["items"]}

        self.assertEqual(summary["counts"]["enabled"], 2)
        self.assertEqual(summary["counts"]["online"], 2)
        self.assertEqual(summary["counts"]["misconfigured"], 0)
        self.assertEqual(items["feishu"]["status"], "online")
        self.assertEqual(items["feishu"]["missing_fields"], [])
        self.assertEqual(items["sharecrm"]["status"], "online")
        self.assertEqual(items["sharecrm"]["missing_fields"], [])


if __name__ == "__main__":
    unittest.main()
