"""
MIT License
Copyright (c) 2026 arpan404
See LICENSE file for full license text.

Module: runtime/coalescing.py.
"""

from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable
from typing import TypeVar

T = TypeVar("T")


class RequestCoalescer:
    """Deduplicate identical in-flight requests."""

    def __init__(self) -> None:
        self._tasks: dict[str, asyncio.Task[T]] = {}
        self._lock = asyncio.Lock()

    async def run(self, key: str, factory: Callable[[], Awaitable[T]]) -> T:
        async with self._lock:
            existing = self._tasks.get(key)
            if existing is not None:
                return await existing

            task: asyncio.Task[T] = asyncio.create_task(factory())
            self._tasks[key] = task

        try:
            return await task
        finally:
            async with self._lock:
                self._tasks.pop(key, None)
