import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from horbot.cli.commands import _create_workspace_templates


class CliWorkspaceTemplateTests(unittest.TestCase):
    def test_create_workspace_templates_uses_canonical_agent_metadata_dirs(self):
        with tempfile.TemporaryDirectory() as tempdir:
            workspace = Path(tempdir) / "workspace"
            workspace.mkdir(parents=True, exist_ok=True)

            with patch("horbot.cli.commands.console.print"):
                _create_workspace_templates(workspace)

            metadata_root = workspace / ".horbot-agent"
            self.assertTrue((metadata_root / "memory" / "MEMORY.md").exists())
            self.assertTrue((metadata_root / "memory" / "HISTORY.md").exists())
            self.assertTrue((metadata_root / "skills").exists())
            self.assertFalse((workspace / "memory").exists())
            self.assertFalse((workspace / "skills").exists())


if __name__ == "__main__":
    unittest.main()
