"""Safe file editing with backup, validation, and rollback support."""

import ast
import shutil
import logging
from datetime import datetime
from pathlib import Path
from typing import Any

from horbot.agent.tools.base import Tool
from horbot.utils.bootstrap import normalize_bootstrap_file_content, reconcile_bootstrap_files

logger = logging.getLogger(__name__)

PROTECTED_FILES = {
    "__init__.py",
    "main.py",
    "cli/commands.py",
    "agent/loop.py",
    "agent/tools/__init__.py",
}

BACKUP_DIR = Path("/tmp/horbot_backups")


def _get_backup_path(file_path: Path) -> Path:
    """Get backup path for a file."""
    BACKUP_DIR.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
    return BACKUP_DIR / f"{file_path.name}.{timestamp}.bak"


def _is_protected_file(file_path: Path, workspace: Path | None = None) -> bool:
    """Check if file is in the protected list."""
    try:
        if workspace:
            rel_path = file_path.relative_to(workspace)
            rel_str = str(rel_path)
            for protected in PROTECTED_FILES:
                if rel_str.endswith(protected) or protected in rel_str:
                    return True
    except ValueError:
        pass
    
    for protected in PROTECTED_FILES:
        if file_path.name == protected:
            return True
    
    return False


def _validate_python_syntax(content: str) -> tuple[bool, str]:
    """Validate Python syntax.
    
    Returns:
        Tuple of (is_valid, error_message)
    """
    try:
        ast.parse(content)
        return True, ""
    except SyntaxError as e:
        return False, f"Syntax error at line {e.lineno}: {e.msg}"


def _backup_file(file_path: Path) -> Path | None:
    """Create a backup of the file.
    
    Returns:
        Path to backup file, or None if backup failed.
    """
    try:
        backup_path = _get_backup_path(file_path)
        shutil.copy2(file_path, backup_path)
        logger.info(f"Created backup: {backup_path}")
        return backup_path
    except Exception as e:
        logger.error(f"Failed to create backup: {e}")
        return None


def _restore_from_backup(backup_path: Path, original_path: Path) -> bool:
    """Restore file from backup.
    
    Returns:
        True if restore succeeded, False otherwise.
    """
    try:
        shutil.copy2(backup_path, original_path)
        logger.info(f"Restored from backup: {backup_path} -> {original_path}")
        return True
    except Exception as e:
        logger.error(f"Failed to restore from backup: {e}")
        return False


def _normalize_after_bootstrap_write(file_path: Path, content: str) -> str:
    normalized_name = file_path.name.upper()
    if normalized_name == "SOUL.MD":
        return normalize_bootstrap_file_content(content, "soul")
    if normalized_name == "USER.MD":
        return normalize_bootstrap_file_content(content, "user")
    return content


def _reconcile_bootstrap_peer(workspace: Path | None, file_path: Path) -> None:
    if workspace is None:
        return
    normalized_name = file_path.name.upper()
    if normalized_name not in {"SOUL.MD", "USER.MD"}:
        return
    reconcile_bootstrap_files(workspace, updated_file=file_path.name)


class SafeWriteFileTool(Tool):
    """Tool to safely write content to a file with backup and validation."""

    def __init__(self, workspace: Path | None = None, allowed_dir: Path | None = None):
        self._workspace = workspace
        self._allowed_dir = allowed_dir

    @property
    def name(self) -> str:
        return "write_file"
    
    @property
    def description(self) -> str:
        return "Write content to a file with automatic backup and validation. Creates parent directories if needed."
    
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
        from horbot.agent.tools.filesystem import _resolve_path
        
        try:
            file_path = _resolve_path(path, self._workspace, self._allowed_dir)
            
            if _is_protected_file(file_path, self._workspace):
                return f"Error: Cannot modify protected file: {path}. This file is critical for system operation."
            
            if file_path.suffix == ".py":
                is_valid, error_msg = _validate_python_syntax(content)
                if not is_valid:
                    return f"Error: Invalid Python syntax. {error_msg}"
            
            if file_path.exists():
                backup_path = _backup_file(file_path)
                if not backup_path:
                    return f"Warning: Could not create backup, proceeding anyway."
            
            normalized_content = _normalize_after_bootstrap_write(file_path, content)
            file_path.parent.mkdir(parents=True, exist_ok=True)
            file_path.write_text(normalized_content, encoding="utf-8")
            _reconcile_bootstrap_peer(self._workspace, file_path)
            
            logger.info(f"Safely wrote {len(content)} bytes to {file_path}")
            return f"Successfully wrote {len(content)} bytes to {file_path}"
            
        except PermissionError as e:
            return f"Error: {e}"
        except Exception as e:
            logger.error(f"Error writing file: {e}")
            return f"Error writing file: {str(e)}"


class SafeEditFileTool(Tool):
    """Tool to safely edit a file with backup and validation."""

    def __init__(self, workspace: Path | None = None, allowed_dir: Path | None = None):
        self._workspace = workspace
        self._allowed_dir = allowed_dir

    @property
    def name(self) -> str:
        return "edit_file"
    
    @property
    def description(self) -> str:
        return "Edit a file by replacing old_text with new_text. Includes backup and validation."
    
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
        import difflib
        from horbot.agent.tools.filesystem import _resolve_path
        
        try:
            file_path = _resolve_path(path, self._workspace, self._allowed_dir)
            
            if not file_path.exists():
                return f"Error: File not found: {path}"
            
            if _is_protected_file(file_path, self._workspace):
                return f"Error: Cannot modify protected file: {path}. This file is critical for system operation."
            
            content = file_path.read_text(encoding="utf-8")
            
            if old_text not in content:
                return self._not_found_message(old_text, content, path)
            
            count = content.count(old_text)
            if count > 1:
                return f"Warning: old_text appears {count} times. Please provide more context to make it unique."
            
            new_content = content.replace(old_text, new_text, 1)
            
            if file_path.suffix == ".py":
                is_valid, error_msg = _validate_python_syntax(new_content)
                if not is_valid:
                    return f"Error: Invalid Python syntax after edit. {error_msg}"
            
            backup_path = _backup_file(file_path)
            if not backup_path:
                return f"Warning: Could not create backup, proceeding anyway."
            
            normalized_content = _normalize_after_bootstrap_write(file_path, new_content)
            file_path.write_text(normalized_content, encoding="utf-8")
            _reconcile_bootstrap_peer(self._workspace, file_path)
            
            logger.info(f"Safely edited {file_path}")
            return f"Successfully edited {file_path}"
            
        except PermissionError as e:
            return f"Error: {e}"
        except Exception as e:
            logger.error(f"Error editing file: {e}")
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
