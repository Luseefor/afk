---
name: afk-docs-maintainer
description: Use this skill when updating AFK docs to keep concept order, remove duplication, preserve public afk.* API usage, and keep docs production-ready for developers.
---

# AFK Docs Maintainer

Use this skill for documentation updates across the AFK docs tree.

Load local references first:

- `references/docs-maintenance-playbook.md`
- `references/icon-and-card-guide.md`
- `references/README.md` (generated; points to bundled docs index)

Use local custom tools when needed:

- `scripts/search_afk_docs.py "query"` for fast lookup
- `scripts/check_docs_quality.py --docs-root docs` for structure checks

## Goals

- keep docs easy for junior engineers to follow
- maintain progression from concepts to production patterns
- avoid duplicate sections and broken links/icons

## Workflow

1. Keep ordering stable:
- start -> concepts -> llm -> reference
- keep examples aligned to maturity levels

2. Prefer production-safe examples:
- use `from afk...` import paths
- avoid references to local filesystem assumptions in user-facing docs
- link to GitHub source paths when code references are needed

3. Keep pages consistent:
- include clear `When To Read`, `Required Features`, `Failure Modes`, `Examples`, `Next Step` sections for concept pages
- use diagrams for complex lifecycle/orchestration flows

4. Quality checks:
- verify all `docs.json` pages exist
- remove duplicate concepts or repeated tables
- fix missing or invalid card icon names

## Reference Docs

- https://afk.arpan.sh
- https://afk.arpan.sh/library/overview
- https://afk.arpan.sh/library/developer-guide
- https://afk.arpan.sh/library/full-module-reference
