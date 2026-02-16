"""
MIT License
Copyright (c) 2026 arpan404
See LICENSE file for full license text.

Observability collector — aggregates telemetry into structured run metrics.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Any

from ..agents.types import AgentResult
from ..core.telemetry import TelemetryEvent, TelemetrySink, TelemetrySpan
from ..llms.types import JSONValue


# ---------------------------------------------------------------------------
# Run metrics
# ---------------------------------------------------------------------------


@dataclass(slots=True)
class RunMetrics:
    """
    Aggregated metrics for a single agent run.

    Attributes:
        run_id: Run identifier.
        agent_name: Agent that was executed.
        state: Terminal agent state.
        total_duration_s: Wall-clock duration in seconds.
        llm_calls: Number of LLM invocations.
        tool_calls: Number of tool invocations.
        input_tokens: Total input tokens consumed.
        output_tokens: Total output tokens consumed.
        total_tokens: Total tokens consumed.
        estimated_cost_usd: Estimated cost in USD (if available).
        steps: Number of execution steps.
        errors: List of error messages encountered.
        tool_latencies_ms: Mapping of tool_name → list of latencies.
        llm_latencies_ms: List of LLM call latencies.
        started_at: Unix timestamp when run started.
        completed_at: Unix timestamp when run completed.
    """

    run_id: str = ""
    agent_name: str = ""
    state: str = "unknown"
    total_duration_s: float = 0.0
    llm_calls: int = 0
    tool_calls: int = 0
    input_tokens: int = 0
    output_tokens: int = 0
    total_tokens: int = 0
    estimated_cost_usd: float | None = None
    steps: int = 0
    errors: list[str] = field(default_factory=list)
    tool_latencies_ms: dict[str, list[float]] = field(default_factory=dict)
    llm_latencies_ms: list[float] = field(default_factory=list)
    started_at: float = 0.0
    completed_at: float = 0.0

    @property
    def success(self) -> bool:
        """Whether the run completed successfully."""
        return self.state == "completed"

    @property
    def avg_llm_latency_ms(self) -> float | None:
        """Average LLM call latency in milliseconds."""
        if not self.llm_latencies_ms:
            return None
        return sum(self.llm_latencies_ms) / len(self.llm_latencies_ms)

    @property
    def avg_tool_latency_ms(self) -> float | None:
        """Average tool call latency across all tools."""
        all_latencies = [
            lat for lats in self.tool_latencies_ms.values() for lat in lats
        ]
        if not all_latencies:
            return None
        return sum(all_latencies) / len(all_latencies)

    def to_dict(self) -> dict[str, JSONValue]:
        """Serialize to JSON-safe dictionary."""
        return {
            "run_id": self.run_id,
            "agent_name": self.agent_name,
            "state": self.state,
            "success": self.success,
            "total_duration_s": round(self.total_duration_s, 3),
            "llm_calls": self.llm_calls,
            "tool_calls": self.tool_calls,
            "input_tokens": self.input_tokens,
            "output_tokens": self.output_tokens,
            "total_tokens": self.total_tokens,
            "estimated_cost_usd": self.estimated_cost_usd,
            "steps": self.steps,
            "errors": self.errors,
            "avg_llm_latency_ms": (
                round(self.avg_llm_latency_ms, 1) if self.avg_llm_latency_ms else None
            ),
            "avg_tool_latency_ms": (
                round(self.avg_tool_latency_ms, 1) if self.avg_tool_latency_ms else None
            ),
        }


# ---------------------------------------------------------------------------
# Collector
# ---------------------------------------------------------------------------


def _now_ms() -> int:
    return int(time.time() * 1000)


class ObservabilityCollector:
    """
    Telemetry sink that aggregates events into structured ``RunMetrics``.

    Implements ``TelemetrySink`` so it can be plugged directly into the
    Runner as the telemetry backend. After a run completes, call
    ``get_metrics()`` to retrieve aggregated metrics.

    Usage::

        collector = ObservabilityCollector()
        runner = Runner(telemetry=collector)
        result = await runner.run(agent, user_message="Hi")
        metrics = collector.get_metrics()
        print(metrics.to_dict())

    It can also extract metrics post-hoc from an ``AgentResult``::

        metrics = ObservabilityCollector.from_result(result)
    """

    def __init__(self) -> None:
        self._events: list[TelemetryEvent] = []
        self._spans: list[dict[str, Any]] = []
        self._counters: dict[str, int] = {}
        self._histograms: dict[str, list[float]] = {}
        self._started_at: float = time.time()

    # --- TelemetrySink interface ---

    def record_event(self, event: TelemetryEvent) -> None:
        """Store event for post-run analysis."""
        self._events.append(event)

    def start_span(
        self, name: str, *, attributes: dict[str, JSONValue] | None = None
    ) -> TelemetrySpan:
        """Start a span and track it."""
        span = TelemetrySpan(
            name=name,
            started_at_ms=_now_ms(),
            attributes=dict(attributes or {}),
        )
        return span

    def end_span(
        self,
        span: TelemetrySpan | None,
        *,
        status: str,
        error: str | None = None,
        attributes: dict[str, JSONValue] | None = None,
    ) -> None:
        """End span and persist metadata."""
        if span is None:
            return
        self._spans.append({
            "name": span.name,
            "started_at_ms": span.started_at_ms,
            "ended_at_ms": _now_ms(),
            "duration_ms": _now_ms() - span.started_at_ms,
            "status": status,
            "error": error,
            "attributes": {**span.attributes, **dict(attributes or {})},
        })

    def increment_counter(
        self,
        name: str,
        value: int = 1,
        *,
        attributes: dict[str, JSONValue] | None = None,
    ) -> None:
        """Increment named counter."""
        self._counters[name] = self._counters.get(name, 0) + value

    def record_histogram(
        self,
        name: str,
        value: float,
        *,
        attributes: dict[str, JSONValue] | None = None,
    ) -> None:
        """Record histogram data point."""
        self._histograms.setdefault(name, []).append(value)

    # --- Metrics extraction ---

    def get_metrics(self) -> RunMetrics:
        """
        Aggregate collected telemetry into ``RunMetrics``.

        Call after the agent run completes.
        """
        metrics = RunMetrics(started_at=self._started_at, completed_at=time.time())
        metrics.total_duration_s = metrics.completed_at - metrics.started_at

        # Extract from counters
        metrics.llm_calls = self._counters.get("llm_calls", 0)
        metrics.tool_calls = self._counters.get("tool_calls", 0)
        metrics.input_tokens = self._counters.get("input_tokens", 0)
        metrics.output_tokens = self._counters.get("output_tokens", 0)
        metrics.total_tokens = self._counters.get("total_tokens", 0)
        metrics.steps = self._counters.get("steps", 0)

        # Extract from histograms
        metrics.llm_latencies_ms = list(self._histograms.get("llm_latency_ms", []))

        # Extract tool latencies from spans
        for span in self._spans:
            if span["name"].startswith("tool:"):
                tool_name = span["name"][5:]
                metrics.tool_latencies_ms.setdefault(tool_name, []).append(
                    span.get("duration_ms", 0)
                )

        # Extract errors from events
        for event in self._events:
            if event.name in ("error", "run_failed") and event.attributes:
                error_msg = event.attributes.get("error", "")
                if error_msg:
                    metrics.errors.append(str(error_msg))

        # Infer from spans
        for span in self._spans:
            if span["name"] == "agent_run":
                agent_name = span.get("attributes", {}).get("agent_name", "")
                if agent_name:
                    metrics.agent_name = str(agent_name)
                run_id = span.get("attributes", {}).get("run_id", "")
                if run_id:
                    metrics.run_id = str(run_id)
                state = span.get("status", "unknown")
                metrics.state = state

        return metrics

    @staticmethod
    def from_result(result: AgentResult) -> RunMetrics:
        """
        Extract metrics post-hoc from an ``AgentResult``.

        Useful when you don't want to inject a collector into the Runner.
        """
        metrics = RunMetrics(
            state=result.state,
            llm_calls=len(result.llm_responses),
            tool_calls=len(result.tool_executions),
            steps=result.steps,
            input_tokens=result.usage.input_tokens,
            output_tokens=result.usage.output_tokens,
            total_tokens=result.usage.total_tokens,
            estimated_cost_usd=result.total_cost_usd,
        )

        # Extract tool latencies
        for tool_exec in result.tool_executions:
            if tool_exec.latency_ms is not None:
                metrics.tool_latencies_ms.setdefault(
                    tool_exec.tool_name, []
                ).append(tool_exec.latency_ms)

        # Extract errors
        for tool_exec in result.tool_executions:
            if tool_exec.error:
                metrics.errors.append(f"tool:{tool_exec.tool_name}: {tool_exec.error}")

        return metrics

    def reset(self) -> None:
        """Clear all collected data for reuse."""
        self._events.clear()
        self._spans.clear()
        self._counters.clear()
        self._histograms.clear()
        self._started_at = time.time()
