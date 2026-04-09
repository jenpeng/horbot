import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import MagicMock, patch

import httpx
from fastapi import FastAPI

from horbot.session.manager import SessionManager
from horbot.web.api import router as api_router


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


if __name__ == "__main__":
    unittest.main()
