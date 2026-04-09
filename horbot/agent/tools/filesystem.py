"""File system tools: read, write, edit."""

import difflib
from pathlib import Path
from typing import Any, Optional

from horbot.agent.tools.base import Tool, PermissionError as ToolPermissionError
from horbot.workspace.manager import WorkspaceManager, get_workspace_manager
from horbot.workspace.access_control import WorkspaceAccessControl, get_access_control


def _resolve_path(
    path: str,
    workspace: Path | None = None,
    allowed_dir: Path | None = None,
    agent_id: Optional[str] = None,
    team_ids: Optional[list[str]] = None,
) -> Path:
    """Resolve path against workspace context and enforce directory restriction.
    
    Args:
        path: The path to resolve
        workspace: Optional workspace root for relative paths (legacy)
        allowed_dir: Optional directory restriction (legacy)
        agent_id: Agent ID for workspace context
        team_ids: List of team IDs the agent belongs to
    
    Returns:
        Resolved absolute path
    """
    access_control = get_access_control()
    resolved = access_control.resolve_path_in_context(path, agent_id, team_ids)
    
    if allowed_dir:
        try:
            resolved.relative_to(allowed_dir.resolve())
        except ValueError:
            raise ToolPermissionError(f"Path {path} is outside allowed directory {allowed_dir}")
    
    return resolved


class ReadFileTool(Tool):
    """Tool to read file contents."""

    def __init__(
        self,
        workspace: Path | None = None,
        allowed_dir: Path | None = None,
        agent_id: Optional[str] = None,
        team_ids: Optional[list[str]] = None,
    ):
        self._workspace = workspace
        self._allowed_dir = allowed_dir
        self._agent_id = agent_id
        self._team_ids = team_ids

    @property
    def name(self) -> str:
        return "read_file"
    
    @property
    def description(self) -> str:
        return "Read the contents of a file at the given path."
    
    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "path": {
                    "type": "string",
                    "description": "The file path to read"
                }
            },
            "required": ["path"]
        }
    
    async def execute(self, path: str, **kwargs: Any) -> str:
        try:
            file_path = _resolve_path(
                path, self._workspace, self._allowed_dir, self._agent_id, self._team_ids
            )
            if not file_path.exists():
                return f"Error: File not found: {path}"
            if not file_path.is_file():
                return f"Error: Not a file: {path}"

            content = file_path.read_text(encoding="utf-8")
            return content
        except ToolPermissionError as e:
            return f"Error: {e}"
        except Exception as e:
            return f"Error reading file: {str(e)}"


class WriteFileTool(Tool):
    """Tool to write content to a file."""

    def __init__(
        self,
        workspace: Path | None = None,
        allowed_dir: Path | None = None,
        agent_id: Optional[str] = None,
        team_ids: Optional[list[str]] = None,
    ):
        self._workspace = workspace
        self._allowed_dir = allowed_dir
        self._agent_id = agent_id
        self._team_ids = team_ids

    @property
    def name(self) -> str:
        return "write_file"
    
    @property
    def description(self) -> str:
        return "Write content to a file at the given path. Creates parent directories if needed."
    
    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "path": {
                    "type": "string",
                    "description": "The file path to write to"
                },
                "content": {
                    "type": "string",
                    "description": "The content to write"
                }
            },
            "required": ["path", "content"]
        }
    
    async def execute(self, path: str, content: str, **kwargs: Any) -> str:
        try:
            file_path = _resolve_path(
                path, self._workspace, self._allowed_dir, self._agent_id, self._team_ids
            )
            file_path.parent.mkdir(parents=True, exist_ok=True)
            file_path.write_text(content, encoding="utf-8")
            return f"Successfully wrote {len(content)} bytes to {file_path}"
        except ToolPermissionError as e:
            return f"Error: {e}"
        except Exception as e:
            return f"Error writing file: {str(e)}"


class EditFileTool(Tool):
    """Tool to edit a file by replacing text."""

    def __init__(
        self,
        workspace: Path | None = None,
        allowed_dir: Path | None = None,
        agent_id: Optional[str] = None,
        team_ids: Optional[list[str]] = None,
    ):
        self._workspace = workspace
        self._allowed_dir = allowed_dir
        self._agent_id = agent_id
        self._team_ids = team_ids

    @property
    def name(self) -> str:
        return "edit_file"
    
    @property
    def description(self) -> str:
        return "Edit a file by replacing old_text with new_text. The old_text must exist exactly in the file."
    
    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "path": {
                    "type": "string",
                    "description": "The file path to edit"
                },
                "old_text": {
                    "type": "string",
                    "description": "The exact text to find and replace"
                },
                "new_text": {
                    "type": "string",
                    "description": "The text to replace with"
                }
            },
            "required": ["path", "old_text", "new_text"]
        }
    
    async def execute(self, path: str, old_text: str, new_text: str, **kwargs: Any) -> str:
        try:
            file_path = _resolve_path(
                path, self._workspace, self._allowed_dir, self._agent_id, self._team_ids
            )
            if not file_path.exists():
                return f"Error: File not found: {path}"

            content = file_path.read_text(encoding="utf-8")

            if old_text not in content:
                return self._not_found_message(old_text, content, path)

            count = content.count(old_text)
            if count > 1:
                return f"Warning: old_text appears {count} times. Please provide more context to make it unique."

            new_content = content.replace(old_text, new_text, 1)
            file_path.write_text(new_content, encoding="utf-8")

            return f"Successfully edited {file_path}"
        except ToolPermissionError as e:
            return f"Error: {e}"
        except Exception as e:
            return f"Error editing file: {str(e)}"

    @staticmethod
    def _not_found_message(old_text: str, content: str, path: str) -> str:
        """Build a helpful error when old_text is not found."""
        lines = content.splitlines(keepends=True)
        old_lines = old_text.splitlines(keepends=True)
        window = len(old_lines)

        best_ratio, best_start = 0.0, 0
        for i in range(max(1, len(lines) - window + 1)):
            ratio = difflib.SequenceMatcher(None, old_lines, lines[i : i + window]).ratio()
            if ratio > best_ratio:
                best_ratio, best_start = ratio, i

        if best_ratio > 0.5:
            diff = "\n".join(difflib.unified_diff(
                old_lines, lines[best_start : best_start + window],
                fromfile="old_text (provided)", tofile=f"{path} (actual, line {best_start + 1})",
                lineterm="",
            ))
            return f"Error: old_text not found in {path}.\nBest match ({best_ratio:.0%} similar) at line {best_start + 1}:\n{diff}"
        return f"Error: old_text not found in {path}. No similar text found. Verify the file content."


class ListDirTool(Tool):
    """Tool to list directory contents."""

    def __init__(
        self,
        workspace: Path | None = None,
        allowed_dir: Path | None = None,
        agent_id: Optional[str] = None,
        team_ids: Optional[list[str]] = None,
    ):
        self._workspace = workspace
        self._allowed_dir = allowed_dir
        self._agent_id = agent_id
        self._team_ids = team_ids

    @property
    def name(self) -> str:
        return "list_dir"
    
    @property
    def description(self) -> str:
        return "List the contents of a directory."
    
    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "path": {
                    "type": "string",
                    "description": "The directory path to list"
                }
            },
            "required": ["path"]
        }
    
    async def execute(self, path: str, **kwargs: Any) -> str:
        try:
            dir_path = _resolve_path(
                path, self._workspace, self._allowed_dir, self._agent_id, self._team_ids
            )
            if not dir_path.exists():
                return f"Error: Directory not found: {path}"
            if not dir_path.is_dir():
                return f"Error: Not a directory: {path}"

            items = []
            for item in sorted(dir_path.iterdir()):
                prefix = "📁 " if item.is_dir() else "📄 "
                items.append(f"{prefix}{item.name}")

            if not items:
                return f"Directory {path} is empty"

            return "\n".join(items)
        except ToolPermissionError as e:
            return f"Error: {e}"
        except Exception as e:
            return f"Error listing directory: {str(e)}"
