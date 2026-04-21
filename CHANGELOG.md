# Changelog

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
