from __future__ import annotations

"""
MIT License
Copyright (c) 2026 socioy
See LICENSE file for full license text.

Module defining middleware protocols and stack for LLM.
"""
from dataclasses import dataclass
from typing import Any, Awaitable, Callable, Dict, List, Optional, Protocol

from .types import LLMRequest, LLMResponse, EmbeddingResponse


LLMChatNext = Callable[[LLMRequest], Awaitable[LLMResponse]]
LLMEmbedNext = Callable[[Dict[str, Any]], Awaitable[EmbeddingResponse]]


class LLMChatMiddleware(Protocol):
    async def __call__(
        self, call_next: LLMChatNext, req: LLMRequest
    ) -> LLMResponse: ...


class LLMEmbedMiddleware(Protocol):
    async def __call__(
        self, call_next: LLMEmbedNext, req: Dict[str, Any]
    ) -> EmbeddingResponse: ...


@dataclass
class MiddlewareStack:
    chat: List[LLMChatMiddleware]
    embed: List[LLMEmbedMiddleware]

    def __init__(
        self,
        chat: Optional[List[LLMChatMiddleware]] = None,
        embed: Optional[List[LLMEmbedMiddleware]] = None,
    ) -> None:
        self.chat = chat or []
        self.embed = embed or []
