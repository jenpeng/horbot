import unittest
from io import BytesIO
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch
from zipfile import ZIP_DEFLATED, ZipFile

import httpx
from fastapi import FastAPI

from horbot.web.api import _describe_skill_source, router as api_router
from horbot.agent.skill_package import validate_skill_archive_bytes


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
        self.assertEqual(skill["source_group"], "custom")
        self.assertEqual(skill["source_origin_kind"], "manual")

    async def test_get_skills_marks_agent_generated_custom_skill_origin(self):
        app = FastAPI()
        app.include_router(api_router, prefix="/api")
        transport = httpx.ASGITransport(app=app)

        with TemporaryDirectory() as tmpdir:
            workspace = Path(tmpdir) / ".horbot" / "agents" / "main" / "workspace"
            skills_dir = workspace / ".horbot-agent" / "skills"
            skill_dir = skills_dir / "auto-demo-skill"
            skill_dir.mkdir(parents=True, exist_ok=True)
            (skill_dir / "SKILL.md").write_text(
                """---
name: auto-demo-skill
description: Agent generated demo skill
generated_by: skill-evolution
---

# Auto Demo Skill
""",
                encoding="utf-8",
            )

            with patch(
                "horbot.web.api._resolve_skill_dir_for_request",
                return_value=(None, workspace, skills_dir),
            ):
                async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
                    response = await client.get("/api/skills")

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        skill = next(item for item in payload["skills"] if item["name"] == "auto-demo-skill")
        self.assertEqual(skill["source_group"], "custom")
        self.assertEqual(skill["source_origin_kind"], "agent")
        self.assertEqual(skill["source_origin_agent_id"], "main")

    async def test_describe_skill_source_marks_relative_agent_generated_skill_origin(self):
        source = _describe_skill_source(
            skill={
                "source": "user",
                "path": ".horbot/agents/main/workspace/.horbot-agent/skills/auto-relative-demo/SKILL.md",
            },
            metadata={"generated_by": "skill-evolution"},
        )

        self.assertEqual(source["source_group"], "custom")
        self.assertEqual(source["source_origin_kind"], "agent")
        self.assertEqual(source["source_origin_agent_id"], "main")

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

    async def test_create_skill_uses_resolved_skill_directory(self):
        app = FastAPI()
        app.include_router(api_router, prefix="/api")
        transport = httpx.ASGITransport(app=app)

        with TemporaryDirectory() as tmpdir:
            workspace = Path(tmpdir) / "workspace"
            skills_dir = Path(tmpdir) / "agent-skills"
            skills_dir.mkdir(parents=True, exist_ok=True)

            with patch(
                "horbot.web.api._resolve_skill_dir_for_request",
                return_value=(None, workspace, skills_dir),
            ):
                async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
                    response = await client.post(
                        "/api/skills",
                        json={
                            "name": "demo-skill",
                            "content": "---\nname: demo-skill\ndescription: Demo skill\n---\n\n# Demo Skill\n",
                        },
                    )

            self.assertTrue((skills_dir / "demo-skill" / "SKILL.md").exists())
            self.assertFalse((workspace / "skills" / "demo-skill" / "SKILL.md").exists())
            self.assertTrue((workspace / ".horbot-agent" / "skill_graph.json").exists())

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["name"], "demo-skill")
        self.assertTrue(response.json()["skill_graph_refreshed"])

    async def test_get_skill_detail_includes_resolved_path(self):
        app = FastAPI()
        app.include_router(api_router, prefix="/api")
        transport = httpx.ASGITransport(app=app)

        with TemporaryDirectory() as tmpdir:
            workspace = Path(tmpdir) / "workspace"
            skills_dir = Path(tmpdir) / "agent-skills"
            skill_dir = skills_dir / "demo-skill"
            skill_dir.mkdir(parents=True, exist_ok=True)
            skill_file = skill_dir / "SKILL.md"
            skill_file.write_text(
                """---
name: demo-skill
description: Demo skill
---

# Demo Skill
""",
                encoding="utf-8",
            )

            with patch(
                "horbot.web.api._resolve_skill_dir_for_request",
                return_value=(None, workspace, skills_dir),
            ):
                async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
                    response = await client.get("/api/skills/demo-skill")

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["name"], "demo-skill")
        self.assertEqual(payload["path"], str(skill_file))
        self.assertEqual(payload["source"], "user")

    async def test_skill_graph_rebuild_persists_graph_with_reference_edges(self):
        app = FastAPI()
        app.include_router(api_router, prefix="/api")
        transport = httpx.ASGITransport(app=app)

        with TemporaryDirectory() as tmpdir:
            workspace = Path(tmpdir) / "workspace"
            skills_dir = Path(tmpdir) / "agent-skills"
            skill_dir = skills_dir / "auto-officecli-ppt"
            references_dir = skill_dir / "references"
            references_dir.mkdir(parents=True, exist_ok=True)
            (skill_dir / "SKILL.md").write_text(
                """---
name: auto-officecli-ppt
description: Reusable PowerPoint editing and layout repair workflows.
generated_by: skill-evolution
---

# OfficeCLI PPT

## Reference Library
- [Layout Repair](references/layout-repair.md)
""",
                encoding="utf-8",
            )
            (references_dir / "layout-repair.md").write_text(
                "# Layout Repair\n\nUse this when PPT text boxes overflow.\n",
                encoding="utf-8",
            )

            with patch(
                "horbot.web.api._resolve_skill_dir_for_request",
                return_value=(None, workspace, skills_dir),
            ):
                async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
                    rebuild_response = await client.post("/api/skills/graph/rebuild")
                    get_response = await client.get("/api/skills/graph")

            graph_path = workspace / ".horbot-agent" / "skill_graph.json"
            self.assertTrue(graph_path.exists())

        self.assertEqual(rebuild_response.status_code, 200)
        payload = rebuild_response.json()
        self.assertTrue(payload["persisted"])
        self.assertGreaterEqual(payload["node_count"], 2)
        self.assertIn("Rebuilt skill graph", payload["message"])
        edge_types = {edge["type"] for edge in payload["edges"]}
        self.assertIn("has_reference", edge_types)

        self.assertEqual(get_response.status_code, 200)
        self.assertTrue(get_response.json()["persisted"])

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

            self.assertTrue((workspace / ".horbot-agent" / "skills" / "demo-skill" / "SKILL.md").exists())
            self.assertTrue((workspace / ".horbot-agent" / "skill_graph.json").exists())

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["name"], "demo-skill")
        self.assertEqual(payload["compatibility"]["status"], "incompatible")
        self.assertTrue(payload["skill_graph_refreshed"])

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

    async def test_export_skill_package_returns_reimportable_skill_archive(self):
        app = FastAPI()
        app.include_router(api_router, prefix="/api")
        transport = httpx.ASGITransport(app=app)

        with TemporaryDirectory() as tmpdir:
            workspace = Path(tmpdir) / "workspace"
            skills_dir = Path(tmpdir) / "agent-skills"
            skill_dir = skills_dir / "demo-skill"
            references_dir = skill_dir / "references"
            references_dir.mkdir(parents=True, exist_ok=True)
            skill_file = skill_dir / "SKILL.md"
            skill_file.write_text(
                """---
name: demo-skill
description: Demo export skill
---

# Demo Skill

## Reference Library
- [Demo Reference](references/demo.md)
""",
                encoding="utf-8",
            )
            (references_dir / "demo.md").write_text("# Demo Reference\n\nReusable details.\n", encoding="utf-8")

            with patch(
                "horbot.web.api._resolve_skill_dir_for_request",
                return_value=(None, workspace, skills_dir),
            ):
                async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
                    response = await client.get("/api/skills/demo-skill/export")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.headers["content-type"], "application/zip")
        self.assertIn('filename="demo-skill.skill"', response.headers["content-disposition"])
        validation = validate_skill_archive_bytes(response.content, "demo-skill.skill")
        self.assertTrue(validation["valid"], validation["issues"])
        self.assertEqual(validation["skill_name"], "demo-skill")
        self.assertIn("references/demo.md", validation["files"])

    async def test_promote_skill_moves_user_skill_to_builtin_directory(self):
        app = FastAPI()
        app.include_router(api_router, prefix="/api")
        transport = httpx.ASGITransport(app=app)

        with TemporaryDirectory() as tmpdir:
            workspace = Path(tmpdir) / "workspace"
            skills_dir = Path(tmpdir) / "agent-skills"
            builtin_dir = Path(tmpdir) / "builtin-skills"
            skill_dir = skills_dir / "demo-skill"
            skill_dir.mkdir(parents=True, exist_ok=True)
            builtin_dir.mkdir(parents=True, exist_ok=True)
            skill_file = skill_dir / "SKILL.md"
            skill_file.write_text(
                """---
name: demo-skill
description: Demo skill
---

# Demo Skill
""",
                encoding="utf-8",
            )

            with patch(
                "horbot.web.api._resolve_skill_dir_for_request",
                return_value=(None, workspace, skills_dir),
            ), patch(
                "horbot.agent.skills.BUILTIN_SKILLS_DIR",
                builtin_dir,
            ):
                async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
                    response = await client.post("/api/skills/demo-skill/promote")

            builtin_skill = builtin_dir / "demo-skill" / "SKILL.md"
            self.assertFalse(skill_dir.exists())
            self.assertTrue(builtin_skill.exists())

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["name"], "demo-skill")
        self.assertEqual(payload["source"], "builtin")
        self.assertEqual(payload["path"], str(builtin_skill))

    async def test_consolidate_generated_skills_merges_related_families(self):
        app = FastAPI()
        app.include_router(api_router, prefix="/api")
        transport = httpx.ASGITransport(app=app)

        with TemporaryDirectory() as tmpdir:
            workspace = Path(tmpdir) / "workspace"
            skills_dir = Path(tmpdir) / "agent-skills"
            workspace.mkdir(parents=True, exist_ok=True)
            skills_dir.mkdir(parents=True, exist_ok=True)

            retry_dir = skills_dir / "auto-shell-retry-checklist"
            retry_dir.mkdir(parents=True, exist_ok=True)
            (retry_dir / "references").mkdir(parents=True, exist_ok=True)
            (retry_dir / "SKILL.md").write_text(
                """---
name: auto-shell-retry-checklist
description: Reusable shell troubleshooting checklists for command retries.
generated_by: skill-evolution
generated_at: 2026-04-26T00:00:00+00:00
metadata: {"horbot":{"enabled":true}}
---

# Shell Retry Checklist

Reusable shell troubleshooting checklists for command retries.

## Reference Library
- [Shell Retry Checklist](references/shell-retry-checklist.md)
""",
                encoding="utf-8",
            )
            (retry_dir / "references" / "shell-retry-checklist.md").write_text(
                "# Shell Retry Checklist\n\n1. Re-run the failing command with the same arguments.\n",
                encoding="utf-8",
            )

            timeout_dir = skills_dir / "auto-shell-timeout-diagnosis"
            timeout_dir.mkdir(parents=True, exist_ok=True)
            (timeout_dir / "references").mkdir(parents=True, exist_ok=True)
            (timeout_dir / "SKILL.md").write_text(
                """---
name: auto-shell-timeout-diagnosis
description: Reusable shell troubleshooting checklists for timeout diagnosis.
generated_by: skill-evolution
generated_at: 2026-04-26T00:00:00+00:00
metadata: {"horbot":{"enabled":true}}
---

# Shell Timeout Diagnosis

Reusable shell troubleshooting checklists for timeout diagnosis.

## Reference Library
- [Timeout Diagnosis Checklist](references/timeout-diagnosis.md)
""",
                encoding="utf-8",
            )
            (timeout_dir / "references" / "timeout-diagnosis.md").write_text(
                "# Timeout Diagnosis Checklist\n\n1. Confirm the timeout boundary before retrying.\n",
                encoding="utf-8",
            )

            with patch(
                "horbot.web.api._resolve_skill_dir_for_request",
                return_value=(None, workspace, skills_dir),
            ):
                async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
                    response = await client.post("/api/skills/consolidate-generated")

            self.assertEqual(response.status_code, 200)
            payload = response.json()
            self.assertEqual(payload["family_count_before"], 2)
            self.assertEqual(payload["family_count_after"], 1)
            self.assertEqual(payload["merged_skill_count"], 1)
            self.assertEqual(len(payload["updated_families"]), 1)

            existing_families = sorted(path.name for path in skills_dir.iterdir() if path.is_dir())
            self.assertEqual(len(existing_families), 1)
            target_family = existing_families[0]
            self.assertIn(
                target_family,
                {"auto-shell-retry-checklist", "auto-shell-timeout-diagnosis"},
            )

            target_skill = skills_dir / target_family / "SKILL.md"
            target_references = skills_dir / target_family / "references"
            self.assertTrue(target_skill.exists())
            self.assertTrue((target_references / "shell-retry-checklist.md").exists())
            self.assertTrue((target_references / "timeout-diagnosis.md").exists())
            self.assertIn("Consolidated 1 generated skills", payload["message"])


if __name__ == "__main__":
    unittest.main()
