"""
MIT License
Copyright (c) 2026 arpan404
See LICENSE file for full license text.

Persistent task queue package for distributed agent execution.

Provides a ``TaskQueue`` abstraction for enqueuing, dequeuing, and tracking
agent tasks with automatic retry, plus a ``TaskWorker`` consumer loop.

Quick start::

    from afk.queues import InMemoryTaskQueue, TaskWorker

    queue = InMemoryTaskQueue()
    await queue.enqueue_simple("greeter", "Hello!")

    worker = TaskWorker(queue, agents={"greeter": my_agent})
    await worker.start()
"""

from .memory import InMemoryTaskQueue
from .types import TaskItem, TaskQueue, TaskStatus
from .worker import TaskWorker, TaskWorkerConfig

__all__ = [
    "TaskItem",
    "TaskQueue",
    "TaskStatus",
    "InMemoryTaskQueue",
    "TaskWorker",
    "TaskWorkerConfig",
]


# Lazy import for Redis queue
def __getattr__(name: str):
    if name == "RedisTaskQueue":
        from .redis_queue import RedisTaskQueue

        return RedisTaskQueue
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
