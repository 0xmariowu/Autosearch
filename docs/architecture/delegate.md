# Delegate (`run_subtask`) Architecture Contract

> Status: enforced as of P0-4 fix (`fix/p0-4-delegate-channel-runtime`).
> `autosearch.core.delegate.run_subtask` is the only public entry for
> parallel multi-channel search dispatch.

## Why this exists

`delegate_subtask` is the MCP tool that fans a single query out to
several channels in parallel. Without discipline, three failure modes
appear:

1. **Cost blowout.** A caller passes the same channel name twice
   (intentional or accidental) and a paid API gets billed twice for
   identical work.
2. **Burst spend.** A caller passes 50 channels and they all fire at
   once — no rate limiter, no concurrency cap, no protection against a
   bug that explodes the channel list.
3. **Stale rate-limit / cost state.** If `delegate_subtask` builds its
   own `Channel` objects via `_build_channels()`, the per-process
   rate limiter and cost tracker that `run_channel` and `doctor` share
   are bypassed — quota is invisible across delegate calls.

## Contract

`run_subtask(task_description, channels, query, max_per_channel=5, *,
channel_runtime: ChannelRuntime, _search_fn=None)`.

### Required: `channel_runtime` is a keyword-only required argument

No default. The caller MUST pass the shared `ChannelRuntime`
(`get_channel_runtime()`) so the rate limiter, health tracker, and cost
tracker in that runtime accumulate across every search — `run_channel`,
`delegate_subtask`, `doctor`. There is no per-call runtime construction.

### Order-preserving dedupe

`channels = list(dict.fromkeys(channels))` runs at function entry. The
same channel name passed N times runs once, in the position of its
first occurrence. Cost stats and evidence are reported per name, so
dedupe also ensures `budget_used[name]` reflects the actual call count.

### Concurrency cap

`asyncio.Semaphore(N)` wraps every `_search_fn` call. Default `N=5`;
override via `AUTOSEARCH_DELEGATE_CONCURRENCY` env var (parsed as int;
invalid value silently falls back to 5; values <1 clamped to 1).

### Test injection

`_search_fn` (private) lets tests inject a synthetic search function
that bypasses real channel lookup. When `_search_fn` is provided,
`channel_runtime` is unused but still required by signature — forces
every test call site to think about runtime ownership.

## Wiring

- `autosearch/mcp/server.py:delegate_subtask` (the MCP tool entry):
  fetches `runtime = get_channel_runtime()` and passes
  `channel_runtime=runtime`.
- No other code path constructs a `Channel` set for delegate. Adding
  one is a contract violation.

## Coverage

- `tests/unit/test_delegate.py`:
  - `test_run_subtask_requires_channel_runtime` — signature-level
    check, no default for the kwarg.
  - `test_run_subtask_propagates_runtime_rate_limit` — `RateLimited`
    raised from `_search_fn` becomes `failed_channels[].status =
    "rate_limited"`.
  - `test_run_subtask_dedupes_repeated_channels` — `[a, b, a]` runs
    each name once.
  - `test_run_subtask_respects_concurrency_cap` — under
    `AUTOSEARCH_DELEGATE_CONCURRENCY=2`, observed in-flight count
    never exceeds 2.
- `tests/unit/test_mcp_delegate.py::test_delegate_subtask_passes_shared_runtime`
  — MCP tool call captures the runtime kwarg and asserts it `is`
  `get_channel_runtime()`.

Source: `docs/security/autosearch-0426-p0-deep-scan-report.md` § P0-4.
