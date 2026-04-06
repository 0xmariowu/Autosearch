# Changelog

All changes to AutoSearch. Format: `## YYYY.MM.DD.N` with `### Changes` and `### Fixes`.

---

## Unreleased


---

## 2026.04.06.2

### Changes

- You can now search YouTube and conference talks with meaningful snippets (author + video length) instead of empty dashes
- Chinese channels xiaohongshu, xiaoyuzhou, xueqiu, 36kr, weibo now use DuckDuckGo as fallback instead of unreliable Baidu Kaifa
- npm search switched from dead npms.io API to official npm registry, PyPI uses DuckDuckGo fallback
- HuggingFace now supports `HF_TOKEN` env var for authenticated API access, falls back to DuckDuckGo
- Semantic Scholar now supports `S2_API_KEY` env var for higher rate limits

### Fixes

- Fixed 5 Chinese channels returning 0 results due to Baidu Kaifa site filter dropping all off-domain results
- Fixed npm-pypi channel 100% failure (npms.io API shut down in 2024)
- Fixed YouTube/conference-talks returning 1-character snippets ("-")
- Fixed StackOverflow API missing Accept-Encoding header and error_id check

## 2026.04.06.1

### Changes

- You can now install via npm: `npm install -g @0xmariowu/autosearch`
- You can now use one API key (`SCRAPECREATORS_API_KEY`) to unlock full Reddit comments and Twitter engagement data
- Reddit and Twitter channels now use three-tier fallback: ScrapeCreators (optional) → native API → DuckDuckGo
- Twitter GraphQL query IDs auto-refresh from X's JS bundles (24h cache), no more brittle hardcoded IDs
- Reddit enrichment tries ScrapeCreators for comments before .json endpoint, with clear 403 logging
- Cookie extraction and fallback paths now log to stderr so users know what's happening
- Release pipeline now auto-syncs version, channel count (34), and skill count (54) across README, docs site, npm, and official website
- Channel count corrected to 34 (was claiming 32), skill count to 54 (was claiming 40+)

### Fixes

- Fixed judge.py Python 3.9 compatibility (`from __future__ import annotations`)
- Removed ghost channel references (github-code, openreview) that never existed
- Fixed HuggingFace miscategorized as premium (it's free, moved to Academic)
- Unified phase naming across README, docs, and pipeline-flow
- Python version requirement standardized to 3.10+ (was inconsistent 3.10/3.11)

## 2026.04.05.5

### Changes

- You can now get deeply processed research content — top results are fetched in full via Jina Reader, filtered to query-relevant paragraphs with BM25, and stored as extracted content
- You can now get richer evidence in reports — claims from deep-processed results include verbatim evidence quotes and specific data points, not just one-sentence summaries
- Content processing pipeline replicated from crawl4ai: BM25 paragraph filtering, HTML noise pruning, sliding window chunking, citation formatting, 3-tier anti-bot detection
- Results are re-scored after content enrichment using full-content relevance (more accurate than snippet-based scoring)
- HN channel now uses story_text for Ask HN / Show HN posts (was showing only points/comments)
- arXiv abstracts are no longer truncated at 300 characters
- Snippet cap increased from 500 to 1500 characters for richer Block 3 evaluation

---

## 2026.04.05.4

## 2026.04.05.3

### Changes

- You can now get Reddit comment insights — top comments with scores, authors, and excerpts are fetched for the highest-scoring Reddit results
- You can now search X/Twitter with full engagement data — cookie-based GraphQL search returns likes, reposts, replies, and author handles (falls back to DuckDuckGo when no credentials)
- You can now run two-phase search — Phase 1 extracts entities (subreddits, X handles, authors), Phase 2 does targeted follow-up searches
- HN channel now includes `num_comments` in metadata (was only in snippet text)
- Claims pipeline now carries engagement scores, cross-platform signals, and top comments through to Block 4 synthesis
- Reranking now boosts cross-source convergent items as stronger evidence
- Channel selection now considers query type (how-to, comparison, opinion, etc.) for smarter prioritization

### Fixes

- CI hygiene author check no longer fails on merge commits created by `actions/checkout`

---

## 2026.04.05.2

### Changes

- You can now see how results rank across platforms — per-platform engagement scoring with composite scores (relevance + recency + engagement)
- You can now see when the same topic appears on multiple platforms — cross-source convergence detection adds "also on" annotations
- Search queries are now classified by type (how-to, comparison, opinion, etc.) for smarter source prioritization

---

## 2026.04.05.1

### Changes

- You can now search HuggingFace models and datasets — new `huggingface` channel searches by downloads
- You can now find trending AI papers — new `papers-with-code` channel via HuggingFace Daily Papers
- 34 search channels total (was 32)
- Cleaned up 18 orphan skills from legacy architecture (1,828 lines removed)
- Removed outdated platform methodology docs, moved evidence principles to root

## 2026.04.04.9

### Changes

- Added CI hygiene workflow — checks author identity, internal codenames, personal paths, and container image pins on every PR and push
- Git history fully rewritten — removed all PII (real names, Tailscale domains) from 270 commits
- Pre-commit hook now enforces author whitelist, personal path scan, and internal codename scan

### Fixes

- Removed literal PII from .gitleaks.toml detection rules (was leaking the values it was detecting)
- Removed internal project references from methodology docs
- Cleaned up 10 stale remote branches from pre-rewrite history

## 2026.04.04.8

### Changes

- Lazy-load channel plugins on first query instead of at import time — faster startup
- Added isort and bugbear rules to ruff linter, fixed import ordering across codebase
- Pyright now checks the correct directories (lib, channels, scripts)
- Replaced deprecated `asyncio.get_event_loop()` with `get_running_loop()`

### Fixes

- Pinned semgrep container image to SHA digest to prevent supply chain attacks
- Fixed shell injection risk in release.yml (github context moved to env blocks)
- Limited autofix CI to Python files only (was mutating JSON/YAML/MD)
- Added .dockerignore to prevent secrets and state from leaking into Docker builds
- Hardened pre-commit secret detection with modern key patterns (sk-ant, sk-or, tvly, github_pat, exa)
- Removed exec re-exec from pre-push hook (eliminated re-execution attack surface)
- HTML-escaped title in report assembly to prevent XSS
- Added `set -euo pipefail` to run_search.sh
- Removed dead code: batch_enrich.py, requirements-test.txt

## 2026.04.04.7

### Changes

- You can now benefit from engine-level health tracking — when Baidu or DuckDuckGo goes down, all dependent channels suspend together instead of failing one-by-one
- Transient failures (timeouts, network blips) now automatically retry once before giving up — timeout waits 5s, network errors wait 2s
- Channel health data now persists immediately after every success/failure, so a crash no longer loses health state from the current run

### Fixes

- Removed redundant internal retry from Semantic Scholar channel (now handled by runner-level retry)
- Added lxml dependency to requirements.txt (wechat channel was broken on fresh install)

## 2026.04.04.6

### Fixes

- Search failures now correctly distinguished from empty results — channels no longer get suspended for returning zero hits
- YouTube innertube key moved to environment variable (YOUTUBE_INNERTUBE_KEY)

## 2026.04.04.5

### Fixes
- You can now search Chinese topics without losing Chinese channels — channel scoring now tracks language separately, so English-session zero-yield no longer poisons Chinese channel selection
- Removed hardcoded Chinese channel exclusion list from select-channels skill

## 2026.04.04.4

### Changes
- You can now run pre-release tests with `./scripts/release-test.sh` — validates unit tests + real pipeline scenarios before tagging
- 6 user scenarios (Quick/Standard/Deep × EN/ZH, cold topic) with `--scenario s1|s2|s3|s4|s5|s7|all`
- Docker support for clean-environment testing (`docker-compose.test.yml`)
- Each scenario checks: timeout, block completion, judge score, delivery file, WebSearch bypass, Chinese content ratio

## 2026.04.04.3

### Fixes
- You can now search 120+ results without Block 4 hanging — claims compression enforced as required step, reducing agent input from 80KB to ~5KB
- All 6 pipeline blocks now have time limits (5/5/5/8/3/3 min) so a stuck block reports timeout instead of waiting forever

### Tests
- Stress tests: judge.py with 200 results, large file compact extraction, claims compression ratio
- Agent simulation tests: Block 4 HTML generation at 50 and 120+ result counts via OpenRouter
- Block 3 claims compression format verification via Haiku
- Evolution A/B test fix: patterns now properly copied between runs

## 2026.04.04.2

### Changes
- You can now get Haiku-compressed claims before synthesis — Block 3 compresses results to one-sentence claims for faster Block 4 input
- You can now get targeted gap-fill queries — Block 3 reflects on coverage gaps and generates follow-up queries
- Research context persists across sessions — same-topic searches skip covered dimensions

## 2026.04.04.1

### Changes
- You can now choose delivery format: Markdown, Rich HTML (tables + diagrams), or Presentation slides
- Language auto-detected from topic — Chinese topic gets Chinese output + Chinese channels prioritized
- Orchestrated 6-block pipeline replaces single-agent black box — you see `[Phase N/6]` progress in real-time
- 6 blocks with correct model routing: Haiku for classification, Sonnet for reasoning
- CalVer switched to `YYYY.MM.DD.N` format
- 9 → 279 tests: judge.py, search_runner, channel smoke, SKILL.md compliance

### Fixes
- Pre-push hook uses project venv for pytest
- Python version standardized to 3.10+

---

## 2026.4.3

### Changes

- **Plugin release.** AutoSearch is now a Claude Code Plugin. Install with `claude plugin marketplace add 0xmariowu/autosearch`. (#22)
- **32 search channels.** Each channel is a directory with SKILL.md + search.py. Auto-discovered by convention-based loader. (#22)
- **Chinese channels.** Switched to Baidu Kaifa Developer Search. 10 Chinese channels now work: zhihu, csdn, juejin, 36kr, infoq-cn, weibo, xueqiu, xiaoyuzhou, xiaohongshu, douyin. (#22)
- **Citation lock.** Two-stage citation: compile numbered reference list before synthesis, cite only from that list. (#24)
- **Model routing.** Haiku for batch (scoring, rubrics, queries), Sonnet for synthesis/evolution. (#24)
- **Benchmark.** AutoSearch 92% vs Native Claude 72% (+20%) across 5 topics. (#26)
- **User interaction.** 3 questions before search (depth, focus, delivery). (#26)

### Fixes

- **ddgs upgrade.** Old `duckduckgo_search` package broken (0 results). Upgraded to `ddgs>=9.12`. (#22)

---

## 2026.4.1

### Changes

- **Rubric AVO.** Auto-generate topic-specific rubrics, score delivery against them, evolve skills based on failures.
- **Pipeline baseline.** 0.880 pass rate (22/25 rubrics) on "self-evolving AI agent frameworks".

---

## 2026.3.29

### Changes

- **V1 capabilities restored.** LLM relevance scoring, 5-dimensional gene queries, 14 platform connectors, goal-driven cycles, anti-cheat, provider health tracking, outcome-based query boosting — all as evolvable skills.
- **Own-knowledge source.** Claude's training data used alongside search results.
- **Concept-organized output.** Results organized by concept, not by platform.
- **judge.py 7 dimensions.** Added latency, adoption, LLM-based relevance.
- **V1 intelligence migrated.** 27 patterns, 290 evolution entries, 31 outcomes.

---

## Pre-plugin history (2026-03-23 to 2026-03-28)

V1 and V2.0 prototype development. Code archived — see git history for details.
