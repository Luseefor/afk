"""
MIT License
Copyright (c) 2026 socioy
See LICENSE file for full license text.

Core runtime exports.
"""

from .interaction import HeadlessInteractionProvider, InMemoryInteractiveProvider, InteractionProvider
from .runner import Runner, RunnerConfig
from .telemetry import (
    InMemoryTelemetrySink,
    NullTelemetrySink,
    OpenTelemetrySink,
    TelemetryEvent,
    TelemetrySink,
    TelemetrySpan,
)

__all__ = [
    "Runner",
    "RunnerConfig",
    "InteractionProvider",
    "HeadlessInteractionProvider",
    "InMemoryInteractiveProvider",
    "TelemetrySink",
    "TelemetryEvent",
    "TelemetrySpan",
    "NullTelemetrySink",
    "InMemoryTelemetrySink",
    "OpenTelemetrySink",
]
