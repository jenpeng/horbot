import os
import sys
import unittest
from unittest import mock

from horbot.agent.tools.mcp import resolve_stdio_command


class ResolveStdioCommandTests(unittest.TestCase):
    def test_prefers_current_interpreter_when_python_missing(self):
        with mock.patch("shutil.which", return_value=None):
            self.assertEqual(resolve_stdio_command("python"), sys.executable)

    def test_uses_resolved_python_binary_when_available(self):
        with mock.patch("shutil.which", return_value="/usr/local/bin/python3"):
            self.assertEqual(resolve_stdio_command("python3"), "/usr/local/bin/python3")

    def test_leaves_non_python_commands_unchanged(self):
        self.assertEqual(resolve_stdio_command("npx"), "npx")

    def test_handles_absolute_python_path(self):
        python_path = os.path.join(os.sep, "tmp", "venv", "bin", "python")
        with mock.patch("shutil.which", return_value=python_path):
            self.assertEqual(resolve_stdio_command(python_path), python_path)


if __name__ == "__main__":
    unittest.main()
