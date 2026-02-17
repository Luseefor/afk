"""
MIT License
Copyright (c) 2026 arpan404
See LICENSE file for full license text.

This module provides the public API for the AFK memory subsystem, including models, stores, and utilities.
"""

from __future__ import annotations


from .types import JsonObject, JsonValue, LongTermMemory, MemoryEvent
from .utils import now_ms, new_id
from .adapters import (
    InMemoryMemoryStore,
    SQLiteMemoryStore,
    RedisMemoryStore,
    PostgresMemoryStore,
)
from .store import MemoryCapabilities, MemoryStore
from .vector import cosine_similarity
from .factory import create_memory_store_from_env
from .lifecycle import (
    MemoryCompactionResult,
    RetentionPolicy,
    StateRetentionPolicy,
    apply_event_retention,
    apply_state_retention,
    compact_thread_memory,
)


__all__ = [
    "JsonValue",
    "JsonObject",
    "MemoryEvent",
    "LongTermMemory",
    "now_ms",
    "new_id",
    "MemoryStore",
    "MemoryCapabilities",
    "cosine_similarity",
    "InMemoryMemoryStore",
    "SQLiteMemoryStore",
    "RedisMemoryStore",
    "PostgresMemoryStore",
    "create_memory_store_from_env",
    "RetentionPolicy",
    "StateRetentionPolicy",
    "MemoryCompactionResult",
    "apply_event_retention",
    "apply_state_retention",
    "compact_thread_memory",
]
