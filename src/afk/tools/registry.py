from __future__ import annotations
"""
MIT License
Copyright (c) 2026 socioy
See LICENSE file for full license text.

This module implements the ToolRegistry for AFK.
It supports registering sync/async tools (tools are executed async via BaseTool/Tool),
optional entry-point plugin discovery, concurrency limiting, allow/deny policies,
and exporting tool specs to LLM tool-calling formats.
"""

import asyncio
import time
from dataclasses import dataclass
from typing import Any, Callable, Dict, Iterable, List, Optional, Sequence

try:
    # Python 3.10+
    from importlib import metadata as importlib_metadata
except Exception:  # pragma: no cover
    import importlib_metadata  # type: ignore

from .base import Tool, ToolContext, ToolResult, ToolSpec 
from .errors import (
    ToolAlreadyRegisteredError,
    ToolNotFoundError,
    ToolPolicyError,
    ToolTimeoutError,
)


ToolPolicy = Callable[[str, Dict[str, Any], ToolContext], None]
# Policy should raise ToolPolicyError (or any Exception) to block execution.


@dataclass(frozen=True, slots=True)
class ToolCallRecord:
    tool_name: str
    started_at_s: float
    ended_at_s: float
    ok: bool
    error: Optional[str] = None
    tool_call_id: Optional[str] = None


class ToolRegistry:
    """
    Stores tools by name and provides safe async execution with:
      - concurrency limiting
      - registry-level default timeout
      - optional policy hook
      - optional plugin discovery via entry points
      - tool spec export for LLM tool-calling
    """

    def __init__(
        self,
        *,
        max_concurrency: int = 32,
        default_timeout: float | None = None,
        policy: ToolPolicy | None = None,
        enable_plugins: bool = False,
        plugin_entry_point_group: str = "afk.tools",
        allow_overwrite_plugins: bool = False,
    ) -> None:
        if max_concurrency < 1:
            raise ValueError("max_concurrency must be >= 1")

        self._tools: Dict[str, Tool[Any, Any]] = {}
        self._sem = asyncio.Semaphore(max_concurrency)
        self._default_timeout = default_timeout
        self._policy = policy
        self._records: List[ToolCallRecord] = []

        if enable_plugins:
            self.load_plugins(
                entry_point_group=plugin_entry_point_group,
                overwrite=allow_overwrite_plugins,
            )

    # ''''''''''''''''''''''''
    # Registration / discovery
    # ''''''''''''''''''''''''

    def register(self, tool: Tool[Any, Any], *, overwrite: bool = False) -> None:
        name = tool.spec.name
        if not overwrite and name in self._tools:
            raise ToolAlreadyRegisteredError(f"Tool already registered: {name}")
        self._tools[name] = tool

    def register_many(self, tools: Iterable[Tool[Any, Any]], *, overwrite: bool = False) -> None:
        for t in tools:
            self.register(t, overwrite=overwrite)

    def unregister(self, name: str) -> None:
        self._tools.pop(name, None)

    def get(self, name: str) -> Tool[Any, Any]:
        try:
            return self._tools[name]
        except KeyError as e:
            raise ToolNotFoundError(f"Unknown tool: {name}") from e

    def list(self) -> List[Tool[Any, Any]]:
        return list(self._tools.values())

    def names(self) -> List[str]:
        return list(self._tools.keys())

    def has(self, name: str) -> bool:
        return name in self._tools

    def load_plugins(self, *, entry_point_group: str = "afk.tools", overwrite: bool = False) -> int:
        """
        Load Tool objects (or factories returning Tool) from Python entry points.

        Plugin pyproject.toml example:
          [project.entry-points."afk.tools"]
          my_tool = "my_pkg.tools:my_tool"  # Tool instance OR factory returning Tool

        Returns number of tools loaded.
        """
        eps = importlib_metadata.entry_points()
        group = eps.select(group=entry_point_group)

        loaded = 0
        for ep in group:
            obj = ep.load()

            tool_obj: Tool[Any, Any] | None = None
            if isinstance(obj, Tool):
                tool_obj = obj
            elif callable(obj):
                maybe = obj()
                if isinstance(maybe, Tool):
                    tool_obj = maybe

            if tool_obj is None:
                # Skip invalid plugin; you can choose to raise instead.
                continue

            self.register(tool_obj, overwrite=overwrite)
            loaded += 1

        return loaded

    # '''''''''
    # Execution
    # '''''''''

    async def call(
        self,
        name: str,
        raw_args: Dict[str, Any],
        *,
        ctx: ToolContext | None = None,
        timeout: float | None = None,
        tool_call_id: str | None = None,
    ) -> ToolResult[Any]:
        """
        Execute a registered tool by name.

        Timeout precedence:
          1) call(timeout=...)
          2) tool.default_timeout (Tool.default_timeout)
          3) registry default_timeout
        """
        tool = self.get(name)
        ctx = ctx or ToolContext()

        # Policy hook (permissions/budget/allowlist)
        if self._policy is not None:
            try:
                self._policy(name, raw_args, ctx)
            except ToolPolicyError:
                raise
            except Exception as e:
                raise ToolPolicyError(str(e)) from e

        started = time.time()

        async with self._sem:
            effective_timeout = (
                timeout
                if timeout is not None
                else (tool.default_timeout if tool.default_timeout is not None else self._default_timeout)
            )

            try:
                if effective_timeout is not None:
                    try:
                        res = await asyncio.wait_for(
                            tool.call(raw_args, ctx=ctx, timeout=None, tool_call_id=tool_call_id),
                            timeout=effective_timeout,
                        )
                    except asyncio.TimeoutError as e:
                        self._records.append(
                            ToolCallRecord(
                                tool_name=name,
                                started_at_s=started,
                                ended_at_s=time.time(),
                                ok=False,
                                error="timeout",
                                tool_call_id=tool_call_id,
                            )
                        )
                        raise ToolTimeoutError(
                            f"Tool '{name}' timed out after {effective_timeout} seconds."
                        ) from e
                else:
                    res = await tool.call(raw_args, ctx=ctx, timeout=None, tool_call_id=tool_call_id)

                self._records.append(
                    ToolCallRecord(
                        tool_name=name,
                        started_at_s=started,
                        ended_at_s=time.time(),
                        ok=res.success,
                        error=res.error_message,
                        tool_call_id=tool_call_id,
                    )
                )
                return res

            except Exception as e:
                self._records.append(
                    ToolCallRecord(
                        tool_name=name,
                        started_at_s=started,
                        ended_at_s=time.time(),
                        ok=False,
                        error=str(e),
                        tool_call_id=tool_call_id,
                    )
                )
                raise

    async def call_many(
        self,
        calls: Sequence[tuple[str, Dict[str, Any]]],
        *,
        ctx: ToolContext | None = None,
        timeout: float | None = None,
        tool_call_id_prefix: str | None = None,
        return_exceptions: bool = False,
    ) -> List[ToolResult[Any] | Exception]:
        """
        Execute multiple tool calls concurrently (bounded by registry semaphore).

        calls: list of (tool_name, raw_args)
        return_exceptions:
          - False: will raise on first exception
          - True: returns Exception objects in result list
        """
        ctx = ctx or ToolContext()

        async def _one(i: int, n: str, a: Dict[str, Any]) -> ToolResult[Any]:
            tcid = f"{tool_call_id_prefix}:{i}" if tool_call_id_prefix else None
            return await self.call(n, a, ctx=ctx, timeout=timeout, tool_call_id=tcid)

        tasks = [asyncio.create_task(_one(i, n, a)) for i, (n, a) in enumerate(calls)]
        results = await asyncio.gather(*tasks, return_exceptions=return_exceptions)
        return results  # type: ignore[return-value]

    # '''''''''''''''''''''''
    # Observability
    # '''''''''''''''''''''''

    def recent_calls(self, limit: int = 100) -> List[ToolCallRecord]:
        return self._records[-limit:]

    # '''''''''''''''''''''''
    # Export / specs
    # '''''''''''''''''''''''

    def specs(self) -> List[ToolSpec]:
        return [t.spec for t in self._tools.values()]

    def to_openai_function_tools(self) -> List[Dict[str, Any]]:
        """
        Export registry tools in OpenAI function-tool format:
        [
          {"type":"function","function":{"name":...,"description":...,"parameters":...}},
          ...
        ]
        """
        out: List[Dict[str, Any]] = []
        for t in self._tools.values():
            out.append(
                {
                    "type": "function",
                    "function": {
                        "name": t.spec.name,
                        "description": t.spec.description,
                        "parameters": t.spec.parameters_schema,
                    },
                }
            )
        return out

    def list_tool_summaries(self) -> List[Dict[str, Any]]:
        """
        Lightweight listing for UIs / debugging.
        """
        return [
            {
                "name": t.spec.name,
                "description": t.spec.description,
            }
            for t in self._tools.values()
        ]