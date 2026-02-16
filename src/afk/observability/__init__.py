"""
MIT License
Copyright (c) 2026 arpan404
See LICENSE file for full license text.

Observability package for AFK agent runtime.

Provides an ``ObservabilityCollector`` (implements ``TelemetrySink``) that
aggregates telemetry into structured ``RunMetrics``, plus reporters for
output in various formats.

Quick start::

    from afk.observability import ObservabilityCollector, ConsoleReporter

    collector = ObservabilityCollector()
    runner = Runner(telemetry=collector)
    result = await runner.run(agent, user_message="Hi")

    metrics = collector.get_metrics()
    ConsoleReporter().report(metrics)
"""

from .collector import ObservabilityCollector, RunMetrics
from .reporter import ConsoleReporter, FileReporter, JSONReporter, Reporter

__all__ = [
    "ObservabilityCollector",
    "RunMetrics",
    "Reporter",
    "ConsoleReporter",
    "JSONReporter",
    "FileReporter",
]
