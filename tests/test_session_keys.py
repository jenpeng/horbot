import unittest

from horbot.utils.helpers import parse_session_key, parse_session_key_with_known_routes


class SessionKeyParsingTests(unittest.TestCase):
    def test_parse_legacy_endpoint_session_key_prefers_longest_route_prefix(self):
        route, chat_id = parse_session_key_with_known_routes(
            "legacy:feishu:ou_559e501c4c575696fb3ac354a75bb794",
            known_route_keys=["legacy:feishu", "legacy:sharecrm"],
        )

        self.assertEqual(route, "legacy:feishu")
        self.assertEqual(chat_id, "ou_559e501c4c575696fb3ac354a75bb794")

    def test_parse_session_key_keeps_colons_inside_chat_id(self):
        route, chat_id = parse_session_key_with_known_routes(
            "legacy:sharecrm:0:fs:b21ddfcd6a074e0abef44266b19c32ee:",
            known_route_keys=["legacy:sharecrm"],
        )

        self.assertEqual(route, "legacy:sharecrm")
        self.assertEqual(chat_id, "0:fs:b21ddfcd6a074e0abef44266b19c32ee:")

    def test_parse_session_key_falls_back_to_standard_prefixes(self):
        route, chat_id = parse_session_key("web:dm_horbot-03")

        self.assertEqual(route, "web")
        self.assertEqual(chat_id, "dm_horbot-03")


if __name__ == "__main__":
    unittest.main()
