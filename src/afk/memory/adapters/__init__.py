"""
MIT License
Copyright (c) 2026 arpan404
See LICENSE file for full license text.

This module provides memory store adapters for the AFK memory subsystem.
"""

from __future__ import annotations

from .in_memory import InMemoryMemoryStore
from .sqlite import SQLiteMemoryStore


__all__ = [
    "InMemoryMemoryStore",
    "SQLiteMemoryStore",
]

try:
    from .redis import RedisMemoryStore
except ModuleNotFoundError:  # optional dependency: redis
    pass
else:
    __all__.append("RedisMemoryStore")

try:
    from .postgres import PostgresMemoryStore
except ModuleNotFoundError:  # optional dependency: asyncpg
    pass
else:
    __all__.append("PostgresMemoryStore")
