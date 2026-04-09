import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

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


if __name__ == "__main__":
    unittest.main()
