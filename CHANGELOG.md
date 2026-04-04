# Changelog

All changes to AutoSearch. Format: `## YYYY.MM.DD.N` with `### Changes` and `### Fixes`.

---

## Unreleased


---

## 2026.04.04.8

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
