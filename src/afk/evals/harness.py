"""
MIT License
Copyright (c) 2026 arpan404
See LICENSE file for full license text.

Deterministic evaluation harness for agent workflows.
"""

from __future__ import annotations


import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable

from ..agents import BaseAgent
from ..agents.types import AgentRunEvent, AgentState, JSONValue
from ..core.runner import Runner


@dataclass(frozen=True, slots=True)
class EvalScenario:
    name: str
    agent: BaseAgent
    user_message: str | None = None
    context: dict[str, JSONValue] = field(default_factory=dict)
    thread_id: str | None = None


@dataclass(frozen=True, slots=True)
class EvalResult:
    scenario: str
    state: AgentState
    final_text: str
    run_id: str
    thread_id: str
    event_types: list[str] = field(default_factory=list)


async def run_scenario(runner: Runner, scenario: EvalScenario) -> EvalResult:
    handle = await runner.run_handle(
        scenario.agent,
        user_message=scenario.user_message,
        context=scenario.context,
        thread_id=scenario.thread_id,
    )
    event_types: list[str] = []
    async for event in handle.events:
        event_types.append(event.type)

    result = await handle.await_result()
    if result is None:
        raise RuntimeError(f"Scenario '{scenario.name}' cancelled")

    return EvalResult(
        scenario=scenario.name,
        state=result.state,
        final_text=result.final_text,
        run_id=result.run_id,
        thread_id=result.thread_id,
        event_types=event_types,
    )


def write_golden_trace(path: str | Path, events: list[AgentRunEvent]) -> None:
    rows = [
        {
            "type": event.type,
            "state": event.state,
            "step": event.step,
            "message": event.message,
            "data": event.data,
        }
        for event in events
    ]
    Path(path).write_text(
        json.dumps(rows, ensure_ascii=True, indent=2), encoding="utf-8"
    )


def compare_event_types(
    expected: list[str], observed: list[str]
) -> tuple[bool, str | None]:
    if expected == observed:
        return True, None
    return False, f"expected={expected} observed={observed}"


async def arun_scenarios(
    *,
    runner_factory: Callable[[], Runner],
    scenarios: list[EvalScenario],
) -> list[EvalResult]:
    """Async variant of ``run_scenarios``.

    Safe for nested event loops (notebooks, existing async apps).
    """
    out: list[EvalResult] = []
    for scenario in scenarios:
        runner = runner_factory()
        out.append(await run_scenario(runner, scenario))
    return out


def run_scenarios(
    *,
    runner_factory: Callable[[], Runner],
    scenarios: list[EvalScenario],
) -> list[EvalResult]:
    import asyncio

    return asyncio.run(
        arun_scenarios(runner_factory=runner_factory, scenarios=scenarios)
    )
