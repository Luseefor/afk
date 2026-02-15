# AFK Agentic Build Playbook

Use this when implementing AFK agents end-to-end.

## Build Order

1. Prompted agent
2. Tool agent
3. Governed agent (policy + HITL)
4. Durable agent (checkpoint/resume)
5. Multi-agent orchestration
6. Production hardening

## Mandatory Engineering Rules

- Use `from afk...` imports only in integration code.
- Define typed tool argument models with clear bounds.
- Add explicit policy checks for side-effect tools.
- Validate resume behavior when workflow spans multiple steps.
- Add tests for changed behavior paths.

## Runtime Safety Baseline

- configure `RunnerConfig` for interaction mode and tool output sanitization
- set sandbox restrictions for risky tools
- choose failure policies for llm/tool/subagent errors

## Useful Pages

- https://afk.arpan.sh/library/developer-guide
- https://afk.arpan.sh/library/agentic-levels
- https://afk.arpan.sh/library/tool-call-lifecycle
- https://afk.arpan.sh/library/security-model
