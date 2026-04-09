import io
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from zipfile import ZIP_DEFLATED, ZipFile

from horbot.agent.skill_package import (
    build_skill_compatibility,
    import_skill_archive_bytes,
    validate_skill_archive_bytes,
    validate_skill_content,
)


def build_skill_archive(entries: dict[str, str]) -> bytes:
    buffer = io.BytesIO()
    with ZipFile(buffer, "w", ZIP_DEFLATED) as archive:
        for name, content in entries.items():
            archive.writestr(name, content)
    return buffer.getvalue()


class SkillPackageValidationTests(unittest.TestCase):
    def test_validate_skill_content_requires_frontmatter(self):
        result = validate_skill_content("# Missing frontmatter")

        self.assertFalse(result["valid"])
        self.assertIn("missing YAML frontmatter", result["issues"][0])

    def test_validate_skill_archive_accepts_standard_skill_package(self):
        payload = build_skill_archive(
            {
                "demo-skill/SKILL.md": """---
name: demo-skill
description: Demo packaged skill
---

# Demo Skill

See [Reference](references/guide.md)
""",
                "demo-skill/references/guide.md": "# Guide\n",
            }
        )

        result = validate_skill_archive_bytes(payload, "demo-skill.skill")

        self.assertTrue(result["valid"])
        self.assertEqual(result["skill_name"], "demo-skill")
        self.assertIn("references/guide.md", result["files"])

    def test_import_skill_archive_rejects_missing_skill_md(self):
        payload = build_skill_archive({"notes/readme.md": "# Not a skill\n"})

        result = validate_skill_archive_bytes(payload, "broken.skill")

        self.assertFalse(result["valid"])
        self.assertIn("does not contain a SKILL.md", result["issues"][0])

    def test_import_skill_archive_writes_files_to_workspace(self):
        payload = build_skill_archive(
            {
                "demo-skill/SKILL.md": """---
name: demo-skill
description: Demo packaged skill
metadata: {"horbot":{"requires":{"bins":["definitely-missing-horbot-bin"]}}}
---

# Demo Skill
""",
                "demo-skill/scripts/run.sh": "echo hi\n",
            }
        )

        with TemporaryDirectory() as tmpdir:
            result = import_skill_archive_bytes(
                payload,
                "demo-skill.skill",
                skills_dir=Path(tmpdir) / "skills",
            )

            self.assertTrue(result["valid"])
            skill_file = Path(tmpdir) / "skills" / "demo-skill" / "SKILL.md"
            self.assertTrue(skill_file.exists())

    def test_build_skill_compatibility_flags_missing_bins(self):
        compatibility = build_skill_compatibility(
            meta={"requires": {"bins": ["definitely-missing-horbot-bin"]}},
            normalized_from_legacy=True,
        )

        self.assertEqual(compatibility["status"], "incompatible")
        self.assertIn("Missing CLI dependency", compatibility["issues"][0])
        self.assertIn("legacy metadata", compatibility["warnings"][0])


if __name__ == "__main__":
    unittest.main()
