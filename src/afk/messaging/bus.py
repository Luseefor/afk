"""
MIT License
Copyright (c) 2026 arpan404
See LICENSE file for full license text.

In-memory message bus for agent-to-agent communication.
"""

from __future__ import annotations

import asyncio
from typing import Any

from .types import AgentMailbox, AgentMessage, MessageBus


class InMemoryMessageBus(MessageBus):
    """
    In-process message bus using ``asyncio.Queue`` per agent.

    Suitable for single-process multi-agent systems and testing.
    Messages are not persisted — they are lost if the process exits.
    """

    def __init__(self) -> None:
        self._queues: dict[str, asyncio.Queue[AgentMessage]] = {}
        self._pending_snapshots: dict[str, list[AgentMessage]] = {}

    async def register(self, agent_name: str) -> AgentMailbox:
        """
        Register an agent with a new in-memory queue.

        Args:
            agent_name: Unique agent identifier.

        Returns:
            Mailbox bound to this bus.

        Raises:
            ValueError: If agent is already registered.
        """
        if agent_name in self._queues:
            raise ValueError(f"Agent '{agent_name}' is already registered")
        self._queues[agent_name] = asyncio.Queue()
        self._pending_snapshots[agent_name] = []
        return AgentMailbox(agent_name, self)

    async def unregister(self, agent_name: str) -> None:
        """Remove agent and discard its queue."""
        self._queues.pop(agent_name, None)
        self._pending_snapshots.pop(agent_name, None)

    async def deliver(self, message: AgentMessage) -> None:
        """
        Deliver message to recipient's queue.

        Raises:
            KeyError: If recipient is not registered.
        """
        queue = self._queues.get(message.recipient)
        if queue is None:
            raise KeyError(f"Agent '{message.recipient}' is not registered")
        await queue.put(message)
        self._pending_snapshots[message.recipient].append(message)

    async def broadcast(self, message: AgentMessage) -> None:
        """Deliver message to all registered agents except the sender."""
        for name, queue in self._queues.items():
            if name != message.sender:
                await queue.put(message)
                self._pending_snapshots[name].append(message)

    async def receive(self, agent_name: str, *, timeout: float | None = None) -> AgentMessage | None:
        """
        Wait for next message with optional timeout.

        Returns:
            Message or ``None`` on timeout.
        """
        queue = self._queues.get(agent_name)
        if queue is None:
            raise KeyError(f"Agent '{agent_name}' is not registered")
        try:
            if timeout is not None:
                msg = await asyncio.wait_for(queue.get(), timeout=timeout)
            else:
                msg = await queue.get()
            # Remove from pending snapshot
            pending = self._pending_snapshots.get(agent_name, [])
            if msg in pending:
                pending.remove(msg)
            return msg
        except asyncio.TimeoutError:
            return None

    async def peek(self, agent_name: str) -> list[AgentMessage]:
        """Return list of pending messages without consuming them."""
        return list(self._pending_snapshots.get(agent_name, []))

    async def message_count(self, agent_name: str) -> int:
        """Return number of pending messages."""
        queue = self._queues.get(agent_name)
        return queue.qsize() if queue else 0

    @property
    def registered_agents(self) -> list[str]:
        """List of currently registered agent names."""
        return list(self._queues.keys())
