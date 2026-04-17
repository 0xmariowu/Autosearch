---
title: "AutoSearch v2 Test Plan"
description: "Full test strategy: current state, gaps, and phased rollout"
---

# AutoSearch v2 Test Plan

## 1. Current state (snapshot)

| Layer | Files | Count | Runs real code? | Gate in CI? |
|---|---|---|---|---|
| Unit | `tests/unit/*.py` | 23 | No — LLMClient mocked via `DummyProvider`, channels are `FakeChannel` / `DemoChannel` | Yes |
| Integration | `tests/integration/*.py` | 3 | Partial — real Pipeline + real SessionStore, mocked LLM + fake Channel | Yes |
| Fixtures | `tests/fixtures/fake_channel.py` | — | — | — |
| Eval harness | `tests/eval/spike_2_trafilatura.py` | 1 | Yes — fetches real URLs via httpx, no pytest integration | Manual |
| **Smoke** (CLI subprocess / live server / MCP stdio) | — | **0** | — | **No** |
| **Real LLM** (actual provider calls) | — | **0** | — | **No** |
| **Perf / concurrency** | — | **0** | — | **No** |

**80 tests passing, all green** — but nothing proves the tool actually runs when you type `autosearch query "..."` on a real machine. Every test substitutes `LLMClient.complete` with canned Pydantic returns. There has been zero verification that:

- any of the 4 LLM providers (Claude / Anthropic / OpenAI / Gemini) actually returns valid JSON under our schema
- `autosearch query` as a subprocess produces stdout + exits 0
- `autosearch serve` binds a port, serves `/health`, serves `/v1/chat/completions`, streams SSE
- `autosearch-mcp` speaks the stdio JSON-RPC protocol any real MCP client expects
- concurrent `/search` SSE requests don't deadlock the Pipeline
- `SessionStore` on a real disk file persists across process restarts
- `DemoChannel` round-trips Evidence through `EvidenceProcessor` (BM25, SimHash) without raising
- failure paths (all providers down, network timeout, malformed LLM response) are handled without crashing

## 2. Gap analysis

### 2.1 What we have vs what we claim

`docs/delivery-status.md` claims the v2 pipeline is "shipped" for M0–M8. Every individual module has a mocked unit test. No module has been run against a real LLM. The "end-to-end pipeline" that the README advertises has never produced a single byte of real markdown from a real network request.

This is a **maturity mismatch**: we have high test count but low test honesty.

### 2.2 Concrete missing coverage

**Smoke (process-level)**

- `autosearch --version` subprocess exits 0 with correct version string
- `autosearch query "..."` subprocess with `DemoChannel` + mocked LLM env → exits 0, stdout contains `## References` and `## Sources`
- `autosearch serve --port ...` starts, `GET /health` returns 200, `GET /v1/models` returns expected JSON, then shuts down cleanly
- `autosearch-mcp` JSON-RPC handshake: `initialize` → `tools/list` → `tools/call research` works
- `/v1/chat/completions` POST with `stream=false` returns valid OpenAI response shape; with `stream=true` returns `text/event-stream` ending in `data: [DONE]`

**Real LLM (env-gated)**

- One minimal structured-output call per provider (Claude Code / Anthropic / OpenAI / Gemini) validates schema adherence
- Spike 1 execution (the harness doc exists in `docs/spikes/spike-1-auto-detect.md` but has never been run): 30 calls × 4 providers × 1 schema, fail rate < 5% per plan § 6
- Full pipeline `autosearch query "retrieval augmented generation"` with `DemoChannel` + real LLM → markdown generated, report < 30s per plan § 10

**Failure paths**

- All 4 LLM providers unavailable (no env vars, no `claude` binary) → `LLMClient()` raises a clear error
- `LLMClient.complete` retries 3× then surfaces exception
- Pipeline with a Channel that raises in `search` → handled gracefully, surfaces in `on_event`
- SessionStore with invalid path → clear error, not silent write failure
- OpenAI-compat endpoint with empty `messages` → 400 not 500

**Persistence & durability**

- `SessionStore(db_path="/tmp/.../autosearch-test.db")` (not `:memory:`), write session, close, reopen, `fetch_session` returns the row
- Large evidence list (100+ items) doesn't break BM25 or SimHash

**Concurrency**

- 10 concurrent `POST /v1/chat/completions` with mocked Pipeline don't interleave events
- 10 concurrent `POST /search` SSE requests complete independently
- MCP server handles rapid sequential `research` calls without state leakage

## 3. Proposed test pyramid

```
                         ┌──────────────┐
                         │  perf (3-5)  │  on-demand, local only
                         └──────────────┘
                      ┌────────────────────┐
                      │ real_llm (6-8)     │  nightly / on env var set
                      └────────────────────┘
                 ┌──────────────────────────────┐
                 │ smoke (8-10)                 │  CI on push to main
                 └──────────────────────────────┘
           ┌────────────────────────────────────────┐
           │ integration (15+)                      │  CI every PR
           └────────────────────────────────────────┘
   ┌──────────────────────────────────────────────────────┐
   │ unit (100+)                                           │  CI every PR
   └──────────────────────────────────────────────────────┘
```

## 4. pytest markers (register in `pyproject.toml`)

```toml
[tool.pytest.ini_options]
markers = [
    "network: tests that require network access",
    "real_llm: tests that call a live LLM API (needs ANTHROPIC/OPENAI/GOOGLE key)",
    "smoke: subprocess or live-server tests (slower but no external calls)",
    "perf: concurrency / load tests (local only)",
    "slow: tests that take > 5s",
]
```

Default CI: `pytest -m "not real_llm and not perf and not slow"`
On-push-to-main workflow: adds `smoke` to the selector
Nightly (or manual): runs `real_llm` with secrets-based env

## 5. Proposed new test files (concrete)

### Phase 1 — Smoke (CI on push, no external deps)

| File | What it proves |
|---|---|
| `tests/smoke/test_cli_version_smoke.py` | subprocess `autosearch --version` exits 0 + correct string |
| `tests/smoke/test_cli_query_smoke.py` | subprocess `autosearch query "test"` with `AUTOSEARCH_LLM=dummy` env + DemoChannel produces markdown stdout, exits 0 |
| `tests/smoke/test_server_health_smoke.py` | Boots uvicorn in bg (ephemeral port), hits `/health`, `/v1/models`, shuts down |
| `tests/smoke/test_server_chat_smoke.py` | Same boot, POST `/v1/chat/completions` (non-stream) returns valid ChatCompletionResponse |
| `tests/smoke/test_mcp_stdio_smoke.py` | Spawns `autosearch-mcp` subprocess, JSON-RPC `initialize` + `tools/list` works |

**Note**: CLI smoke needs a way to inject a fake LLM without API keys — add a `--llm-mode dummy` CLI flag or a `AUTOSEARCH_LLM_MODE=dummy` env var that routes `LLMClient` through a `DummyProvider`. This is a tiny source change, test infrastructure.

### Phase 2 — Failure paths + persistence (unit-level, CI every PR)

| File | What it proves |
|---|---|
| `tests/unit/test_llm_no_provider.py` | No env vars set + no `claude` binary → `LLMClient()` raises `NoProviderAvailable` with helpful message |
| `tests/unit/test_llm_all_retry_fail.py` | Provider.complete raises 3× → LLMClient surfaces the underlying exception |
| `tests/unit/test_pipeline_channel_error.py` | Channel.search raises → pipeline emits `on_event({type: "error", ...})` and either degrades (continues other channels) or aborts cleanly |
| `tests/unit/test_openai_compat_empty_messages.py` | POST `/v1/chat/completions` with `{messages: []}` returns 400 |
| `tests/integration/test_session_disk_durability.py` | `SessionStore("/tmp/.../test.db")`: create + write + close + reopen + fetch → round-trip ok |
| `tests/integration/test_evidence_processor_scale.py` | `EvidenceProcessor.rerank_bm25(100 evidences)` completes < 1s |

### Phase 3 — Real LLM (env-gated)

| File | What it proves |
|---|---|
| `tests/real_llm/test_provider_roundtrip.py` | Parametrized over available providers (skip when env var absent), 1 call with simple JSON schema, parse success |
| `tests/real_llm/test_pipeline_demo.py` | DemoChannel + real LLM → markdown report with ≥ 1 section + References |
| `tests/real_llm/spike_1_harness.py` | Ports the design in `docs/spikes/spike-1-auto-detect.md`: 30 × schema calls per provider, asserts fail rate < 5%, writes results back to the doc |

### Phase 4 — Perf (on-demand)

| File | What it proves |
|---|---|
| `tests/perf/test_sse_concurrency.py` | 10 concurrent `/v1/chat/completions` stream requests complete without deadlock |
| `tests/perf/test_mcp_rapid_calls.py` | 20 sequential `research` tool invocations over one MCP stdio session |
| `tests/perf/test_pipeline_large_evidence.py` | Pipeline with 500 canned Evidence items completes end-to-end < 10s |

## 6. Phased rollout

| Wave | Scope | Estimated effort | Ships with |
|---|---|---|---|
| **W1** (this PR) | Plan doc + marker registration + 1 infra change (`--llm-mode dummy`) | ~30 min | this PR |
| **W2** | Phase 1 smoke tests (5 files) + CI workflow job for smoke on push-to-main | 1 Codex wave | after W1 merges |
| **W3** | Phase 2 failure + persistence tests (6 files) | 1 Codex wave | after W2 |
| **W4** | Phase 3 real_llm tests (3 files) + nightly GH Actions workflow with secret-injected env vars | 1 Codex wave + 1 workflow file | when boss sets up API-key secrets |
| **W5** | Phase 4 perf (3 files) — optional, on-demand only, no CI gating | 1 Codex wave | lowest priority |

## 7. Success criteria

After W1–W3 land:

- CI runs **mocked unit + integration + smoke** on every PR (≤ 2 min)
- CI runs **smoke** on push-to-main (catches CLI/server/MCP process-level regressions)
- Any `autosearch` process-level surface that doesn't work fails a test, not silently in a user's terminal

After W4:

- Every night (or on-demand), we know whether real LLM providers still honor our schema
- Spike 1 gets its first real result table (currently empty in `docs/spikes/spike-1-auto-detect.md`)

## 8. Non-goals

- Channel-layer adapter tests (deferred — channel layer is paused)
- Load test under real-LLM cost (too expensive; perf runs against mocked Pipeline)
- Browser-based end-to-end tests (no browser UI ships in v2)

## 9. Follow-ups (out of this plan)

- `tests/eval/spike_2_trafilatura.py` already runs against real URLs; consider moving it under `real_network` marker + a nightly workflow so we track Chinese-site extraction rate over time
- Mutation testing (e.g. `mutmut`) to validate that tests catch real bugs, not just pass shape assertions
