"""
MIT License
Copyright (c) 2026 arpan404
See LICENSE file for full license text.

Agent-to-agent messaging package.

Provides a ``MessageBus`` abstraction for peer-to-peer communication
between agents, with in-memory and Redis backends.

Quick start::

    from afk.messaging import InMemoryMessageBus

    bus = InMemoryMessageBus()
    mailbox_a = await bus.register("agent_a")
    mailbox_b = await bus.register("agent_b")

    await mailbox_a.send("agent_b", "Hello from A!")
    msg = await mailbox_b.receive()
    print(msg.content)  # "Hello from A!"
"""

from .bus import InMemoryMessageBus
from .types import AgentMailbox, AgentMessage, MessageBus, MessagePriority

__all__ = [
    "AgentMessage",
    "AgentMailbox",
    "MessageBus",
    "MessagePriority",
    "InMemoryMessageBus",
]


# Lazy import for Redis bus to avoid hard dependency
def __getattr__(name: str):
    if name == "RedisMessageBus":
        from .redis_bus import RedisMessageBus

        return RedisMessageBus
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
