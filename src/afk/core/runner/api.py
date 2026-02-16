"""
MIT License
Copyright (c) 2026 socioy
See LICENSE file for full license text.

Public runner API and lifecycle entrypoints.
"""

from __future__ import annotations

import asyncio
from typing import Any

from ...agents.core.base import BaseAgent
from ...agents.errors import AgentCancelledError, AgentCheckpointCorruptionError, AgentConfigurationError
from ...agents.policy.engine import PolicyEngine
from ...agents.lifecycle.runtime import EffectJournal, checkpoint_latest_key
from ...agents.types import AgentResult, AgentRunHandle
from ...memory import (
    MemoryCompactionResult,
    MemoryStore,
    RetentionPolicy,
    StateRetentionPolicy,
    compact_thread_memory,
)
from ..interaction import HeadlessInteractionProvider, InteractionProvider
from ..telemetry import NullTelemetrySink, TelemetrySink
from .types import RunnerConfig, _RunHandle


class RunnerAPIMixin:
    """
    Public API surface for running, resuming, and compacting agent threads.

    This mixin owns dependency wiring (memory, interaction, policy, telemetry)
    and exposes the stable entrypoints used by `Agent.call(...)` and external
    runtime integrations.
    """

    def __init__(
        self,
        *,
        memory_store: MemoryStore | None = None,
        interaction_provider: InteractionProvider | None = None,
        policy_engine: PolicyEngine | None = None,
        telemetry: TelemetrySink | None = None,
        config: RunnerConfig | None = None,
    ) -> None:
        """
        Initialize a runner API surface with optional runtime dependencies.

        Args:
            memory_store: Memory backend. When `None`, runtime resolves from
                environment on first use and may fallback to in-memory.
            interaction_provider: Human-in-the-loop provider. Required when
                `config.interaction_mode` is not `headless`.
            policy_engine: Optional deterministic policy engine shared across runs.
            telemetry: Telemetry sink for counters/spans/events.
            config: Runner configuration. Defaults to `RunnerConfig()`.

        Raises:
            AgentConfigurationError: If interaction mode requires provider but
                none is supplied.
        """
        self.config = config or RunnerConfig()
        self._memory_store = memory_store
        self._owns_memory_store = memory_store is None
        self._memory_fallback_reason: str | None = None
        if interaction_provider is None:
            if self.config.interaction_mode == "headless":
                self._interaction = HeadlessInteractionProvider(
                    approval_fallback=self.config.approval_fallback,
                    input_fallback=self.config.input_fallback,
                )
            else:
                raise AgentConfigurationError(
                    "interaction_provider is required when interaction_mode is not 'headless'"
                )
        else:
            self._interaction = interaction_provider
        self._policy_engine = policy_engine
        self._telemetry = telemetry or NullTelemetrySink()
        self._effect_journal = EffectJournal()
        self._active_runs = 0

    async def compact_thread(
        self,
        *,
        thread_id: str,
        event_policy: RetentionPolicy | None = None,
        state_policy: StateRetentionPolicy | None = None,
    ) -> MemoryCompactionResult:
        """
        Compact retained memory records for a thread.

        Args:
            thread_id: Thread identifier whose memory should be compacted.
            event_policy: Optional override for event retention compaction.
            state_policy: Optional override for state retention compaction.

        Returns:
            Memory compaction summary for the thread.

        Raises:
            AgentConfigurationError: If `thread_id` is empty.
        """
        if not isinstance(thread_id, str) or not thread_id.strip():
            raise AgentConfigurationError("thread_id must be a non-empty string")
        memory = await self._ensure_memory_store()
        return await compact_thread_memory(
            memory,
            thread_id=thread_id,
            event_policy=event_policy,
            state_policy=state_policy,
        )

    async def run(
        self,
        agent: BaseAgent,
        *,
        user_message: str | None = None,
        context: dict[str, Any] | None = None,
        thread_id: str | None = None,
    ) -> AgentResult:
        """
        Execute an agent run and wait for terminal result.

        Args:
            agent: Agent definition to execute.
            user_message: Optional initial user message.
            context: Optional JSON-like run context.
            thread_id: Optional thread id for memory continuity.

        Returns:
            Terminal agent result.

        Raises:
            AgentCancelledError: If run is cancelled before completion.
        """
        handle = await self.run_handle(
            agent,
            user_message=user_message,
            context=context,
            thread_id=thread_id,
        )
        result = await handle.await_result()
        if result is None:
            raise AgentCancelledError("Run cancelled")
        return result

    def run_sync(
        self,
        agent: BaseAgent,
        *,
        user_message: str | None = None,
        context: dict[str, Any] | None = None,
        thread_id: str | None = None,
    ) -> AgentResult:
        """
        Execute an agent run synchronously (blocking).

        Convenience wrapper around :meth:`run` for scripts and CLIs that
        do not have their own event loop. Raises ``RuntimeError`` if called
        from inside an already-running async event loop.

        Args:
            agent: Agent definition to execute.
            user_message: Optional initial user message.
            context: Optional JSON-like run context.
            thread_id: Optional thread id for memory continuity.

        Returns:
            Terminal agent result.

        Raises:
            AgentCancelledError: If run is cancelled before completion.
            RuntimeError: If called inside a running event loop.
        """
        from ...llms.utils import run_sync as _run_sync

        return _run_sync(
            self.run(
                agent,
                user_message=user_message,
                context=context,
                thread_id=thread_id,
            )
        )

    async def resume(
        self,
        agent: BaseAgent,
        *,
        run_id: str,
        thread_id: str,
        context: dict[str, Any] | None = None,
    ) -> AgentResult:
        """
        Resume a previously checkpointed run and wait for completion.

        Args:
            agent: Agent definition to resume.
            run_id: Existing run identifier.
            thread_id: Existing thread identifier.
            context: Optional context overlay for resumed execution.

        Returns:
            Terminal agent result.

        Raises:
            AgentCancelledError: If resumed run is cancelled.
        """
        handle = await self.resume_handle(
            agent,
            run_id=run_id,
            thread_id=thread_id,
            context=context,
        )
        result = await handle.await_result()
        if result is None:
            raise AgentCancelledError("Run cancelled")
        return result

    async def resume_handle(
        self,
        agent: BaseAgent,
        *,
        run_id: str,
        thread_id: str,
        context: dict[str, Any] | None = None,
    ) -> AgentRunHandle:
        """
        Resume a run and return a live handle for lifecycle control.

        If the latest checkpoint already contains a terminal result, this method
        returns a handle pre-populated with that result.

        Args:
            agent: Agent definition used for continued execution.
            run_id: Existing run identifier.
            thread_id: Existing thread identifier.
            context: Optional context overlay for resumed execution.

        Returns:
            Active run handle or pre-resolved terminal handle.

        Raises:
            AgentConfigurationError: If `run_id`/`thread_id` is invalid.
            AgentCheckpointCorruptionError: If checkpoint chain is missing or
                invalid for the given run.
        """
        if not isinstance(run_id, str) or not run_id.strip():
            raise AgentConfigurationError("run_id must be a non-empty string")
        if not isinstance(thread_id, str) or not thread_id.strip():
            raise AgentConfigurationError("thread_id must be a non-empty string")

        memory = await self._ensure_memory_store()
        latest = await memory.get_state(thread_id, checkpoint_latest_key(run_id))
        if not isinstance(latest, dict):
            raise AgentCheckpointCorruptionError(
                f"No checkpoint found for run_id={run_id} thread_id={thread_id}"
            )
        latest = self._normalize_checkpoint_record(latest)

        payload = latest.get("payload")
        phase = latest.get("phase")
        if isinstance(payload, dict):
            terminal = payload.get("terminal_result")
            if phase == "run_terminal" and isinstance(terminal, dict):
                handle = _RunHandle()
                result = self._deserialize_agent_result(terminal)
                await handle.set_result(result)
                return handle

        resume_snapshot = await self._load_latest_runtime_snapshot(
            memory=memory,
            thread_id=thread_id,
            run_id=run_id,
            latest=latest,
        )

        return await self.run_handle(
            agent,
            context=context,
            thread_id=thread_id,
            _resume_run_id=run_id,
            _resume_snapshot=resume_snapshot,
        )

    async def run_handle(
        self,
        agent: BaseAgent,
        *,
        user_message: str | None = None,
        context: dict[str, Any] | None = None,
        thread_id: str | None = None,
        _depth: int = 0,
        _lineage: tuple[int, ...] = (),
        _resume_run_id: str | None = None,
        _resume_snapshot: dict[str, Any] | None = None,
    ) -> AgentRunHandle:
        """
        Start execution and return an async run handle.

        Args:
            agent: Agent definition to execute.
            user_message: Optional initial user message.
            context: Optional JSON-like run context.
            thread_id: Optional thread id for memory continuity.
            _depth: Internal recursion depth for subagent execution.
            _lineage: Internal lineage tuple used for tracing nested runs.
            _resume_run_id: Internal run id for resume continuation.
            _resume_snapshot: Internal restored snapshot payload.

        Returns:
            Handle exposing event stream and run lifecycle controls.
        """
        handle = _RunHandle()
        task = asyncio.create_task(
            self._execute(
                handle,
                agent,
                user_message=user_message,
                context=context,
                thread_id=thread_id,
                depth=_depth,
                lineage=_lineage,
                resume_run_id=_resume_run_id,
                resume_snapshot=_resume_snapshot,
            )
        )
        handle.attach_task(task)
        return handle

    async def run_stream(
        self,
        agent: BaseAgent,
        *,
        user_message: str | None = None,
        context: dict[str, Any] | None = None,
        thread_id: str | None = None,
    ) -> "AgentStreamHandle":
        """
        Start an agent run and return a stream handle for real-time events.

        The stream yields ``AgentStreamEvent`` instances including text deltas,
        tool lifecycle events, and a terminal ``completed`` event with the
        final ``AgentResult``.

        Usage::

            handle = await runner.run_stream(agent, user_message="Hi")
            async for event in handle:
                if event.type == "text_delta":
                    print(event.text_delta, end="", flush=True)
            result = handle.result

        Args:
            agent: Agent definition to execute.
            user_message: Optional initial user message.
            context: Optional JSON-like run context.
            thread_id: Optional thread id for memory continuity.

        Returns:
            ``AgentStreamHandle`` for consuming stream events.
        """
        from ..streaming import (
            AgentStreamHandle,
            stream_completed,
            stream_error,
            text_delta,
            tool_completed as _tool_completed,
            tool_started as _tool_started,
            step_started as _step_started,
            status_update,
        )

        run_handle = await self.run_handle(
            agent,
            user_message=user_message,
            context=context,
            thread_id=thread_id,
        )
        stream = AgentStreamHandle()

        async def _bridge() -> None:
            """Bridge run events → stream events."""
            try:
                async for event in run_handle.events:
                    # Map known event types to stream events
                    if event.event_type == "llm_completed" and event.data:
                        response_text = event.data.get("text", "")
                        if response_text:
                            await stream.emit(text_delta(str(response_text)))
                    elif event.event_type == "tool_batch_started" and event.data:
                        tool_names = event.data.get("tool_names", [])
                        if isinstance(tool_names, list):
                            for tn in tool_names:
                                await stream.emit(_tool_started(str(tn)))
                    elif event.event_type == "tool_completed" and event.data:
                        await stream.emit(_tool_completed(
                            tool_name=str(event.data.get("tool_name", "")),
                            tool_call_id=event.data.get("tool_call_id"),
                            success=bool(event.data.get("success", False)),
                            output=event.data.get("output"),
                            error=event.data.get("error"),
                        ))
                    elif event.event_type == "step_started":
                        await stream.emit(_step_started(
                            step=int(event.data.get("step", 0)) if event.data else 0,
                            state=event.data.get("state", "running") if event.data else "running",
                        ))
                    elif event.event_type in ("run_failed", "run_interrupted"):
                        error_msg = (
                            event.data.get("error", str(event.event_type))
                            if event.data
                            else str(event.event_type)
                        )
                        await stream.emit(stream_error(str(error_msg)))

                # Run completed — emit terminal event
                result = await run_handle.await_result()
                if result is not None:
                    await stream.emit(stream_completed(result))
            except Exception as exc:
                await stream.emit(stream_error(str(exc)))
            finally:
                await stream.close()

        asyncio.create_task(_bridge())
        return stream
