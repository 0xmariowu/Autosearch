# AutoSearch Upgrade Report

Date: 2026-04-24

Scope: this report evaluates the current repository as a fresh-install product and a production-grade agent tool supplier. It intentionally does not cover migration of already-installed user machines.

## Executive Summary

AutoSearch has moved from a full "deep research pipeline that writes reports" into a v2 MCP tool-supplier architecture. The strongest current product shape is:

1. install AutoSearch;
2. configure it as an MCP server;
3. let the host Agent call `list_skills`, `run_clarify`, `select_channels_tool`, `run_channel`, `citation_*`, and workflow tools;
4. let the host Agent synthesize the final report.

The codebase is much healthier than the public-facing story. The repository has good unit coverage, working packaging, a real MCP server, and 39 channel skills. A fresh, no-secret environment exposes 25 working channels. In a configured local environment, 32 channels report usable or partially usable status.

The main production risk is not "the code does not exist". The main risk is product contract mismatch:

- README and docs still promise a one-line deep-research experience.
- `autosearch query` is deprecated and exits non-zero.
- `research()` MCP is deprecated by default.
- `autosearch doctor` is documented as a CLI command but does not exist as a CLI command.
- report quality is now delegated to the host Agent, but docs do not teach the Agent a reliable synthesis workflow.

Recommended upgrade direction: make AutoSearch honest and excellent as an Agent research toolbox, not as a standalone report writer. Ship a fresh-install path that proves MCP tools are available, channels are inspectable, and evidence can be turned into cited reports by the Agent.

## Current Ground Truth

Observed repository state:

- Python package version in project metadata: `2026.04.23.9`.
- PyPI latest version: `2026.4.23.9`.
- npm wrapper latest version: `autosearch-ai@2026.423.9`.
- Python requirement: `>=3.12`.
- Primary CLI entrypoint: `autosearch = autosearch.cli.main:app`.
- MCP entrypoint: `autosearch-mcp = autosearch.mcp.cli:main`.
- Channel skill count: 39.
- Channel method implementation files: 43.

Local verification performed:

```bash
./.venv/bin/ruff check .
./.venv/bin/ruff format --check .
AUTOSEARCH_LLM_MODE=dummy ./.venv/bin/pytest -q -m "not real_llm and not perf and not slow and not live" --ignore=tests/perf
AUTOSEARCH_LLM_MODE=dummy ./.venv/bin/pytest -q -m smoke
uv build
```

Results:

- Ruff lint passed.
- Ruff format check passed.
- Non-live default test set passed: 725 tests.
- Smoke test set passed: 5 tests.
- `uv build` produced a wheel and sdist for `2026.4.23.9`.
- Fresh wheel install worked in a temporary Python 3.12 environment.

Important caveat:

- The local development `.venv` had stale editable metadata showing `2026.4.22.5`, while the built wheel metadata correctly showed `2026.4.23.9`. This is not a release artifact problem, but it can confuse local manual checks.

## Product Contract Mismatch

The public surface currently sends contradictory signals.

README says:

- `npx autosearch-ai` fixes deep research in one line.
- after install, the Agent searches 39 channels simultaneously.
- `autosearch doctor` checks every channel.

Actual behavior:

- `autosearch query ...` exits with a v2 deprecation message.
- unknown CLI commands are treated as default `query`, so `autosearch doctor` currently becomes `query("doctor")` and fails with the deprecation message.
- MCP `research()` is present for compatibility but returns `delivery_status="deprecated"` by default unless `AUTOSEARCH_LEGACY_RESEARCH=1` is set.
- the actual useful MCP interface is the v2 tool set, especially `list_skills`, `run_clarify`, `run_channel`, `list_channels`, and `doctor`.

This mismatch is the highest-priority issue because it affects the first five minutes of a fresh install.

## Fresh Install Path

The fresh install path should become:

```bash
npx autosearch-ai
```

or:

```bash
curl -fsSL https://raw.githubusercontent.com/0xmariowu/Autosearch/main/scripts/install.sh | bash
```

Expected outcome for a new user:

1. Python 3.12+ is found or a clear error is printed.
2. AutoSearch is installed.
3. `autosearch init` runs.
4. MCP config is written for Claude Code and Cursor when those config directories exist.
5. user can run a real local CLI verification command.
6. user sees a correct channel status table.
7. user gets one clear prompt to restart/reload their Agent MCP client.

Current blockers:

- `autosearch init` tells users to run `autosearch doctor`, but CLI `doctor` does not exist.
- `InitRunner` still says the next setup test is `autosearch query "your question"`, but `query` is deprecated.
- docs show `doctor --fix`, but no CLI `--fix` exists.
- docs describe `research()` as the main MCP tool in some places, which is no longer true.

Upgrade target:

```bash
autosearch --version
autosearch doctor
autosearch mcp-check
```

`mcp-check` can be a small CLI verification command that creates the MCP server in-process, lists tools, and confirms required v2 tools exist. It does not need to call network channels.

Minimum required tools:

- `list_skills`
- `run_clarify`
- `run_channel`
- `list_channels`
- `doctor`
- `select_channels_tool`
- `citation_create`
- `citation_add`
- `citation_export`

## CLI Upgrade Requirements

### P0. Add `autosearch doctor`

The CLI should expose the same channel health scanner already available through MCP.

Required behavior:

- exit 0 when scan completes;
- print grouped channel status;
- show fix hints for blocked channels;
- support `--json` for machine-readable status;
- avoid noisy structlog output from missing optional implementations;
- do not require LLM keys.

Acceptance command:

```bash
env -i PATH="$PATH" HOME="$HOME" autosearch doctor
```

Expected:

- includes total channel count;
- includes always-on/API-key/login groupings;
- exits 0.

### P0. Replace `query` as the post-install test

`query` is deprecated. It should not be suggested as a setup validation path.

Replace with:

```bash
autosearch doctor
```

and:

```bash
autosearch mcp-check
```

Optional future command:

```bash
autosearch sample "BM25 ranking"
```

This could run `run_channel` against a free channel like `ddgs` or `arxiv`, then print raw evidence. It must not pretend to be a full report generator.

### P1. Make unknown commands fail as unknown commands

The default-query behavior was useful when CLI query was the main product. Now it hides user mistakes. `autosearch doctor` currently fails as a deprecated query, which is confusing.

Recommended change:

- remove or restrict `_DefaultQueryGroup`;
- keep `autosearch query <text>` explicit;
- unknown commands should produce normal Typer command errors.

This makes the CLI safer and clearer.

## MCP Upgrade Requirements

The MCP server is the core product surface.

Current strengths:

- `create_server()` registers many useful tools.
- `run_channel` returns structured evidence.
- `run_channel` deduplicates URLs, near-deduplicates with SimHash, and BM25-reranks.
- `list_skills` exposes static skill metadata.
- `list_channels` and `doctor` expose runtime availability.
- citation tools exist and are simple.

Current weaknesses:

- docs still center the deprecated `research()` tool.
- `research()` still appears in tools list and may attract Agents because it looks like the obvious high-level action.
- server instructions say the trio is preferred, but not all client docs teach a concrete workflow.
- no CLI command verifies MCP tool registration from a fresh install.

Upgrade target:

The docs and server instructions should describe this standard workflow:

1. call `doctor` or `list_channels`;
2. call `list_skills(group="channels")` if channel discovery is needed;
3. call `run_clarify(query)`;
4. if clarification is needed, ask the user;
5. call `select_channels_tool` using clarify output;
6. call `run_channel` on selected channels, preferably in parallel;
7. use `citation_create` and `citation_add` while writing;
8. synthesize the report in the host Agent;
9. call `citation_export` for references;
10. self-check report against rubrics from `run_clarify`.

Recommended server-side prompt addition:

```text
Do not call research() unless the user explicitly asks for the deprecated legacy path. For new work, call run_clarify and run_channel, then synthesize directly from evidence.
```

## Channel Reliability Assessment

### Channel Inventory

Current channel list:

```text
arxiv bilibili crossref dblp ddgs devto dockerhub douyin github google_news
hackernews huggingface_hub infoq_cn instagram kr36 kuaishou linkedin openalex
package_search papers podcast_cn pubmed reddit searxng sec_edgar sogou_weixin
stackoverflow tieba tiktok twitter v2ex wechat_channels weibo wikidata wikipedia
xiaohongshu xueqiu youtube zhihu
```

### Clean Environment Status

In a clean environment with no API keys or cookies:

- total: 39 channels;
- ok: 25;
- warn: 3;
- off: 11.

This is a good base for a fresh-install product. The correct claim should be "25+ channels work out of the box; 39 total are available with optional configuration", not "39 ready immediately".

### Configured Local Environment Status

In the current local environment:

- total: 39 channels;
- ok: 32;
- warn: 5;
- off: 2.

This indicates that optional environment configuration can unlock substantial coverage, but this should not be used as the baseline public promise.

### Live Free-Channel Sampling

Manual live sample results:

| Channel | Result |
|---|---|
| arxiv | returned 10 results |
| ddgs | returned 10 results |
| github | returned 10 results |
| reddit | returned 10 results |
| hackernews | returned 10 results |
| sogou_weixin | returned 10 results |
| stackoverflow | returned 10 results |
| pubmed | returned 10 results |
| wikipedia | returned 10 results |
| google_news | returned 10 results |
| tieba | returned empty |

Interpretation:

- academic, developer, web, and English community channels have credible live behavior;
- `sogou_weixin` works in this sample but is HTML-scrape based and should be treated as fragile;
- `tieba` is not reliable enough to count as high-confidence without better parsing or query fallback.

### Reliability Tiers

Recommended public tier names:

- Always-on: no key, no login, expected to work for most users.
- Optional key: requires a free or paid key.
- Account/session: requires cookies or browser login.
- Experimental: available, but platform payload or anti-bot behavior may change.

Recommended internal reliability scoring:

| Score | Meaning |
|---|---|
| A | official or stable API, live-tested nightly |
| B | public API or stable RSS/HTML, some rate/shape risk |
| C | scraped or third-party payload, likely to drift |
| D | requires account/cookie or paid proxy; must classify failures carefully |

Likely classification:

- A: arxiv, pubmed, openalex, crossref, dblp, hackernews, stackoverflow, wikipedia, wikidata, google_news, dockerhub, package_search.
- B: ddgs, github anonymous repo search, reddit public search, devto, huggingface_hub, sec_edgar, kr36, infoq_cn, v2ex.
- C: sogou_weixin, tieba, linkedin via Jina.
- D: TikHub channels, XHS signing-worker path, cookie-based paths, xueqiu.

## Channel Failure Handling

Current behavior is user-safe but diagnostically weak:

- many channel methods catch exceptions and return `[]`;
- MCP `run_channel` returns `ok=True` when a channel ran but returned no evidence;
- platform/auth/quota/parser problems can look identical to a legitimate empty result.

This is acceptable for not crashing, but not enough for production-quality research.

Upgrade target:

`RunChannelResponse` should distinguish:

- `ok`: channel executed and evidence was returned;
- `empty`: channel executed successfully but found no results;
- `auth_required`: missing or invalid credentials;
- `quota_exhausted`: known quota/budget/rate limit failure;
- `platform_blocked`: anti-bot, CAPTCHA, account restriction, or platform refusal;
- `parser_changed`: payload shape changed or expected fields missing;
- `network_error`: timeout, DNS, connection reset;
- `unknown_error`: uncategorized exception.

This change would materially improve report quality because the Agent can say "XHS was unavailable due to account restriction" instead of silently omitting XHS evidence.

## Report Quality Assessment

AutoSearch should not currently claim that it independently produces high-quality full reports.

What it can credibly claim:

- it discovers channels;
- it clarifies intent;
- it retrieves raw evidence;
- it deduplicates and reranks evidence;
- it provides citation-index helpers;
- it provides workflow helpers for planning, loops, recency filtering, context retention, and delegation.

What is not currently a reliable product promise:

- standalone `autosearch query` report generation;
- default MCP `research()` report generation;
- guaranteed "deep research report" from one command.

Recommended report-quality workflow:

1. `run_clarify` generates rubrics and channel priorities.
2. Agent asks clarification if needed.
3. Agent selects 3-8 channels using `select_channels_tool`.
4. Agent calls `run_channel` across channels.
5. Agent drops failed/empty channels only after recording why.
6. Agent reruns follow-up searches for coverage gaps.
7. Agent uses citation tools to deduplicate source URLs.
8. Agent writes report with inline citations.
9. Agent includes a source coverage table.
10. Agent lists unavailable channels and impact on confidence.

Recommended report structure:

```markdown
# Title

## Answer

## Evidence

## Comparison / Analysis

## Gaps And Confidence

## Sources
```

Required report quality bars:

- every factual claim from search evidence has a source URL;
- at least two independent sources for important claims when possible;
- channel failures are disclosed when they affect coverage;
- recency-sensitive topics include dates;
- Chinese UGC reports separate organic user opinion from paid/promo content when evidence allows;
- no uncited "training data" claims should be mixed into search-backed conclusions without labeling them as model background.

## Documentation Upgrade Requirements

### README

README should be rewritten around the true product:

- "Research tools for coding agents" rather than "one-line deep research replacement".
- "25+ channels work out of the box; 39 total with optional keys/cookies."
- "Use through MCP from Claude Code/Cursor."
- "AutoSearch supplies evidence; your Agent synthesizes."

README quickstart should be:

```bash
npx autosearch-ai
autosearch doctor
```

Then a short Agent prompt:

```text
Use AutoSearch MCP. First call doctor/list_channels, then run_clarify, then run_channel on relevant channels. Write a cited report from the evidence.
```

### Install Docs

Fix these contradictions:

- remove `autosearch query "your question"` as a setup test;
- do not mention `doctor --fix` until implemented;
- make MCP client restart/reload explicit;
- describe optional channel unlocks after the base install is verified.

### MCP Docs

Rewrite `docs/mcp-clients.md` around the v2 tools.

The old `research` tool section should become a deprecation appendix.

New main examples should show:

- listing tools;
- running `doctor`;
- running `run_channel` for `ddgs` or `arxiv`;
- creating citations;
- synthesizing a report in the client.

### Channels Docs

Fix counts and terms:

- README currently says 39 channels.
- docs say Tier 0 has 26 channels, but clean runtime status showed 25 ok.
- some channels are "available" because a paid key exists in local env, not because they are always-on.

Channels docs should be generated from the registry where possible.

## Test And Release Gate Upgrade

Current automated test health is good, but some release matrices still contain old assumptions.

Observed outdated release-gate pattern:

```bash
autosearch query "What is BM25" --mode fast --no-stream
```

expected:

```text
References
```

This conflicts with v2 deprecation. It should be removed from release gates unless `AUTOSEARCH_LEGACY_RESEARCH=1` is intentionally being tested.

Recommended release gates:

### Gate A: Fresh Install

```bash
uv venv --python 3.12 /tmp/fresh
uv pip install --python /tmp/fresh/bin/python dist/autosearch-*.whl
/tmp/fresh/bin/autosearch --version
/tmp/fresh/bin/autosearch doctor
/tmp/fresh/bin/autosearch mcp-check
```

### Gate B: MCP Tool Availability

Create server in-process and assert required tools exist.

Required:

- `list_skills`
- `run_clarify`
- `run_channel`
- `list_channels`
- `doctor`
- `select_channels_tool`
- `delegate_subtask`
- `citation_create`
- `citation_add`
- `citation_export`

### Gate C: Free Channel Live Smoke

Nightly, not every PR:

- arxiv
- pubmed
- ddgs
- github anonymous repo search
- hackernews
- reddit
- stackoverflow
- wikipedia
- google_news
- sogou_weixin, with warning-only status if blocked

### Gate D: Report Workflow E2E

Mock or live-light:

1. run clarify;
2. select channels;
3. run 2 free channels;
4. add citations;
5. export citations;
6. assert evidence and citations are non-empty.

This tests the actual v2 product path without relying on deprecated synthesis.

### Gate E: Docs Contract

Add a static check that fails if primary docs recommend:

- `autosearch query` as the main happy path;
- `research()` as the primary MCP path;
- `autosearch doctor --fix` before `--fix` exists;
- "39 ready out of the box".

## Packaging And Release Notes

Packaging mostly works:

- wheel builds;
- package data includes channel skills, methods, prompts, router references, and tool skills;
- console scripts are registered.

Needed cleanup:

- update `pyproject.toml` description from `AutoSearch v2 M1 skeleton` to a real product description;
- remove `pytest`, `ruff`, and test-only dependencies from runtime dependencies if they are not needed at runtime;
- move dev dependencies into an optional `dev` extra;
- ensure `.claude-plugin/marketplace.json` nested versions match top-level version;
- add CI check for nested marketplace versions.

Recommended package description:

```toml
description = "MCP research tool supplier for coding agents, with 39 academic, web, developer, and Chinese-source channels"
```

## Security And Privacy

Areas already handled reasonably:

- secret values are not printed in normal configuration paths;
- `configure` writes masked confirmation;
- cookie import supports browser extraction and direct string.

Production concerns:

- `autosearch configure KEY VALUE` takes secret value as a CLI argument, which can be captured in shell history and process listings.
- cookie strings are stored in `~/.config/ai-secrets.env`.
- `autosearch login --from-string` also puts cookie in shell history.

Recommended upgrade:

- add `autosearch configure KEY` interactive prompt mode that reads secret from stdin without echo;
- update docs to prefer prompt mode for secrets;
- keep current positional value as advanced/automation path with warning;
- document where secrets are stored and how to remove them.

## Upgrade Roadmap

### Phase 1: Contract Repair

Goal: fresh install no longer points users into deprecated paths.

Tasks:

1. Add CLI `doctor`.
2. Add CLI `mcp-check`.
3. Change `init` success text and `InitRunner.next_steps`.
4. Remove `query` from primary docs.
5. Rewrite MCP docs around v2 tools.
6. Change README promise from "39 ready" to "25+ out of box, 39 total".

Acceptance:

```bash
uv build
uv venv --python 3.12 /tmp/as-fresh
uv pip install --python /tmp/as-fresh/bin/python dist/autosearch-*.whl
/tmp/as-fresh/bin/autosearch doctor
/tmp/as-fresh/bin/autosearch mcp-check
```

### Phase 2: Channel Diagnostics

Goal: Agents can tell the user why a channel was not useful.

Tasks:

1. Add status/failure category to `RunChannelResponse`.
2. Standardize channel method exception classes or return envelopes.
3. Distinguish empty result from failed fetch.
4. Add auth/quota/platform-block/parser-changed categories.
5. Update `doctor` to use the same category vocabulary where applicable.

Acceptance:

- missing YouTube key returns `auth_required` or `not_configured`, not silent empty;
- XHS account restriction returns `platform_blocked`;
- parser shape mismatch returns `parser_changed`;
- `run_channel` tests cover each category.

### Phase 3: Report Workflow Quality

Goal: make host Agents reliably turn evidence into good reports.

Tasks:

1. Add an `autosearch-report-workflow.md` prompt or skill.
2. Teach Agents to disclose channel coverage and failures.
3. Add citation workflow examples.
4. Add mocked end-to-end report workflow tests.
5. Add a small report quality rubric checker that can run without the legacy pipeline.

Acceptance:

- a fresh Agent prompt can produce a cited answer from `run_channel` outputs;
- no dependency on deprecated `research()`;
- final report includes references and coverage limitations.

### Phase 4: Release Gate Alignment

Goal: CI protects the real product shape.

Tasks:

1. Remove deprecated `query` report expectations from release matrices.
2. Add fresh-wheel install gate.
3. Add MCP tool availability gate.
4. Add free-channel nightly gate.
5. Add docs-contract static gate.
6. Add version consistency gate for nested marketplace fields.

Acceptance:

- release cannot pass if docs recommend dead commands;
- release cannot pass if CLI `doctor` is missing;
- release cannot pass if MCP trio is missing.

### Phase 5: Packaging Polish

Goal: reduce install weight and make package metadata professional.

Tasks:

1. Move `pytest` and `ruff` to a `dev` extra.
2. audit dependencies for runtime necessity.
3. update package description.
4. run `twine check` in CI.
5. verify wheel contents include skills and prompts.

Acceptance:

- fresh install works without dev-only packages;
- wheel metadata has production description;
- `twine check dist/*` passes.

## Go / No-Go Criteria For Next Release

Go if all are true:

- `autosearch doctor` exists and works from a fresh wheel install.
- `autosearch mcp-check` exists and verifies v2 tools.
- README and install docs no longer point to deprecated `query` as happy path.
- MCP docs center v2 tools, with `research()` only in a deprecation note.
- fresh no-secret install clearly reports always-on channels.
- release gates test the v2 workflow, not the legacy report pipeline.

No-go if any are true:

- fresh install tells the user to run `autosearch query`.
- docs claim 39 channels are ready out of the box.
- `autosearch doctor` is still missing.
- release tests still expect `autosearch query` to return `References`.
- `research()` is presented as the primary MCP API.

## Recommended Positioning

Best current positioning:

> AutoSearch gives coding agents live research tools across academic, developer, web, and Chinese-source channels. It supplies evidence and citations through MCP; your Agent keeps control of reasoning and final synthesis.

Avoid:

> One-line replacement for OpenAI or Perplexity Deep Research.

Reason:

That claim implies a standalone report-writing pipeline. The current architecture deliberately moved away from that because the host Agent is better at synthesis than the old internal pipeline.

## Immediate Next PR

The next PR should be small and contract-focused:

1. add CLI `doctor`;
2. add CLI `mcp-check`;
3. fix `init` next steps;
4. update README quickstart wording;
5. update `docs/install.md`;
6. add tests for `doctor` and `mcp-check`.

Suggested test commands:

```bash
./.venv/bin/ruff check .
./.venv/bin/ruff format --check .
AUTOSEARCH_LLM_MODE=dummy ./.venv/bin/pytest -q tests/unit/test_cli_main.py tests/unit/test_cli_init.py tests/smoke/test_cli_doctor_smoke.py tests/smoke/test_mcp_stdio_smoke.py
uv build
```

This PR would remove the most visible production breakage without touching channel internals or already-installed user migration.
