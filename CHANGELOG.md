# Changelog

## 2026.04.23.3 — 2026-04-23

- `autosearch init` now shows ASCII banner, auto-configures MCP for Claude Code / Cursor, and displays Integration Status + "You are all set!" — vibeusage-style install UX



## 2026.04.23.2 — 2026-04-23

**百万用户化改造（G1–G7，1:1 参考 Agent-Reach / MediaCrawlerPro）**

**G1 — 一行安装：**
- `docs/install.md`：把 URL 粘贴给 AI Agent 即可完成安装和 MCP 配置
- `autosearch init` 末尾输出 MCP config snippet

**G2 — Doctor 分层输出（1:1 from Agent-Reach doctor.py）：**
- Tier 0（开箱即用 25 个）/ Tier 1（需 API key）/ Tier 2（需登录）三层展示
- 每个未配置渠道显示 fix_hint（如 `autosearch login xhs`）
- MCP `doctor()` 返回 `{report, channels, summary}` 结构化响应

**G3 — 多平台登录：**
- `autosearch login` 支持 7 个平台：xhs / twitter / bilibili / weibo / douyin / zhihu / xueqiu
- `--from-string` 参数：Cookie-Editor 导出字符串直接粘贴
- `_write_cookie_to_secrets()` 提取为可复用 helper

**G4 — 新渠道（1:1 from Agent-Reach channels/）：**
- `xueqiu`（雪球）：股票搜索 + 热门帖子，需 `autosearch login xueqiu`
- `linkedin`：公开页面 via Jina Reader，零配置可用

**G5 — 配额管理：**
- Python 侧：`TikhubBudgetExhausted` 触发 fallback_chain 下一个方法，不再报错
- Worker 侧：每个 IP 独立配额 50 次/天，防止一个用户耗尽共享 token

**G6 — Circuit breaker 分类（MediaCrawlerPro 账号池设计）：**
- `FailureCategory` 枚举：QUOTA_EXHAUSTED / AUTH_FAILURE / NETWORK_ERROR / PLATFORM_BLOCK
- `ChannelHealth.record_categorized_failure()`：每类失败有独立冷却时间（24h / 0 / 5min / 1h）

**G7 — 输出优化（1:1 from Agent-Reach format_xhs_result）：**
- `Evidence.to_context_dict(max_content_chars=500)`：精简版，省约 60% token
- `run_channel` MCP 工具默认使用精简输出

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
