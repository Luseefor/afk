"""
MIT License
Copyright (c) 2026 arpan404
See LICENSE file for full license text.

Task queue types and abstract base.
"""

from __future__ import annotations

import time
import uuid
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Literal

from ..llms.types import JSONValue

# ---------------------------------------------------------------------------
# Task types
# ---------------------------------------------------------------------------

TaskStatus = Literal[
    "pending", "running", "completed", "failed", "retrying", "cancelled"
]


@dataclass(slots=True)
class TaskItem:
    """
    A unit of work in the task queue.

    Attributes:
        id: Unique task identifier.
        agent_name: Agent to execute this task.
        payload: Task input data (user_message, context, etc.).
        status: Current task lifecycle status.
        result: Task output after completion.
        error: Error message on failure.
        retry_count: Number of times this task has been retried.
        max_retries: Maximum allowed retries before permanent failure.
        created_at: Unix timestamp when task was enqueued.
        started_at: Unix timestamp when execution began.
        completed_at: Unix timestamp when task reached terminal state.
        metadata: Optional JSON-safe metadata.
    """

    agent_name: str
    payload: dict[str, JSONValue]
    id: str = field(default_factory=lambda: uuid.uuid4().hex)
    status: TaskStatus = "pending"
    result: JSONValue | None = None
    error: str | None = None
    retry_count: int = 0
    max_retries: int = 3
    created_at: float = field(default_factory=time.time)
    started_at: float | None = None
    completed_at: float | None = None
    metadata: dict[str, JSONValue] = field(default_factory=dict)

    @property
    def is_terminal(self) -> bool:
        """Whether the task has reached a terminal state."""
        return self.status in ("completed", "failed", "cancelled")

    @property
    def duration_s(self) -> float | None:
        """Execution duration in seconds, or None if not started/completed."""
        if self.started_at and self.completed_at:
            return self.completed_at - self.started_at
        return None


# ---------------------------------------------------------------------------
# Queue abstract base
# ---------------------------------------------------------------------------


class TaskQueue(ABC):
    """
    Abstract task queue for distributed agent work.

    Implementations provide the persistence layer (in-memory, Redis, etc.).
    """

    @abstractmethod
    async def enqueue(self, task: TaskItem) -> TaskItem:
        """
        Add a task to the queue.

        Args:
            task: Task to enqueue.

        Returns:
            The enqueued task (may have updated fields).
        """
        ...

    @abstractmethod
    async def dequeue(self, *, timeout: float | None = None) -> TaskItem | None:
        """
        Remove and return the next pending task.

        Args:
            timeout: Max seconds to wait. ``None`` = wait forever.

        Returns:
            Next task, or ``None`` on timeout.
        """
        ...

    @abstractmethod
    async def complete(self, task_id: str, *, result: JSONValue | None = None) -> None:
        """
        Mark a task as completed.

        Args:
            task_id: Task identifier.
            result: Optional result payload.
        """
        ...

    @abstractmethod
    async def fail(self, task_id: str, *, error: str) -> None:
        """
        Mark a task as failed.

        If retry_count < max_retries, the task is re-enqueued with status
        ``retrying``. Otherwise the task moves to ``failed``.

        Args:
            task_id: Task identifier.
            error: Error message.
        """
        ...

    @abstractmethod
    async def cancel(self, task_id: str) -> None:
        """
        Cancel a pending or running task.

        Args:
            task_id: Task identifier.
        """
        ...

    @abstractmethod
    async def get(self, task_id: str) -> TaskItem | None:
        """
        Retrieve a task by ID.

        Returns:
            Task item, or ``None`` if not found.
        """
        ...

    @abstractmethod
    async def list_tasks(
        self,
        *,
        status: TaskStatus | None = None,
        limit: int = 100,
    ) -> list[TaskItem]:
        """
        List tasks with optional status filter.

        Args:
            status: Filter by task status.
            limit: Max number of tasks to return.

        Returns:
            List of matching tasks.
        """
        ...

    async def enqueue_simple(
        self,
        agent_name: str,
        user_message: str,
        *,
        context: dict[str, JSONValue] | None = None,
        max_retries: int = 3,
        **metadata: JSONValue,
    ) -> TaskItem:
        """
        Convenience method to enqueue a task with just agent name and message.

        Args:
            agent_name: Agent to execute.
            user_message: User message to pass to agent.
            context: Optional run context.
            max_retries: Maximum retry attempts.
            **metadata: Additional metadata fields.
        """
        task = TaskItem(
            agent_name=agent_name,
            payload={"user_message": user_message, "context": context or {}},
            max_retries=max_retries,
            metadata=dict(metadata),
        )
        return await self.enqueue(task)
