"""
MIT License
Copyright (c) 2026 socioy
See LICENSE file for full license text.

Agent-to-agent messaging types and protocols.
"""

from __future__ import annotations

import time
import uuid
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Literal

from ..llms.types import JSONValue

# ---------------------------------------------------------------------------
# Message types
# ---------------------------------------------------------------------------

MessagePriority = Literal["low", "normal", "high", "urgent"]


@dataclass(frozen=True, slots=True)
class AgentMessage:
    """
    A message sent between agents via the message bus.

    Attributes:
        id: Unique message identifier.
        sender: Name of the sending agent.
        recipient: Name of the target agent (or ``"*"`` for broadcast).
        content: Message payload (text or structured data).
        correlation_id: Optional ID linking request and reply messages.
        priority: Message priority level.
        timestamp: Unix timestamp when message was created.
        metadata: Optional JSON-safe metadata.
    """

    sender: str
    recipient: str
    content: str | JSONValue
    id: str = field(default_factory=lambda: uuid.uuid4().hex)
    correlation_id: str | None = None
    priority: MessagePriority = "normal"
    timestamp: float = field(default_factory=time.time)
    metadata: dict[str, JSONValue] = field(default_factory=dict)

    def reply(self, content: str | JSONValue, **kwargs: Any) -> "AgentMessage":
        """
        Create a reply message with sender/recipient swapped and
        correlation_id preserved.
        """
        return AgentMessage(
            sender=self.recipient,
            recipient=self.sender,
            content=content,
            correlation_id=self.correlation_id or self.id,
            **kwargs,
        )


# ---------------------------------------------------------------------------
# Mailbox protocol
# ---------------------------------------------------------------------------


class AgentMailbox:
    """
    Per-agent message inbox backed by the message bus.

    Provides send, receive, and peek operations for agent-to-agent messaging.
    """

    def __init__(self, agent_name: str, bus: "MessageBus") -> None:
        self._agent_name = agent_name
        self._bus = bus

    @property
    def agent_name(self) -> str:
        """Name of the agent this mailbox belongs to."""
        return self._agent_name

    async def send(self, recipient: str, content: str | JSONValue, **kwargs: Any) -> AgentMessage:
        """
        Send a message to another agent.

        Args:
            recipient: Target agent name.
            content: Message payload.
            **kwargs: Additional ``AgentMessage`` fields.

        Returns:
            The sent ``AgentMessage``.
        """
        msg = AgentMessage(
            sender=self._agent_name,
            recipient=recipient,
            content=content,
            **kwargs,
        )
        await self._bus.deliver(msg)
        return msg

    async def broadcast(self, content: str | JSONValue, **kwargs: Any) -> AgentMessage:
        """
        Broadcast a message to all registered agents.

        Args:
            content: Message payload.
            **kwargs: Additional ``AgentMessage`` fields.

        Returns:
            The broadcast ``AgentMessage``.
        """
        msg = AgentMessage(
            sender=self._agent_name,
            recipient="*",
            content=content,
            **kwargs,
        )
        await self._bus.broadcast(msg)
        return msg

    async def receive(self, timeout: float | None = None) -> AgentMessage | None:
        """
        Wait for and return the next message, or ``None`` on timeout.

        Args:
            timeout: Maximum seconds to wait. ``None`` = wait forever.
        """
        return await self._bus.receive(self._agent_name, timeout=timeout)

    async def peek(self) -> list[AgentMessage]:
        """Return all pending messages without consuming them."""
        return await self._bus.peek(self._agent_name)

    async def message_count(self) -> int:
        """Return the number of pending messages."""
        return await self._bus.message_count(self._agent_name)


# ---------------------------------------------------------------------------
# Message bus abstract base
# ---------------------------------------------------------------------------


class MessageBus(ABC):
    """
    Abstract message bus for agent-to-agent communication.

    Implementations provide the transport layer (in-memory, Redis, etc.).
    """

    @abstractmethod
    async def register(self, agent_name: str) -> AgentMailbox:
        """
        Register an agent and return its mailbox.

        Args:
            agent_name: Unique agent identifier.

        Returns:
            ``AgentMailbox`` bound to this bus.
        """
        ...

    @abstractmethod
    async def unregister(self, agent_name: str) -> None:
        """
        Unregister an agent and discard its pending messages.

        Args:
            agent_name: Agent to remove.
        """
        ...

    @abstractmethod
    async def deliver(self, message: AgentMessage) -> None:
        """
        Deliver a message to a specific recipient's mailbox.

        Args:
            message: Message to deliver.

        Raises:
            KeyError: If recipient is not registered.
        """
        ...

    @abstractmethod
    async def broadcast(self, message: AgentMessage) -> None:
        """
        Broadcast a message to all registered agents (except sender).

        Args:
            message: Message to broadcast.
        """
        ...

    @abstractmethod
    async def receive(self, agent_name: str, *, timeout: float | None = None) -> AgentMessage | None:
        """
        Wait for the next message for an agent.

        Args:
            agent_name: Target agent.
            timeout: Max wait time in seconds.

        Returns:
            Next message, or ``None`` on timeout.
        """
        ...

    @abstractmethod
    async def peek(self, agent_name: str) -> list[AgentMessage]:
        """Return pending messages without consuming them."""
        ...

    @abstractmethod
    async def message_count(self, agent_name: str) -> int:
        """Return number of pending messages for agent."""
        ...
