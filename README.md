# AFK Python SDK (v1.0.0)

`AFK` is a production-grade Python framework for building robust agent systems with deterministic orchestration, typed messaging, pluggable LLM providers, contract-aware queues, observability, and evals.

## Installation

```bash
pip install the-afk==1.0.0
```

## Imports

```python
import afk
from afk import agents, core, llms
from afk.llms import LLMBuilder
```

## Quick Start

```python
from afk.agents import Agent
from afk.core import Runner

agent = Agent(
    name="assistant",
    model="gpt-4.1-mini",
    instructions="Answer clearly and precisely.",
)

runner = Runner()
result = runner.run_sync(agent, user_message="What is a service level objective?")
print(result.output_text)
```

## Key Capabilities

- deterministic runner lifecycle with typed run events
- secure tool execution with policy hooks
- DAG-based parallel subagent orchestration
- internal and external A2A protocol integration
- provider-driven LLM runtime with retry/timeout/routing/cache controls
- observability backend registry and structured exporters
- eval suites with adaptive scheduling, budgets, and assertions
- contract-aware task queues for agent and non-agent jobs

## Development

```bash
uvx ruff format .
uvx ruff check .
PYTHONPATH=src pytest -q
```

## Documentation

- Main index: `/Users/arpanbhandari/Code/afk-py/docs/index.mdx`
- Navigation config: `/Users/arpanbhandari/Code/afk-py/docs/docs.json`

## License

MIT. See `LICENSE`.
