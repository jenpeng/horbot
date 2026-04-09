from types import SimpleNamespace
import unittest

from horbot.agent.loop import AgentLoop


class ExternalSourceMetadataTests(unittest.TestCase):
    def test_build_execution_source_metadata_for_legacy_feishu_session(self):
        fake_loop = SimpleNamespace(
            _list_bound_channel_endpoints=lambda: [
                {"id": "legacy:feishu", "channel": "feishu", "name": "飞书"}
            ]
        )

        metadata = AgentLoop._build_execution_source_metadata(
            fake_loop,
            "legacy:feishu:ou_559e501c4c575696fb3ac354a75bb794",
        )

        self.assertEqual(metadata["source_session_key"], "legacy:feishu:ou_559e501c4c575696fb3ac354a75bb794")
        self.assertEqual(metadata["source_channel_instance_id"], "legacy:feishu")
        self.assertEqual(metadata["source_chat_id"], "ou_559e501c4c575696fb3ac354a75bb794")
        self.assertEqual(metadata["source_channel_type"], "feishu")
        self.assertEqual(metadata["source_endpoint_name"], "飞书")
        self.assertEqual(metadata["source_chat_kind"], "external")

    def test_build_execution_source_metadata_for_legacy_sharecrm_session(self):
        fake_loop = SimpleNamespace(
            _list_bound_channel_endpoints=lambda: [
                {"id": "legacy:sharecrm", "channel": "sharecrm", "name": "ShareCRM"}
            ]
        )

        metadata = AgentLoop._build_execution_source_metadata(
            fake_loop,
            "legacy:sharecrm:0:fs:b21ddfcd6a074e0abef44266b19c32ee:",
        )

        self.assertEqual(metadata["source_session_key"], "legacy:sharecrm:0:fs:b21ddfcd6a074e0abef44266b19c32ee:")
        self.assertEqual(metadata["source_channel_instance_id"], "legacy:sharecrm")
        self.assertEqual(metadata["source_chat_id"], "0:fs:b21ddfcd6a074e0abef44266b19c32ee:")
        self.assertEqual(metadata["source_channel_type"], "sharecrm")
        self.assertEqual(metadata["source_endpoint_name"], "ShareCRM")
        self.assertEqual(metadata["source_chat_kind"], "external")


if __name__ == "__main__":
    unittest.main()
