from __future__ import annotations

"""Demonstration script for AFK memory backends."""

import asyncio
import os
from pathlib import Path

import numpy as np

from src.afk.memory import (
    InMemoryMemoryStore,
    LongTermMemory,
    MemoryEvent,
    SQLiteMemoryStore,
    new_id,
    now_ms,
)
from src.afk.memory.store import MemoryStore


async def run_demo(store_name: str, store: MemoryStore) -> None:
    """Run a full read/write/search demo against one store backend."""
    thread_id = "thread_demo"
    user_id = "user_demo"

    print(f"\n=== {store_name} ===")
    async with store:
        await store.append_event(
            MemoryEvent(
                id=new_id("evt"),
                thread_id=thread_id,
                user_id=user_id,
                type="message",
                timestamp=now_ms(),
                payload={
                    "role": "user",
                    "content": "I like coffee and concise answers.",
                },
                tags=["chat", "preference"],
            ),
        )
        await store.append_event(
            MemoryEvent(
                id=new_id("evt"),
                thread_id=thread_id,
                user_id=user_id,
                type="tool_call",
                timestamp=now_ms(),
                payload={"tool": "calendar.lookup", "args": {"day": "Friday"}},
                tags=["tool"],
            ),
        )
        recent_events = await store.get_recent_events(thread_id, limit=10)
        print(f"events count: {len(recent_events)}")

        await store.put_state(thread_id, "session.locale", "en-US")
        await store.put_state(thread_id, "session.intent", "planning")
        state_snapshot = await store.list_state(thread_id, prefix="session.")
        print(f"state: {state_snapshot}")

        memory_one = LongTermMemory(
            id=new_id("ltm"),
            user_id=user_id,
            scope="global",
            text="User prefers coffee over tea in the morning.",
            data={"category": "preferences", "topic": "drink", "value": "coffee"},
            tags=["preference", "morning"],
            metadata={"source": "conversation"},
        )
        memory_two = LongTermMemory(
            id=new_id("ltm"),
            user_id=user_id,
            scope="project:roadmap",
            text="Project deadline moved to next Friday.",
            data={"category": "project", "deadline": "Friday"},
            tags=["project", "deadline"],
            metadata={"source": "meeting-notes"},
        )

        await store.upsert_long_term_memory(
            memory_one, embedding=np.array([0.9, 0.1, 0.0], dtype=np.float64)
        )
        await store.upsert_long_term_memory(
            memory_two, embedding=np.array([0.1, 0.8, 0.2], dtype=np.float64)
        )

        text_results = await store.search_long_term_memory_text(
            user_id, "coffee", limit=5
        )
        print(f"text search IDs: {[memory.id for memory in text_results]}")

        vector_results = await store.search_long_term_memory_vector(
            user_id,
            np.array([0.95, 0.05, 0.0], dtype=np.float64),
            limit=5,
        )
        vector_result_preview = [
            (memory.id, round(score, 4)) for memory, score in vector_results
        ]
        print(f"vector search: {vector_result_preview}")


def _sqlite_demo_store() -> SQLiteMemoryStore:
    database_path = Path(".data") / "afk_memory_demo.sqlite3"
    database_path.parent.mkdir(parents=True, exist_ok=True)
    return SQLiteMemoryStore(path=str(database_path))


def _redis_demo_store() -> MemoryStore | None:
    redis_url = os.getenv("AFK_REDIS_URL")
    if not redis_url:
        return None
    from src.afk.memory.store.redis import RedisMemoryStore

    return RedisMemoryStore(url=redis_url)


def _postgres_demo_store() -> MemoryStore | None:
    postgres_dsn = os.getenv("AFK_PG_DSN")
    vector_dim = os.getenv("AFK_VECTOR_DIM")
    if not postgres_dsn or not vector_dim:
        return None
    from src.afk.memory.store.postgres import PostgresMemoryStore

    return PostgresMemoryStore(dsn=postgres_dsn, vector_dim=int(vector_dim))


async def main() -> None:
    await run_demo("InMemoryMemoryStore", InMemoryMemoryStore())
    await run_demo("SQLiteMemoryStore", _sqlite_demo_store())

    redis_store = _redis_demo_store()
    if redis_store is not None:
        await run_demo("RedisMemoryStore", redis_store)
    else:
        print("\nSkipping Redis demo. Set AFK_REDIS_URL to enable it.")

    postgres_store = _postgres_demo_store()
    if postgres_store is not None:
        await run_demo("PostgresMemoryStore", postgres_store)
    else:
        print("Skipping Postgres demo. Set AFK_PG_DSN and AFK_VECTOR_DIM to enable it.")


if __name__ == "__main__":
    asyncio.run(main())
