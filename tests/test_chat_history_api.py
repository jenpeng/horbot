import unittest
from tempfile import TemporaryDirectory
from pathlib import Path

from horbot.agent.conversation import format_history_for_agent
from horbot.session.manager import Session, SessionManager
from horbot.web.api import (
    _load_merged_session_messages,
    _merge_history_messages,
    clean_message_content,
    ensure_history_message_id,
)


class ChatHistoryApiTests(unittest.TestCase):
    def test_session_history_keeps_metadata_for_agent_filtering(self):
        session = Session(key="web:dm_alpha")
        session.messages = [
            {
                "id": "user-1",
                "role": "user",
                "content": "你好",
                "timestamp": "2026-04-24T10:00:00",
            },
            {
                "id": "assistant-alpha",
                "role": "assistant",
                "content": "这是 Alpha 的上一条回复",
                "timestamp": "2026-04-24T10:00:01",
                "metadata": {
                    "agent_id": "alpha",
                    "agent_name": "Alpha",
                },
            },
            {
                "id": "assistant-beta",
                "role": "assistant",
                "content": "这是 Beta 的历史回复，不应该出现在 Alpha 的 DM 上下文里",
                "timestamp": "2026-04-24T10:00:02",
                "metadata": {
                    "agent_id": "beta",
                    "agent_name": "Beta",
                },
            },
        ]

        history = format_history_for_agent(
            session.get_history(),
            target_agent_id="alpha",
            target_agent_name="Alpha",
            is_group_chat=False,
        )

        self.assertEqual(
            [message["content"] for message in history],
            ["你好", "这是 Alpha 的上一条回复"],
        )

    def test_clean_message_content_unwraps_message_wrapper_with_to_attribute(self):
        content = '<message from="小项 🐎" to="袭人">\n你好呀\n</message>'

        self.assertEqual(clean_message_content(content), "你好呀")

    def test_clean_message_content_unwraps_nested_message_wrappers(self):
        content = (
            '<message from="小项 🐎">\n'
            '<message from="袭人" to="小项 🐎">\n'
            'DM_SMOKE_OK_1234\n'
            '</message>\n'
            '</message>'
        )

        self.assertEqual(clean_message_content(content), "DM_SMOKE_OK_1234")

    def test_preserves_existing_message_id(self):
        message = {"id": "msg-123", "role": "assistant", "content": "hello"}

        self.assertEqual(ensure_history_message_id(message), "msg-123")

    def test_generates_stable_legacy_message_id(self):
        message = {
            "role": "assistant",
            "content": '<message from="小项 🐎">\n你好呀\n</message>',
            "timestamp": "2026-03-31T10:41:49.796462",
            "metadata": {
                "agent_id": "main",
                "agent_name": "小项 🐎",
            },
        }

        first = ensure_history_message_id(message)
        second = ensure_history_message_id(dict(message))

        self.assertEqual(first, second)
        self.assertTrue(first.startswith("legacy-"))

    def test_legacy_id_uses_cleaned_content(self):
        wrapped = {
            "role": "assistant",
            "content": '<message from="小项 🐎">\n你好呀\n</message>',
            "timestamp": "2026-03-31T10:41:49.796462",
            "metadata": {"agent_id": "main"},
        }
        plain = {
            "role": "assistant",
            "content": "你好呀",
            "timestamp": "2026-03-31T10:41:49.796462",
            "metadata": {"agent_id": "main"},
        }

        self.assertEqual(
            ensure_history_message_id(wrapped),
            ensure_history_message_id(plain),
        )

    def test_merge_history_messages_prefers_more_complete_payload(self):
        shared_id = "msg-1"
        older = [{
            "id": shared_id,
            "role": "assistant",
            "content": "旧内容",
            "timestamp": "2026-04-08T10:00:00",
        }]
        richer = [{
            "id": shared_id,
            "role": "assistant",
            "content": "新内容",
            "timestamp": "2026-04-08T10:00:00",
            "files": [{"original_name": "demo.pdf"}],
            "execution_steps": [{"id": "step-1"}],
            "metadata": {"agent_id": "main", "agent_name": "小项 🐎"},
        }]

        merged = _merge_history_messages([older, richer])

        self.assertEqual(len(merged), 1)
        self.assertEqual(merged[0]["content"], "新内容")
        self.assertEqual(merged[0]["files"][0]["original_name"], "demo.pdf")
        self.assertEqual(merged[0]["execution_steps"][0]["id"], "step-1")
        self.assertEqual(merged[0]["metadata"]["agent_name"], "小项 🐎")

    def test_load_merged_session_messages_reads_legacy_and_current_agent_paths(self):
        session_key = "web:dm_main"

        with TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            legacy_manager = SessionManager(workspace=root / "workspace" / "sessions")
            current_manager = SessionManager(workspace=root / ".horbot-agent" / "sessions")

            legacy_session = legacy_manager.get_or_create(session_key)
            legacy_session.messages = [
                {
                    "id": "legacy-user",
                    "role": "user",
                    "content": "第一条消息",
                    "timestamp": "2026-04-08T10:00:00",
                },
                {
                    "id": "shared-assistant",
                    "role": "assistant",
                    "content": "旧助手回复",
                    "timestamp": "2026-04-08T10:00:01",
                },
            ]
            legacy_manager.save(legacy_session)

            current_session = current_manager.get_or_create(session_key)
            current_session.messages = [
                {
                    "id": "shared-assistant",
                    "role": "assistant",
                    "content": "补全后的助手回复",
                    "timestamp": "2026-04-08T10:00:01",
                    "metadata": {"agent_id": "main", "agent_name": "小项 🐎"},
                },
                {
                    "id": "current-user",
                    "role": "user",
                    "content": "第二条消息",
                    "timestamp": "2026-04-08T10:01:00",
                },
            ]
            current_manager.save(current_session)

            merged = _load_merged_session_messages(session_key, [legacy_manager, current_manager])

        self.assertEqual([message["id"] for message in merged], ["legacy-user", "shared-assistant", "current-user"])
        self.assertEqual(merged[1]["content"], "补全后的助手回复")
        self.assertEqual(merged[1]["metadata"]["agent_name"], "小项 🐎")


if __name__ == "__main__":
    unittest.main()
