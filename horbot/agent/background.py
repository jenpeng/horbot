"""Background task management with notification support."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Callable, Optional
import uuid

from loguru import logger


class TaskStatus(Enum):
    """Background task status."""
    
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


@dataclass
class BackgroundTask:
    """Represents a background task."""
    
    id: str
    name: str
    status: TaskStatus = TaskStatus.PENDING
    result: Any = None
    error: str | None = None
    created_at: datetime = field(default_factory=datetime.now)
    started_at: datetime | None = None
    completed_at: datetime | None = None
    progress: float = 0.0
    
    def to_dict(self) -> dict:
        """Convert to dictionary."""
        return {
            "id": self.id,
            "name": self.name,
            "status": self.status.value,
            "result": str(self.result)[:500] if self.result else None,
            "error": self.error,
            "created_at": self.created_at.isoformat(),
            "started_at": self.started_at.isoformat() if self.started_at else None,
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
            "progress": self.progress,
        }


@dataclass
class TaskNotification:
    """Notification about a background task."""
    
    task_id: str
    status: TaskStatus
    result: Any = None
    error: str | None = None
    timestamp: datetime = field(default_factory=datetime.now)
    
    def to_dict(self) -> dict:
        """Convert to dictionary."""
        return {
            "task_id": self.task_id,
            "status": self.status.value,
            "result": str(self.result)[:500] if self.result else None,
            "error": self.error,
            "timestamp": self.timestamp.isoformat(),
        }


class BackgroundNotifier:
    """Manages background tasks with async notification support.
    
    Features:
    - Run coroutines in background
    - Get notified when tasks complete
    - Track task status and progress
    - Support cancellation
    
    Example:
        notifier = BackgroundNotifier()
        
        # Start a background task
        task_id = await notifier.run_in_background(
            "my_task",
            my_async_function(arg1, arg2)
        )
        
        # Wait for notification
        notification = await notifier.wait_for_notification(timeout=60)
        
        # Or poll status
        status = notifier.get_task_status(task_id)
    """
    
    def __init__(self, max_concurrent: int = 10):
        """Initialize background notifier.
        
        Args:
            max_concurrent: Maximum concurrent background tasks
        """
        self.max_concurrent = max_concurrent
        self._tasks: dict[str, BackgroundTask] = {}
        self._asyncio_tasks: dict[str, asyncio.Task] = {}
        self._notify_queue: asyncio.Queue[TaskNotification] = asyncio.Queue()
        self._semaphore = asyncio.Semaphore(max_concurrent)
        self._progress_callbacks: dict[str, Callable[[float], None]] = {}
    
    async def run_in_background(
        self,
        name: str,
        coro: Any,
        on_progress: Callable[[float], None] | None = None,
    ) -> str:
        """Run a coroutine in the background.
        
        Args:
            name: Task name for identification
            coro: Coroutine to run
            on_progress: Optional progress callback
            
        Returns:
            Task ID
        """
        task_id = str(uuid.uuid4())[:8]
        
        bg_task = BackgroundTask(
            id=task_id,
            name=name,
            status=TaskStatus.PENDING,
        )
        self._tasks[task_id] = bg_task
        
        if on_progress:
            self._progress_callbacks[task_id] = on_progress
        
        async def wrapped_coro():
            async with self._semaphore:
                bg_task.status = TaskStatus.RUNNING
                bg_task.started_at = datetime.now()
                logger.info(f"Background task {task_id} ({name}) started")
                
                try:
                    result = await coro
                    bg_task.result = result
                    bg_task.status = TaskStatus.COMPLETED
                    bg_task.completed_at = datetime.now()
                    logger.info(f"Background task {task_id} ({name}) completed")
                    
                    await self._notify_queue.put(TaskNotification(
                        task_id=task_id,
                        status=TaskStatus.COMPLETED,
                        result=result,
                    ))
                    
                except asyncio.CancelledError:
                    bg_task.status = TaskStatus.CANCELLED
                    bg_task.completed_at = datetime.now()
                    logger.info(f"Background task {task_id} ({name}) cancelled")
                    
                    await self._notify_queue.put(TaskNotification(
                        task_id=task_id,
                        status=TaskStatus.CANCELLED,
                    ))
                    raise
                    
                except Exception as e:
                    bg_task.status = TaskStatus.FAILED
                    bg_task.error = str(e)
                    bg_task.completed_at = datetime.now()
                    logger.error(f"Background task {task_id} ({name}) failed: {e}")
                    
                    await self._notify_queue.put(TaskNotification(
                        task_id=task_id,
                        status=TaskStatus.FAILED,
                        error=str(e),
                    ))
        
        asyncio_task = asyncio.create_task(wrapped_coro())
        self._asyncio_tasks[task_id] = asyncio_task
        
        return task_id
    
    async def wait_for_notification(
        self,
        timeout: float | None = None,
    ) -> TaskNotification | None:
        """Wait for a task notification.
        
        Args:
            timeout: Timeout in seconds (None = wait forever)
            
        Returns:
            TaskNotification or None if timeout
        """
        try:
            if timeout:
                return await asyncio.wait_for(
                    self._notify_queue.get(),
                    timeout=timeout,
                )
            return await self._notify_queue.get()
        except asyncio.TimeoutError:
            return None
    
    def get_task(self, task_id: str) -> BackgroundTask | None:
        """Get task by ID.
        
        Args:
            task_id: Task identifier
            
        Returns:
            BackgroundTask or None
        """
        return self._tasks.get(task_id)
    
    def get_task_status(self, task_id: str) -> TaskStatus | None:
        """Get task status.
        
        Args:
            task_id: Task identifier
            
        Returns:
            TaskStatus or None
        """
        task = self._tasks.get(task_id)
        return task.status if task else None
    
    def list_tasks(
        self,
        status: TaskStatus | None = None,
    ) -> list[BackgroundTask]:
        """List tasks, optionally filtered by status.
        
        Args:
            status: Filter by status
            
        Returns:
            List of BackgroundTask
        """
        tasks = list(self._tasks.values())
        if status:
            tasks = [t for t in tasks if t.status == status]
        return tasks
    
    def update_progress(self, task_id: str, progress: float) -> bool:
        """Update task progress.
        
        Args:
            task_id: Task identifier
            progress: Progress value (0.0 to 1.0)
            
        Returns:
            True if successful
        """
        task = self._tasks.get(task_id)
        if not task:
            return False
        
        task.progress = max(0.0, min(1.0, progress))
        
        callback = self._progress_callbacks.get(task_id)
        if callback:
            try:
                callback(progress)
            except Exception as e:
                logger.warning(f"Progress callback failed for {task_id}: {e}")
        
        return True
    
    async def cancel_task(self, task_id: str) -> bool:
        """Cancel a running task.
        
        Args:
            task_id: Task identifier
            
        Returns:
            True if cancellation was initiated
        """
        asyncio_task = self._asyncio_tasks.get(task_id)
        if not asyncio_task:
            return False
        
        asyncio_task.cancel()
        return True
    
    async def wait_for_task(
        self,
        task_id: str,
        timeout: float | None = None,
    ) -> BackgroundTask | None:
        """Wait for a specific task to complete.
        
        Args:
            task_id: Task identifier
            timeout: Timeout in seconds
            
        Returns:
            BackgroundTask or None
        """
        asyncio_task = self._asyncio_tasks.get(task_id)
        if not asyncio_task:
            return None
        
        try:
            if timeout:
                await asyncio.wait_for(asyncio_task, timeout=timeout)
            else:
                await asyncio_task
        except asyncio.TimeoutError:
            return None
        except asyncio.CancelledError:
            pass
        
        return self._tasks.get(task_id)
    
    def get_summary(self) -> dict:
        """Get summary of all tasks.
        
        Returns:
            Dict with task counts
        """
        summary = {
            "total": len(self._tasks),
            "pending": 0,
            "running": 0,
            "completed": 0,
            "failed": 0,
            "cancelled": 0,
        }
        
        for task in self._tasks.values():
            if task.status.value in summary:
                summary[task.status.value] += 1
        
        return summary
    
    async def cleanup_completed(self, max_age_hours: float = 24) -> int:
        """Clean up completed tasks older than max_age.
        
        Args:
            max_age_hours: Maximum age in hours
            
        Returns:
            Number of tasks cleaned up
        """
        cutoff = datetime.now().timestamp() - (max_age_hours * 3600)
        to_remove = []
        
        for task_id, task in self._tasks.items():
            if task.status in (TaskStatus.COMPLETED, TaskStatus.FAILED, TaskStatus.CANCELLED):
                if task.completed_at and task.completed_at.timestamp() < cutoff:
                    to_remove.append(task_id)
        
        for task_id in to_remove:
            del self._tasks[task_id]
            self._asyncio_tasks.pop(task_id, None)
            self._progress_callbacks.pop(task_id, None)
        
        if to_remove:
            logger.info(f"Cleaned up {len(to_remove)} old tasks")
        
        return len(to_remove)
