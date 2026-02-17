"""
MIT License
Copyright (c) 2026 arpan404
See LICENSE file for full license text.

Redis-backed persistent task queue.
"""

from __future__ import annotations

import json
import time
from dataclasses import asdict
from typing import Any

from ..llms.types import JSONValue
from .types import TaskItem, TaskQueue, TaskStatus


class RedisTaskQueue(TaskQueue):
    """
    Persistent task queue using Redis for durability across restarts.

    Uses:
    - Redis list (``{prefix}:pending``) for the FIFO queue
    - Redis hash (``{prefix}:tasks``) for task state tracking

    Requires ``redis.asyncio`` (``pip install redis``).

    Args:
        redis: An ``redis.asyncio.Redis`` client instance.
        prefix: Key prefix for namespacing.
    """

    def __init__(self, redis: Any, *, prefix: str = "afk:queue") -> None:
        self._redis = redis
        self._prefix = prefix

    def _pending_key(self) -> str:
        return f"{self._prefix}:pending"

    def _tasks_key(self) -> str:
        return f"{self._prefix}:tasks"

    def _serialize(self, task: TaskItem) -> str:
        data = asdict(task)
        return json.dumps(data, default=str)

    def _deserialize(self, raw: str | bytes) -> TaskItem:
        if isinstance(raw, bytes):
            raw = raw.decode("utf-8")
        data = json.loads(raw)
        return TaskItem(**data)

    async def enqueue(self, task: TaskItem) -> TaskItem:
        """Add task to Redis queue and hash."""
        task.status = "pending"
        await self._redis.hset(self._tasks_key(), task.id, self._serialize(task))
        await self._redis.rpush(self._pending_key(), task.id)
        return task

    async def dequeue(self, *, timeout: float | None = None) -> TaskItem | None:
        """
        Block-pop next task ID from pending list, then load from hash.

        Uses ``BLPOP`` for efficient blocking.
        """
        wait = int(timeout) if timeout is not None else 0
        result = await self._redis.blpop(self._pending_key(), timeout=wait)
        if result is None:
            return None

        _, task_id_raw = result
        task_id = (
            task_id_raw.decode("utf-8")
            if isinstance(task_id_raw, bytes)
            else task_id_raw
        )

        raw = await self._redis.hget(self._tasks_key(), task_id)
        if raw is None:
            return None

        task = self._deserialize(raw)
        if task.is_terminal:
            return None

        task.status = "running"
        task.started_at = time.time()
        await self._redis.hset(self._tasks_key(), task.id, self._serialize(task))
        return task

    async def complete(self, task_id: str, *, result: JSONValue | None = None) -> None:
        """Mark task completed in Redis hash."""
        raw = await self._redis.hget(self._tasks_key(), task_id)
        if raw is None:
            raise KeyError(f"Task '{task_id}' not found")
        task = self._deserialize(raw)
        task.status = "completed"
        task.result = result
        task.completed_at = time.time()
        await self._redis.hset(self._tasks_key(), task.id, self._serialize(task))

    async def fail(self, task_id: str, *, error: str) -> None:
        """Mark task failed or re-enqueue for retry."""
        raw = await self._redis.hget(self._tasks_key(), task_id)
        if raw is None:
            raise KeyError(f"Task '{task_id}' not found")
        task = self._deserialize(raw)
        task.retry_count += 1

        if task.retry_count < task.max_retries:
            task.status = "retrying"
            task.error = error
            task.started_at = None
            await self._redis.hset(self._tasks_key(), task.id, self._serialize(task))
            await self._redis.rpush(self._pending_key(), task.id)
        else:
            task.status = "failed"
            task.error = error
            task.completed_at = time.time()
            await self._redis.hset(self._tasks_key(), task.id, self._serialize(task))

    async def cancel(self, task_id: str) -> None:
        """Cancel a pending or running task."""
        raw = await self._redis.hget(self._tasks_key(), task_id)
        if raw is None:
            raise KeyError(f"Task '{task_id}' not found")
        task = self._deserialize(raw)
        if not task.is_terminal:
            task.status = "cancelled"
            task.completed_at = time.time()
            await self._redis.hset(self._tasks_key(), task.id, self._serialize(task))

    async def get(self, task_id: str) -> TaskItem | None:
        """Retrieve task by ID from Redis hash."""
        raw = await self._redis.hget(self._tasks_key(), task_id)
        if raw is None:
            return None
        return self._deserialize(raw)

    async def list_tasks(
        self,
        *,
        status: TaskStatus | None = None,
        limit: int = 100,
    ) -> list[TaskItem]:
        """List all tasks from Redis hash with optional status filter."""
        all_raw = await self._redis.hvals(self._tasks_key())
        tasks = [self._deserialize(r) for r in all_raw]
        if status is not None:
            tasks = [t for t in tasks if t.status == status]
        return tasks[:limit]
