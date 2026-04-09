import tempfile
import unittest
import json
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

    def test_title_persists_across_save_and_reload(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            manager = SessionManager(workspace=Path(tmpdir))
            session = manager.get_or_create("web:test")
            session.add_message("user", "This title should persist")
            manager.save(session)

            manager.invalidate("web:test")
            reloaded = manager.get("web:test")

            self.assertIsNotNone(reloaded)
            self.assertEqual(reloaded.title, "This title should persist")
            self.assertEqual(reloaded.metadata.get("title"), "This title should persist")

    def test_list_sessions_uses_persisted_message_count_metadata(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            manager = SessionManager(workspace=Path(tmpdir))
            session = manager.get_or_create("web:test")
            session.add_message("user", "one")
            session.add_message("assistant", "two")
            manager.save(session)

            session_path = manager._get_session_path("web:test")
            with open(session_path, encoding="utf-8") as f:
                metadata = json.loads(f.readline())

            self.assertEqual(metadata["message_count"], 2)
            self.assertEqual(manager.list_sessions()[0]["message_count"], 2)

    def test_list_sessions_falls_back_for_legacy_metadata_without_message_count(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            manager = SessionManager(workspace=Path(tmpdir))
            session_path = manager._get_session_path("web:test")

            with open(session_path, "w", encoding="utf-8") as f:
                f.write(json.dumps({
                    "_type": "metadata",
                    "key": "web:test",
                    "created_at": "2026-04-09T10:00:00",
                    "updated_at": "2026-04-09T10:00:00",
                    "metadata": {"title": "Legacy Session"},
                    "last_consolidated": 0,
                }, ensure_ascii=False) + "\n")
                f.write(json.dumps({"role": "user", "content": "one"}, ensure_ascii=False) + "\n")
                f.write(json.dumps({"role": "assistant", "content": "two"}, ensure_ascii=False) + "\n")

            session_info = manager.list_sessions()[0]
            self.assertEqual(session_info["title"], "Legacy Session")
            self.assertEqual(session_info["message_count"], 2)

    def test_list_sessions_can_filter_by_key_prefix(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            manager = SessionManager(workspace=Path(tmpdir))
            web_session = manager.get_or_create("web:test")
            web_session.add_message("user", "web")
            manager.save(web_session)

            agent_session = manager.get_or_create("agent:test")
            agent_session.add_message("user", "agent")
            manager.save(agent_session)

            session_infos = manager.list_sessions(key_prefix="web:")

            self.assertEqual(len(session_infos), 1)
            self.assertEqual(session_infos[0]["key"], "web:test")


if __name__ == "__main__":
    unittest.main()
