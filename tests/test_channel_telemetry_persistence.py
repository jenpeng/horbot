import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import horbot.channels.telemetry as telemetry
from horbot.utils.paths import HORBOT_ROOT_ENV


class ChannelTelemetryPersistenceTests(unittest.TestCase):
    def test_telemetry_persists_to_runtime_files_and_can_be_reloaded(self):
        with tempfile.TemporaryDirectory() as tmpdir, patch.dict(
            os.environ,
            {HORBOT_ROOT_ENV: str(Path(tmpdir) / ".horbot")},
            clear=False,
        ):
            telemetry.clear_channel_telemetry()
            telemetry.record_channel_event(
                "legacy:feishu",
                channel_type="feishu",
                event_type="outbound",
                status="ok",
                message="Dispatched outbound message to group-001",
                details={"chat_id": "group-001", "via": "gateway_http"},
            )

            telemetry._EVENTS.clear()
            telemetry._SUMMARY.clear()

            summary = telemetry.get_channel_summary("legacy:feishu")
            events = telemetry.get_channel_events("legacy:feishu", limit=5)

            self.assertEqual(summary["messages_sent"], 1)
            self.assertEqual(summary["last_event_type"], "outbound")
            self.assertEqual(events[0]["event_type"], "outbound")
            self.assertEqual(events[0]["details"]["via"], "gateway_http")


if __name__ == "__main__":
    unittest.main()
