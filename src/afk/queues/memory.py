"""
MIT License
Copyright (c) 2026 arpan404
See LICENSE file for full license text.

In-memory task queue implementation.
"""

from __future__ import annotations

import asyncio
import time
from typing import Any

from ..llms.types import JSONValue
from .types import TaskItem, TaskQueue, TaskStatus


class InMemoryTaskQueue(TaskQueue):
    """
    In-process task queue using ``asyncio.Queue`` and dict-based tracking.

    Suitable for single-process systems and testing. Tasks are lost on
    process restart.
    """

    def __init__(self) -> None:
        self._queue: asyncio.Queue[str] = asyncio.Queue()
        self._tasks: dict[str, TaskItem] = {}

    async def enqueue(self, task: TaskItem) -> TaskItem:
        """Add task to queue and tracking dict."""
        task.status = "pending"
        self._tasks[task.id] = task
        await self._queue.put(task.id)
        return task

    async def dequeue(self, *, timeout: float | None = None) -> TaskItem | None:
        """
        Wait for and return the next pending task.

        Skips tasks that have been cancelled/completed while in queue.
        """
        try:
            while True:
                if timeout is not None:
                    task_id = await asyncio.wait_for(self._queue.get(), timeout=timeout)
                else:
                    task_id = await self._queue.get()

                task = self._tasks.get(task_id)
                if task is None or task.is_terminal:
                    continue  # Skip cancelled/completed tasks

                task.status = "running"
                task.started_at = time.time()
                return task
        except asyncio.TimeoutError:
            return None

    async def complete(self, task_id: str, *, result: JSONValue | None = None) -> None:
        """Mark task as completed with optional result."""
        task = self._tasks.get(task_id)
        if task is None:
            raise KeyError(f"Task '{task_id}' not found")
        task.status = "completed"
        task.result = result
        task.completed_at = time.time()

    async def fail(self, task_id: str, *, error: str) -> None:
        """
        Mark task as failed or re-enqueue for retry.

        If retry_count < max_retries, re-enqueues with ``retrying`` status.
        """
        task = self._tasks.get(task_id)
        if task is None:
            raise KeyError(f"Task '{task_id}' not found")

        task.retry_count += 1
        if task.retry_count < task.max_retries:
            task.status = "retrying"
            task.error = error
            task.started_at = None
            await self._queue.put(task.id)
        else:
            task.status = "failed"
            task.error = error
            task.completed_at = time.time()

    async def cancel(self, task_id: str) -> None:
        """Cancel a task if it hasn't completed."""
        task = self._tasks.get(task_id)
        if task is None:
            raise KeyError(f"Task '{task_id}' not found")
        if not task.is_terminal:
            task.status = "cancelled"
            task.completed_at = time.time()

    async def get(self, task_id: str) -> TaskItem | None:
        """Retrieve task by ID."""
        return self._tasks.get(task_id)

    async def list_tasks(
        self,
        *,
        status: TaskStatus | None = None,
        limit: int = 100,
    ) -> list[TaskItem]:
        """List tasks with optional status filter."""
        items = list(self._tasks.values())
        if status is not None:
            items = [t for t in items if t.status == status]
        return items[:limit]

    @property
    def pending_count(self) -> int:
        """Number of tasks waiting in queue."""
        return self._queue.qsize()

    @property
    def total_count(self) -> int:
        """Total number of tracked tasks."""
        return len(self._tasks)
