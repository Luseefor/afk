# AFK SDK — Environment Variables Reference

All configuration variables use the `AFK_` prefix. None are required — sensible defaults are used throughout.

## LLM Configuration

| Variable                   | Default        | Description                                         |
| -------------------------- | -------------- | --------------------------------------------------- |
| `AFK_LLM_ADAPTER`          | `litellm`      | LLM adapter: `litellm`, `openai`, `anthropic_agent` |
| `AFK_LLM_MODEL`            | `gpt-4.1-mini` | Default model identifier                            |
| `AFK_EMBED_MODEL`          | _(none)_       | Embedding model identifier                          |
| `AFK_LLM_API_BASE_URL`     | _(none)_       | Custom API base URL                                 |
| `AFK_LLM_API_KEY`          | _(none)_       | API key override                                    |
| `AFK_LLM_TIMEOUT_S`        | `30`           | Request timeout in seconds                          |
| `AFK_LLM_MAX_RETRIES`      | `3`            | Max retry attempts on transient failures            |
| `AFK_LLM_BACKOFF_BASE_S`   | `0.5`          | Exponential backoff base (seconds)                  |
| `AFK_LLM_BACKOFF_JITTER_S` | `0.15`         | Random jitter added to backoff (seconds)            |
| `AFK_LLM_JSON_MAX_RETRIES` | `2`            | Max retries for invalid JSON structured output      |
| `AFK_LLM_MAX_INPUT_CHARS`  | `200000`       | Max input character limit                           |

## Memory Backend

| Variable             | Default  | Description                                             |
| -------------------- | -------- | ------------------------------------------------------- |
| `AFK_MEMORY_BACKEND` | `sqlite` | Backend type: `inmemory`, `sqlite`, `redis`, `postgres` |

> Import behavior: `afk.memory` uses conditional imports for Redis/Postgres
> adapters. This keeps base imports working without optional dependencies.
> If you choose `redis`/`postgres`, install their clients (`redis`,
> `asyncpg`).

### SQLite

| Variable          | Default              | Description               |
| ----------------- | -------------------- | ------------------------- |
| `AFK_SQLITE_PATH` | `afk_memory.sqlite3` | SQLite database file path |

### Redis

| Variable               | Default     | Description                                        |
| ---------------------- | ----------- | -------------------------------------------------- |
| `AFK_REDIS_URL`        | _(none)_    | Full Redis connection URL (overrides host/port/db) |
| `AFK_REDIS_HOST`       | `localhost` | Redis host                                         |
| `AFK_REDIS_PORT`       | `6379`      | Redis port                                         |
| `AFK_REDIS_DB`         | `0`         | Redis database number                              |
| `AFK_REDIS_PASSWORD`   | _(empty)_   | Redis password                                     |
| `AFK_REDIS_EVENTS_MAX` | `2000`      | Max events per thread                              |

> Note: The Redis adapter implements an *atomic upsert* for long-term
> memories — calling `upsert_long_term_memory(..., embedding=None)` will
> preserve any existing embedding atomically (no race). Redis also
> supports TTL for transient state entries.

### PostgreSQL

| Variable          | Default      | Description                                    |
| ----------------- | ------------ | ---------------------------------------------- |
| `AFK_PG_DSN`      | _(none)_     | Full PostgreSQL DSN (overrides host/port/user) |
| `AFK_PG_HOST`     | `localhost`  | PostgreSQL host                                |
| `AFK_PG_PORT`     | `5432`       | PostgreSQL port                                |
| `AFK_PG_USER`     | `postgres`   | PostgreSQL user                                |
| `AFK_PG_PASSWORD` | _(empty)_    | PostgreSQL password                            |
| `AFK_PG_DB`       | `afk`        | PostgreSQL database name                       |
| `AFK_PG_SSL`      | `false`      | Enable SSL connections                         |
| `AFK_PG_POOL_MIN` | `1`          | Minimum connection pool size                   |
| `AFK_PG_POOL_MAX` | `10`         | Maximum connection pool size                   |
| `AFK_VECTOR_DIM`  | _(required)_ | Embedding vector dimension (e.g. `1536`)       |

## Task Queue Backend

| Variable            | Default    | Description                             |
| ------------------- | ---------- | --------------------------------------- |
| `AFK_QUEUE_BACKEND` | `inmemory` | Backend type: `inmemory`, `redis`       |
| `AFK_QUEUE_RETRY_BACKOFF_BASE_S` | `0.5` | Retry backoff base delay in seconds     |
| `AFK_QUEUE_RETRY_BACKOFF_MAX_S` | `30` | Retry backoff maximum delay cap in seconds |
| `AFK_QUEUE_RETRY_BACKOFF_JITTER_S` | `0.2` | Random retry jitter window in seconds   |

> Execution contracts are configured at worker construction time
> (`TaskWorker(..., execution_contracts=..., job_handlers=...)`), not by
> environment variables in this release.

### Queue Redis

| Variable                   | Default     | Description                                              |
| -------------------------- | ----------- | -------------------------------------------------------- |
| `AFK_QUEUE_REDIS_URL`      | _(none)_    | Full Redis URL (falls back to `AFK_REDIS_URL`)          |
| `AFK_QUEUE_REDIS_HOST`     | `localhost` | Redis host (fallback to `AFK_REDIS_HOST`)               |
| `AFK_QUEUE_REDIS_PORT`     | `6379`      | Redis port (fallback to `AFK_REDIS_PORT`)               |
| `AFK_QUEUE_REDIS_DB`       | `0`         | Redis DB number (fallback to `AFK_REDIS_DB`)            |
| `AFK_QUEUE_REDIS_PASSWORD` | _(empty)_   | Redis password (fallback to `AFK_REDIS_PASSWORD`)       |
| `AFK_QUEUE_REDIS_PREFIX`   | `afk:queue` | Key prefix for queue list/hash (`<prefix>:pending/tasks`) |

## Agent Prompts

| Variable                | Default          | Description                            |
| ----------------------- | ---------------- | -------------------------------------- |
| `AFK_AGENT_PROMPTS_DIR` | `.agents/prompt` | Root directory for system prompt files |
