---
title: "Roadmap"
description: "What's shipped, what's planned, what's deferred"
---

# AutoSearch Roadmap

## Shipped

The v2 tool-supplier architecture is live. Stable surfaces today:

- **MCP server** (`autosearch-mcp` stdio): `list_skills`, `run_clarify`,
  `run_channel`, `decompose-task`, `delegate-subtask`, `consolidate-research`,
  `citation-export`, plus per-channel skill bundles.
- **CLI** (`autosearch`): `init`, `doctor`, `mcp`, `mcp-check`, `configure`,
  `login`. The CLI is the wrapper around the MCP tools — host AIs (Claude
  Code, Cursor, Zed) drive the synthesis.
- **Channels**: 40 sources spanning academic preprints, web search,
  developer platforms, news, video, and Chinese social media. See
  [`docs/channels.mdx`](channels.mdx).
- **Distribution**: `pipx install autosearch`, `npx autosearch-ai`, and the
  `curl ... | bash` install script. See [`docs/install.md`](install.md).

Module-level status of the v2 pipeline lives in
[`docs/delivery-status.md`](delivery-status.md). The legacy `research()`
MCP tool is in deprecation; the migration guide is at
[`docs/migration/legacy-research-to-tool-supplier.md`](migration/legacy-research-to-tool-supplier.md).

## Planned (next)

- **Channel reliability**: typed failure status everywhere (no more
  `failure-as-empty`), per-channel published_at metadata, citation
  canonicalization. Most of this is already in `v2026.04.25.x`.
- **Doctor / MCP health parity**: `autosearch doctor` and `mcp-check`
  must show the same channel availability that `run_channel` actually
  experiences at runtime.
- **First-use smoke test**: a `pipx install` → first query → evidence
  output flow that runs end-to-end without manual configuration.

## Considered (waiting for signal)

- **Token-by-token streaming** for the OpenAI-compat endpoint. Today's
  stream emits one role + one content chunk + `[DONE]`. True streaming
  needs `ReportSynthesizer` to become an async generator. Deferred until
  there's a real user workflow that requires it.
- **Session store TTL / GC**. `SessionStore` rows accumulate
  indefinitely. Will add `prune(older_than)` once disk usage is visibly
  a problem.
- **Public-endpoint rate limiting**. `/v1/chat/completions` and `/search`
  have no throttle today. Matters only if AutoSearch is ever deployed as
  a public-facing service rather than a personal MCP server.

## Out of scope

- Mutation testing.
- A `CONTRIBUTING.md` template — the existing `CLAUDE.md` covers
  contributor rules until there's an external contributor base.
- A "real-time research" mode — AutoSearch is a tool supplier, not an
  agent runtime.

## Versioning

CalVer (`YYYY.MM.DD.N`) — daily release sequence. The release workflow
publishes both PyPI and npm artifacts. Source-of-truth version lives in
`pyproject.toml`; `.claude-plugin/plugin.json`, `.claude-plugin/marketplace.json`,
and `npm/package.json` are kept in sync by `scripts/bump-version.sh`.
