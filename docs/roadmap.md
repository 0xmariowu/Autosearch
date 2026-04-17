---
title: "v2 Post-Test-Plan Roadmap"
description: "What's worth doing after TEST_PLAN waves land, with channel layer paused"
---

# v2 Roadmap — Post Test Plan

> Owner: vimala. Status: draft, waiting approval.
> Prior plans: `~/.claude/plans/autosearch-v2-dev.md` (v2.3), `docs/testing/TEST_PLAN.md` (waves 1-5 merged).

## 1. Ground state

After the test plan, `main` has:

- Pipeline M0–M8 + orchestrator wired to Cost + Session primitives
- 4 user surfaces: CLI (`query / mcp / serve`), FastAPI `/search` SSE, OpenAI-compat `/v1/chat/completions`, MCP `autosearch-mcp` stdio, Claude Code `/autosearch` slash
- 104 tests across 4 tiers (default / smoke / real_llm nightly / perf on-demand)
- `DemoChannel` placeholder; real channel adapters deferred per boss

What's missing to call v2 "real"? One blocker plus several polish items. This plan lists everything except the blocker (channel layer, paused).

## 2. Explicit exclusions

The items below are **not** on this roadmap:

- **Channel layer adapters** (海外 P0 + 中文 P0) — paused by boss. Resumes separately when unpaused; plan § 5 + § 12 already detail scope.
- **`autosearch init` channel-dep installer** (npm mcporter / xhs-cli / rdt-cli / cookie harvester / MCP service boot) — requires channel layer unpaused.
- **Plan v2.3 revision** — delivery-status.md already documents actual shipped state; plan itself doesn't need editing (spike 2 confirmed plan § 5's API + cookie paths rather than refuting them).
- **Mutation testing, CHANGELOG.md, CONTRIBUTING.md** — not worth doing until there's an external contributor base or a tagged release.

## 3. Ranked follow-ups

### P0 — real bug, fast

**R1. Pipeline channel-error event emission** — ~30 min
  - **Gap**: `Pipeline._TrackingIterationController._search` swallows `Channel.search()` exceptions via `try/except` + `structlog` log only. No `on_event({type:"error"})` emitted. Downstream consumers (CLI `--stream`, SSE `/search`, real users) see nothing when a channel breaks.
  - **Discovery**: W3 `test_pipeline_channel_error.py` had to downgrade its assertion to match current swallow-and-log behavior.
  - **Fix**: emit a structured error event from the catch block with `{channel: name, phase: "search", message: str(exc)}`. Keep the swallow (don't crash the pipeline) but surface visibility. Upgrade W3 test to assert the event is emitted.
  - **Why P0**: it's a real correctness gap our own test plan found; leaving it means our "error handling" claim is a lie.

### P1 — make `pipx install autosearch` actually usable

**R2. First v2 alpha release** — ~1 h
  - `pyproject.toml` already has `version = "0.0.1a1"` but there's no git tag, no GitHub Release, no PyPI artifact.
  - Deliver: `.github/workflows/release.yml` that triggers on `v*` tag → `python -m build` → `twine upload` to PyPI + creates GitHub Release with notes derived from commits since last tag.
  - Boss action: push a `v0.0.1a1` tag once the workflow lands.
  - **Why P1**: README's Quick Start says `pipx install autosearch`. Until this ships, that's a dead promise.

**R3. `autosearch init` minimal version (channel-agnostic parts only)** — ~half day
  - Scope (excludes channel-dep installers):
    - Detect Python 3.12+ (error with message if older)
    - Probe each LLM provider: check env var set OR `claude` binary on PATH; print a summary table of which providers are available
    - Create `~/.autosearch/config.yaml` with detected defaults (provider priority, log level, optional DB path for `SessionStore`)
    - Print next-step hint: "Run `autosearch query "your question"` to test"
  - Explicitly NOT in scope for this slice:
    - `npm install -g mcporter xhs-cli rdt-cli`
    - `pip install douyin-mcp-server mcp-server-weibo`
    - `rookiepy` cookie extraction
    - Booting any MCP service
  - **Why P1**: closes the `pipx install` → first-query loop. Channel-dep install gets added on top later when channel layer unpauses.

### P2 — polish / completeness

**R4. OpenAI-compat metadata (visitedURLs / reasoning_content)** — ~1-2 h
  - node-deepresearch `src/app.ts:L387-L824` exposes `visitedURLs`, `readURLs`, `reasoning_content` (Claude-style) in the response. Our simplified port dropped them.
  - Fill them from `PipelineResult` (evidences → URLs; pipeline's `on_event` gap reflection → `reasoning_content` block).
  - Keep backwards-compatible — new fields optional in response schema.

**R5. LLMClient provider fallback chain** — ~1 d
  - Today: `LLMClient` auto-detects the first available provider at init and sticks with it. If that provider's API is down mid-call, no recovery.
  - Add: ordered provider preference (config-driven), per-call fallback when primary raises `httpx.HTTPError` or times out, surface `fallback_count` in metrics.
  - Add cost-tracker notes when fallback used (different model → different token cost).

### P3 — nice-to-haves, defer

**R6. Real token-by-token streaming** — ~1-2 d (architectural)
  - Current `/v1/chat/completions` stream emits one role chunk + one content chunk + `[DONE]`. Spec-valid.
  - True streaming needs `ReportSynthesizer.synthesize` to become an async generator yielding section chunks, and `Pipeline.run` to thread that through. Non-trivial refactor.
  - Defer until there's a user signal that chunked stream matters for real workflows.

**R7. Session store garbage collection / TTL** — ~2-3 h
  - `SessionStore` rows accumulate indefinitely. Add a `prune(older_than: timedelta)` method + optional background task.
  - Defer until disk usage is a visible problem.

**R8. Public-endpoint rate limiting** — ~2-3 h
  - `/v1/chat/completions` + `/search` currently have no throttle. Fine for personal / localhost use. Matters if ever deployed publicly.
  - Defer; not a v0.1-alpha concern.

## 4. Proposed wave order

| Wave | Items | Cost | Gate |
|---|---|---|---|
| **R1** | Pipeline error-event emission + test upgrade | ~30 min | single PR |
| **R2** | Release workflow + first alpha tag | ~1 h | single PR + boss pushes tag |
| **R3** | `autosearch init` minimal | ~half day | single PR (one Codex wave) |
| **R4** | OpenAI-compat metadata | ~1-2 h | single PR (small Codex wave) |
| **R5** | LLMClient fallback chain | ~1 day | single PR (one Codex wave + new tests) |
| **R6–R8** | deferred until signal | — | — |

Recommended execution: **R1 → R2 → R3** in that order. R2 unblocks real install; R3 unblocks real first-run; R1 fixes known bug before either surfaces to users. R4/R5 land whenever; not on critical path.

## 5. When channel layer unpauses

At that point this roadmap interleaves with plan § 5 / § 12 (real channel impls) + `autosearch init` channel-dep layer. R3's minimal init gets extended, not rewritten.

## 6. Decision needed

- Confirm R1 → R2 → R3 sequencing
- Confirm R4/R5 as "land opportunistically" (no strict order)
- Confirm R6/R7/R8 stay deferred
