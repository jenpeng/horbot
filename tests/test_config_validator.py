import unittest

from horbot.config.schema import Config
from horbot.config.validator import PermissionRule


class ConfigValidatorTests(unittest.TestCase):
    def setUp(self) -> None:
        self.rule = PermissionRule()

    def test_permission_rule_accepts_runtime_profiles(self):
        for profile in ("full", "balanced", "readonly", "coding", "minimal"):
            config = Config()
            config.tools.permission.profile = profile

            result = self.rule.validate(config)

            self.assertFalse(
                any(message.code == "UNKNOWN_PERMISSION_PROFILE" for message in result.warnings),
                msg=f"profile {profile} should not trigger UNKNOWN_PERMISSION_PROFILE",
            )

    def test_permission_rule_warns_for_unknown_profile(self):
        config = Config()
        config.tools.permission.profile = "nonexistent-profile"

        result = self.rule.validate(config)

        warning = next(
            (message for message in result.warnings if message.code == "UNKNOWN_PERMISSION_PROFILE"),
            None,
        )
        self.assertIsNotNone(warning)
        self.assertEqual(warning.field_path, "tools.permission.profile")
        self.assertIn("balanced", warning.suggestion or "")
        self.assertIn("full", warning.suggestion or "")


if __name__ == "__main__":
    unittest.main()
