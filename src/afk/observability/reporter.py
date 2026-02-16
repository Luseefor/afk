"""
MIT License
Copyright (c) 2026 arpan404
See LICENSE file for full license text.

Observability reporters — output metrics in various formats.
"""

from __future__ import annotations

import json
import sys
import time
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any, TextIO

from .collector import RunMetrics


class Reporter(ABC):
    """Abstract base for metrics reporters."""

    @abstractmethod
    def report(self, metrics: RunMetrics) -> None:
        """
        Output metrics in the reporter's format.

        Args:
            metrics: Aggregated run metrics.
        """
        ...


class ConsoleReporter(Reporter):
    """
    Pretty-prints metrics to the console.

    Usage::

        reporter = ConsoleReporter()
        reporter.report(metrics)
    """

    def __init__(self, *, output: TextIO | None = None, color: bool = True) -> None:
        self._output = output or sys.stdout
        self._color = color

    def _c(self, text: str, code: str) -> str:
        """Apply ANSI color if enabled."""
        if not self._color:
            return text
        return f"\033[{code}m{text}\033[0m"

    def report(self, metrics: RunMetrics) -> None:
        """Print formatted metrics summary."""
        out = self._output
        header = self._c("═" * 50, "36")
        out.write(f"\n{header}\n")
        out.write(self._c("  AFK Run Report\n", "1;36"))
        out.write(f"{header}\n\n")

        # Status
        status = self._c("✓ SUCCESS", "32") if metrics.success else self._c("✗ FAILED", "31")
        out.write(f"  Status:    {status}\n")
        if metrics.agent_name:
            out.write(f"  Agent:     {metrics.agent_name}\n")
        if metrics.run_id:
            out.write(f"  Run ID:    {metrics.run_id[:16]}...\n")
        out.write(f"  Duration:  {metrics.total_duration_s:.2f}s\n")
        out.write(f"  Steps:     {metrics.steps}\n")
        out.write("\n")

        # LLM stats
        out.write(self._c("  LLM Usage\n", "1"))
        out.write(f"  ├─ Calls:          {metrics.llm_calls}\n")
        out.write(f"  ├─ Input tokens:   {metrics.input_tokens:,}\n")
        out.write(f"  ├─ Output tokens:  {metrics.output_tokens:,}\n")
        out.write(f"  ├─ Total tokens:   {metrics.total_tokens:,}\n")
        if metrics.avg_llm_latency_ms is not None:
            out.write(f"  └─ Avg latency:    {metrics.avg_llm_latency_ms:.0f}ms\n")
        else:
            out.write(f"  └─ Avg latency:    N/A\n")
        out.write("\n")

        # Tool stats
        if metrics.tool_calls > 0:
            out.write(self._c("  Tool Usage\n", "1"))
            out.write(f"  ├─ Total calls:    {metrics.tool_calls}\n")
            if metrics.avg_tool_latency_ms is not None:
                out.write(f"  ├─ Avg latency:    {metrics.avg_tool_latency_ms:.0f}ms\n")
            for tool_name, latencies in metrics.tool_latencies_ms.items():
                avg = sum(latencies) / len(latencies) if latencies else 0
                out.write(f"  │  └─ {tool_name}: {len(latencies)}x avg {avg:.0f}ms\n")
            out.write("\n")

        # Cost
        if metrics.estimated_cost_usd is not None:
            cost_str = f"${metrics.estimated_cost_usd:.4f}"
            out.write(f"  Cost:      {self._c(cost_str, '33')}\n")
            out.write("\n")

        # Errors
        if metrics.errors:
            out.write(self._c(f"  Errors ({len(metrics.errors)})\n", "31"))
            for err in metrics.errors[:5]:
                out.write(f"  └─ {err[:80]}\n")
            out.write("\n")

        out.write(f"{header}\n")
        out.flush()


class JSONReporter(Reporter):
    """
    Outputs metrics as a JSON object.

    Can write to a file or return as string.
    """

    def __init__(self, *, path: str | Path | None = None, indent: int = 2) -> None:
        self._path = Path(path) if path else None
        self._indent = indent
        self._last_output: str | None = None

    def report(self, metrics: RunMetrics) -> None:
        """Write metrics as JSON."""
        data = metrics.to_dict()
        data["reported_at"] = time.time()
        output = json.dumps(data, indent=self._indent, default=str)
        self._last_output = output

        if self._path:
            self._path.write_text(output + "\n")
        else:
            print(output)

    @property
    def last_output(self) -> str | None:
        """Last generated JSON string."""
        return self._last_output


class FileReporter(Reporter):
    """
    Appends metrics as JSONL (one JSON object per line) to a log file.

    Suitable for long-running systems that accumulate run data.
    """

    def __init__(self, path: str | Path) -> None:
        self._path = Path(path)

    def report(self, metrics: RunMetrics) -> None:
        """Append one JSON line to the file."""
        data = metrics.to_dict()
        data["reported_at"] = time.time()
        line = json.dumps(data, default=str)
        self._path.parent.mkdir(parents=True, exist_ok=True)
        with self._path.open("a") as f:
            f.write(line + "\n")

    def read_all(self) -> list[dict[str, Any]]:
        """Read all recorded metrics from the JSONL file."""
        if not self._path.exists():
            return []
        entries = []
        with self._path.open() as f:
            for line in f:
                line = line.strip()
                if line:
                    entries.append(json.loads(line))
        return entries
