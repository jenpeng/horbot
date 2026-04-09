import tempfile
import unittest
from pathlib import Path

from horbot.agent.skill_metadata_adapter import parse_skill_metadata
from horbot.agent.skills import SkillsLoader


class SkillMetadataAdapterTests(unittest.TestCase):
    def test_parse_horbot_metadata_marks_canonical_source(self):
        metadata = parse_skill_metadata('{"horbot":{"enabled":"true","always":true,"emoji":"🐎"}}')

        self.assertEqual(metadata["enabled"], "true")
        self.assertTrue(metadata["always"])
        self.assertEqual(metadata["emoji"], "🐎")
        self.assertEqual(metadata["_compat"]["source_schema"], "horbot")
        self.assertEqual(metadata["_compat"]["source_schema_version"], 1)
        self.assertEqual(metadata["_compat"]["canonical_schema"], "horbot")
        self.assertEqual(metadata["_compat"]["canonical_schema_version"], 1)
        self.assertFalse(metadata["_compat"]["normalized_from_legacy"])

    def test_parse_openclaw_metadata_is_normalized_to_horbot_shape(self):
        metadata = parse_skill_metadata('{"openclaw":{"enabled":"false","requires":{"bins":["python3"]}}}')

        self.assertEqual(metadata["enabled"], "false")
        self.assertEqual(metadata["requires"], {"bins": ["python3"]})
        self.assertEqual(metadata["_compat"]["source_schema"], "openclaw")
        self.assertEqual(metadata["_compat"]["source_schema_version"], 1)
        self.assertEqual(metadata["_compat"]["canonical_schema"], "horbot")
        self.assertEqual(metadata["_compat"]["canonical_schema_version"], 1)
        self.assertTrue(metadata["_compat"]["normalized_from_legacy"])

    def test_parse_scoped_wrapper_preserves_declared_schema_version(self):
        metadata = parse_skill_metadata('{"schema":"openclaw","schema_version":3,"metadata":{"enabled":"true"}}')

        self.assertEqual(metadata["enabled"], "true")
        self.assertEqual(metadata["_compat"]["source_schema"], "openclaw")
        self.assertEqual(metadata["_compat"]["source_schema_version"], 3)
        self.assertTrue(metadata["_compat"]["normalized_from_legacy"])

    def test_parse_unscoped_metadata_is_supported_for_import_flows(self):
        metadata = parse_skill_metadata('{"always":true,"requires":{"env":["OPENAI_API_KEY"]}}')

        self.assertTrue(metadata["always"])
        self.assertEqual(metadata["_compat"]["source_schema"], "unscoped")
        self.assertIsNone(metadata["_compat"]["source_schema_version"])
        self.assertFalse(metadata["_compat"]["normalized_from_legacy"])

    def test_parse_invalid_metadata_returns_empty_dict(self):
        self.assertEqual(parse_skill_metadata('not-json'), {})
        self.assertEqual(parse_skill_metadata('[]'), {})

    def test_parse_install_metadata_is_preserved(self):
        metadata = parse_skill_metadata(
            '{"horbot":{"requires":{"bins":["gh"]},"install":[{"id":"brew","kind":"brew","formula":"gh","label":"Install GitHub CLI"}]}}'
        )

        self.assertEqual(metadata["install"][0]["kind"], "brew")
        self.assertEqual(metadata["install"][0]["formula"], "gh")


class SkillsLoaderCompatibilityTests(unittest.TestCase):
    def test_openclaw_metadata_still_controls_enabled_and_always_flags(self):
        with tempfile.TemporaryDirectory() as tempdir:
            workspace = Path(tempdir)
            skill_dir = workspace / 'skills' / 'legacy-skill'
            skill_dir.mkdir(parents=True, exist_ok=True)
            (skill_dir / 'SKILL.md').write_text(
                """---
description: Legacy skill
metadata: {"openclaw":{"enabled":"true","always":true}}
---

# Legacy Skill
""",
                encoding='utf-8',
            )

            loader = SkillsLoader(workspace=workspace, builtin_skills_dir=workspace / 'missing-builtin')

            listed = loader.list_skills(filter_unavailable=False)
            self.assertEqual([skill['name'] for skill in listed], ['legacy-skill'])
            self.assertEqual(loader.get_always_skills(), ['legacy-skill'])
            self.assertEqual(loader._get_skill_meta('legacy-skill')["_compat"]["source_schema"], 'openclaw')

    def test_openclaw_metadata_disabled_skill_stays_filtered(self):
        with tempfile.TemporaryDirectory() as tempdir:
            workspace = Path(tempdir)
            skill_dir = workspace / 'skills' / 'disabled-legacy'
            skill_dir.mkdir(parents=True, exist_ok=True)
            (skill_dir / 'SKILL.md').write_text(
                """---
description: Disabled legacy skill
metadata: {"openclaw":{"enabled":"false"}}
---

# Disabled Legacy Skill
""",
                encoding='utf-8',
            )

            loader = SkillsLoader(workspace=workspace, builtin_skills_dir=workspace / 'missing-builtin')

            self.assertEqual(loader.list_skills(filter_unavailable=False), [])
            skills_with_disabled = loader.list_skills(filter_unavailable=False, include_disabled=True)
            self.assertEqual(len(skills_with_disabled), 1)
            self.assertFalse(skills_with_disabled[0]['enabled'])

    def test_missing_requirements_returns_a_list_for_ui_rendering(self):
        loader = SkillsLoader(workspace=Path(tempfile.gettempdir()), builtin_skills_dir=Path(tempfile.gettempdir()) / 'missing-builtin')

        missing = loader._get_missing_requirements({
            "requires": {
                "bins": ["definitely-missing-horbot-bin"],
                "env": ["DEFINITELY_MISSING_HORBOT_ENV"],
            }
        })

        self.assertEqual(
            missing,
            ["CLI: definitely-missing-horbot-bin", "ENV: DEFINITELY_MISSING_HORBOT_ENV"],
        )


if __name__ == '__main__':
    unittest.main()
