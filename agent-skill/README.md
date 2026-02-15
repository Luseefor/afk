# AFK Agent Skills

This folder contains installable skill packs for coding agents.

GitHub path:
- https://github.com/socioy/afk/tree/main/agent-skill

Included skills:
- `afk-agentic-coding`
- `afk-docs-maintainer`

Install via skills CLI:

```bash
npx skills add socioy/afk
```

Maintainer-only prebuild step (before publishing):

```bash
./scripts/build_agentic_ai_assets.sh
```

Prebuilt assets included in skill packages:

- `ai-index/docs-index.json`, `ai-index/docs-index.jsonl`, `ai-index/inverted-index.json`
- `ai-index/examples.md` (merged from `docs/library/snippets/*.mdx`)
- `agent-skill/index.json`
- `agent-skill/<skill>/references/afk-docs/*`
- `agent-skill/<skill>/references/examples.md`

Skill installation/distribution should be handled by your skills package workflow.
