# AFK (Agent Forge Kit)

AFK is an agent runtime and SDK for building production-oriented agent systems with:

- policy-aware execution
- tool orchestration with security boundaries
- checkpoint/resume workflows
- provider-agnostic LLM integrations
- eval harness support

## Development Status

> **Note:** AFK is in **fast-paced development mode**.
> APIs, behavior, and docs may change quickly. Pin versions and test upgrades carefully.

## Installation

### From source (this repository)

```bash
python -m pip install --upgrade pip
python -m pip install -e .
```

### SDK usage

Import from public package paths:

```python
from afk.agents import Agent
from afk.core import Runner, RunnerConfig
from afk.tools import tool
from afk.llms import create_llm
```

## Quick Start

```python
from pydantic import BaseModel, Field
from afk.agents import Agent
from afk.tools import tool


class SumArgs(BaseModel):
    numbers: list[float] = Field(min_length=1)


@tool(
    args_model=SumArgs,
    name="sum_numbers",
    description="Add all numbers and return their sum.",
)
def sum_numbers(args: SumArgs) -> dict[str, float]:
    return {"sum": float(sum(args.numbers))}


agent = Agent(
    model="gpt-4.1-mini",
    instructions="Use sum_numbers for arithmetic.",
    tools=[sum_numbers],
)
```

Configure environment for your adapter/model before running full examples:

```bash
export AFK_LLM_ADAPTER=openai
export AFK_LLM_MODEL=gpt-4.1-mini
export AFK_LLM_API_KEY=your_key_here
export AFK_AGENT_PROMPTS_DIR=.agents/prompt
```

## Memory backends & guarantees

AFK supports multiple memory backends (`sqlite`, `redis`, `postgres`). Key guarantees:
- Redis: supports TTL for transient state and provides an *atomic upsert* for
  long-term memories — omitting `embedding` will preserve an existing
  embedding under concurrent updates.
- SQLite/Postgres: preserve embeddings on upsert (SQLite uses ON CONFLICT with
  COALESCE; Postgres uses JSONB + vector upserts).

Import behavior:
- `afk.memory` conditionally imports Redis/Postgres adapters so base imports
  keep working when optional backend clients are not installed.
- In practice, this means SQLite/InMemory workflows can run without Redis/
  Postgres dependencies, but selecting `redis` or `postgres` backends still
  requires their client libraries (`redis`, `asyncpg`).

## System Prompt Loader

AFK supports file-backed system prompts for all `BaseAgent` types.

Resolution order:

1. inline/callable `instructions` (highest priority)
2. `instruction_file`
3. auto file from agent name (`UPPER_SNAKE.md`)

Prompt root order:

1. `prompts_dir` argument
2. `AFK_AGENT_PROMPTS_DIR`
3. `.agents/prompt`

Example:

```python
from afk.agents import Agent

agent = Agent(
    name="ChatAgent",
    model="gpt-4.1-mini",
    prompts_dir=".agents/prompt",
)
# Auto file: .agents/prompt/CHAT_AGENT.md
```

## Documentation

- Public docs: `https://afk.arpan.sh`
- Docs source: `docs/`
- Main docs entry: `docs/index.mdx`
- Mintlify config: `docs/docs.json`

Run docs locally:

```bash
cd docs
bunx mintlify dev
```

## Building with AI

For SDK users, install AFK skills directly from GitHub:

```bash
npx skills add socioy/afk
```

Then use skill prompts like:

- `Use $afk-agentic-coding to implement this AFK feature.`
- `Use $afk-docs-maintainer to improve docs structure.`

AFK skill pack location:

- `agent-skill/`
- https://github.com/socioy/afk/tree/main/agent-skill

Maintainer-only asset build step:

```bash
./scripts/build_agentic_ai_assets.sh
```

This prebuilds bundled docs/index assets before publishing skill packages.

## Running Tests

```bash
PYTHONPATH=src pytest -q
```

CI currently runs Python `3.13`.

## Contributing

See `CONTRIBUTING.md` for setup, workflow, and pull request expectations.

## Maintainer Contact

- GitHub: `arpan404@github` (handle: `@arpan404`)
- LinkedIn: `arpanbhandari`
- Email: `contact@arpan.sh`

## License

MIT. See `LICENSE`.
