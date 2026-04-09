import unittest

from horbot.agent.tools.permission import PermissionManager, PermissionLevel


class PermissionProfileTests(unittest.TestCase):
    def test_balanced_profile_expands_default_rules(self):
        manager = PermissionManager(profile="balanced")

        self.assertEqual(manager.check_permission("read_file"), PermissionLevel.ALLOW)
        self.assertEqual(manager.check_permission("web_search"), PermissionLevel.ALLOW)
        self.assertEqual(manager.check_permission("exec"), PermissionLevel.CONFIRM)
        self.assertEqual(manager.check_permission("task"), PermissionLevel.DENY)

    def test_readonly_profile_blocks_mutation_tools(self):
        manager = PermissionManager(profile="readonly")

        self.assertEqual(manager.check_permission("read_file"), PermissionLevel.ALLOW)
        self.assertEqual(manager.check_permission("write_file"), PermissionLevel.DENY)
        self.assertEqual(manager.check_permission("edit_file"), PermissionLevel.DENY)
        self.assertEqual(manager.check_permission("exec"), PermissionLevel.DENY)


if __name__ == "__main__":
    unittest.main()
