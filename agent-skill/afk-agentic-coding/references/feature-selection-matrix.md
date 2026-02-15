# Feature Selection Matrix

Select only the capabilities needed for the current project stage.

| Target Level | Required Features |
| --- | --- |
| 1 | `Agent`, prompt strategy (`instructions` or prompt file), one model |
| 2 | typed tools, tool descriptions, argument validation |
| 3 | policy gate on `tool_before_execute`, approvals, sandbox/output limits |
| 4 | checkpoint persistence, `Runner.resume`, replay-safe operations |
| 5 | subagents, router, explicit context inheritance boundaries |
| 6 | fail-safe budgets, fallback path, telemetry, tests/evals |

## Anti-Patterns

- jumping to subagents before safety and durability controls
- exposing command or filesystem tools without policy/sandbox
- mixing internal imports (`src/...`) in shipped examples
- shipping behavior changes without tests and docs updates
