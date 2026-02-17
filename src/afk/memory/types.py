"""
MIT License
Copyright (c) 2026 arpan404
See LICENSE file for full license text.

This module defines core data models and JSON helpers for the AFK memory subsystem.
"""

from __future__ import annotations


from dataclasses import dataclass, field
import time
from typing import TypeAlias, cast
from typing import List, Literal, Optional

EventType = Literal["tool_call", "tool_result", "message", "system", "trace"]
JsonPrimitive: TypeAlias = str | int | float | bool | None
JsonValue: TypeAlias = JsonPrimitive | list["JsonValue"] | dict[str, "JsonValue"]
JsonObject: TypeAlias = dict[str, JsonValue]


@dataclass(frozen=True, slots=True)
class MemoryEvent:
    """Represents an event in short-term memory for a specific conversation thread."""

    id: str
    thread_id: str
    user_id: Optional[str]
    type: EventType
    timestamp: int
    payload: JsonObject
    tags: List[str] = field(default_factory=list)


@dataclass(frozen=True, slots=True)
class LongTermMemory:
    """Represents a durable memory record for retrieval and personalization."""

    id: str
    user_id: Optional[str]
    scope: str  # e.g. "global", "org:123", "project:abc"
    data: JsonObject
    text: Optional[str] = None
    tags: List[str] = field(default_factory=list)
    metadata: JsonObject = field(default_factory=dict)
    created_at: int = field(default_factory=lambda: int(time.time() * 1000))
    updated_at: int = field(default_factory=lambda: int(time.time() * 1000))
