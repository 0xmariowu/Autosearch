# Changelog

All changes to AutoSearch. Format: `## YYYY.M.D` with `### Changes` and `### Fixes`.

---

## Unreleased


---

## 2026.4.7

## 2026.4.6

## 2026.4.5

## 2026.4.4-1

## 2026.4.4

### Changes

- **Delivery format selection.** `/autosearch` now asks for delivery medium (Markdown / Rich HTML / Presentation slides) instead of content structure. Content structure auto-determined by Depth. (#29)
- **Language auto-detection.** Output language and channel prioritization auto-detected from topic language. No extra question needed. (#29)
- **Language pre-filter.** Channel selection reads SKILL.md Language section to exclude mismatched channels (e.g., English topic skips Chinese-only channels). Saves 10+ wasted channel calls. (#31)
- **Orchestrated progress output.** Replaced single researcher agent (11-minute black box) with 4 orchestrated blocks. Each block is a Sonnet agent; between blocks, the main context outputs `[Phase N/6] ✓ {name} — {metric}` visible to the user in real-time. Errors surface immediately instead of after a timeout. (#31)
- **Inter-block data contract.** Added `state/session-{id}-knowledge.md` (systematic recall output) and `state/session-{id}-queries.json` (query array) for clean data handoff between blocks. (#31)
- **Model routing.** Each block runs in Sonnet (`model: "sonnet"`). Phase A (config) runs in parent model. No more implicit model inheritance. (#31)
- **CalVer versioning.** Switched from SemVer to CalVer `YYYY.M.D`. First tag: `v2026.4.3`. (#29)
- **Test suite.** 9 → 279 tests: judge.py (27), search_runner (19), channel smoke (64), SKILL.md compliance (160). (#27)
- **CI improvements.** Draft PRs skip CI. Runtime deps installed in test job. Network tests excluded. (#27, #29)
- **PR template.** Added Scope checklist and CHANGELOG checkbox. (#29)
- **STANDARD.md.** Body sections updated to match actual channel format. (#27)

### Fixes

- **Pre-push hook.** Uses project venv for pytest instead of system Python. (#27)
- **Python version.** Standardized to 3.10+ (was inconsistent 3.10/3.11). (#27)

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
