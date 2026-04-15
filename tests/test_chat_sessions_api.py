import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import MagicMock, patch

import httpx
from fastapi import FastAPI

from horbot.session.manager import SessionManager
from horbot.web.api import get_chat_history, router as api_router


class ChatSessionsApiTests(unittest.IsolatedAsyncioTestCase):
    async def test_create_session_uses_requested_title(self):
        app = FastAPI()
        app.include_router(api_router, prefix="/api")
        transport = httpx.ASGITransport(app=app)

        with TemporaryDirectory() as tmpdir:
            manager = SessionManager(Path(tmpdir))
            with patch("horbot.web.api.get_session_manager", return_value=manager):
                async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
                    response = await client.post("/api/chat/sessions", json={"title": "Alpha Session"})

            self.assertEqual(response.status_code, 200)
            payload = response.json()
            self.assertEqual(payload["title"], "Alpha Session")

            session = manager.get(f"web:{payload['session_key']}")
            self.assertIsNotNone(session)
            self.assertEqual(session.title, "Alpha Session")
            self.assertEqual(session.metadata["title"], "Alpha Session")

    async def test_create_session_generates_unique_keys(self):
        app = FastAPI()
        app.include_router(api_router, prefix="/api")
        transport = httpx.ASGITransport(app=app)

        with TemporaryDirectory() as tmpdir:
            manager = SessionManager(Path(tmpdir))
            with patch("horbot.web.api.get_session_manager", return_value=manager):
                async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
                    first = await client.post("/api/chat/sessions")
                    second = await client.post("/api/chat/sessions")

            self.assertEqual(first.status_code, 200)
            self.assertEqual(second.status_code, 200)
            self.assertNotEqual(first.json()["session_key"], second.json()["session_key"])
            self.assertEqual(len(manager.list_sessions()), 2)

    async def test_list_sessions_uses_metadata_without_loading_full_session(self):
        app = FastAPI()
        app.include_router(api_router, prefix="/api")
        transport = httpx.ASGITransport(app=app)

        with TemporaryDirectory() as tmpdir:
            manager = SessionManager(Path(tmpdir))
            session = manager.get_or_create("web:session_a")
            session.add_message("user", "hello")
            session.add_message("assistant", "world")
            session.title = "Pinned Title"
            manager.save(session)
            manager.get = MagicMock(side_effect=AssertionError("full session load should not be needed"))

            with patch("horbot.web.api.get_session_manager", return_value=manager):
                async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
                    response = await client.get("/api/chat/sessions")

            self.assertEqual(response.status_code, 200)
            payload = response.json()
            self.assertEqual(len(payload["sessions"]), 1)
            self.assertEqual(payload["sessions"][0]["title"], "Pinned Title")
            self.assertEqual(payload["sessions"][0]["message_count"], 2)

    async def test_list_sessions_requests_web_prefix_filter(self):
        app = FastAPI()
        app.include_router(api_router, prefix="/api")
        transport = httpx.ASGITransport(app=app)

        with TemporaryDirectory() as tmpdir:
            manager = SessionManager(Path(tmpdir))

            web_session = manager.get_or_create("web:session_a")
            web_session.add_message("user", "hello")
            manager.save(web_session)

            agent_session = manager.get_or_create("agent:session_b")
            agent_session.add_message("user", "hidden")
            manager.save(agent_session)

            original_list_sessions = manager.list_sessions
            manager.list_sessions = MagicMock(side_effect=original_list_sessions)

            with patch("horbot.web.api.get_session_manager", return_value=manager):
                async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
                    response = await client.get("/api/chat/sessions")

            self.assertEqual(response.status_code, 200)
            manager.list_sessions.assert_called_once_with(key_prefix="web:")
            payload = response.json()
            self.assertEqual(len(payload["sessions"]), 1)
            self.assertEqual(payload["sessions"][0]["key"], "web:session_a")

    async def test_chat_history_promotes_remote_image_links_to_files(self):
        with TemporaryDirectory() as tmpdir:
            manager = SessionManager(Path(tmpdir))
            session = manager.get_or_create("web:session_case")
            session.add_message(
                "assistant",
                "彭老师，继续用“小马主题”给你生成了1张，见下图～\n\n1. https://image.pollinations.ai/prompt/pony?seed=1776249001",
            )
            manager.save(session)

            with patch("horbot.web.api.get_session_manager", return_value=manager):
                payload = await get_chat_history(session_key="web:session_case")

            self.assertEqual(len(payload["messages"]), 1)
            self.assertEqual(payload["messages"][0]["content"], "彭老师，继续用“小马主题”给你生成了1张，见下图～")
            self.assertEqual(len(payload["messages"][0]["files"]), 1)
            self.assertEqual(
                payload["messages"][0]["files"][0]["preview_url"],
                "https://image.pollinations.ai/prompt/pony?seed=1776249001",
            )
            self.assertEqual(
                payload["messages"][0]["files"][0]["filename"],
                "pony-theme-1776249001.jpg",
            )

    async def test_chat_history_prefers_cached_local_attachment_for_remote_image_links(self):
        with TemporaryDirectory() as tmpdir:
            manager = SessionManager(Path(tmpdir))
            session = manager.get_or_create("web:session_case")
            remote_url = "https://image.pollinations.ai/prompt/pony?seed=1776249001"
            session.add_message(
                "assistant",
                f"彭老师，继续用“小马主题”给你生成了1张，见下图～\n\n{remote_url}",
            )
            manager.save(session)

            cached_file = {
                "file_id": "remote-image-caed12c03f8f",
                "filename": "3f72c72e-3fb6-4d4f-987d-88f932f28159.jpg",
                "original_name": "pony-theme-1776249001.jpg",
                "mime_type": "image/jpeg",
                "size": 73728,
                "category": "image",
                "url": "/api/files/remote-image-caed12c03f8f",
                "preview_url": "/api/files/remote-image-caed12c03f8f/preview",
            }

            with (
                patch("horbot.web.api.get_session_manager", return_value=manager),
                patch("horbot.web.api._cache_remote_image_file", return_value=cached_file),
            ):
                payload = await get_chat_history(session_key="web:session_case")

            self.assertEqual(len(payload["messages"]), 1)
            self.assertEqual(payload["messages"][0]["files"][0]["preview_url"], cached_file["preview_url"])
            self.assertEqual(payload["messages"][0]["files"][0]["size"], 73728)

    async def test_remote_image_cache_status_and_clear(self):
        app = FastAPI()
        app.include_router(api_router, prefix="/api")
        transport = httpx.ASGITransport(app=app)

        with TemporaryDirectory() as tmpdir:
            upload_dir = Path(tmpdir)
            first = upload_dir / "remote-image-a1b2c3d4e5f6.jpg"
            first.write_bytes(b"a" * 1024)
            second = upload_dir / "remote-image-b1c2d3e4f5a6.jpg"
            second.write_bytes(b"b" * 2048)
            (upload_dir / "normal-file.txt").write_text("ignore", encoding="utf-8")

            with patch("horbot.web.api._get_upload_dir", return_value=upload_dir):
                async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
                    status_response = await client.get("/api/files/cache/remote-images")
                    clear_response = await client.delete("/api/files/cache/remote-images")
                    status_after_clear = await client.get("/api/files/cache/remote-images")

            self.assertEqual(status_response.status_code, 200)
            self.assertEqual(status_response.json()["count"], 2)
            self.assertEqual(status_response.json()["total_size_bytes"], 3072)

            self.assertEqual(clear_response.status_code, 200)
            self.assertEqual(clear_response.json()["deleted_count"], 2)
            self.assertEqual(clear_response.json()["deleted_size_bytes"], 3072)

            self.assertEqual(status_after_clear.status_code, 200)
            self.assertEqual(status_after_clear.json()["count"], 0)
            self.assertTrue((upload_dir / "normal-file.txt").exists())


if __name__ == "__main__":
    unittest.main()
