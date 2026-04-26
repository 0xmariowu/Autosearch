# Changelog

## 2026.04.26.1 — 2026-04-26

- **P0 / P1 security + reliability rollup (10 PRs).** Closes the
  `reports/autosearch-p0-fix-plan.md` punch-list:
  - **npm wrapper no longer fakes success on missing binary.** ENOENT /
    EACCES / EPERM during the post-install spawn now exits non-zero with
    a fix hint; `scripts/install.sh` persists `~/.local/bin` to a real
    shell profile (zsh/bash; fish/csh skip with a warning instead of
    writing bash syntax to `.bashrc`); install passes `--no-init` so
    bare `npx autosearch-ai` no longer auto-runs init. (#427)
  - **Cloud transcription stops leaking local paths.** OpenAI / Groq
    transcribe modules route `source` and `audio_path` through a new
    `redact_path_for_output()` (basenames for local files, redacted-URL
    form for URL inputs); failure-path `extra` fields are redacted
    before merge; Windows drive-letter paths detected correctly. (#428)
  - **bcut transcribe redacts signed URLs.** All log call sites and
    structured output's `source` / `reason` now walk
    `redact_url` / `redact`; `LOGGER.exception` swapped for redacted
    `LOGGER.warning` so tracebacks no longer echo the signed URL; empty
    or non-string `source` is guarded before redaction. (#429)
  - **Per-channel timeout + cooldown in delegate.** `run_subtask`
    accepts `per_channel_timeout` (env override
    `AUTOSEARCH_PER_CHANNEL_TIMEOUT_SECONDS`); timeout is mapped to
    `transient_error`, recorded against executable channel methods so
    cooldown actually triggers, and tracked with the real elapsed
    latency. `asyncio.CancelledError` propagates and exception types
    are narrowed instead of `noqa`-suppressed. (#430)
  - **Atomic write to `~/.config/ai-secrets.env`.** New
    `secrets_store.write_secret(...)` does fcntl-locked
    read-modify-write with `fsync` + `os.replace`, preserving comments,
    ordering, and unknown lines. `fcntl` import is now optional so the
    module imports on Windows; newline / control-character keys + values
    are rejected. CLI `configure --replace` and the cookie-write path
    both route through the helper. (#431)
  - **e2b reports redact scenario error text.** `summary.md`,
    `results.json`, and the comprehensive transcript writer all walk
    `redact()` before disk. (#432)
  - **`scripts/e2b/run_validation.py --output` no longer rmtree's
    arbitrary directories.** Default behaviour creates a
    `run-<timestamp>` subdir; `--clean-output` is required to delete and
    only inside the repo's `reports/` root, with both sides `.resolve()`d
    to defeat symlink escape. E2B test stubs register proper `__path__`
    so nested submodule imports work. (#433)
  - **Legacy `research()` MCP path redacts exception text.** Same
    sanitisation as the new pipeline. (#434)
  - **CLI top-level error redact.** `_exit_query_failure()` redacts
    before stderr / `--json` envelope. (#435)
  - **kr36 channel switched to working JSON gateway endpoint.** Old
    endpoint returned 404; new code reads article fields from the nested
    template payload, skips empty fallback values, and gracefully maps
    upstream failures to `transient_error` with an actionable
    `fix_hint`. Legacy HTML fallback now driven by an explicit feature
    flag instead of monkeypatch identity. (#436)
- **Companion infra fixes shipped alongside the rollup.**
  `.gitleaks.toml` gained allowlists for placeholder usernames + `.local`
  POSIX paths used in the new install / wrapper tests; a regression in
  `papers/via_paper_search.py` per-source timeout (caused by the F006a
  exception narrowing) was repaired so the existing skip-slow-source
  test still passes.

## 2026.04.25.11 — 2026-04-26

- **No more signed-URL secret leaks from fetch / video tools.** `autosearch.core.redact` gains `redact_url(url, *, strip_query=True)`; six MCP-visible tools (`fetch-jina`, `fetch-crawl4ai`, `fetch-firecrawl`, `video-to-text-openai`, `video-to-text-groq`, `video-to-text-local`) now sanitize URLs at every output boundary (return fields + log calls). Previously a user passing `https://example.com/foo?access_token=SECRET&X-Amz-Signature=...` would see the credential echoed back in the tool result and structured logs. A new integration suite (`tests/tools/test_url_leak_prevention.py`) parametrizes 6 leak scenarios and locks the contract. Closes P0-2 from `docs/exec-plans/active/autosearch-0425-p0-scan-report.md`.
- **Rolls up #406** (CN→EN cleanup residuals — workflow comment, e2b harness stdout, scenario docstring) and syncs `pyproject.toml` to `2026.04.25.11` (the bump in #406 missed this file, leaving `test_version_consistency` failing on main).

## 2026.04.25.10 — 2026-04-25

- **`autosearch query "..." --json` is now parseable.** The CLI was leaking structlog `[info]` lines onto stdout, so piping into `jq` failed with "Extra data". Logs now route to stderr (matching the MCP path), and a fresh-install smoke test (`tests/smoke/test_first_use_flow.py`) locks the contract in: markdown brief + JSON envelope + `--help` all pass without network or LLM keys, closing the P1-7 first-use loop from the production-critical-fix-plan-v2.
- **Public-repo hygiene rollup.** Bumps in PRs #395–#403 were intentionally deferred per the "bump once after a merge batch" rule; this release ships them: install paths unified to npx / AI-agent / curl with `--yes` removed (#395); internal docs + runtime experience stripped from HEAD (#396); committer / husky / gitleaks tooling layer (#397); `public_repo_hygiene.py` + tests + npm/CI entrypoints (#398); gitleaks split into public/private notes (#399); CLAUDE.md cleanup + stale validation/bench/plan docs removed (#400); 5 user-facing docs rewritten to drop internal voice (#401); "boss" wording removed from skill READMEs + `public-repo-policy.md` added (#402); history-exposure assessment + verification procedure (#403).

## 2026.04.25.9 — 2026-04-25

Hotfix on top of `.25.8`. PR #387 wired `pre_release_check.py` into
the release workflow as a blocking step, but the checklist bundles
dev-sanity checks (channel experience/patterns.jsonl bootstrap state,
Gate 12 bench results) that fail when those artifacts haven't been
generated for a given commit. `.25.8` release blocked at this step
before any real release work happened.

Removed the workflow step. `pre_release_check.py` remains as a local
developer tool — run `python scripts/validate/pre_release_check.py`
before tagging. The checklist itself is fine; just shouldn't be a
release-pipeline gate without separating release-blocking from
dev-sanity tiers.

`.25.9` ships the full `.25.8` content (Gate 12 commit binding +
label-based open-PR gating from #387) plus this workflow unwire.

## 2026.04.25.8 — 2026-04-25

Ships PR #387 — the Gate 12 / pre-release-check / open-PR-label
work that was open while the `.25.4`–`.25.7` release-pipeline
hotfixes landed.

- `scripts/bench/judge.py`: Gate 12 stats now include `commit_sha`,
  `version`, `generated_at`, `test_config` provenance.
- `scripts/validate/pre_release_check.py`: requires Gate 12
  `commit_sha == HEAD`; supports `--allow-stale-gate12` override;
  open PR gate switched from "any open PR blocks" to
  "PR labeled `release-blocker` blocks".
- `.github/workflows/release.yml`: pre-release check is now a
  release-job step.

## 2026.04.25.7 — 2026-04-25

GitHub Release auto-creation hotfix on top of `.25.6`. The
`.25.6` workflow successfully published to PyPI and npm using the
PyPA action, but the `create-github-release` job lacked
`actions/checkout` — `gh release create` failed with "fatal: not a
git repository" because the runner had no `.git` context. The GH
Release was created manually for `.25.6`. This release adds the
missing checkout step so future releases auto-create the GH Release
end-to-end.

`.25.6` content (already on PyPI / npm):
- All `.25.3`–`.25.5` rollup (twelve PRs from the production-critical
  sweep audit)
- License metadata + `setuptools>=80` / `twine>=6.1` / PyPA action

## 2026.04.25.6 — 2026-04-25

Third (and hopefully final) release-pipeline hotfix. `.25.4` and `.25.5`
both pinned `twine>=6.1` but still failed at upload with the same
`InvalidDistribution: unrecognized or malformed field 'license-file'`
error — even though local `twine check --strict` passed on identical
wheels. Cause appears to be GitHub's `ubuntu-latest` runner shadowing
the user-installed twine with a system-installed older pkginfo on the
fallback path.

Switched the publish-pypi step to `pypa/gh-action-pypi-publish@release/v1`,
the official PyPA action. It manages the upload toolchain internally
and is the recommended path. No more manual twine version pinning.

Same content as `.25.5` (which had `.25.3` content + license metadata
hotfix + publish-pypi twine pin). Just the action change.

## 2026.04.25.5 — 2026-04-25

Second hotfix attempt for the `.25.3`/`.25.4` PyPI publish failure.
`.25.4` pinned `twine>=6.1` in the **build** job but missed the
**publish-pypi** job which had its own separate `pip install twine`
without the pin — so the upload step grabbed older twine and rejected
metadata-2.4 license-file/license-expression fields. Both `.25.3` and
`.25.4` tags exist on GitHub but neither shipped to PyPI / npm / 
GitHub Release.

This release pins `twine>=6.1` in the publish-pypi job too. Same
content as `.25.4` (which had all `.25.3` content + license metadata
hotfix) — just the second half of the workflow fix.

## 2026.04.25.4 — 2026-04-25

The "release plumbing hotfix" release — `2026.04.25.3` was tagged and
the GitHub workflow ran, but `twine upload` rejected the wheel with
`Invalid distribution metadata: unrecognized or malformed field
'license-file'`. Older setuptools (75-77 range) wrote a metadata 2.4
field that older twine clients didn't accept. The PyPI / npm /
GitHub Release for `.25.3` never actually shipped.

This release contains all `.25.3` changes (the "production-critical
sweep" — see the `.25.3` entry below for the full list of 21 features
from the 5-agent audit) plus the release-plumbing hotfix:

- `pyproject.toml`: explicit `license = "MIT"` (PEP 639 SPDX) and
  `license-files = ["LICENSE"]`. `[build-system].requires` bumped to
  `setuptools>=80` so build environments use a clean metadata-2.4
  generator.
- `.github/workflows/release.yml`: pin `--upgrade build>=1.2`,
  `twine>=6.1`, `setuptools>=80` in the build job. Twine 6.1+ knows
  about metadata 2.4 license-file fields.

Verified locally with `python -m build` + `twine check dist/*` after
the fix (both wheel and sdist PASS).

## 2026.04.25.3 — 2026-04-25

The "production-critical sweep" release — twelve PRs landing 21
features from a 5-agent audit. Two security P0s, one supply-chain
P0, three secrets-hygiene P0s, plus channel reliability, release
plumbing, docs alignment, report quality, and observability.

**Security**
- `scripts/install.sh --version` now validates against a PEP 440
  allowlist and runs install commands as argv arrays — the previous
  `eval` path was a real command-injection vector via the
  `curl | bash` install URL.
- Bearer-token redaction now covers the full token character set
  (`+/=._-~` plus base64url and JWT). Earlier regex stopped at the
  first special char and leaked the tail of the token.
- `secrets_store.inject_into_env()` no longer overwrites a key the
  parent process / orchestrator set explicitly. Tracks file-injected
  keys and only refreshes those it already owns.
- `ClaudeCodeProvider` subprocess gets a minimal allowlisted `env`
  (PATH/HOME/SHELL/TERM/USER/LANG/LC_*/TMPDIR plus
  ANTHROPIC_*/CLAUDE_CODE_*/XDG_*) instead of inheriting the full
  parent environment with unrelated secrets like `TIKHUB_API_KEY`.

**Channel reliability**
- `package_search` / `xueqiu` / `discourse_forum` no longer return
  `[]` when upstream fails — typed errors propagate. Aggregated
  channels distinguish "all sources failed" from "partial failure".
- All TikHub channels now raise `PermanentError` on item-level
  schema drift (`zhihu` / `xiaohongshu` / `instagram` / `weibo` /
  `wechat_channels`) instead of silently returning `[]` when items
  are present but every one fails to parse — caught field renames
  TikHub deploys without warning.
- `tieba` Baidu safety-verification (captcha) page is now classified
  as `TransientError`, not `ChannelAuthError`. Users no longer told
  to "fix your auth" for platform-side anti-scrape.
- `xiaohongshu/SKILL.md` `via_signsrv.requires` now matches the env
  name `autosearch login xhs` actually writes (`XHS_COOKIES`).
  Login worked, runtime worked, but the requires gate referenced a
  legacy name nothing wrote.
- TikHub hosted-proxy mode actually works end-to-end now.
  PR #366 added the requires shim; this release adds the
  corresponding `KNOWN_ENV_KEYS` entries so `probe_environment()`
  reports the proxy vars and the shim can fire.

**MCP runtime**
- `run_channel` now distinguishes `transient_error`,
  `channel_unavailable`, and `channel_error` (was all
  `channel_error`). Host agents can backoff vs. retry vs. give up
  with the right strategy.
- `delegate_subtask` returns `failed_channel_details` per failed
  channel (status / reason / fix_hint / unmet_requires) instead of
  squashing into a flat name list. Legacy `failed_channels` field
  retained for compat.
- Channel health cooldown distinguishes auth/permanent failures
  (long cooldown — waiting won't help) from transient/rate-limited
  (short cooldown — try again later).
- Experience layer no longer writes raw user query strings to
  `~/.autosearch/experience/.../patterns.jsonl`. Replaced with
  `query_shape` (length bucket, language detection) so summaries
  capture pattern info without leaking PII.

**Report quality**
- `consolidate_research` preserves `published_at` when rebuilding
  Evidence (was dropped, breaking time-sensitive reports). Heading
  renamed from "Top findings" to "Top evidence snippets" — these
  are raw excerpts, not synthesized findings.
- `citation_index` canonicalizes URLs before dedupe (strip utm_*,
  fbclid, gclid, fragment, trailing slash, arXiv version suffix).
  Same source no longer gets multiple citation numbers.

**Release plumbing**
- `.claude-plugin/marketplace.json` `metadata.version` and
  `plugins[0].version` are now synced by `bump-version.sh` and
  validated by `check_version_consistency.py`. Official Claude
  plugin tag gates would have failed on the drift.
- `release.yml` requires PyPI publish success before npm publish —
  no more npm-only releases when `PYPI_API_TOKEN` is missing.
  `npx autosearch-ai` users always have a matching Python package.
- `release-gate.sh` now verifies `.venv/bin/autosearch --version`
  and `python -m autosearch.cli.main --version` match
  `pyproject.toml` via PEP 440 normalization. Catches stale
  editable-install console scripts that previously slipped past.

**Docs**
- `docs/install.md` Claude Code + Cursor config examples use the
  correct `mcpServers.autosearch` shape (was a top-level
  `"autosearch"` key that doesn't work).
- `docs/mcp-clients.md` required-tools table matches
  `_REQUIRED_MCP_TOOLS`; `delegate_subtask` listed as required;
  `health` clarified as helper. `run_channel` schema dropped
  non-existent `method_id`, added `rationale`. `research` correctly
  documented as opt-in via `AUTOSEARCH_LEGACY_RESEARCH=1`.

**Testing**
- Live coverage extended to seven free production-critical channels
  (`package_search` / `openalex` / `crossref` / `dblp` / `reddit` /
  `google_news` / `discourse_forum`). Added `flaky_live` marker for
  anti-scrape-prone channels (currently `tieba`); nightly default
  excludes them so platform-side captcha doesn't gate CI.

## 2026.04.25.2 — 2026-04-25

The "sixth-pass channel-error" release — two more bugs from the
post-`.25.1` audit round.

- **TikHub hosted-proxy mode now actually works.** PR #364 taught
  `TikhubClient` to run in proxy mode (`AUTOSEARCH_PROXY_URL` +
  `AUTOSEARCH_PROXY_TOKEN` instead of `TIKHUB_API_KEY`), but every
  TikHub channel's `SKILL.md` still hardcodes
  `requires: [env:TIKHUB_API_KEY]`, so the MCP boundary's requires
  check returned `unmet_requires=["env:TIKHUB_API_KEY"]` and every
  TikHub channel surfaced `status=not_configured` for proxy users.
  `ChannelRegistry._resolve_requires` now treats `env:TIKHUB_API_KEY`
  as satisfied when both proxy vars are present. TikHub-specific shim,
  documented inline; other `env:` tokens unaffected.
- **Schema drift no longer hides at intermediate dict levels.** The
  earlier audits closed the `invalid_payload_shape` hole at the final
  `items` / `cards` level, but the navigation above it still used
  `payload.get("data", {})` with dict defaults. When `data` was
  missing or the wrong type, the default `{}` silently fell through,
  the next `.get()` returned `[]`, and the final shape check saw a
  valid (empty) list and skipped the raise — schema drift masqueraded
  as a legitimate empty result. Four channels (`zhihu`, `xiaohongshu`,
  `instagram`, `weibo`) now check `isinstance(d, Mapping)` at every
  nesting level and raise `PermanentError` on mismatch.

## 2026.04.25.1 — 2026-04-25

The "fifth-pass channel-error" release — three more audit rounds on
top of v8/v9/v10 caught the last remaining paths where upstream
failures masqueraded as "no results", plus a P0 MCP stdio bug that
was silently corrupting JSON-RPC for every client.

- **MCP stdio JSON-RPC was being polluted by structlog on stdout.**
  `autosearch-mcp` runs `transport="stdio"` (stdout = JSON-RPC
  channel), but structlog's default `PrintLoggerFactory` writes log
  lines to stdout. Any `LOGGER.warning(...)` inside a channel during a
  `run_channel` call corrupted the stream — clients silently failed or
  dropped messages. `autosearch/mcp/cli.py` now configures structlog
  to `WriteLoggerFactory(file=sys.stderr)` at the start of `main()`.
  The CLI entry point is unaffected — CLI users still see logs on
  stdout for their terminal. Regression smoke test spawns a real
  `autosearch-mcp` subprocess, triggers a log-producing code path, and
  asserts every non-empty stdout line parses as valid JSON-RPC.
- **TikHub proxy-token misconfiguration surfaced as `no_results`.**
  When `AUTOSEARCH_PROXY_URL` was set but `AUTOSEARCH_PROXY_TOKEN` was
  missing, `TikhubClient()` raised `ValueError` which every channel
  swallowed as `return []`. The `except ValueError` safety net was
  labeled "redundant" (because SKILL.md requires catches the
  `TIKHUB_API_KEY` case) but `PROXY_TOKEN` isn't in any requires list,
  so the net was the primary handler and silently ate a real auth
  failure. Now raises `ChannelAuthError` which surfaces as
  `status="auth_failed"` with a fix hint pointing at
  `autosearch configure AUTOSEARCH_PROXY_TOKEN`.
- **Eight more TikHub channels raise on schema drift instead of
  returning `[]`.** Follow-up audits caught the channels missed by
  earlier passes — `bilibili` / `zhihu` / `douyin` / `tiktok` /
  `kuaishou` / `instagram` / `weibo` / `wechat_channels` (the
  unambiguous `data not a Mapping` branch). When TikHub changes
  payload shape on any of these, the MCP client now gets
  `status="channel_error"` with the drift reason instead of a fake
  empty result. `wechat_channels` keeps a noted-ambiguous path
  (`if not items: return []`) because the recursive `docID` scanner
  can't distinguish schema drift from a legit zero-result search — a
  comment flags this for future revisit.
- **Docs/code drift cleaned up.** `docs/mcp-clients.md` now lists
  `auth_failed` and `budget_exhausted` in the `run_channel` status
  table (they've been emitted since v8 but the doc never caught up)
  and removes the fictional `retry_after` field from the troubleshooting
  section — `ChannelToolResponse` has never had that field.
- **Test-isolation fix.** `tests/unit/test_e2b_orchestrator_imports.py`
  registered loaded modules under bare stdlib names
  (`sys.modules["secrets"]`), hijacking stdlib for every later test.
  This silently broke `tests/channels/ddgs/test_api.py` in the full
  test run. Prefixed registration name to avoid the collision.

## 2026.04.24.10 — 2026-04-25

The "fourth-pass fallback" release — seven more paths that masqueraded
upstream failures as "no results", surfaced by a follow-up audit of the
v8 fixes.

- **XHS 300011 account-flag raise was eaten by an outer `try/except Exception: pass`.** The v8 release added `raise ChannelAuthError` for the account-restricted case but the raise lived inside the health-check `try` block, so the typed error was swallowed and the channel still returned `[]`. Restructured the health check so the raise fires outside the swallow. Regression test added.
- **`ChannelAuthError` no longer short-circuits the channel fallback chain.** It inherits `PermanentError`, so the registry's `except PermanentError: raise` was re-raising it immediately — the paid TikHub backup never got a chance to run when the primary method's cookie was bad. Added a dedicated `except ChannelAuthError` branch that records health-failure, stashes the error in `last_retryable`, and continues to the next method. If every method exhausts, `last_retryable` still surfaces so MCP reports `auth_failed`.
- **TikHub payload-shape drift (Twitter, Xiaohongshu) now raises `PermanentError`.** Two `return []` paths were masking schema changes at the provider as silent empty results. Now surfaces as `channel_error` so the user knows to file a bug.
- **v2ex / kr36 broad `except Exception: return []` converted to `raise_as_channel_error`.** HTTP 5xx, network errors, and schema drift were all collapsed into a single fake empty result. Now get classified into `TransientError` / `PermanentError` / `RateLimited` / `ChannelAuthError` by the shared adapter.
- **`npx autosearch-ai --version` runs the version-skew check.** The `--version` short-circuit was returning before `checkVersionAlignment()` could fire, so users filing bugs never saw the wrapper/CLI drift warning the v8 release added.
- **`scripts/validate/test_experience_e2e.py` uses a real bundled channel.** The fake `CHANNEL = "test-experience-channel"` caused `_runtime_skill_dir` to early-return; `patterns.jsonl` was never written and the script was always red with `FileNotFoundError`. Now uses `github` (temp `AUTOSEARCH_EXPERIENCE_DIR` keeps the real runtime clean).

## 2026.04.24.9 — 2026-04-24

The "third-pass diagnostic" release — six follow-up bugs the v8 audit
caught that the previous batch missed.

- **YouTube failures stop hiding as `no_results`.** A separate `except httpx.HTTPStatusError` branch in `youtube/data_api_v3.py` was logging "auth_failed" but still returning `[]`, so 401 / 403 / 429 / quota-exhausted looked identical to "no matching videos". Now propagates through the typed-error classifier — same pattern as every other channel.
- **xiaohongshu / bilibili / linkedin: inner `return []` defeated the fallback chain.** The registry's fallback chain is supposed to try `via_tikhub` when the primary method dies, but it treats `[]` as success and stops. Three channels had inner `except: return []` that swallowed real failures (signsrv outage, WBI salt fetch failure, Jina HTTP error). All converted to typed-error raises. XHS code 300011 ("account flagged") now raises `ChannelAuthError` with the right `autosearch login xhs` fix hint.
- **TikHub 401 → `auth_failed`, 402 → new `budget_exhausted` status.** A stale `TIKHUB_API_KEY` (HTTP 401) used to surface as `channel_error` because `_error_for_status` lacked a 401 case. And 402 ("top up your wallet") was lumped into `rate_limited`, which prompted the agent to wait-and-retry instead of telling the user to refill. Distinct typed error `BudgetExhausted` now produces `status="budget_exhausted"`.
- **`scripts/validate/run_validation.py` excludes network markers.** A tieba/twitter network blip would kill the whole release-validation run because the script ran plain `pytest -x -q --ignore=tests/perf` with no marker filter. Fixed.
- **`scripts/validate/test_experience_e2e.py` uses the v2 runtime path.** It used to patch `_SKILLS_ROOT`, but runtime experience writes resolve via `AUTOSEARCH_EXPERIENCE_DIR` — so the test was reading from the wrong file. Fixed.
- **Release gate catches `uv.lock` drift.** New `uv lockfile freshness` step in `scripts/release-gate.sh` runs `uv lock --check`. Without this gate, `uv.lock` could lag pyproject for days; any `uv run` would silently rewrite it and pollute the working tree. Fixed (and ran `uv lock` to sync to v8 → v9).
- **`npm` wrapper warns on Python-CLI version skew.** It used to accept any installed `autosearch` regardless of version. Now compares the wrapper's `year.month.day` prefix against the installed CLI and prints an upgrade hint when they diverge — so users with a stale Python install don't silently run an old CLI.

## 2026.04.24.8 — 2026-04-24

The "every channel stops lying about success" release — finishes the github
pilot from `2026.04.24.7` across all 30+ channel adapters.

- **Channels propagate typed failures.** Every channel (TikHub-shared and
  direct-HTTP alike) now turns network errors / 401-403 / 429 / parse failures
  into typed exceptions (`ChannelAuthError`, `RateLimited`, `TransientError`,
  `PermanentError`) that the MCP boundary maps to distinct `run_channel`
  statuses. A YouTube key gone bad surfaces as `auth_failed`; a TikHub
  budget-exhausted surfaces as `rate_limited`; a network blip surfaces as
  `channel_error`. Real empty results still come back as `no_results`.
- **arxiv specifically:** an empty atom feed is now a quiet `[]` (legitimate
  "no matches"). `ArxivRateLimitError` raises `RateLimited` and bozo / parse
  errors raise `PermanentError`, so retry logic + circuit breaker can react
  to the right thing.
- **Two new helpers** in the public API: `autosearch.channels.base.raise_as_channel_error(exc)` for direct-HTTP channels, and `autosearch.lib.tikhub_client.to_channel_error(exc)` for TikHub-routed ones. New channel implementations only need to call the right helper from their broad except block.

## 2026.04.24.7 — 2026-04-24

The "second-pass diagnostic" release — six follow-up bugs the v6 audit caught
that the original fix-plan missed.

- **Channels stop lying about success.** A 401 / 403 / 429 / schema change used to come back from `run_channel` as `status="no_results"`, indistinguishable from "nothing matched your query". New typed exceptions (`ChannelAuthError`, plus the existing `RateLimited`) propagate from channel adapters to the MCP boundary, where `run_channel` now surfaces `status="auth_failed"` / `"rate_limited"` / `"channel_error"` distinctly. github channel piloted; remaining 30+ adapters migrate in follow-up PRs. (#353)
- **`autosearch configure --replace KEY` actually reaches the running MCP.** Previously the file was rewritten but the long-running process kept the stale `os.environ[KEY]` it had injected on first load, because `inject_into_env()` skipped any key already in env. New `force=True` mode wipes file-injected values on every fingerprint-triggered runtime rebuild; user-explicit `KEY=… autosearch …` overrides still win. (#351)
- **`autosearch configure` and `autosearch login` honour `AUTOSEARCH_SECRETS_FILE`.** Both used to write to the hardcoded `~/.config/ai-secrets.env` while the runtime read from `secrets_path()` — containers, CI, and multi-user installs ended up writing to A and reading from B. Both call sites now use `secrets_path()`. (#351)
- **Cookie writes don't ride bare in shell history.** `autosearch login --stdin` added (pipe the cookie in); `--from-string` kept for back-compat but emits a deprecation warning + recommends `--stdin`. `_write_cookie_to_secrets` now `chmod(0o600)` after write so cookies aren't world-readable on shared boxes. (#351)
- **`npx autosearch-ai` works on Windows.** The wrapper used to hardcode `bash -c "curl … | bash"`. It now picks an installer based on `process.platform`: pipx → `py -3.12 -m pip --user` → `python -m pip --user` on Windows; the existing curl path on macOS / Linux. `--help` and `--version` short-circuit before the install probe so users can inspect without triggering a y/N prompt. (#352)
- **`scripts/validate/check_mcp_tools.py` and the perf test follow the v6 contract.** Both still expected the deprecated `research` tool in the default registration list (which v5 made opt-in). The validate script now asserts research is NOT in the default list AND reappears under `AUTOSEARCH_LEGACY_RESEARCH=1`; the perf test sets the env before constructing the server. (#350)

## 2026.04.24.6 — 2026-04-24

The "six bugs caught by the product diagnostic" release. All 6 items in
`docs/exec-plans/active/autosearch-0424-product-diagnostic-fix-plan.md`
are fixed; each landed as a separate minimal-change PR with regression tests.

- **Long-running MCP processes pick up `autosearch configure NEW_KEY` without restart.** The shared `ChannelRuntime` now computes a cheap fingerprint (secrets-file mtime + presence of 20 channel-relevant env keys) on every `get_channel_runtime()` call. When the user adds a new key while Claude Code / Cursor is open, the runtime rebuilds and re-injects secrets into the env, so `run_channel("youtube")` no longer disagrees with `doctor` in the same process. (#348)
- **`autosearch doctor` and `autosearch init --check-channels` agree on the count.** They used to report 37/40 vs 38/40 because they ran two independent availability pipelines; init now delegates to `doctor.scan_channels` as the single source of truth. (#346)
- **`consolidate_research` no longer marks every item as `unknown source`.** `Evidence.to_context_dict()` writes the channel name under `source`; the compressor now reads either `source` or `source_channel`. Cross-channel grouping and citation tools work again. (#344)
- **`recent_signal_fusion` actually ranks by date.** `Evidence` carries an optional `published_at` field; `to_context_dict()` emits it as ISO 8601; `arxiv` channel pilots the field by parsing the feed's `<published>` tag. Other channels can opt in incrementally. (#345)
- **`citation_*` and `loop_*` MCP tools return structured errors on invalid IDs.** Previously a bad `index_id` / `state_id` raised a FastMCP `ToolError` and crashed the host agent's workflow. Now agents get `{"ok": false, "reason": "invalid_index_id" | "invalid_state_id"}` and can recover. (#347)
- **Smoke test asserts the v2 default tool list, not the deprecated `research` tool.** v2026.04.24.5 hid `research` by default but the stdio smoke test still expected it; CI red on every push. Fixed. (#343)

## 2026.04.24.5 — 2026-04-24

The "trim, gate, and stop tempting LLMs" release.

- **The deprecated `research` MCP tool no longer registers by default.** Previously it shipped on every server start and only returned a deprecation response when called — but the attractive name still tempted host LLMs to pick it over the v2 trio. Default tool count drops from 24 → 23. Set `AUTOSEARCH_LEGACY_RESEARCH=1` to opt in if you really need it; the behavior in opt-in mode is unchanged.
- **`scripts/install.sh` now supports `--dry-run`, `--no-init`, and `--version`.** Enterprise users can preview every command before piping the script into bash, CI can run unattended without the interactive `autosearch init`, and you can pin a specific release (`--version 2026.04.24.5`) instead of always taking latest. Default behavior is byte-identical when no flags are passed.
- **Windows CI now exercises the v2 runtime experience path.** The `cross-platform.yml` workflow's experience-layer step was still mutating `_SKILLS_ROOT` (v1 contract); it now sets `AUTOSEARCH_EXPERIENCE_DIR` and asserts writes against the real runtime path so a Windows-specific path-handling regression actually trips a check.
- **E2B test matrices stop importing modules that were removed in 2026.04.24.4.** `matrix.yaml` shipped-imports list dropped 5 deleted module names; `matrix-extensions.yaml`'s F112 channel-failure-isolation phase removed (covered by unit tests against `ChannelRuntime`); `roadmap_r1_r5_commits_exist` task removed; `tests/e2b/bench/single_channel_bench.py` deleted (132-line v1 bench whose import target no longer exists). Net **-269 / +3 lines**.
- **Two new package-content guards**: `tests/unit/test_package_contents.py` now also fails the release if any channel ships a seed digest at the legacy `<skill>/experience/experience.md` path (the runtime loader only checks the top-level `<skill>/experience.md`, so subdir variants were silently dead). Caught and removed `linkedin/experience/experience.md` + `xueqiu/experience/experience.md` 1-byte placeholders that had been quietly riding in the wheel.

## 2026.04.24.4 — 2026-04-24

The "smaller wheel, honest docs" release.

- **Wheel surface shrinks ~600 lines.** The legacy v1 modules `autosearch/synthesis/` (citation + outline + report-rendering helpers) and the empty `autosearch/server/` shell are gone from the runtime package. Two new gates in `tests/unit/test_package_contents.py` (`test_legacy_v1_modules_not_in_source_tree`, `test_built_wheel_does_not_ship_legacy_v1_modules`) prevent them from sneaking back in. No production caller depended on them; v2 host agents synthesize their own answers.
- **Docs no longer lie about the contract** while leaving the product narrative untouched per owner directive:
  - `README.md` / `README.zh.md` doctor sample updated from the stale `Always-on (21/21) / Env-gated (0/1) / Login (0/15)` to the real tiers (`27/27 / API-key 0/11 / Login 0/2`).
  - `docs/install.md` channel count `39 → 40`; the npx note now says it prompts before running install (matching the consent step added in `2026.04.24.3`).
  - `docs/mcp-clients.md` rewritten around the v2 tool-supplier toolkit (10 required tools listed, `run_channel` schema documented, verification script switched from `call_tool("research", …)` to a `tools/list` check + free-channel smoke). The deprecated `research` tool is no longer the documented happy path.

## 2026.04.24.3 — 2026-04-24

The "tighten the install path and the release gate" release. Closes the
remaining million-user-readiness items where the v2 contract was correct in
code but not enforced at the install / release boundary.

- **`npm install -g autosearch-ai` no longer silently downloads and runs a remote install script.** The `postinstall` hook is removed. `npx autosearch-ai` (the recommended one-line install) still works, but now prints the URL it's about to fetch and waits for `y` to confirm — pass `--yes` (or `-y`) for non-interactive automation. In a non-TTY environment without `--yes`, it refuses rather than installing silently.
- **Release gate now runs named contract checks even in `--quick` mode.** `scripts/release-gate.sh` adds an explicit "contract gates" step that lists each plan §Gate A-G (plus the P0-5/6 invariants) by name. A regression in secrets visibility, MCP redaction, channel availability, runtime health persistence, rate-limit enforcement, or wheel content now produces a contract-named failure banner instead of blending into the 800-test default suite. Gate E (docs contract) deferred pending the narrative refresh.
- **E2B matrix contract test scans every `tests/e2b/*.yaml`**, not just the main matrix. Cleaned residual v1 expectations in `matrix-extensions.yaml`: `stdout_contains: "References"` → topic-surface check, "Use the research tool" prompt → list_skills + run_channel flow.
- **New `tests/unit/test_package_contents.py` gate** — fails the release if runtime dependencies pull in `pytest` / `ruff` / etc., if the setuptools package-data glob would ship `*.jsonl`, if the cross-file version pins drift, or if a built wheel ships runtime `patterns.jsonl`.

## 2026.04.24.2 — 2026-04-24

The "runtime actually does what doctor says" release. Fixes audit findings
against `2026.04.24.1` — configured keys now reach the actual channel call,
doctor stops reporting ghost methods as available, `run_channel` returns a
precise `not_configured` (with fix hint) instead of `unknown_channel`, MCP
responses don't leak secret-shaped strings, circuit-breaker / rate-limit state
persists across calls, and `health()` returns a useful snapshot.

- **`autosearch configure KEY value` is now visible to the actual runtime.** Previously `configure` wrote `~/.config/ai-secrets.env` but channel methods (youtube `data_api_v3.py`, `tikhub_client.py`) and LLM providers (openai / anthropic / gemini) still called `os.getenv()` directly — `doctor` saw the key and reported `ok`, but `run_channel` ran with no key and returned empty. Now the secrets file is injected into `os.environ` at MCP-server and CLI startup; explicit env overrides still win.
- **`autosearch doctor` rejects channels whose impl file doesn't exist.** Ten methods across `bilibili / douyin / github / twitter / xiaohongshu / zhihu` were declared in SKILL.md without ever shipping their `.py` file — doctor still reported them ready. Those ghost methods were removed and doctor now counts `impl_missing` as unmet so a half-scaffolded method can't report `ok`.
- **`run_channel` for a known-but-unconfigured channel returns `not_configured` with `unmet_requires` + `fix_hint`** — not `unknown_channel`. Agents can now ask the user for the missing key instead of falling back to the wrong channel. New response fields: `status` (`ok | no_results | not_configured | unknown_channel | channel_error | rate_limited`), `unmet_requires`, `fix_hint`.
- **MCP error responses redact secrets.** An upstream library or accidental traceback carrying `Bearer sk-...` no longer leaks into the `reason` field of `run_channel` / `run_clarify`. Shared `autosearch.core.redact.redact()` now guards every CLI/MCP boundary; runtime experience events (`~/.autosearch/experience/.../patterns.jsonl`) also redact `query` before write.
- **`autosearch configure` no longer requires the secret on the command line.** Default flow prompts with hidden input (no leak to shell history or `ps`). New flags: `--stdin` (automation), `--replace` (overwrite existing key). Secrets file is chmod'd to `0600` after write.
- **Circuit breaker + rate limits actually fire at runtime.** Previously `ChannelHealth` was recreated on every `run_channel` call so cooldown state evaporated. Now a process-lifetime `ChannelRuntime` owns the shared `ChannelHealth` and `RateLimiter`. Declared `rate_limit: {per_min, per_hour}` in SKILL.md is enforced per-`(channel, method)` via sliding-window counter; exceeded requests surface as `status="rate_limited"` with `retry_after` guidance.
- **MCP `health()` returns a structured snapshot** instead of the literal string `"ok"` — version, tool count, required-v2-tool present/missing, channel counts by status, secrets-file presence (key NAMES only, never values), and the shared `ChannelHealth.snapshot()`.

## 2026.04.24.1 — 2026-04-24

The "make a fresh install actually work" release. After running `autosearch init`,
the v2 contract is now honest end-to-end: configured keys take effect, the MCP
client really sees the tools, runtime writes don't pollute the installed
package, and one command tells you what's wrong.

- **`autosearch doctor` and `autosearch mcp-check` are first-class CLI commands** — `doctor` tier-groups channels and tells you the exact one-liner to fix each blocked one; `mcp-check` proves all 10 required v2 MCP tools are registered. `--json` emits machine-readable output. Unknown subcommands now error instead of silently routing to the deprecated `query` path.
- **`autosearch configure KEY value` actually takes effect** — runtime now reads `~/.config/ai-secrets.env` (the file `configure` writes to), so a fresh `doctor` run reflects keys you just added without a shell restart. Process env still overrides the file.
- **`autosearch init` writes the right MCP config shape per client** — Claude Code and Cursor get `mcpServers.autosearch`, Zed gets `context_servers.autosearch` (and the writer respects Zed's JSONC so your existing font/theme settings survive). `init --dry-run` previews writes without touching files. Backs up corrupt JSON instead of silently overwriting.
- **`autosearch mcp-check --client claude|cursor|zed`** — verifies the named client's config file is shaped correctly, in addition to the server-side tool registry.
- **`autosearch diagnostics --redact`** — copy-pasteable JSON support bundle (version, install method, MCP config presence, tool count, doctor summary). Refuses to run without `--redact`; scrubs API keys, Bearer tokens, cookies, and secret values before printing.
- **Runtime writes leave the installed package alone** — channel experience and compaction now write to `~/.autosearch/experience/` (or `$XDG_DATA_HOME/autosearch/experience` if set), never to `site-packages`. Bundled `experience.md` files remain read-only seeds.
- **Discourse forum search added (linux.do channel)** — bringing the channel count from 39 to 40.
- **Channel routing + doctor tier/fix-hint now driven by `SKILL.md` metadata** — `tier:` and `fix_hint:` declared in a channel's frontmatter take precedence over inferred defaults; selectors and channels-table generator share the same source of truth.
- **Circuit breaker is wired into runtime** — `_build_channels` now attaches `ChannelHealth`, so cooldown / failure-rate tracking actually fires and `available()` filters out cooled-down channels. `PermanentError` propagates correctly (was unreachable due to exception ordering).
- **OpenAI provider honors `OPENAI_BASE_URL`** — point any OpenAI-compatible backend at the provider without code changes.
- **One-command release gate** — `scripts/release-gate.sh` runs version consistency + lint/format + tests + CLI surface in one shot; release.yml uses it before publishing, and pyproject↔npm version mapping comes from a single shared helper.
- **`pytest` / `ruff` moved out of runtime dependencies** — installed wheels no longer pull in dev tools. CI installs with `pip install -e ".[dev]"`.

## 2026.04.23.9 — 2026-04-24

- `npx autosearch-ai` is now the one-command installer — auto-installs and shows init screen on any machine


## 2026.04.23.8 — 2026-04-23

- New one-command installer: `curl -fsSL https://raw.githubusercontent.com/0xmariowu/Autosearch/main/scripts/install.sh | bash` — handles uv/pipx/pip automatically and shows the init screen


## 2026.04.23.7 — 2026-04-23

- Fixed `npm install -g autosearch-ai` failing on Macs where pip3 points to Xcode's Python 3.9 — now detects Python 3.12+ explicitly


## 2026.04.23.6 — 2026-04-23

- `npm install -g autosearch-ai` now runs init automatically — no second step needed


## 2026.04.23.5 — 2026-04-23

- README rewritten in Agent-Reach style: pain points first, two install formats (Agent one-liner + npm)


## 2026.04.23.4 — 2026-04-23

- You can now install AutoSearch with `npm install -g autosearch-ai` — no Python setup required
- Docs site (docs.autosearch.dev) overhauled: new Quickstart, Channels, and Install pages
- README rewritten to reflect current feature set



## 2026.04.23.3 — 2026-04-23

- `autosearch init` now shows ASCII banner, auto-configures MCP for Claude Code / Cursor, and displays Integration Status + "You are all set!" — vibeusage-style install UX



## 2026.04.23.2 — 2026-04-23

- You can now run `autosearch init` to get a tiered channel status report with fix hints for each unconfigured channel
- `autosearch login` supports 7 platforms: xhs / twitter / bilibili / weibo / douyin / zhihu / xueqiu — with `--from-string` for cookie paste
- New channels: xueqiu (雪球 stock search) and linkedin (via Jina Reader, no auth)
- TikHub budget exhaustion now triggers graceful fallback instead of error
- Circuit breaker with failure categories: QUOTA_EXHAUSTED / AUTH_FAILURE / NETWORK_ERROR / PLATFORM_BLOCK — each with independent cooldown
- `run_channel` output reduced ~60% in token count via `Evidence.to_context_dict(max_content_chars=500)`

## 2026.04.23.1 — 2026-04-23

**Channels — 37 total (+3 new, +4 fixed):**
- You can now search Instagram and WeChat Channels (视频号) via TikHub
- Bilibili now uses direct WBI signing (free, no TikHub needed) with TikHub as fallback
- Twitter flat-timeline parsing fixed (was silently returning 0 results)
- XHS now uses two-step TikHub sign flow (`sign` → `search`) — previous endpoints returned 400
- Douyin switched to the working POST search endpoint (16 results)

**Search quality:**
- EvidenceProcessor is now active in `run_channel`: URL dedup → SimHash near-dedup → BM25 rerank. Previously written but never wired in.
- New `consolidate_research` MCP tool: compresses multi-channel evidence lists to prevent context overflow in long research sessions

**Search modes:**
- New `list_modes` MCP tool: discover 5 built-in search modes (academic / news / chinese_ugc / developer / product)
- `run_clarify` auto-detects query intent and injects channel priority/skip from the matched mode
- User-customizable via `~/.config/autosearch/custom_modes.json`

**Video transcription:**
- New `video-to-text-bcut` skill: Bilibili Bcut API (free, no key needed, word-level timestamps — more precise than Whisper)

**Signing Worker (Cloudflare):**
- `POST /sign/bilibili` — WBI signing with KV-cached salt, cron refresh every 2h
- `POST /sign/xhs` — TikHub sign + local X-s-common (saves per-call sign cost)
- Rate-limit: 1000 requests/day per service token
- Self-hosted: `autosearch-signsrv.autosearch-dev.workers.dev`

**E2B test suite expanded:**
- Phase 1: 59 scenarios, **96.3/100** 🟢 (install diversity, channel quality, error handling, AVO evolution, report quality, Windows emulation)
- Phase 2: 126 scenarios, **84.3/100** 🟢 (desktop GUI, search quality judge, channel reliability, stress, experience effectiveness, TikHub pathfinding, cross-platform)

**Cleanup:**
- Deleted HTTP server (`autosearch serve`, 577 lines) — v2 is MCP-first, the endpoint was calling `Pipeline.run()` → `NotImplementedError`
- `TikhubClient` retry logic deduplicated (`get()`/`post()` → shared `_execute()`, −45 lines)
- Cross-platform CI: Windows + macOS runners, Python 3.11 reverse-compat test

## 2026.04.22.5 — 2026-04-23  ← v1.0.0

This is the first production release of AutoSearch v2 tool-supplier architecture.

**Quality gates passed:**
- Gate 12 bench: augmented vs bare win rate **51.67%** (30 topics × 2 runs, OpenRouter)
- E2B comprehensive test: **91.5/100** 🟢 READY (18/20 scenarios, 7 categories)
  - Real channel searches: pubmed (10 results), dockerhub (10 results), hackernews, arxiv, ddgs ✅
  - Full golden path: clarify → delegate_subtask → citation_index → OpenRouter report ✅
  - AVO evolution cycle (Rule 22): all 12 tests pass ✅
- pytest suite: 750+ tests passing

**What's new in v2 (vs legacy pipeline):**
- `/autosearch` now uses v2 tool-supplier flow: `run_clarify → select_channels → run_channel → synthesize`
- 21 MCP tools: run_clarify / run_channel / list_skills / list_channels / doctor / select_channels_tool / delegate_subtask / loop state / citation index / 5 workflow skills
- Experience layer: each channel accumulates `patterns.jsonl` → auto-compacts to `experience.md` → injected into next search
- 35 channels including new: pubmed (free), dockerhub (free), searxng (local), tieba (Chinese UGC)
- Clarify wizard: 4-step `AskUserQuestion` flow with `question_options` for structured choices
- `autosearch doctor` / `autosearch configure` CLI tools



## 2026.04.22.4 — 2026-04-22

- Release quality test suite: G1 static checks (version consistency, SKILL.md format, experience dirs), G2 mock tests (arxiv/ddgs/hackernews/youtube/tieba + clarify wizard + experience injection), G3 smoke tests (doctor/list_channels/configure), G4 live integration (9 channels, nightly CI), G5 E2E flow (fast/clarify/deep/experience, all mock), G6 AVO evolution (12 tests covering full 6-step Rule 22 cycle), G7 pre-release checklist script.
- `ClarifyToolResponse` + `ClarifyResult` + `Clarifier` now carry `question_options: list[str]` for structured `AskUserQuestion` UI.
- 56 SKILL.md files: added `# Quality Bar` section (CLAUDE.md rule 18).
- All 34 channel experience dirs initialized with empty `patterns.jsonl`.
- New pytest marks: `live`, `e2e`, `avo`.


## 2026.04.22.3 — 2026-04-22

- You can now run `autosearch doctor` (via MCP) to scan all channel health — shows which channels are ready, missing API keys, or unavailable.
- You can now run `autosearch configure KEY value` CLI to safely append API keys to `~/.config/ai-secrets.env` with TTY confirmation.
- New MCP workflow tools: `trace_harvest` (extract winning query patterns), `perspective_questioning` (multi-viewpoint sub-questions), `graph_search_plan` (parallel DAG batching), `recent_signal_fusion` (recency filter), `context_retention_policy` (token-budget trim).
- New channels: `pubmed` (PubMed E-utilities, free), `dockerhub` (Docker Hub public search, free), `searxng` (local SearXNG meta-search, requires `SEARXNG_URL`).
- New tool skill: `fetch-firecrawl` (URL → Markdown via Firecrawl API, requires `FIRECRAWL_API_KEY`, degrades to warn when key missing).


## 2026.04.22.2 — 2026-04-22

- `autosearch query` CLI now exits immediately with a v2 deprecation notice directing you to `list_skills / run_clarify / run_channel` MCP tools.
- `pipeline.py` and `synthesis/report.py` physically deleted — v2 tool-supplier is now the only research path.


## 2026.04.22.1 — 2026-04-22

- You can now use `/autosearch` with the v2 tool-supplier flow: run_clarify → channel selection → run_channel → runtime AI synthesizes. Legacy pipeline no longer invoked.
- Per-skill experience layer: each channel now records search outcomes in `experience/patterns.jsonl` and surfaces a compacted `experience.md` digest before the next call — skills grow smarter over time.
- New MCP tools: `select_channels_tool` (group-first channel routing), `delegate_subtask` (parallel multi-channel search), `loop_init/update/get_gaps/add_gap` (reflective loop state), `citation_create/add/export/merge` (cross-channel citation deduplication).


## Unreleased

### Added

- `fetch-jina` skill: Jina Reader URL-to-Markdown fetcher. Free, no auth, best for articles/docs. First fast-path of v2 fetch layer.
- `yt-dlp` dependency (>=2026.3.17): audio/video extraction for v2 video-to-text skills (bilibili / youtube / douyin / xiaoyuzhou) and media download utilities.
- `video-to-text-groq` skill: yt-dlp + Groq Whisper API transcription (free tier). First of the v2 transcription trio; returns raw text + SRT + metadata. Summary is caller's responsibility (tool supplier principle).
- `video-to-text-openai` skill: yt-dlp + OpenAI Whisper API transcription (paid, ~$0.006/min). Second of the v2 transcription trio; paid fallback when Groq is rate-limited. Same output shape as `video-to-text-groq`.
- `video-to-text-local` skill: yt-dlp + local `mlx-whisper` transcription (Apple Silicon, offline, free). Third of the v2 transcription trio; opt-in advanced path for M-series Macs with mlx-whisper installed. Default model `mlx-community/whisper-large-v3-turbo`, overridable via `AUTOSEARCH_MLX_WHISPER_MODEL`.
- `fetch-crawl4ai` skill: deep URL fetch via `crawl4ai` (Playwright-backed) for JS-rendered pages, anti-bot sites, and dynamic content. Slower than `fetch-jina` but handles pages that block simple fetchers. Opt-in (user installs `crawl4ai` + `playwright install chromium` separately; not a default autosearch dep to keep the core lightweight).
- `fetch-playwright` skill: documentation-only skill routing the runtime AI to Microsoft's official `@playwright/mcp` server for interactive browser automation (click, type, wait, screenshot, navigate). No autosearch-side Python; the runtime AI calls the MCP tools directly. Install via one MCP-client config block, no API key.
- `mcporter` skill: documentation-only routing skill that exposes a curated set of free third-party MCP servers (Exa semantic web search, Weibo, Douyin, Xiaohongshu, LinkedIn) to the runtime AI via the upstream `mcporter` router. Free fallback path before paid TikHub for Chinese UGC and a free semantic-search alternative to Exa/Tavily.
- `autosearch:router` + 14 group index files (progressive disclosure L0 + L1). Router reads at session start (short); runtime AI picks 1-3 groups per task and only then reads the matching group indexes. 14 groups: channels-chinese-ugc / channels-cn-tech / channels-academic / channels-code-package / channels-market-product / channels-community-en / channels-social-career / channels-generic-web / channels-video-audio / tools-fetch-render / workflow-planning / workflow-quality / workflow-synthesis / workflow-growth. Each group index lists its leaf skills with when-to-use / model-tier / auth fields.
- `autosearch:model-routing` meta skill: advisory Fast / Standard / Best tier catalog for all autosearch skills. Tells runtime AI which tier each leaf needs (Fast for ~60 retrieval/normalization skills, Standard for ~20 ranking/extraction skills, Best for ~13 clarify/decompose/synthesize/evaluate-delivery/skill-evolution skills) and when to escalate or de-escalate. Autosearch does not switch models itself; runtime AI is the decision-maker.
- Backfill v2 progressive-disclosure metadata (`layer: leaf` / `domains` / `scenarios` / `model_tier: Fast` / `experience_digest: experience.md`) to all 31 existing channel SKILL.md frontmatters (arxiv, bilibili, crossref, dblp, ddgs, devto, douyin, github, google_news, hackernews, huggingface_hub, infoq_cn, kr36, kuaishou, openalex, package_search, papers, podcast_cn, reddit, sec_edgar, sogou_weixin, stackoverflow, tiktok, twitter, v2ex, weibo, wikidata, wikipedia, xiaohongshu, youtube, zhihu). Enables router/group routing to see each leaf's domain + tier without reading the full SKILL.md body.
- `autosearch:tikhub-fallback` meta skill: advisory decision tree for when the runtime AI should escalate from free native Chinese channels (bilibili / weibo / xiaohongshu / douyin / zhihu) to the paid TikHub fallback. Codifies the "free first, paid only when research-critical" rule, flags Weibo upstream flakiness and Zhihu rate-limit boundaries, and lists 5 covered platforms + what TikHub does NOT cover.
- Wave 2 deprecation scaffolding: `deprecated: true` + `deprecation_notice` frontmatter on 4 legacy prompts (`m3_evidence_compaction`, `m7_section_write`, `m7_section_write_v2`, `m7_outline`). Deprecation header comments in 3 caller modules (`autosearch/core/context_compaction.py`, `autosearch/core/iteration.py`, `autosearch/synthesis/section.py`). No behavior change — legacy pipeline still runs; wave 3 rewrites entry points and then deletes these.
- Gate 12 new bench framing spec (`docs/bench/gate-12-augment-vs-bare.md`). New bench compares `claude -p + autosearch plugin installed` (A) vs `claude -p bare` (B), measures autosearch as augmentation not adversary. Implementation deferred to wave 3 pending `scripts/bench/judge.py` port to main.
- Wave 2 status + wave 3 plan (`docs/proposals/2026-04-22-wave-2-status-and-wave-3-plan.md`). Documents what shipped in waves 1-2, why remaining items are deferred, and the W3.1–W3.6 execution sequence (entry-point rewrite → infra port → pipeline removal → first augment-vs-bare bench → experience-layer kick-off).
- `autosearch:experience-capture` meta skill (W3.5 part 1): appends one JSON line per skill execution to `<leaf>/experience/patterns.jsonl`. Fast tier, no LLM, latency < 50 ms, append-only. Event schema: ts / session_id / skill / group / task_domain / query_type / input_shape / method / environment / outcome / metrics / winning_pattern / failure_mode / good_query / bad_query / evidence_refs / promote_candidate / notes. Privacy rules sanitize PII before capture.
- `autosearch:experience-compact` meta skill (W3.5 part 2): promotes recurring patterns from `patterns.jsonl` into the compact `experience.md` digest (≤120 lines). Triggers on ≥10 new events / >64KB file size / user feedback / session end. Promotion threshold: seen≥3 + success≥2 + last_verified≤30d. Anti-pollution: single success never promotes; user corrections/rubric failures go to Failure Modes only; cold rules expire. Patterns.jsonl rotates to `experience/archive/YYYY-MM.jsonl` at 1 MB.
- `scripts/bench/judge.py` — pairwise judge for autosearch bench runs (W3.2). Compares two directories of markdown reports (A and B) via Anthropic Claude API (sonnet), randomizes A/B position per pair to suppress position bias, emits per-pair JSON verdicts + `pairwise-summary.md` + `stats.json`. Graceful fallback to `tie` on API error, non-JSON response, or malformed verdict. CLI: `python scripts/bench/judge.py pairwise --a-dir X --b-dir Y --a-label A --b-label B --output-dir Z [--parallel N] [--model M]`. Requires `ANTHROPIC_API_KEY`. 11 test cases cover success / tie / malformed / api-error / swap ordering / summary stats / markdown render.
- `list_skills` MCP tool (W3.1 first step — tool-supplier entry point). Non-destructively augments the existing `research()` pipeline tool. Returns a structured catalog of all autosearch skills (channels / tools / meta / router) with frontmatter metadata (name, description, layer, domains, scenarios, model_tier, auth_required, cost, deprecated). Filters by `group` and `domain`; hides `deprecated: true` skills by default. Runtime AI calls `list_skills()` at session start to discover autosearch's surface area without reading 80+ SKILL.md bodies. 11 test cases cover parse / scan / group filter / domain filter / deprecated visibility / MCP registration.
- `run_channel` MCP tool (W3.1 second step). Executes a single autosearch channel and returns raw Evidence (slim-dict form) — no synthesis, no compaction. Signature: `run_channel(channel_name, query, rationale="", k=10)`. Returns `RunChannelResponse{channel, ok, evidence, reason, count_total, count_returned}`. Structured error on unknown channel (lists available) or channel exception. Runtime AI: call `list_skills(group="channels")` to discover names, then call `run_channel(...)` to fetch evidence directly, synthesize in-runtime. 7 test cases cover slim-dict / propagate-exception / registration / unknown-channel / happy-path / channel-exception / model-roundtrip.
- W3.2 bench runner: `scripts/bench/bench_augment_vs_bare.py` — augment-vs-bare bench driver for Gate 12. For each topic, calls the Anthropic Messages API twice: once with the **augmented** system prompt (injects the autosearch skill catalog — trio tool names + 10 channel groups + 31 channels), once with the **bare** system prompt (no autosearch context). Writes paired markdown reports to `{output}/a/<topic>-run<N>.md` and `{output}/b/<topic>-run<N>.md`, ready to feed into `scripts/bench/judge.py pairwise`. Approximation of the full E2B-plugin-loading path (boss verification pending); exercises "runtime AI with skill catalog knowledge" vs. "bare runtime AI" directly without needing a sandboxed plugin install. 11 test cases cover yaml loading / API success / error / non-JSON / empty response / prompt content invariants. CLI: `python scripts/bench/bench_augment_vs_bare.py --topics scripts/bench/topics/gate-12-topics.yaml --output reports/<date>-augment-vs-bare --parallel 4 --runs-per-topic 1`. Topics file `scripts/bench/topics/gate-12-topics.yaml` shipped with 15 Gate 12 topics spanning Chinese UGC / academic / code / market / English community / time-sensitive categories per `docs/bench/gate-12-augment-vs-bare.md` §Hypothesis.
- W3.2 select-channels rewrite: new `autosearch:channel-selection` meta skill with group-first algorithm. Replaces the legacy flat-rank `select-channels` (source was in the plugin marketplace, not this repo) with a two-stage pick: select 1-3 groups from the router's 14 group indexes → pick 3-8 leaf channels within those groups. Codifies the boss rule that Chinese queries must retain ≥ 2 chinese-ugc/cn-tech channels regardless of past yield. Includes scoring weights, input/output schema, hard filters, and stage-level boss-rule enforcements. Docs-only skill; runtime AI reads it before fanning out `run_channel` calls.
- W3.3 PR E: remove `Pipeline` import + live-instantiation from `autosearch/mcp/server.py`. `_default_pipeline_factory()` now raises `NotImplementedError` instead of constructing a live Pipeline; `create_server(pipeline_factory)` type hint loosened to `Callable[[], Any] | None`. Tests that exercise the legacy env path pass their own stub factory via `pipeline_factory=` kwarg (autouse fixture already handles this). `cli/main.py` and `server/main.py` still import Pipeline for their own factory helpers — a larger refactor deferred (they're single-call sites that already hit `Pipeline.run()` → `NotImplementedError` under the PR D stub). New tests verify: `_default_pipeline_factory` raises; `mcp.server` module has no `Pipeline` attribute. 445 unit tests green.
- W3.3 PR D: gut legacy pipeline. Delete 4 modules (`autosearch/core/iteration.py`, `autosearch/core/context_compaction.py`, `autosearch/core/delegation.py`, `autosearch/synthesis/section.py`). Reduce `autosearch/core/pipeline.py` from 751 lines to a ~80-line stub where `Pipeline.run()` raises `NotImplementedError` pointing at the v2 trio; `Pipeline.__init__` accepts any legacy signature for import compat; `PipelineEvent` + `PipelineResult` re-exports preserved. Reduce `autosearch/synthesis/report.py` from 281 lines to a ~40-line stub where `ReportSynthesizer.synthesize()` raises `NotImplementedError`. Keep `_bypass_clarify_enabled()` helper for backward-compat. Net: ~2500 lines deleted or gutted across 6 files; 437 tests still green (1 CLI test updated to assert new deprecation message).
- W3.3 PR C: delete 9 m3/m7 prompt markdown files from `autosearch/skills/prompts/` (m3_evidence_compaction, m3_follow_up_query, m3_gap_reflection, m3_gap_reflection_perspective, m3_perspective_labels, m3_search_reflection, m7_outline, m7_section_write, m7_section_write_v2). Replace module-level `load_prompt(...)` calls in `autosearch/core/iteration.py`, `autosearch/core/context_compaction.py`, `autosearch/synthesis/section.py` with empty-string sentinels so imports still succeed — the runtime paths that would use these constants are env-gated behind `AUTOSEARCH_LEGACY_RESEARCH=1` and will be removed entirely in PR D. Update `tests/unit/test_prompt_loader.py` `PROMPT_NAMES` list to drop removed prompts.
- W3.3 PR B: delete 22 orphan pipeline-only test files (unit: core/test_context_compaction, core/test_delegation, core/test_perspectives, synthesis/test_section, test_iteration, test_iteration_empty_counts, test_iteration_routing, test_m3_compaction_prompt_preserves_specifics, test_m7_prompt_substance, test_pipeline_channel_error, test_pipeline_channel_scope, test_pipeline_events, test_pipeline_initial_subquery_count, test_pipeline_tokens, test_synthesis; integration: test_full_synthesis, test_iteration_e2e, test_pipeline_clarification_exit, test_pipeline_e2e, test_pipeline_with_session; perf: test_pipeline_large_evidence; real_llm: test_pipeline_demo). Remaining 437 tests stay green. Clears the path for PR C (prompt markdown deletion) and PR D (pipeline internals gut).
- W3.3 PR A: freeze `research()` MCP tool to return deprecation response by default (does NOT invoke the legacy Pipeline). Pipeline execution can still be opted-in via `AUTOSEARCH_LEGACY_RESEARCH=1` env var for emergency backward-compat or bench. New tests: `test_research_default_returns_deprecation_without_pipeline` / `test_research_legacy_env_opt_in_restores_pipeline_path`. Existing pipeline-behavior tests (`test_mcp_research_scope.py`, `test_mcp_server.py`) retain green status via autouse monkeypatch fixture that sets the opt-in env var. Prepares the ground for PR B (orphan-test deletion) and PR C (prompt markdown deletion) per the W3.3 plan.
- W3.3 pipeline-removal multi-PR plan at `docs/proposals/2026-04-22-w3-3-pipeline-removal-plan.md`. Splits the destructive legacy-removal work into 5 sequenced PRs (A freeze research() surface → B delete orphan tests → C delete m3/m7 prompt markdowns → D gut pipeline internals → E delete Pipeline class). Each PR ≤ 1000 lines changed, self-contained, rollbackable. Respects CLAUDE.md "do not take overly destructive actions" by sequencing. Next action after plan merges: boss go for PR A.
- Migration guide `docs/migration/legacy-research-to-tool-supplier.md` (W3.3 first safe step). Documents how runtime AI moves from the legacy `research()` MCP pipeline to the v2 trio (`list_skills` + `run_clarify` + `run_channel`). Includes minimum migration pattern, quick-research pattern, deep-research composition with wave-3 meta skills, cost comparison, and FAQ.
- Runtime `DeprecationWarning` on `research()` MCP tool invocation pointing to the migration guide. Legacy pipeline continues to run; the warning surfaces in tool output so integrators notice the v2 path without breaking existing flows. MCP server `instructions` string also updated to steer new integrations toward the trio.
- 8 new workflow skill candidates landed (W3.6, from v2 proposal §3.7). All docs-only meta skills that codify runtime-AI workflow patterns borrowed from prior art in external deep-research reference repos — they do not add Python code, the runtime AI is the implementer:
  - `delegate-subtask` (Standard) — execution contract for isolated sub-tasks (input / budget / output / stop-conditions). Sources: MiroThinker + DeepAgents + deer-flow + DeepResearchAgent.
  - `trace-harvest` (Standard) — distills successful session trace into promote-candidate experience events. Sources: MiroThinker collect-trace + DeepResearchAgent memory system.
  - `reflective-search-loop` (Best) — explicit multi-round loop state (gaps / visited / bad_urls / evaluator failures / stop conditions). Sources: WebThinker + node-deepresearch + Scira extreme-search.
  - `perspective-questioning` (Best) — multi-persona question generation (3-6 stakeholders), union → scope. Source: STORM pre-writing research.
  - `citation-index` (Standard) — URL canonicalization, dedup, stable citation numbers, subagent merge. Sources: STORM + deepagents.
  - `graph-search-plan` (Best) — DAG over sub-questions with depends_on edges and parallel execution policy. Source: MindSearch WebSearchGraph.
  - `recent-signal-fusion` (Standard) — cross-channel time-weighted candidate clustering with platform-spread scoring + anti-collapse guard. Sources: last30days-skill + Scira group mode.
  - `context-retention-policy` (Fast) — session-level keep-last-k / offload / compact policy with never-compact list. Sources: MiroThinker keep_tool_result + deepagents summarization + deer-flow SummarizationEvent.
- `run_clarify` MCP tool (W3.1 third step, W3.1 trio complete). Runs the autosearch clarifier on a query without running the pipeline. Signature: `run_clarify(query, mode_hint=None)`. Returns `ClarifyToolResponse{query, ok, need_clarification, question, verification, mode, query_type, rubrics, channel_priority, channel_skip, reason}`. Structured error on clarifier exception. With `list_skills` + `run_channel` + `run_clarify` in place, the runtime AI can now drive a full autosearch session end-to-end without touching the legacy m3/m7/iteration/synthesis pipeline — tool-supplier architecture is operational in parallel. 6 test cases cover registration / no-clarify-needed / clarify-needed / exception / model-roundtrip / tool-call-delegation.

### Changed

- ci: fix codex-autofix-dispatch marker mismatch — loop-prevention guard searched `codex-autofix-dispatch:` but write-block emitted `copilot-autofix-dispatch:`, so repeat CI failures on the same PR head spammed fresh `@copilot please fix` comments. Unified both to `copilot-autofix-dispatch:`.
- fix(ci): update 6 sync-pack files to v1.4.1 canonical — shellcheck/actionlint/gitleaks/@copilot/tools[] fixes (Closes #208)
- feat(ci): bootstrap AI-native dev environment from sync pack v1.4 (Closes #203)
- docs(mcp): add per-client MCP config guide for Claude Code / Cursor / Zed / Continue; document `research` + `health` tools and the full input schema.
- chore(ci): port E2B validation orchestrator (`run_validation.py`, `bench_channels.py`, `bench_variance.py`, `lib/`) into repo `scripts/e2b/` so nightly/weekly CI workflows stop short-circuiting. Also fixes bench bugs — host-only E2B_API_KEY, null-safe variance summarize, docstring/CLI alignment.
- fix(ci): pin e2b nightly/weekly workflow `content-filepath` to a concrete date (was a glob peter-evans-create-issue-from-file silently ignored) + add a fallback "failure summary" step so auto-issues always have real content, even when the orchestrator crashed before writing summary.md.
- chore(nightly): add `scripts/nightly-local.sh` + macOS launchd / Linux systemd recipes in `docs/local-nightly.md` so Gate 13 observation-period evidence can be collected without GitHub Actions secrets.
- fix(clarify): add `AUTOSEARCH_BYPASS_CLARIFY` env var so batch / non-interactive callers can proceed past `need_clarification=true` instead of halting with CLI exit 2. Unblocks `zh_tech_moe`-class queries in the F203 variance bench.
- fix(m7): synthesizer prompt now enforces content-substance rules — concrete specifics (numbers, error codes, benchmarks, issue #s), no generic/meaningless conclusions, no repetition.
- fix(m3): evidence-compaction prompt now preserves specifics verbatim (numbers, error codes, issue numbers, benchmarks, version strings, named entities) instead of collapsing to 5-15 concise bullets. Aligns with the compress-research prompt pattern in open_deep_research.
