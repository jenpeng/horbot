"""Worktree isolation module for task-level directory isolation."""

from __future__ import annotations

import os
import shutil
import tempfile
from datetime import datetime
from pathlib import Path
from typing import Optional

from loguru import logger


class WorktreeManager:
    """Manages isolated work directories for parallel task execution.
    
    Each task gets its own isolated directory to prevent interference
    when multiple tasks run in parallel.
    
    Directory structure:
    .worktrees/
    ├── task_abc123/
    │   ├── src/
    │   ├── tests/
    │   └── ...
    └── task_def456/
        └── ...
    """
    
    DEFAULT_EXCLUDE = {
        ".git",
        "node_modules",
        "__pycache__",
        ".venv",
        "venv",
        ".env",
        ".worktrees",
        "dist",
        "build",
        "*.pyc",
        ".DS_Store",
        "Thumbs.db",
    }
    
    def __init__(
        self,
        base_dir: str | Path = ".worktrees",
        source_dir: str | Path | None = None,
        exclude: set[str] | None = None,
        auto_cleanup: bool = False,
    ):
        """Initialize WorktreeManager.
        
        Args:
            base_dir: Base directory for worktrees
            source_dir: Source directory to copy from (defaults to cwd)
            exclude: Set of patterns to exclude from copying
            auto_cleanup: Whether to auto-cleanup worktrees on task completion
        """
        self.base_dir = Path(base_dir)
        self.source_dir = Path(source_dir) if source_dir else Path.cwd()
        self.exclude = exclude or self.DEFAULT_EXCLUDE
        self.auto_cleanup = auto_cleanup
        self._active_worktrees: dict[str, Path] = {}
        
    def _ensure_base_dir(self) -> None:
        """Ensure base directory exists."""
        self.base_dir.mkdir(parents=True, exist_ok=True)
        
    def _should_exclude(self, path: Path) -> bool:
        """Check if path should be excluded from copying.
        
        Args:
            path: Path to check
            
        Returns:
            True if path should be excluded
        """
        name = path.name
        
        for pattern in self.exclude:
            if pattern.startswith("*"):
                if name.endswith(pattern[1:]):
                    return True
            elif name == pattern:
                return True
                
        return False
    
    def create_worktree(
        self,
        task_id: str,
        copy_source: bool = True,
        symlink_large_dirs: bool = True,
    ) -> Path:
        """Create an isolated work directory for a task.
        
        Args:
            task_id: Unique task identifier
            copy_source: Whether to copy source files
            symlink_large_dirs: Whether to symlink large directories instead of copying
            
        Returns:
            Path to the created worktree
        """
        worktree_path = self.base_dir / f"task_{task_id}"
        
        if worktree_path.exists():
            logger.warning(f"Worktree already exists: {worktree_path}")
            return worktree_path
            
        self._ensure_base_dir()
        worktree_path.mkdir(parents=True, exist_ok=True)
        
        if copy_source:
            self._copy_source(worktree_path, symlink_large_dirs)
        
        self._active_worktrees[task_id] = worktree_path
        
        logger.info(f"Created worktree for task {task_id}: {worktree_path}")
        return worktree_path
    
    def _copy_source(self, dest: Path, symlink_large_dirs: bool = True) -> None:
        """Copy source files to worktree.
        
        Args:
            dest: Destination path
            symlink_large_dirs: Whether to symlink large directories
        """
        large_dir_threshold = 100 * 1024 * 1024  # 100MB
        
        for item in self.source_dir.iterdir():
            if self._should_exclude(item):
                continue
                
            dest_item = dest / item.name
            
            try:
                if item.is_file():
                    shutil.copy2(item, dest_item)
                elif item.is_dir():
                    if symlink_large_dirs:
                        dir_size = sum(f.stat().st_size for f in item.rglob("*") if f.is_file())
                        if dir_size > large_dir_threshold:
                            dest_item.symlink_to(item)
                            logger.debug(f"Symlinked large directory: {item.name}")
                            continue
                    
                    shutil.copytree(
                        item,
                        dest_item,
                        ignore=shutil.ignore_patterns(*self.exclude),
                    )
            except Exception as e:
                logger.warning(f"Failed to copy {item}: {e}")
    
    def get_worktree(self, task_id: str) -> Path | None:
        """Get worktree path for a task.
        
        Args:
            task_id: Task identifier
            
        Returns:
            Path to worktree or None if not found
        """
        return self._active_worktrees.get(task_id)
    
    def list_worktrees(self) -> dict[str, Path]:
        """List all active worktrees.
        
        Returns:
            Dict of task_id -> worktree_path
        """
        result = {}
        if self.base_dir.exists():
            for item in self.base_dir.iterdir():
                if item.is_dir() and item.name.startswith("task_"):
                    task_id = item.name[5:]  # Remove "task_" prefix
                    result[task_id] = item
        return result
    
    def cleanup_worktree(self, task_id: str) -> bool:
        """Clean up a worktree.
        
        Args:
            task_id: Task identifier
            
        Returns:
            True if cleanup was successful
        """
        worktree_path = self._active_worktrees.pop(task_id, None)
        
        if worktree_path is None:
            worktree_path = self.base_dir / f"task_{task_id}"
            
        if not worktree_path.exists():
            logger.debug(f"Worktree does not exist: {worktree_path}")
            return False
            
        try:
            shutil.rmtree(worktree_path)
            logger.info(f"Cleaned up worktree for task {task_id}")
            return True
        except Exception as e:
            logger.error(f"Failed to cleanup worktree {task_id}: {e}")
            return False
    
    def cleanup_all(self) -> int:
        """Clean up all worktrees.
        
        Returns:
            Number of worktrees cleaned up
        """
        count = 0
        for task_id in list(self._active_worktrees.keys()):
            if self.cleanup_worktree(task_id):
                count += 1
        return count
    
    def get_worktree_info(self, task_id: str) -> dict | None:
        """Get information about a worktree.
        
        Args:
            task_id: Task identifier
            
        Returns:
            Dict with worktree info or None if not found
        """
        worktree_path = self.get_worktree(task_id)
        if worktree_path is None:
            return None
            
        stat = worktree_path.stat()
        return {
            "task_id": task_id,
            "path": str(worktree_path),
            "created": datetime.fromtimestamp(stat.st_ctime).isoformat(),
            "modified": datetime.fromtimestamp(stat.st_mtime).isoformat(),
        }
