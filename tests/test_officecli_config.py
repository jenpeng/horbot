import json
import os
import tempfile
import unittest
from pathlib import Path

from horbot.config.officecli import ensure_officecli_defaults, ensure_officecli_defaults_in_file, detect_officecli_command


class OfficeCliConfigTests(unittest.TestCase):
    def test_detect_officecli_command_falls_back_to_local_bin(self):
        with tempfile.TemporaryDirectory() as tempdir:
            home = Path(tempdir)
            officecli = home / ".local" / "bin" / "officecli"
            officecli.parent.mkdir(parents=True, exist_ok=True)
            officecli.write_text("#!/bin/sh\n", encoding="utf-8")
            officecli.chmod(0o755)

            detected = detect_officecli_command(path_env="", home=home)

            self.assertEqual(detected, str(officecli))

    def test_ensure_officecli_defaults_adds_mcp_server_and_exec_path(self):
        config = {
            "tools": {
                "exec": {
                    "timeout": 60,
                    "pathAppend": "",
                },
                "mcpServers": {},
            }
        }

        changed = ensure_officecli_defaults(
            config,
            officecli_command="/tmp/officecli",
            officecli_bin_dir="/tmp",
        )

        self.assertTrue(changed)
        self.assertEqual(config["tools"]["mcpServers"]["officecli"]["command"], "/tmp/officecli")
        self.assertEqual(config["tools"]["mcpServers"]["officecli"]["args"], ["mcp"])
        self.assertEqual(config["tools"]["mcpServers"]["officecli"]["toolTimeout"], 120)
        self.assertEqual(config["tools"]["exec"]["pathAppend"], "/tmp")

    def test_ensure_officecli_defaults_respects_existing_office_server_names(self):
        config = {
            "tools": {
                "mcpServers": {
                    "office-word": {
                        "command": "officecli",
                    }
                },
                "exec": {
                    "pathAppend": "/usr/local/bin",
                },
            }
        }

        changed = ensure_officecli_defaults(
            config,
            officecli_command="/tmp/officecli",
            officecli_bin_dir="/tmp",
        )

        self.assertTrue(changed)
        self.assertNotIn("officecli", config["tools"]["mcpServers"])
        self.assertEqual(config["tools"]["mcpServers"]["office-word"]["command"], "/tmp/officecli")
        self.assertEqual(config["tools"]["mcpServers"]["office-word"]["args"], ["mcp"])
        self.assertEqual(config["tools"]["mcpServers"]["office-word"]["toolTimeout"], 120)
        self.assertEqual(config["tools"]["exec"]["pathAppend"], os.pathsep.join(["/usr/local/bin", "/tmp"]))

    def test_ensure_officecli_defaults_upgrades_existing_generic_command(self):
        config = {
            "tools": {
                "mcpServers": {
                    "officecli": {
                        "command": "officecli",
                        "args": ["mcp"],
                        "env": {},
                    }
                },
                "exec": {},
            }
        }

        changed = ensure_officecli_defaults(
            config,
            officecli_command="/Users/test/.local/bin/officecli",
            officecli_bin_dir="/Users/test/.local/bin",
        )

        self.assertTrue(changed)
        self.assertEqual(
            config["tools"]["mcpServers"]["officecli"]["command"],
            "/Users/test/.local/bin/officecli",
        )
        self.assertEqual(
            config["tools"]["exec"]["pathAppend"],
            "/Users/test/.local/bin",
        )

    def test_ensure_officecli_defaults_in_file_persists_changes(self):
        with tempfile.TemporaryDirectory() as tempdir:
            config_path = Path(tempdir) / "config.json"
            config_path.write_text(json.dumps({"tools": {"mcpServers": {}, "exec": {}}}), encoding="utf-8")

            result = ensure_officecli_defaults_in_file(
                config_path,
                officecli_command="/opt/officecli",
                officecli_bin_dir="/opt",
            )

            self.assertTrue(result["changed"])
            saved = json.loads(config_path.read_text(encoding="utf-8"))
            self.assertEqual(saved["tools"]["mcpServers"]["officecli"]["command"], "/opt/officecli")
            self.assertEqual(saved["tools"]["exec"]["pathAppend"], "/opt")


if __name__ == "__main__":
    unittest.main()
