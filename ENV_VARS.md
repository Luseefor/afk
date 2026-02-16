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

## Agent Prompts

| Variable                | Default          | Description                            |
| ----------------------- | ---------------- | -------------------------------------- |
| `AFK_AGENT_PROMPTS_DIR` | `.agents/prompt` | Root directory for system prompt files |
