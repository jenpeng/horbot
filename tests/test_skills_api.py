import unittest
from io import BytesIO
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch
from zipfile import ZIP_DEFLATED, ZipFile

import httpx
from fastapi import FastAPI

from horbot.web.api import router as api_router


class SkillsApiTests(unittest.IsolatedAsyncioTestCase):
    async def test_get_skills_returns_missing_requirements_as_list_with_install_metadata(self):
        app = FastAPI()
        app.include_router(api_router, prefix="/api")
        transport = httpx.ASGITransport(app=app)

        with TemporaryDirectory() as tmpdir:
            workspace = Path(tmpdir)
            skill_dir = workspace / "skills" / "missing-ui-skill"
            skill_dir.mkdir(parents=True, exist_ok=True)
            (skill_dir / "SKILL.md").write_text(
                """---
name: missing-ui-skill
description: Skill with unmet CLI requirement
metadata: {"horbot":{"requires":{"bins":["definitely-missing-horbot-bin"]},"install":[{"id":"brew","kind":"brew","formula":"demo-cli","label":"Install demo CLI (brew)"}]}}
---

# Missing UI Skill
""",
                encoding="utf-8",
            )

            with patch("horbot.web.api._resolve_agent_workspace_for_request", return_value=(None, workspace)):
                async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
                    response = await client.get("/api/skills")

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        skill = next(item for item in payload["skills"] if item["name"] == "missing-ui-skill")
        self.assertFalse(skill["available"])
        self.assertEqual(skill["missing_requirements"], ["CLI: definitely-missing-horbot-bin"])
        self.assertEqual(skill["install"][0]["kind"], "brew")
        self.assertEqual(skill["install"][0]["formula"], "demo-cli")
        self.assertEqual(skill["compatibility"]["status"], "incompatible")

    async def test_create_skill_rejects_invalid_skill_content(self):
        app = FastAPI()
        app.include_router(api_router, prefix="/api")
        transport = httpx.ASGITransport(app=app)

        with TemporaryDirectory() as tmpdir:
            workspace = Path(tmpdir)
            with patch("horbot.web.api._resolve_agent_workspace_for_request", return_value=(None, workspace)):
                async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
                    response = await client.post(
                        "/api/skills",
                        json={"name": "broken-skill", "content": "# Missing frontmatter"},
                    )

        self.assertEqual(response.status_code, 400)
        self.assertIn("Skill validation failed", response.json()["detail"])

    async def test_import_skill_package_accepts_valid_skill_archive(self):
        app = FastAPI()
        app.include_router(api_router, prefix="/api")
        transport = httpx.ASGITransport(app=app)

        archive_buffer = BytesIO()
        with ZipFile(archive_buffer, "w", ZIP_DEFLATED) as archive:
            archive.writestr(
                "demo-skill/SKILL.md",
                """---
name: demo-skill
description: Demo packaged skill
metadata: {"horbot":{"requires":{"bins":["definitely-missing-horbot-bin"]}}}
---

# Demo Skill
""",
            )

        with TemporaryDirectory() as tmpdir:
            workspace = Path(tmpdir)
            with patch("horbot.web.api._resolve_agent_workspace_for_request", return_value=(None, workspace)):
                async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
                    response = await client.post(
                        "/api/skills/import",
                        files={"file": ("demo-skill.skill", archive_buffer.getvalue(), "application/zip")},
                    )

            self.assertTrue((workspace / "skills" / "demo-skill" / "SKILL.md").exists())

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["name"], "demo-skill")
        self.assertEqual(payload["compatibility"]["status"], "incompatible")

    async def test_import_skill_package_rejects_invalid_archive(self):
        app = FastAPI()
        app.include_router(api_router, prefix="/api")
        transport = httpx.ASGITransport(app=app)

        archive_buffer = BytesIO()
        with ZipFile(archive_buffer, "w", ZIP_DEFLATED) as archive:
            archive.writestr("notes/readme.md", "# Not a skill\n")

        with TemporaryDirectory() as tmpdir:
            workspace = Path(tmpdir)
            with patch("horbot.web.api._resolve_agent_workspace_for_request", return_value=(None, workspace)):
                async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
                    response = await client.post(
                        "/api/skills/import",
                        files={"file": ("broken.skill", archive_buffer.getvalue(), "application/zip")},
                    )

        self.assertEqual(response.status_code, 400)
        self.assertIn("Skill import failed", response.json()["detail"])


if __name__ == "__main__":
    unittest.main()
