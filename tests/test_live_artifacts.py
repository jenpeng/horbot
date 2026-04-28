import json
import time
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace
from unittest.mock import patch

import httpx
from fastapi import FastAPI

from horbot.web.api import router as api_router
from horbot.web.artifacts import (
    ArtifactValidationError,
    cleanup_expired_artifacts,
    get_runtime_artifacts_root,
    normalize_renderable_spec,
    render_artifact,
    resolve_runtime_artifact_file,
)


class LiveArtifactTests(unittest.IsolatedAsyncioTestCase):
    def test_runtime_root_is_project_level_horbot_runtime(self):
        with TemporaryDirectory() as tmpdir:
            workspace = Path(tmpdir) / ".horbot" / "agents" / "main" / "workspace"
            workspace.mkdir(parents=True)
            config = SimpleNamespace(workspace_path=str(workspace))

            with patch("horbot.web.artifacts.get_cached_config", return_value=config):
                root = get_runtime_artifacts_root()

            self.assertEqual(root, (Path(tmpdir) / ".horbot" / "runtime" / "rendered-artifacts").resolve())

    def test_render_artifact_writes_only_temporary_runtime_files(self):
        with TemporaryDirectory() as tmpdir:
            workspace = Path(tmpdir) / ".horbot" / "agents" / "main" / "workspace"
            workspace.mkdir(parents=True)
            config = SimpleNamespace(workspace_path=str(workspace))
            spec = {
                "title": "Smoke Dashboard",
                "summary": "A structured render smoke test.",
                "template": "dashboard",
                "items": [{"label": "Revenue", "value": "$1.2M"}],
                "points": [{"label": "Jan", "value": 12}],
            }

            with patch("horbot.web.artifacts.get_cached_config", return_value=config):
                result = render_artifact(spec, ttl_seconds=60)
                html_path = resolve_runtime_artifact_file(result["artifact_id"], "index.html")

            self.assertTrue(html_path.exists())
            self.assertIn("/.horbot/runtime/rendered-artifacts/", str(html_path))
            self.assertFalse((workspace.parent / "runtime").exists())
            self.assertEqual(result["template"], "dashboard")

    def test_rejects_unsupported_template(self):
        with self.assertRaises(ArtifactValidationError):
            normalize_renderable_spec({"title": "Unsafe", "template": "raw-html"})

    def test_cleanup_removes_expired_artifacts(self):
        with TemporaryDirectory() as tmpdir:
            workspace = Path(tmpdir) / ".horbot" / "agents" / "main" / "workspace"
            workspace.mkdir(parents=True)
            config = SimpleNamespace(workspace_path=str(workspace))

            with patch("horbot.web.artifacts.get_cached_config", return_value=config):
                result = render_artifact({"title": "Short", "template": "dashboard"}, ttl_seconds=60)
                manifest_path = get_runtime_artifacts_root() / result["artifact_id"] / "manifest.json"
                manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
                manifest["expires_at_epoch"] = time.time() - 1
                manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
                removed = cleanup_expired_artifacts()

            self.assertEqual(removed, 1)

    async def test_artifact_render_api_returns_runtime_url(self):
        app = FastAPI()
        app.include_router(api_router, prefix="/api")
        transport = httpx.ASGITransport(app=app)

        with TemporaryDirectory() as tmpdir:
            workspace = Path(tmpdir) / ".horbot" / "agents" / "main" / "workspace"
            workspace.mkdir(parents=True)
            config = SimpleNamespace(workspace_path=str(workspace))

            with patch("horbot.web.artifacts.get_cached_config", return_value=config):
                async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
                    response = await client.post(
                        "/api/artifacts/render",
                        json={
                            "ttl_seconds": 60,
                            "spec": {
                                "title": "API Dashboard",
                                "template": "dashboard",
                                "items": [{"label": "OK", "value": "1"}],
                            },
                        },
                    )

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["title"], "API Dashboard")
        self.assertTrue(payload["render_url"].startswith("/api/artifacts/runtime/"))
