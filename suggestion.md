# AFK SDK — Architecture review & recommendations

Date: 2026-02-16

## Quick verdict ✅
Well‑structured, modular SDK with excellent DX foundations — clear separation between *declaration* (`Agent`) and *execution* (`Runner`), powerful tool abstractions, and production-ready safety/observability. Main opportunity: make the high-power capabilities feel irresistibly easy to use for newcomers (one‑line common paths, clearer examples, friendlier errors).

---

## High-level architecture (summary) 🔧
- Declarative agent definitions: `BaseAgent` / `Agent` (`src/afk/agents/core/base.py`).
- Execution: `Runner` composed from mixins (`src/afk/core/runner/`).
- Tools system: `@tool` decorator, `Tool`, `ToolRegistry` (`src/afk/tools/`).
- LLM adapters: `create_llm` factory & registry (`src/afk/llms/factory.py`).
- Prompts: Jinja-backed `PromptStore` with caching (`src/afk/agents/prompts/store.py`).
- Memory: pluggable backends (`src/afk/memory/factory.py`).
- Policy & security: deterministic `PolicyEngine`, sandboxing, allowlists.
- Observability: pluggable telemetry sinks (`src/afk/core/telemetry.py`).
- Strong test coverage for core flows and edge cases.

---

## Strengths ✅
- Clear separation of concerns (declaration vs runtime).
- DX-first tool authoring (Pydantic args, pre/post hooks, middleware).
- Pluggable adapters and backends for production flexibility.
- Built-in policy, sandboxing, and telemetry for safety & observability.
- Well-tested critical subsystems.

---

## Risks & opportunities ⚠️
- Onboarding friction for beginners — powerful surface but learning curve remains.
- Missing high-level one-liners / sync helpers for common flows.
- Docs/cookbook could expose advanced features (subagents, policies) more clearly.
- Some error messages could be more actionable for users.

---

## Prioritized, concrete recommendations (actionable) 🔢
1. High priority — Beginner DX:
   - Add a one-liner/sync convenience helper (e.g. `afk.quickstart.run_chat()` or `Agent.call_sync()`).
   - Files: `src/afk/quickstart.py`, `src/afk/core/runner/api.py`.

2. Medium priority — Cookbooks & examples:
   - Add focused examples for subagents, policy rules, sandbox profiles, and streaming.
   - Expand `examples/` and `docs/` with copy-paste snippets.

3. Medium priority — Better errors & tests:
   - Improve error messages around tool-signature/validation and policy denials.
   - Add tests that assert helpful error text.

4. Medium/Long — CLI + templates:
   - Add `afk` CLI scaffolding (`init`, `run`) and VSCode/user snippets for tools/agents.

5. Long term — Observability & benchmarks:
   - Provide telemetry exporters and performance benchmarks for tool-batching and concurrency.

---

## Quick wins (30–120 minutes) ⚡
- Implement `Agent.call_sync()` or `Runner.run_sync()` wrapper.
- Add a 5-line quickstart to `README.md` and `examples/basic_agent.py`.
- Improve two error messages (tool signature validation + prompt template missing variable).

---

## Suggested 3‑sprint roadmap (practical) 📅
1. Sprint 1: Add sync/one-liner helpers + README quickstart + tests (High impact). 
2. Sprint 2: Cookbook pages + CLI prototype + more examples for subagents/policy. 
3. Sprint 3: Telemetry exporters + benchmarks + API stability polish.

---

## Files to inspect / update first 🔎
- UX/API: `src/afk/quickstart.py`, `src/afk/agents/core/base.py`, `src/afk/core/runner/api.py`
- Tool DX & validation: `src/afk/tools/core/decorator.py`, `src/afk/tools/core/base.py`
- Prompt UX: `src/afk/agents/prompts/store.py`
- Adapter/backends: `src/afk/llms/factory.py`, `src/afk/memory/factory.py`
- Tests to add/expand: `tests/` (add `tests/quickstart.py`, expand docs examples coverage)

---

## Next recommended step (pick one) ▶️
1) Implement the sync/one-liner helper + README example (fast, high-impact).
2) Create a short cookbook page showing subagents + policies (improves discoverability).

---

If you want, I can implement option 1 or 2 and open the necessary files/PR. Which do you prefer?