# Changelog

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
- 8 new workflow skill candidates landed (W3.6, from v2 proposal §3.7). All docs-only meta skills that codify runtime-AI workflow patterns borrowed from prior art in `~/Armory/Search/` — they do not add Python code, the runtime AI is the implementer:
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
