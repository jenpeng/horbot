import tempfile
import unittest
from pathlib import Path

from horbot.session.manager import SessionManager


class ChatSessionIdTests(unittest.TestCase):
    def test_add_message_preserves_explicit_message_id(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            manager = SessionManager(workspace=Path(tmpdir))
            session = manager.get_or_create("web:test")

            message_id = session.add_message("assistant", "hello", message_id="msg-1234")

            self.assertEqual(message_id, "msg-1234")
            self.assertEqual(session.messages[-1]["id"], "msg-1234")

    def test_dedup_returns_existing_message_id(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            manager = SessionManager(workspace=Path(tmpdir))
            session = manager.get_or_create("web:test")

            first_id = session.add_message("assistant", "same content", message_id="msg-1111")
            second_id = session.add_message(
                "assistant",
                "same content",
                dedup=True,
                message_id="msg-2222",
            )

            self.assertEqual(first_id, "msg-1111")
            self.assertEqual(second_id, "msg-1111")
            self.assertEqual(len(session.messages), 1)


if __name__ == "__main__":
    unittest.main()
