# Changelog

All changes to AutoSearch. Format: `## YYYY.M.D` with `### Changes` and `### Fixes`.

---

## Unreleased

### Changes

- **Delivery format selection.** `/autosearch` now asks for delivery medium (Markdown / Rich HTML / Presentation slides) instead of content structure. Content structure auto-determined by Depth. (#29)
- **Language auto-detection.** Output language and channel prioritization auto-detected from topic language. No extra question needed. (#29)
- **Language pre-filter.** Channel selection reads SKILL.md Language section to exclude mismatched channels (e.g., English topic skips Chinese-only channels). Saves 10+ wasted channel calls. (#31)
- **Progress output.** Each pipeline phase outputs `[Phase N/6] ✓ {name} — {metric}`. No more 15-minute black hole. (#31)
- **Model routing.** Pipeline runs in Sonnet via researcher agent (5x cheaper than Opus). Command file split into Phase A (config, Opus) + Phase B (pipeline, Sonnet). (#31)
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

- **AutoSearch is now a Claude Code Plugin.** Install with `/plugin marketplace add 0xmariowu/autosearch` + `/plugin install autosearch@autosearch`. Full plugin structure: commands, agents, skills, hooks, marketplace.json. Why: making AutoSearch distributable to any Claude Code user.
- **32 search channels as independent plugins.** Each channel is a directory with SKILL.md (capability profile) + search.py (search implementation). Channels auto-discovered by convention-based loader. Why: each channel can be independently developed, tested, and evolved.
- **Chinese channels work (0% → 100%).** Switched from DuckDuckGo (which doesn't index Chinese sites) to Baidu Kaifa Developer Search (kaifa.baidu.com). 10 Chinese channels now return results: zhihu, csdn, juejin, 36kr, infoq-cn, weibo, xueqiu, xiaoyuzhou, xiaohongshu, douyin. Why: ddgs site:zhihu.com returned 0 results; kaifa.baidu.com returns 10+ with no CAPTCHA.
- **7 channels extracted from SearXNG.** bilibili (API), stackoverflow (StackExchange API), reddit (JSON API + ddgs fallback), google-scholar (HTML + ddgs fallback), youtube (HTML parsing), wechat (Sogou), npm-pypi (npm API + PyPI HTML). Why: real APIs beat ddgs site:X in quality and reliability.
- **Twitter/X channel added.** Searches both twitter.com and x.com via ddgs, deduplicates by status ID. Why: many announcements, paper releases, and tech discussions happen on Twitter first.
- **ddgs package upgraded to v9.12.** Old `duckduckgo_search` package was completely broken (0 results). New `ddgs` package restores all ddgs-dependent channels. Why: the old package was deprecated and stopped returning results.
- **Two-stage citation lock.** Before synthesis, all search result URLs are compiled into a numbered reference list. Synthesis can only cite from this list. Background knowledge marked explicitly. Why: prevents URL hallucination (rubric r023 was failing).
- **Mandatory query rules.** Academic topics must generate conference/workshop queries. Product topics must generate company/product queries. Chinese channels must use Chinese query text. Why: rubrics r005 (companies) and r013 (conferences) were failing due to missing query types.
- **Model routing: Haiku for batch, Sonnet for quality.** Scoring, rubric checking, and query generation use Haiku. Synthesis and AVO evolution use Sonnet. Search itself uses no LLM. Why: 3-5x cost reduction on batch tasks without quality loss.
- **AVO evolution targets refined.** Evolution now prefers data updates (channel-scores.jsonl) over skill text changes. Priority: data > rules > structure. Why: data changes are more precise, verifiable, and revertible.
- **Benchmark: +20% vs native Claude.** 5 topics tested (academic, tools, business, Chinese, how-to). AutoSearch: 92%, Native Claude: 72%. Biggest gains: citations (+30%), fresh content (+20%), Chinese sources (+15%). Why: quantifiable proof of value.
- **search_runner.py reduced from 735 to 149 lines.** All channel code moved to plugin directories. search_runner is now a thin dispatcher. Why: separation of concerns — channels are independent, runner just orchestrates.
- **V1 code archived to legacy/.** 28 Python files, 14 directories moved. Root directory is clean plugin structure. Why: V1 code was prototype-era, not part of the distributable plugin.
- **User interaction flow.** 3 questions before search (depth, focus, format) + 1 confirmation after search results. 4 output format templates (executive summary, comparison, full report, resource list). Why: different users need different search strategies and output styles.

## 2026-04-01 (v4.0 — Rubric AVO)

- Rubric-based evolution system: auto-generate topic-specific rubrics, score delivery against them, evolve skills based on failures. Why: generic quality metrics didn't catch specific content gaps.
- Pipeline test: 0.880 pass rate (22/25 rubrics) on "self-evolving AI agent frameworks". 4/8 channels failed (reddit, zhihu, producthunt, papers-with-code). Why: established baseline for channel improvement work.

## 2026-03-29 (v2.2)
- You can now run `/autosearch` with V1's full capabilities restored as evolvable skills: LLM-based relevance scoring (not keyword matching), 5-dimensional gene query generation, 14 platform connectors (8 free + 6 paid), goal-driven research cycles, anti-cheat validation, provider health tracking, and outcome-based query boosting. Why: v2.0 was an amputation — it removed V1's computational capabilities. v2.2 brings them back as skills that AVO can evolve.
- AutoSearch now uses your own knowledge as a research source alongside API searches. Claude's training data covers foundational works, key researchers, and domain concepts that no API search can find. Why: comparison testing showed native Claude outperformed AutoSearch specifically because of training knowledge + conceptual synthesis.
- Search results are now organized by concept (categories, design patterns, risk analysis) instead of by platform (GitHub results, Reddit results). Why: users need insight frameworks for decision-making, not URL lists sorted by source.
- judge.py expanded to 7 dimensions: +latency (time to delivery), +adoption (user feedback), relevance switched from keyword counting to LLM-based scoring. Why: V2.0's judge gave 0.993 relevance to irrelevant results because it only matched keywords.
- V1 accumulated intelligence migrated: 27 patterns, 290 evolution entries, 31 outcomes, 30 playbook entries. Why: V1 ran hundreds of sessions — that experience shouldn't be lost in a rewrite.
- 29 skills total in superpowers format (name + description, free-form body), including 5 meta-skills for self-evolution: create-skill, observe-user, extract-knowledge, interact-user, discover-environment.

## 2026-03-28 (v2.0)
- You can now run `/autosearch "find AI agent frameworks"` to execute a self-evolving search session. The system autonomously searches 5 platforms, scores results with judge.py, reflects, evolves its strategy, and delivers. Why: v2 replaces ~7000 lines of Python with ~100 lines of code + ~2500 lines of Markdown skills. Everything is now skills-native and AVO-driven.
- Added `autosearch/v2/` — complete skills-native architecture: PROTOCOL.md (operating protocol), skill-spec.md (skill format), judge.py (deterministic scorer), 14 skills (5 platform + 4 strategy + 5 AVO), state management. Why: v1's Python runtime was hard to evolve; v2 lets the AVO loop modify skills directly as Markdown.
- End-to-end validated: 43 results from 4 platforms, judge score 0.853, full worklog cycle from task_spec to delivery.
- You can now evolve search strategies as JSON genomes instead of hardcoded Python. New `genome/` module: schema (8 sections), runtime interpreter, 13 primitives, 5 mutation operators, safe expression evaluator. Run `python3 avo.py "task" --genome` to start genome-based AVO evolution. Why: AVO paper's Vary(P_t) needs a structured, evolvable representation — Python code can't be safely mutated by an AI agent, but JSON genomes can.
- Three seed genomes created from existing strategies: `engine-3phase.json` (3-phase explore/harvest/postmortem), `orchestrator-react.json` (ReAct loop), `daily-discovery.json` (daily discovery). Why: AVO needs initial population members to start evolution from known-good strategies.
- All existing modules now accept optional `genome=` parameter with fallback to current hardcoded defaults. Files: modes.py, lexical.py, planner.py, synthesizer.py, project_experience.py, engine.py, orchestrator.py, daily.py, goal_runtime.py. Why: gradual migration — genome config is opt-in, existing behavior unchanged.
- MCP `autosearch_evolve` tool now uses genome-based evolution via `run_avo_genome()`. Why: genome evolution is the new default path for AVO.

## 2026-03-24
- Added `goal_cases/`, `goal_judge.py`, and `goal_loop.py` to test a concrete `autoresearch`-style improvement loop against project-specific problems and score deltas. Why: AutoSearch needed a measurable self-improvement path based on goal progress, not only generic search quality.
- Added `program.md`, `control_plane.py`, and `control/latest-program.json` to synthesize the current operating program from objective + capability + experience. Why: AutoSearch needed a machine-readable equivalent of the lightweight `program.md` idea from `karpathy/autoresearch`, but adapted to search work instead of model training.
- Added `sources/catalog.json`, `source_capability.py`, `doctor.py`, and `sources/latest-capability.json`, then wired daily/runtime to consume static provider availability before search. Why: AutoSearch needed a real capability layer inspired by agent-reach so it knows what sources are usable, not just what performed well recently.
- Added AlphaXiv SSE MCP server to `/Users/dev/.mcp.json` and documented it in AutoSearch methodology/platform docs. Why: the system needed a paper-native research source that is available in the environment now, even before it becomes a first-class runtime provider.
- Added `standards/` docs for demand, search, content candidates, routeable-map handoff, and project experience. Why: AutoSearch needed atoms-style boundary docs that separate demand, search execution, routing preparation, and runtime policy without prematurely defining final admission rules.
- Added `project_experience.py` plus `experience/` runtime files (`experience-ledger/index/policy/latest-health`) and wired `daily.py` + `engine.py` to refresh them automatically after runs. Why: AutoSearch needed a lightweight runtime policy layer that can reorder providers and skip cooldown providers without changing the 3-phase core.
- Preserved `query_family` and stronger harvest provenance in engine/evolution/outcomes flow, and added minimal tests. Why: future feedback loops need stable `source_query/query_family` lineage instead of guessing only from sample titles.
- Added global CLAUDE.md reference to autosearch/CLAUDE.md. Why: AI-friendly standard requires declaring relationship to global rules.
- Fixed broken reference in docs/README.md: `AIMD/projects/search-methodology/` → `autosearch/docs/methodology/`. Why: content moved on 2026-03-23 but reference wasn't updated.

## 2026-03-23
- Moved search methodology from `AIMD/projects/search-methodology/` to `autosearch/docs/methodology/`. Why: methodology belongs with the code that implements it, not in the global experience library.
