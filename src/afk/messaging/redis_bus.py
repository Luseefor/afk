"""
MIT License
Copyright (c) 2026 socioy
See LICENSE file for full license text.

Redis-backed message bus for distributed agent-to-agent communication.
"""

from __future__ import annotations

import json
import time
from dataclasses import asdict
from typing import Any

from .types import AgentMailbox, AgentMessage, MessageBus


class RedisMessageBus(MessageBus):
    """
    Distributed message bus using Redis lists for persistent delivery.

    Each agent gets a Redis list (``afk:mailbox:{agent_name}``) and a
    Redis set tracks registered agents (``afk:agents``).

    Requires ``redis.asyncio`` (``pip install redis``).

    Args:
        redis: An ``redis.asyncio.Redis`` client instance.
        prefix: Key prefix for namespacing.
    """

    def __init__(self, redis: Any, *, prefix: str = "afk:messaging") -> None:
        self._redis = redis
        self._prefix = prefix

    def _agents_key(self) -> str:
        return f"{self._prefix}:agents"

    def _mailbox_key(self, agent_name: str) -> str:
        return f"{self._prefix}:mailbox:{agent_name}"

    def _serialize(self, msg: AgentMessage) -> str:
        """Serialize message to JSON string."""
        data = asdict(msg)
        return json.dumps(data, default=str)

    def _deserialize(self, raw: str | bytes) -> AgentMessage:
        """Deserialize JSON string to AgentMessage."""
        if isinstance(raw, bytes):
            raw = raw.decode("utf-8")
        data = json.loads(raw)
        return AgentMessage(**data)

    async def register(self, agent_name: str) -> AgentMailbox:
        """Register an agent in Redis and return its mailbox."""
        await self._redis.sadd(self._agents_key(), agent_name)
        return AgentMailbox(agent_name, self)

    async def unregister(self, agent_name: str) -> None:
        """Unregister agent and delete its mailbox."""
        await self._redis.srem(self._agents_key(), agent_name)
        await self._redis.delete(self._mailbox_key(agent_name))

    async def deliver(self, message: AgentMessage) -> None:
        """
        Push message to recipient's Redis list.

        Raises:
            KeyError: If recipient is not registered.
        """
        is_member = await self._redis.sismember(self._agents_key(), message.recipient)
        if not is_member:
            raise KeyError(f"Agent '{message.recipient}' is not registered")
        await self._redis.rpush(self._mailbox_key(message.recipient), self._serialize(message))

    async def broadcast(self, message: AgentMessage) -> None:
        """Push message to all registered agents except sender."""
        members = await self._redis.smembers(self._agents_key())
        for name in members:
            agent_name = name.decode("utf-8") if isinstance(name, bytes) else name
            if agent_name != message.sender:
                await self._redis.rpush(
                    self._mailbox_key(agent_name), self._serialize(message)
                )

    async def receive(self, agent_name: str, *, timeout: float | None = None) -> AgentMessage | None:
        """
        Block-pop next message from agent's Redis list.

        Uses ``BLPOP`` for efficient blocking.
        """
        key = self._mailbox_key(agent_name)
        wait = int(timeout) if timeout is not None else 0
        result = await self._redis.blpop(key, timeout=wait)
        if result is None:
            return None
        _, raw = result
        return self._deserialize(raw)

    async def peek(self, agent_name: str) -> list[AgentMessage]:
        """Return all pending messages without consuming them (LRANGE)."""
        key = self._mailbox_key(agent_name)
        items = await self._redis.lrange(key, 0, -1)
        return [self._deserialize(raw) for raw in items]

    async def message_count(self, agent_name: str) -> int:
        """Return length of agent's mailbox list."""
        return await self._redis.llen(self._mailbox_key(agent_name))
