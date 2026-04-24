# AutoSearch Million-User Product Readiness Repair Plan

Date: 2026-04-24

Scope: current checkout after the latest v2 repair round. This document focuses
on bugs and product gaps that still block AutoSearch from being safe, reliable,
and understandable for a large public user base.

The plan intentionally focuses on fresh installs and current users of the v2
tool-supplier architecture. Existing-user migration is out of scope unless it
directly affects fresh-install correctness.

## Executive Verdict

AutoSearch is much healthier than it was before the latest repairs, but it is
not ready for million-user distribution yet.

The current release gate passes:

```bash
scripts/release-gate.sh --quick
uv run pytest -q -m "not real_llm and not perf and not slow and not network" -x
uv build --wheel
```

Observed result:

- quick release gate passed;
- default non-live test suite passed: 818 passed, 21 deselected;
- wheel build succeeded;
- `autosearch doctor --json` returns a valid channel list;
- `autosearch mcp-check` reports the 10 required v2 tools.

However, the current gates do not catch several production blockers:

- configured secrets can be visible to `doctor` but invisible to the actual
  channel method;
- channels with missing implementation files can be reported as available;
- `run_channel` still reports some configured-off channels as `unknown_channel`;
- channel errors can leak secret-looking strings into MCP tool responses;
- runtime health/circuit breaker state is recreated per call;
- `rate_limit` metadata is declared but not enforced;
- public docs and some E2B matrices still describe the old v1 research/report
  contract;
- npm/install paths still execute remote mutable scripts by default.

The next repair round should not add channels. It should make the existing v2
contract true end to end.

## Current Product Contract

The product should be described and tested as:

1. User installs AutoSearch.
2. User runs `autosearch doctor`.
3. User runs `autosearch mcp-check`.
4. User connects AutoSearch as an MCP server.
5. The host agent calls:
   - `list_channels`
   - `list_skills`
   - `run_clarify`
   - `select_channels_tool`
   - `run_channel`
   - `citation_create`
   - `citation_add`
   - `citation_export`
   - optional workflow helpers such as `consolidate_research`
6. The host agent synthesizes the final answer.

AutoSearch should not be marketed as a standalone one-command report generator.
The deprecated `query` CLI and deprecated MCP `research` tool must stay out of
the default happy path.

## Evidence Collected

The audit verified these commands locally:

```bash
scripts/release-gate.sh --quick
uv run pytest -q -m "not real_llm and not perf and not slow and not network" -x
uv run autosearch --version
uv run autosearch doctor --json
uv run autosearch mcp-check
uv build --wheel
```

Focused probes also checked:

- secrets-file-only YouTube configuration;
- missing channel implementations;
- `run_channel` behavior for unconfigured known channels;
- secret leakage through exception messages;
- wheel content;
- stale documentation and E2B contract text.

## Critical Findings

### P0-1. Secrets File Visibility Is Split Between Doctor And Runtime

`autosearch configure` and `autosearch login` write to a secrets file. The new
`autosearch.core.secrets_store` module lets `doctor` and environment probing see
keys from that file.

But many actual runtime methods still read only process environment variables:

- `autosearch/skills/channels/youtube/methods/data_api_v3.py`
- `autosearch/lib/tikhub_client.py`
- `autosearch/llm/providers/openai.py`
- `autosearch/llm/providers/anthropic.py`
- `autosearch/llm/providers/gemini.py`
- `autosearch/skills/tools/fetch-firecrawl/methods/scrape.py`
- video transcription tools

Reproduction:

```bash
tmpd="$(mktemp -d)"
printf 'YOUTUBE_API_KEY=dummy-key\n' > "$tmpd/secrets.env"

env -u YOUTUBE_API_KEY \
  AUTOSEARCH_SECRETS_FILE="$tmpd/secrets.env" \
  AUTOSEARCH_EXPERIENCE_DIR="$tmpd/experience" \
  uv run python - <<'PY'
import asyncio, os
from autosearch.core.doctor import scan_channels
from autosearch.mcp.server import create_server

print("env_youtube=", bool(os.environ.get("YOUTUBE_API_KEY")))
print("doctor_youtube=", [
    (r.status, r.message) for r in scan_channels() if r.channel == "youtube"
])

async def main():
    tm = create_server()._tool_manager
    res = await tm.call_tool(
        "run_channel",
        {"channel_name": "youtube", "query": "test", "k": 1},
    )
    print(res.model_dump())

asyncio.run(main())
PY
```

Observed behavior:

- process env does not contain `YOUTUBE_API_KEY`;
- `doctor` reports YouTube as `ok`;
- `run_channel` returns `ok=True`;
- evidence is empty;
- `reason=None`;
- logs show the method skipped because there was no API key.

Impact:

- user believes configuration succeeded;
- agent believes channel succeeded;
- no useful evidence is returned;
- release gate does not catch this.

Required fix:

- Introduce a single runtime configuration API for secret values.
- Either inject secrets-file values into process env at CLI/MCP startup, or
  replace direct `os.getenv()` calls with `resolve_env_value()`.
- Ensure environment variables still override file values.
- Add tests where the secret exists only in `AUTOSEARCH_SECRETS_FILE`.

Acceptance:

```bash
uv run pytest tests/unit/test_secrets_store.py
uv run pytest tests/unit/test_runtime_secrets_contract.py
```

The required contract:

- if `doctor` says a method is configured because of a secrets-file key, the
  actual method must see the same key;
- if the actual method cannot see the key, `doctor` must not report that method
  as available.

### P0-2. Doctor Can Report Missing Implementations As Available

Several channel methods are declared in `SKILL.md` but their implementation
files do not exist in the current runtime package.

Observed missing declarations:

```text
bilibili      api_video_detail       methods/api_video_detail.py
douyin        via_douyin_mcp         methods/via_douyin_mcp.py
github        search_repositories    methods/search_repos.py
github        search_issues          methods/search_issues.py
github        search_code            methods/search_code.py
twitter       api_search             methods/api_search.py
xiaohongshu   via_mcporter           methods/via_mcporter.py
xiaohongshu   via_xhs_cli            methods/via_xhs_cli.py
zhihu         api_search             methods/api_search.py
zhihu         api_answer_detail      methods/api_answer.py
```

Reproduction:

```bash
uv run python - <<'PY'
from pathlib import Path
from autosearch.skills.loader import load_all

root = Path("autosearch/skills/channels")
missing = []
for spec in load_all(root):
    for method in spec.methods:
        if not (spec.skill_dir / method.impl).is_file():
            missing.append((spec.name, method.id, method.impl))

print("missing_count", len(missing))
for row in missing:
    print(row)
PY
```

Doctor currently computes availability from declared requirements, not from
compiled method availability. That means a method with a satisfied key but
missing implementation can be counted as available.

Impact:

- status output overstates real channel coverage;
- users configure keys and still hit fallback paths;
- support diagnostics will mislead maintainers;
- channel governance numbers are not trustworthy.

Required fix:

- Make `doctor.scan_channels()` use the same compiled method model as
  `ChannelRegistry`.
- Count `impl_missing` as unavailable.
- Include missing implementations in JSON output.
- Add a static test that all declared method impl files exist unless explicitly
  marked as planned/disabled.

Acceptance:

```bash
uv run pytest tests/unit/test_channel_skill_scaffolds.py
uv run pytest tests/unit/test_doctor_impl_availability.py
```

Expected behavior:

- missing impls never count as available;
- `doctor --json` exposes `impl_missing`;
- release gate fails if new missing impl declarations are introduced.

### P0-3. run_channel Confuses Known But Unconfigured Channels With Unknown Channels

When a channel is known but not configured, `run_channel` should return a
recoverable `not_configured` response with fix hints.

Current behavior:

```bash
tmpd="$(mktemp -d)"

env -u YOUTUBE_API_KEY \
  AUTOSEARCH_SECRETS_FILE="$tmpd/missing.env" \
  AUTOSEARCH_EXPERIENCE_DIR="$tmpd/experience" \
  uv run python - <<'PY'
import asyncio
from autosearch.core.doctor import scan_channels
from autosearch.mcp.server import create_server

print([
    {"channel": r.channel, "status": r.status, "fix_hint": r.fix_hint}
    for r in scan_channels() if r.channel == "youtube"
])

async def main():
    res = await create_server()._tool_manager.call_tool(
        "run_channel",
        {"channel_name": "youtube", "query": "test"},
    )
    print(res.model_dump())

asyncio.run(main())
PY
```

Observed:

- `doctor` knows YouTube is `off` and gives a fix hint;
- `run_channel("youtube")` returns `unknown_channel`;
- the user does not get the YouTube-specific fix hint.

Impact:

- agents cannot self-repair setup;
- users see contradictory diagnostics;
- configured-off channels look like typos.

Required fix:

- Return all known channel metadata from the runtime registry.
- Keep separate sets for:
  - known channel;
  - available channel;
  - configured-off channel;
  - unknown channel.
- Change `RunChannelResponse` to include:
  - `status`: `ok | no_results | not_configured | unknown_channel | channel_error`
  - `unmet_requires`
  - `fix_hint`

Acceptance:

```bash
uv run pytest tests/unit/test_mcp_run_channel.py
```

Expected behavior:

- `run_channel("youtube")` without key returns `not_configured`;
- response includes `env:YOUTUBE_API_KEY`;
- response includes `autosearch configure YOUTUBE_API_KEY <your-key>`.

### P0-4. MCP Tool Responses Can Leak Secret-Looking Error Messages

`run_channel` catches all exceptions and includes `str(exc)` in the MCP response.

Reproduction:

```bash
AUTOSEARCH_EXPERIENCE_DIR="$(mktemp -d)" uv run python - <<'PY'
import asyncio
from autosearch.mcp.server import create_server

class BadChannel:
    name = "arxiv"
    languages = ["en"]

    async def search(self, query):
        raise RuntimeError(
            "upstream rejected Authorization: Bearer sk-ant-SECRETSECRETSECRETSECRET"
        )

async def main():
    import autosearch.mcp.server as server_mod
    server_mod._build_channels = lambda: [BadChannel()]
    res = await create_server()._tool_manager.call_tool(
        "run_channel",
        {"channel_name": "arxiv", "query": "x"},
    )
    print(res.model_dump())

asyncio.run(main())
PY
```

Observed:

- the secret-looking Bearer token appears in `reason`.

Impact:

- a channel library, upstream response, or accidental exception can expose
  credentials to an MCP client transcript;
- users may paste leaked credentials into issues or logs;
- diagnostics redaction does not protect live tool responses.

Required fix:

- Move redaction to a shared runtime utility.
- Apply redaction at every CLI/MCP boundary:
  - `run_channel`
  - `run_clarify`
  - `research`
  - `delegate_subtask`
  - `citation_*`
  - `doctor`
- Return stable error categories instead of raw exception text where possible.

Acceptance:

```bash
uv run pytest tests/unit/test_secret_redaction.py
uv run pytest tests/unit/test_mcp_error_redaction.py
```

Expected behavior:

- no `sk-`, `sk-ant-`, `Bearer`, `Cookie:`, or token-shaped value appears in
  MCP response text;
- the user still sees a useful error category and next action.

### P0-5. ChannelHealth Is Recreated Per Call

The runtime now attaches `ChannelHealth`, but `_build_channels()` creates a new
registry and a new `ChannelHealth()` each time.

Impact:

- failure state does not persist across MCP tool calls;
- circuit breaker is mostly local to one short-lived registry;
- cooldown behavior is not useful under real user traffic.

Required fix:

- Create a server-lifecycle `ChannelRuntime` object.
- Store:
  - compiled registry;
  - shared `ChannelHealth`;
  - limiter state;
  - last error summaries;
  - optional reload timestamp.
- Inject this runtime into MCP tools.

Acceptance:

```bash
uv run pytest tests/unit/test_channel_bootstrap_health.py
uv run pytest tests/unit/test_mcp_runtime_health_persistence.py
```

Expected behavior:

- repeated failures across separate `run_channel` tool calls enter cooldown;
- `health()` and `doctor()` can report cooldown state.

### P0-6. Declared Method rate_limit Is Not Enforced

Channel `SKILL.md` files declare `rate_limit`, but runtime does not enforce it.

Impact:

- free upstreams can be hammered;
- paid providers such as TikHub can burn budget unexpectedly;
- rate-limit metadata gives a false sense of safety.

Required fix:

- Add per-method limiter keyed by `(channel, method)`.
- Start with in-process limits:
  - `per_min`
  - `per_hour`
  - optional concurrency cap
- Return structured `rate_limited` status when exceeded.

Acceptance:

```bash
uv run pytest tests/unit/test_channel_rate_limit.py
```

Expected behavior:

- parallel calls obey the declared method limit;
- exceeded limit does not call upstream;
- response includes reset or retry-after guidance where available.

## High Priority Product Gaps

### P1-1. Public Docs Still Describe The Old Product

Stale examples remain in:

- `README.md`
- `README.zh.md`
- `docs/install.md`
- `docs/mcp-clients.md`
- plugin metadata

Examples:

- README still says AutoSearch is an open-source deep research replacement.
- README still says AutoSearch fixes the problem in one line.
- README still shows `Always-on (21/21)`.
- install docs still show old MCP config shape.
- MCP docs still say the server exposes two tools and that `research` is the
  main entry point.

Required fix:

- Rewrite public docs around the v2 MCP tool-supplier contract.
- Make `doctor + mcp-check + run_channel` the happy path.
- Move `query` and `research` to legacy migration docs only.
- Update examples to match current channel counts and current config writers.

Acceptance:

```bash
rg -n "Always-on \\(21/21\\)|21/37|Use the research tool|main deep-research entry point|autosearch query" README.md README.zh.md docs
```

Expected behavior:

- no match in primary docs;
- legacy docs may mention old paths only when clearly labeled deprecated.

### P1-2. E2B Contract Tests Still Miss Some Old v1 Expectations

`tests/unit/test_e2b_matrix_contract.py` only checks selected matrix files.

Stale v1 expectations still exist in:

- `tests/e2b/matrix-extensions.yaml`
- `tests/e2b/matrix-w1w4-bench.yaml`

Required fix:

- Expand the matrix contract test to scan all `tests/e2b/*.yaml`.
- Allow old `query` checks only when they explicitly assert deprecation.
- Disallow `stdout_contains: "References"` in release or extension gates.
- Disallow prompts telling agents to use the deprecated `research` tool.

Acceptance:

```bash
uv run pytest tests/unit/test_e2b_matrix_contract.py
rg -n "stdout_contains: \"References\"|Use the research tool|call_tool\\(\"research\"" tests/e2b
```

### P1-3. configure/login Still Put Secrets On Command Lines

Current `configure` takes the secret value as a required argument.

Risks:

- shell history leak;
- process-list leak;
- no non-interactive `--stdin`;
- no explicit permission hardening;
- existing keys require manual edits.

Required fix:

- Change `autosearch configure KEY` to prompt with hidden input by default.
- Add `--stdin` for automation.
- Add `--yes` or equivalent for tests.
- Add `--replace` for existing keys.
- Set secrets file mode to `0600`.
- For `login --from-string`, prefer stdin or hidden prompt.

Acceptance:

```bash
uv run pytest tests/unit/test_cli_configure.py
uv run pytest tests/unit/test_cli_login.py
```

Expected behavior:

- no secret argument is required on the CLI;
- file permissions are `0600`;
- replacing a key is explicit and tested.

### P1-4. Deprecated research Tool Is Still Listed By Default

The MCP `research` tool is registered and visible in tool lists even though it
returns a deprecation response by default.

Impact:

- LLMs are likely to choose the attractive high-level tool name;
- users see a tool that product docs should no longer promote;
- compatibility surface remains larger than needed.

Required fix:

- Default: do not register `research`.
- Compatibility mode: register `legacy_research` only when
  `AUTOSEARCH_LEGACY_RESEARCH=1`.
- If removing registration is too risky, rename to `legacy_research` and mark
  it deprecated in the description.

Acceptance:

```bash
uv run autosearch mcp-check
```

Expected behavior:

- required v2 tools are present;
- default tool list does not include `research`;
- legacy opt-in has its own explicit test.

### P1-5. MCP health() Is Not A Real Health Report

Current `health()` returns only `ok`.

Required fix:

Return structured data:

- AutoSearch version;
- tool count;
- required tool status;
- channel counts by status and tier;
- secrets file exists / key count, without values;
- MCP client config status if available;
- runtime health cooldown snapshot;
- last error summary, redacted.

Acceptance:

```bash
uv run pytest tests/unit/test_mcp_health.py
```

### P1-6. delegate_subtask Bypasses run_channel Semantics

`delegate_subtask` directly calls channels and returns slim dicts. It bypasses:

- not-configured semantics;
- redaction;
- BM25/rerank pipeline;
- future rate limiter;
- future shared health;
- citation-ready output.

Required fix:

- Extract a shared internal `run_channel_core()` function.
- Make both `run_channel` and `delegate_subtask` use it.
- Preserve parallelism with a configurable concurrency cap.

Acceptance:

```bash
uv run pytest tests/test_delegate.py
uv run pytest tests/unit/test_mcp_run_channel.py
```

## Install And Release Trust

### P1-7. install.sh Uses Mutable main And Runs init Automatically

Current installer uses:

```bash
https://raw.githubusercontent.com/0xmariowu/Autosearch/main/scripts/install.sh
```

and runs:

```bash
autosearch init
```

Required fix:

- support `--version`;
- support `--dry-run`;
- support `--no-init`;
- prefer pinned release URL in docs;
- show source URL before execution;
- avoid modifying shell profiles unless user accepts.

Acceptance:

```bash
bash scripts/install.sh --dry-run
bash scripts/install.sh --dry-run --no-init
bash scripts/install.sh --dry-run --version 2026.04.24.1
```

### P1-8. npm postinstall Executes Remote Installer

`npm/package.json` still has:

```json
"postinstall": "node bin/autosearch-ai.js"
```

The wrapper runs:

```bash
curl -fsSL .../main/scripts/install.sh | bash
```

Required fix:

- remove `postinstall`;
- make `npx autosearch-ai` an explicit launcher only;
- do not execute remote scripts during npm install;
- add a confirmation step unless `--yes` is passed;
- provide a no-network diagnostic path.

Acceptance:

```bash
cd npm
npm pack
npm install --ignore-scripts ./autosearch-ai-*.tgz
```

Expected behavior:

- install does not run remote scripts;
- explicit `npx autosearch-ai` is the only execution path.

### P1-9. Release Workflow npm Summary Computes The Wrong Version Link

The release workflow publishes npm with `derive_npm_version()`, but the summary
computes a different version string using `YEAR.MMDD.SEQ`.

Required fix:

- use the same Python helper for the summary.

Acceptance:

```bash
uv run pytest tests/unit/test_release_gate_script.py
```

Add a test that asserts `release.yml` does not manually compute npm version
with a separate formula.

## Cross-Platform And Packaging

### P1-10. Cross-Platform Experience Test Uses The Old Path Contract

The Windows workflow mutates `_SKILLS_ROOT` and expects experience writes under
that directory. The current runtime experience path uses
`AUTOSEARCH_EXPERIENCE_DIR` or `~/.autosearch/experience`.

Required fix:

- Set `AUTOSEARCH_EXPERIENCE_DIR` in the workflow test.
- Assert the new runtime path, not the bundled skill root.

Acceptance:

```bash
pytest tests/unit/test_experience_runtime_isolation.py
```

and the GitHub `cross-platform.yml` workflow should pass on Windows and macOS.

### P2-1. Wheel Still Ships Legacy Pipeline And Server Modules

The wheel still contains:

- `autosearch/core/pipeline.py`
- `autosearch/server/main.py`
- `autosearch/server/openai_compat.py`
- `autosearch/synthesis/report.py`
- `autosearch/synthesis/section.py`

This is not immediately fatal, but it increases the accidental public surface.

Required fix:

- decide whether these are supported legacy modules;
- if not supported, move behind a legacy extra or remove from runtime package;
- if supported, document and test them explicitly.

Acceptance:

```bash
uv build --wheel
python -m zipfile -l dist/autosearch-*.whl | rg "autosearch/core/pipeline|autosearch/server|autosearch/synthesis/report"
```

The expected output must match the product decision.

### P2-2. Bundled Experience Seeds Need A Clear Policy

Runtime experience writes are now moved out of the package tree, which is good.
The wheel still includes seed experience files such as:

- `autosearch/skills/channels/bilibili/experience.md`
- `autosearch/skills/channels/github/experience.md`
- `autosearch/skills/channels/linkedin/experience/experience.md`
- `autosearch/skills/channels/xueqiu/experience/experience.md`

Required fix:

- decide whether seed digests are allowed package data;
- remove any raw `patterns.jsonl` from package data;
- standardize seed digest path as either `<skill>/experience.md` or
  `<skill>/experience/experience.md`, not both.

Acceptance:

```bash
uv build --wheel
wheel="$(ls -1t dist/*.whl | head -1)"
python -m zipfile -l "$wheel" | rg "experience/(patterns\\.jsonl|experience\\.md)|/experience\\.md"
```

No raw `patterns.jsonl` should ship.

### P2-3. Experience Stores Raw Query Text

Runtime location is safer now, but `append_event()` still stores raw `query`.

Required fix:

- redact obvious secrets and PII before writing;
- consider hashing query text by default;
- make raw-query capture opt-in.

Acceptance:

```bash
uv run pytest tests/unit/test_experience_redaction.py
```

Expected behavior:

- API keys, cookies, Bearer tokens, email addresses, and phone-like strings do
  not appear in runtime experience files.

## Release Gate Upgrades

The release gate should fail on real product-contract breakage, not only on
lint and basic CLI surface.

Add these gates:

### Gate A. Secrets Runtime Contract

```bash
uv run pytest tests/unit/test_runtime_secrets_contract.py
```

Must prove:

- secrets-file-only key is visible to the method that uses it;
- `doctor` and `run_channel` agree.

### Gate B. Channel Implementation Integrity

```bash
uv run pytest tests/unit/test_channel_impl_integrity.py
```

Must prove:

- every non-planned method has a real impl file;
- missing impls cannot count as available.

### Gate C. MCP Error Redaction

```bash
uv run pytest tests/unit/test_mcp_error_redaction.py
```

Must prove:

- secret-looking strings never appear in MCP tool responses.

### Gate D. Known-Off Channel Semantics

```bash
uv run pytest tests/unit/test_mcp_run_channel_not_configured.py
```

Must prove:

- known but unconfigured channels return `not_configured`, not `unknown_channel`.

### Gate E. Docs Contract

```bash
uv run pytest tests/unit/test_docs_contract.py
```

Must scan:

- `README.md`
- `README.zh.md`
- `docs/install.md`
- `docs/mcp-clients.md`
- `npm/package.json`
- `.claude-plugin/*.json`

Must reject default-path claims such as:

- `Always-on (21/21)`
- `21/37`
- `Use the research tool`
- `main deep-research entry point`
- `OpenAI and Perplexity Deep Research alternative`

Legacy docs can mention old paths only with clear deprecation language.

### Gate F. E2B Matrix Contract

```bash
uv run pytest tests/unit/test_e2b_matrix_contract.py
```

Must scan every `tests/e2b/*.yaml`, not just the main matrix.

Must reject:

- `stdout_contains: "References"` in default v2 gates;
- prompts that tell the agent to use deprecated `research`;
- `autosearch query` unless the task explicitly asserts deprecation.

### Gate G. Package Content

```bash
uv build --wheel
uv run pytest tests/unit/test_package_contents.py
```

Must prove:

- no raw runtime `patterns.jsonl` in wheel;
- runtime deps do not include `pytest` or `ruff`;
- version files are consistent;
- published package contents match intentional policy.

## Repair Roadmap

### Batch 1: Runtime Truth

Goal: make status, config, and runtime behavior agree.

Tasks:

1. Add runtime secrets contract tests.
2. Replace or wrap direct `os.getenv()` uses in channels/providers.
3. Make doctor use compiled method availability.
4. Add missing-impl integrity test.
5. Change `run_channel` to return `not_configured` for known-off channels.
6. Add structured status to `RunChannelResponse`.

Verification:

```bash
uv run pytest tests/unit/test_secrets_store.py
uv run pytest tests/unit/test_runtime_secrets_contract.py
uv run pytest tests/unit/test_channel_impl_integrity.py
uv run pytest tests/unit/test_mcp_run_channel.py
```

### Batch 2: Safety Boundaries

Goal: no secrets leak through normal support or MCP paths.

Tasks:

1. Move redaction to a shared utility.
2. Redact all CLI/MCP boundary error strings.
3. Add experience redaction.
4. Harden `configure` and `login` input paths.

Verification:

```bash
uv run pytest tests/unit/test_secret_redaction.py
uv run pytest tests/unit/test_mcp_error_redaction.py
uv run pytest tests/unit/test_experience_redaction.py
uv run pytest tests/unit/test_cli_configure.py
```

### Batch 3: Runtime Reliability

Goal: make health, cooldown, and rate limits real.

Tasks:

1. Add `ChannelRuntime`.
2. Persist `ChannelHealth` across MCP tool calls.
3. Add rate limiter.
4. Make `delegate_subtask` use shared channel core.
5. Upgrade `health()` to structured report.

Verification:

```bash
uv run pytest tests/unit/test_mcp_runtime_health_persistence.py
uv run pytest tests/unit/test_channel_rate_limit.py
uv run pytest tests/test_delegate.py
uv run pytest tests/unit/test_mcp_health.py
```

### Batch 4: Product Contract Cleanup

Goal: docs, examples, matrices, and plugin metadata tell the same story.

Tasks:

1. Rewrite README and README.zh.
2. Rewrite install docs.
3. Rewrite MCP client docs.
4. Update plugin metadata.
5. Update E2B extension and bench matrices.
6. Expand docs and matrix contract tests.

Verification:

```bash
uv run pytest tests/unit/test_docs_contract.py
uv run pytest tests/unit/test_e2b_matrix_contract.py
rg -n "Always-on \\(21/21\\)|21/37|Use the research tool|main deep-research entry point" README.md README.zh.md docs tests/e2b
```

### Batch 5: Install Trust

Goal: reduce surprise execution and improve enterprise acceptability.

Tasks:

1. Add install script flags: `--dry-run`, `--no-init`, `--version`.
2. Update docs to prefer pinned release installs.
3. Remove npm `postinstall`.
4. Require explicit execution for remote install.
5. Fix release npm summary version calculation.

Verification:

```bash
bash scripts/install.sh --dry-run
bash scripts/install.sh --dry-run --no-init
cd npm && npm pack
uv run pytest tests/unit/test_release_gate_script.py
```

### Batch 6: Release Gate Integration

Goal: prevent the same regressions from returning.

Tasks:

1. Add new gate tests from this document.
2. Wire them into `scripts/release-gate.sh`.
3. Run the full gate in release workflow, not only `--quick`, or make `--quick`
   include all contract tests.

Verification:

```bash
scripts/release-gate.sh
```

## Final Acceptance Bar

AutoSearch can be considered public-release ready when all of these are true:

- A fresh user can install, run `doctor`, run `mcp-check`, and use at least one
  free channel through MCP without reading source code.
- If a channel is unconfigured, `run_channel` returns a precise fix hint.
- If `doctor` reports a method available, the actual method can use the same
  configuration source.
- Missing implementation files cannot count as available.
- MCP responses and diagnostics do not leak secret-looking strings.
- Runtime health and rate-limit state persist across tool calls.
- Docs no longer direct users to deprecated `query` or `research` as the happy path.
- npm install does not silently execute remote scripts.
- Release gate catches stale docs, stale E2B expectations, secret leaks, and
  channel availability false positives.

## Do Not Prioritize Yet

Do not prioritize these before the P0/P1 items above:

- adding more channels;
- improving report prose;
- large benchmark expansions;
- new synthesis pipelines;
- legacy `query` resurrection;
- UI or dashboard work.

The current bottleneck is not channel count. The bottleneck is trust: status must
be truthful, configuration must really work, failures must be safe, and the docs
must describe the product that actually ships.
