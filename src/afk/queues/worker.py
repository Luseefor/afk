"""
MIT License
Copyright (c) 2026 arpan404
See LICENSE file for full license text.

Task worker — consumer loop that dequeues and executes agent tasks.
"""

from __future__ import annotations

import asyncio
import logging
import time
from dataclasses import dataclass, field
from typing import Any, Callable, Awaitable

from ..agents import BaseAgent
from ..llms.types import JSONValue
from .types import TaskItem, TaskQueue

logger = logging.getLogger("afk.queues.worker")

# Callback signature: called after each task completes or fails
TaskCallback = Callable[[TaskItem], Awaitable[None] | None]


@dataclass
class TaskWorkerConfig:
    """
    Configuration for the task worker.

    Attributes:
        poll_interval_s: Seconds between dequeue attempts when idle.
        max_concurrent_tasks: Maximum tasks executed concurrently.
        shutdown_timeout_s: Grace period for in-flight tasks on shutdown.
    """

    poll_interval_s: float = 1.0
    max_concurrent_tasks: int = 4
    shutdown_timeout_s: float = 30.0


class TaskWorker:
    """
    Consumer loop that dequeues tasks and executes them via a Runner.

    Usage::

        from afk.queues import InMemoryTaskQueue, TaskWorker

        queue = InMemoryTaskQueue()
        worker = TaskWorker(queue, agents={"greeter": my_agent})
        await worker.start()       # runs until shutdown
        await worker.shutdown()    # graceful stop

    Args:
        queue: Task queue to consume from.
        agents: Registry mapping agent_name → BaseAgent instances.
        runner_factory: Optional factory to create Runner instances.
        config: Worker configuration.
        on_complete: Optional callback invoked after task completion.
        on_failure: Optional callback invoked after task failure.
    """

    def __init__(
        self,
        queue: TaskQueue,
        *,
        agents: dict[str, BaseAgent],
        runner_factory: Callable[[], Any] | None = None,
        config: TaskWorkerConfig | None = None,
        on_complete: TaskCallback | None = None,
        on_failure: TaskCallback | None = None,
    ) -> None:
        self._queue = queue
        self._agents = agents
        self._runner_factory = runner_factory
        self._config = config or TaskWorkerConfig()
        self._on_complete = on_complete
        self._on_failure = on_failure
        self._running = False
        self._task: asyncio.Task[None] | None = None
        self._semaphore = asyncio.Semaphore(self._config.max_concurrent_tasks)
        self._active_tasks: set[asyncio.Task[None]] = set()

    async def start(self) -> None:
        """
        Start the worker loop.

        Runs until ``shutdown()`` is called. Dequeues tasks and executes
        them concurrently up to ``max_concurrent_tasks``.
        """
        self._running = True
        self._task = asyncio.create_task(self._loop())
        logger.info(
            "TaskWorker started (max_concurrent=%d, poll=%.1fs)",
            self._config.max_concurrent_tasks,
            self._config.poll_interval_s,
        )

    async def shutdown(self) -> None:
        """
        Gracefully shut down the worker.

        Waits for in-flight tasks up to ``shutdown_timeout_s``.
        """
        self._running = False
        if self._task and not self._task.done():
            self._task.cancel()
            try:
                await asyncio.wait_for(
                    self._task, timeout=self._config.shutdown_timeout_s
                )
            except (asyncio.CancelledError, asyncio.TimeoutError):
                pass

        # Wait for active tasks
        if self._active_tasks:
            logger.info("Waiting for %d active tasks...", len(self._active_tasks))
            done, pending = await asyncio.wait(
                self._active_tasks,
                timeout=self._config.shutdown_timeout_s,
            )
            for t in pending:
                t.cancel()

        logger.info("TaskWorker shut down")

    @property
    def is_running(self) -> bool:
        """Whether the worker loop is active."""
        return self._running

    @property
    def active_task_count(self) -> int:
        """Number of currently executing tasks."""
        return len(self._active_tasks)

    async def _loop(self) -> None:
        """Main consumer loop."""
        while self._running:
            try:
                await self._semaphore.acquire()
                task_item = await self._queue.dequeue(
                    timeout=self._config.poll_interval_s
                )
                if task_item is None:
                    self._semaphore.release()
                    continue

                # Spawn execution
                exec_task = asyncio.create_task(self._execute_task(task_item))
                self._active_tasks.add(exec_task)
                exec_task.add_done_callback(lambda t: self._task_done(t))
            except asyncio.CancelledError:
                self._semaphore.release()
                break
            except Exception:
                self._semaphore.release()
                logger.exception("Worker loop error")
                await asyncio.sleep(self._config.poll_interval_s)

    def _task_done(self, task: asyncio.Task[None]) -> None:
        """Cleanup callback when a task execution completes."""
        self._active_tasks.discard(task)
        self._semaphore.release()

    async def _execute_task(self, task_item: TaskItem) -> None:
        """Execute a single task item."""
        agent = self._agents.get(task_item.agent_name)
        if agent is None:
            error = f"Agent '{task_item.agent_name}' not found in registry"
            logger.error(error)
            await self._queue.fail(task_item.id, error=error)
            if self._on_failure:
                task_item.error = error
                await self._invoke_callback(self._on_failure, task_item)
            return

        try:
            # Create runner
            if self._runner_factory:
                runner = self._runner_factory()
            else:
                from ..core.runner import Runner
                runner = Runner()

            # Execute
            user_message = task_item.payload.get("user_message")
            context = task_item.payload.get("context")

            result = await runner.run(
                agent,
                user_message=str(user_message) if user_message else None,
                context=dict(context) if isinstance(context, dict) else None,
            )

            # Complete
            await self._queue.complete(
                task_item.id,
                result={"final_text": result.final_text, "state": result.state},
            )
            logger.info("Task %s completed (agent=%s)", task_item.id[:8], task_item.agent_name)
            if self._on_complete:
                task_item.status = "completed"
                await self._invoke_callback(self._on_complete, task_item)

        except Exception as exc:
            error = str(exc)
            logger.exception("Task %s failed: %s", task_item.id[:8], error)
            await self._queue.fail(task_item.id, error=error)
            if self._on_failure:
                task_item.error = error
                await self._invoke_callback(self._on_failure, task_item)

    async def _invoke_callback(self, cb: TaskCallback, item: TaskItem) -> None:
        """Invoke a callback, handling both sync and async signatures."""
        import inspect
        result = cb(item)
        if inspect.isawaitable(result):
            await result
