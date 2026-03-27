# AutoSearch Handoff

## main

**Last session**: 2026-03-27 (evening) — Capabilities System + AVO Evolution + MCP Server [SESSION-ID: 1526-reykjavik-quiet]

**What was done**: Built AI-native capabilities registry (43 caps), orchestrator (OpenRouter ReAct loop), AVO evolution framework (arXiv:2603.24517), MCP server (6 tools). Fixed 20 bugs (6 infra + 14 audit). Researched 18 open-source search projects. AVO evolved search score 0.50→0.81, cumulative 321 URLs across 15 generations.

**Current state**: 194 tests pass. 43/43 capability self-tests pass. 12 commits on main. Evolved prompt at `sources/evolved-prompt.txt` (auto-loaded). MCP registered at `~/.mcp.json`.

**Key files**: `capabilities/` (43 files), `orchestrator.py`, `avo.py`, `autosearch-mcp/` (3 files), `docs/2026-03-27-deep-research-patterns.md`

**Usage**: `python3 cli.py --orchestrated "find repos" --max-steps 15` | `python3 avo.py "find 200 repos" --generations 10` | MCP: restart Claude Code, say "搜一下 XX"

**Next**: MCP e2e verify (restart session), AVO 20+ gen, add OPENROUTER_API_KEY to shell profile, fix remaining 400 errors

## worktree-1037-zanzibar-teal

**Last session**: 2026-03-27. Two workstreams completed.

### Workstream 1: AI Judge Pipeline Fixes (DONE)
- PR #4 merged: 5 bugs fixed — `_bundle_sample()` rich content, content truncation 500→3000, `_dimension_aware_bundle_sample()`, `search_for_gaps()` acquisition policy, `scripts/batch_enrich.py`
- PR #5 merged: content limit 1500→3000
- Batch enriched 60 evidence records (3% → 35% with page content)
- Ran evolve 5+3 rounds: score stuck at 68. Root cause = evidence relevance, not pipeline
- Cleaned 4 stale tests, fixed pre-push hook (pytest → unittest)

### Workstream 2: BaZi Case Collection (IN PROGRESS)
- **Goal**: Collect 200K real BaZi (八字) fortune-telling case studies from the internet
- **Infrastructure**: Set up SearXNG Docker (port 8888) + installed ddgs. All 12 AutoSearch backends now online.
- **Goal case**: `goal_cases/bazi-case-collection.json` — 4 dimensions (birth_data, four_pillars, analysis_content, case_depth)
- **Evidence**: `goal_cases/runtime/bazi-case-collection/evidence-index.jsonl` — **6,757 evidence pages** (39MB)
  - 1,132 with page content (fit_markdown/acquired_text)
  - 1,098 unique domains
  - Top sources: 知乎专栏 (587), 抖音 (355), 搜狐 (336), 百家号 (215), B站 (199), 360doc (125)
- **Queries run**: ~3,718 unique queries across 8 parallel batches, zero errors
- **Search saturation**: Dedup rate very high at end — public Chinese web BaZi URLs approaching coverage ceiling

**Next step for BaZi collection**:
1. **Content extraction**: 6,757 pages collected but only 1,132 have page content. Run `scripts/batch_enrich.py --goal-case bazi-case-collection --limit 3000` to fetch page content for top records
2. **Case parsing**: Each page may contain multiple individual cases. Need extraction script to pull structured BaZi data (birth datetime, four pillars, analysis text) from page content
3. **More queries**: Generated 3,315 queries but could expand to 10K+ by adding more combinatorial dimensions (specific 六十甲子 year combos, more site targets, pagination patterns)
4. **Quality filtering**: Filter evidence by dimension keyword coverage to keep only pages that actually contain case data

**Key files**:
- `goal_cases/bazi-case-collection.json` — goal case definition
- `goal_cases/runtime/bazi-case-collection/evidence-index.jsonl` — collected evidence (39MB, 6,757 records)
- `chinese-divination-knowledge-bases.md` — comprehensive catalog of ~65 open-source divination projects (also copied to repo root)
- `/tmp/bazi_queries_10k.json` — 3,315 generated queries (NOTE: in /tmp, may not survive reboot — regenerate with `/tmp/gen_bazi_queries.py`)
- `/tmp/bazi_batch_runner.py` — parallel batch search runner
- `/tmp/gen_bazi_queries.py` — combinatorial query generator

**SearXNG**: Docker container `searxng` on port 8888. Config at `/tmp/searxng/settings.yml` (JSON API enabled, limiter off). Container may need restart after reboot: `docker start searxng`
