---
title: "Delivery Status"
description: "Module-by-module status of the v2 rewrite"
---

# v2 Delivery Status

Snapshot of which v2 modules have landed. All shipped modules have unit or integration tests and a 1:1 source comment on each file.

## Pipeline (M0–M8)

| Module | Status | Source |
|---|---|---|
| M0 Knowledge Recall | ✅ shipped | Self-written (node-deepresearch semantics) |
| M1 Clarify | ✅ shipped | open_deep_research/src/open_deep_research/prompts.py:L3-L41 |
| M2 Search Strategy | ✅ shipped | gpt-researcher/gpt_researcher/prompts.py:L213-L255 |
| M3 Iteration Controller | ✅ shipped | open_deep_research/src/legacy/graph.py:L235-L354 |
| M4 Trafilatura Cleaner | ✅ shipped | storm/knowledge_storm/utils.py:L685-L711 |
| M4 per-source cleaner framework | 🟡 Protocol only; real cleaners pending channel layer | Self-written |
| M5 Evidence Processor (URL dedup + BM25 + SimHash) | ✅ shipped | deer-flow infoquest_client.py:L183-L230 + rank-bm25 + simhash |
| M7 Report Synthesizer | ✅ shipped | storm outline_generation / article_generation + open_deep_research citation rules |
| M8 Quality Gate | ✅ shipped | open_deep_research/src/legacy/prompts.py:L168-L198 |

`Pipeline` orchestrator composes the above with a clarification early-exit and one quality-gate retry. Phase events are emitted through a user-supplied callback.

## Presentation

| Surface | Status | Notes |
|---|---|---|
| CLI `autosearch query` | ✅ shipped | `--mode fast\|deep`, `--top-k`, `--stream`, `--json` |
| CLI `autosearch mcp` | ✅ shipped | Alias for `autosearch-mcp` stdio server |
| CLI `autosearch serve` | ✅ shipped | `--host`, `--port` for FastAPI SSE |
| HTTP `/health` | ✅ shipped | JSON liveness |
| HTTP `/search` SSE | ✅ shipped | Streams `phase` / `iteration` / `gap` / `quality` / `finished` events |
| MCP server (FastMCP stdio) | ✅ shipped | Tools: `research(query, mode)`, `health()` |
| Claude Code `/autosearch` slash command | ✅ shipped | `commands/autosearch.md` |
| Citation rendering | ✅ shipped | Inline `[n]` + `## References` + `## Sources` breakdown |
| Progress streaming | ✅ shipped | Callback → stderr NDJSON (CLI) + SSE (HTTP) |
| OpenAI-compat `/v1/chat/completions` + `/v1/models` | ✅ shipped | node-deepresearch port; SSE chunked stream (role + content + DONE) |

## Observability & Persistence

| Module | Status | Notes |
|---|---|---|
| Cost Tracker | ✅ shipped + wired into `LLMClient` and `Pipeline` | gpt-researcher utils/costs.py |
| Session SQLite store (3-table schema) | ✅ shipped + wired into `Pipeline` | crawl4ai async_database.py pattern + self-written schema |

## Channels

Deferred — real adapters will land after the channel layer unpauses. `DemoChannel` ships today as a placeholder implementing the `Channel` Protocol so the pipeline runs end-to-end.

Planned roadmap:

- Overseas P0 (12–15): arxiv / DDGS / GitHub repos+issues / Reddit / HackerNews / StackOverflow / YouTube / ProductHunt / Semantic Scholar / HuggingFace / npm / PyPI
- Chinese P0 (6): 小红书 / B 站 / 微信公众号 / 知乎 / 抖音 / 微博
- Chinese P1 (4–6): CSDN / 掘金 / 36kr / 雪球 / 小宇宙 / 快手

## Known Deferred Items

- `autosearch init` dependency orchestrator — channel-dep-heavy, deferred until channel layer unpauses.
- Per-source HTML cleaners for specific Chinese sites — deferred (channel layer owns the fetch path).

## Test Coverage

- 131 tests across 4 tiers: unit + integration (default CI), smoke (push-to-main), real_llm (nightly, needs secrets), perf (on-demand)
- 0 ruff issues, consistent ruff format
- Pre-commit hook enforces author identity + PII/codename scan
- Pre-push rebases on main and runs the default selector (`not real_llm and not perf and not slow and not network`) in ~2 s
- See [`docs/testing/TEST_PLAN.md`](testing/TEST_PLAN.md) for the full pyramid

## Related Docs

- Test pyramid: [`docs/testing/TEST_PLAN.md`](testing/TEST_PLAN.md)
- Channel matrix: [`docs/channels.mdx`](channels.mdx)
- Migration guide: [`docs/migration/legacy-research-to-tool-supplier.md`](migration/legacy-research-to-tool-supplier.md)
