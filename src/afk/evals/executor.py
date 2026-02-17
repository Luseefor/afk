"""
MIT License
Copyright (c) 2026 arpan404
See LICENSE file for full license text.

Single-case eval execution helpers.
"""

from __future__ import annotations

import asyncio

from ..core.runner import Runner
from ..observability.projectors import project_run_metrics_from_result
from .models import EvalCase, EvalCaseResult


async def arun_case(runner: Runner, case: EvalCase) -> EvalCaseResult:
    """Run one eval case asynchronously and return case result envelope."""

    handle = await runner.run_handle(
        case.agent,
        user_message=case.user_message,
        context=case.context,
        thread_id=case.thread_id,
    )
    event_types: list[str] = []
    async for event in handle.events:
        event_types.append(event.type)

    result = await handle.await_result()
    if result is None:
        raise RuntimeError(f"Eval case '{case.name}' cancelled")

    metrics = project_run_metrics_from_result(result)
    passed = result.state == "completed"
    return EvalCaseResult(
        case=case.name,
        state=result.state,
        final_text=result.final_text,
        run_id=result.run_id,
        thread_id=result.thread_id,
        event_types=event_types,
        metrics=metrics,
        passed=passed,
    )


def run_case(runner: Runner, case: EvalCase) -> EvalCaseResult:
    """Run one eval case synchronously using a dedicated event loop."""

    return asyncio.run(arun_case(runner, case))
