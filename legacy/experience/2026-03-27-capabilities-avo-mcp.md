---
date: 2026-03-27
project: autosearch
type: experience
tags: [capabilities, avo, mcp, orchestrator, evolution, search]
---

# AutoSearch V6: Capabilities System + AVO Evolution + MCP Server

## Done

- Built AI-native capabilities registry: 43 capabilities with auto-discovery, self-tests, health checks, and manifest generation for LLM prompt injection
- Wrapped 17 existing modules (search_mesh, acquisition, evidence, rerank, goal_judge, research) as capabilities with standard contract (name/description/when/input_type/output_type/run/test)
- Implemented 26 new capabilities from 18 open-source projects: consensus scoring (SearXNG), content merging (Vane), 7-persona query expansion (Jina), learnings accumulation (dzhng), stuck detection (OpenManus), beast mode (Jina), backend health tracking (SearXNG), result caching (search_with_lepton), Jina reranker, freshness checking, breadth control, deep URL discovery, quality filtering, result export, search_all (concurrent 6-provider), search_and_process (combined pipeline)
- Built orchestrator with OpenRouter tool-use (gemini-2.5-flash): ReAct loop, learnings persistence, checkpoint/resume, token compression, message cleaning
- Implemented AVO (Agentic Variation Operators, arXiv:2603.24517): evolves orchestrator prompt via population lineage + LLM supervisor + edit-evaluate-diagnose inner loop
- Created MCP server (6 tools) for cross-project search access
- Fixed 6 infra bugs (evidence ID collision, URL normalization, connector KeyError, LLM JSON parsing, Tavily score) + 14 bugs from code review audit
- Added concurrent search execution (ThreadPoolExecutor), CLI --orchestrated/--evolve/--resume modes, daily pipeline orchestrator integration
- Tool filter (43→19 tools sent to LLM) eliminated 400 errors

## Produced

- `capabilities/` — 43 capability files + registry (__init__.py)
- `orchestrator.py` + `orchestrator_prompts.py` — ReAct orchestrator
- `avo.py` — AVO evolution framework
- `autosearch-mcp/` — MCP server (server.py, tools.py, requirements.txt)
- `docs/2026-03-27-deep-research-patterns.md` — research analysis of 18 repos
- `tests/test_capabilities_registry.py`, `test_new_capabilities.py`, `test_orchestrator.py` — test suite
- `sources/evolved-prompt.txt` — AVO-evolved best prompt (auto-loaded by orchestrator)

## Discovered

- [insight] Tool count matters for LLM reliability: 38 tools → intermittent 400 errors; 19 tools → 0 errors. Filter to only tools the orchestrator actually calls
- [insight] AVO evolution works for search: 15 generations evolved score from 0.50 to 0.81, cumulative 321 unique URLs. The evolved prompt was SHORTER and SIMPLER than the hand-written one
- [insight] The skill/dispatch pattern (describe what a tool does, let AI pick) maps perfectly to search capabilities. Adding a capability = adding a file, zero changes elsewhere
- [insight] search_all (concurrent 6-provider) + search_and_process (auto dedup) changed per-step yield from ~15 URLs to ~80 URLs
- [insight] deep_discover must use GitHub README API (raw.githubusercontent.com), not HTML scraping — GitHub pages are JS-rendered, raw HTML has no README links
- [insight] Gemini 2.5 Flash rejects assistant messages with `content: null` + extra fields (refusal, reasoning, index). Must clean message before appending to conversation
- [insight] AVO's edit-evaluate-diagnose inner loop (Section 3.2) prevents wasting generations on bad prompts. Retry up to 2 times within one generation if < 5 URLs found
- [insight] AVO supervisor needs LLM analysis of trajectory (not just template mutations) to generate effective redirect strategies. Template mutations ("add PRIORITY: X") don't help much; LLM redirect with high temperature (0.9) produces genuinely different approaches
- [mistake] Initial consensus_score multiplied scores N times for N duplicate hit dicts of the same URL. Fix: track boosted URLs in a set
- [mistake] SQLite cache without check_same_thread=False crashes when called from ThreadPoolExecutor
- [mistake] quality_filter used substring domain matching (`"github.com" in domain`) which falsely matches "notgithub.com". Fix: exact match or endswith
- [decision] OpenRouter (gemini-2.5-flash) instead of Anthropic API direct — cheaper, already used by goal_editor
- [decision] Capabilities as module-level variables (SearXNG engine pattern) instead of classes/decorators — simplest possible contract

## Pending

- MCP end-to-end verification: requires new Claude Code session to load autosearch MCP server from ~/.mcp.json
- Run AVO 20+ generations to see if score plateaus or continues improving
- Investigate remaining intermittent 400 errors (occur ~1 in 5 generations)
- Add more search sources: Bilibili, XiaoHongShu, podcasts via agent-reach
- Implement AVO population-level branching (paper mentions but doesn't implement)
- Consider multi-LLM AVO: parallel agents with different models competing
