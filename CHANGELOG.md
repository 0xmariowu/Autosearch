# Changelog

All changes to AutoSearch. Every entry includes **what** changed and **why**.

---

## 2026-03-28
- You can now evolve search strategies as JSON genomes instead of hardcoded Python. New `genome/` module: schema (8 sections), runtime interpreter, 13 primitives, 5 mutation operators, safe expression evaluator. Run `python3 avo.py "task" --genome` to start genome-based AVO evolution. Why: AVO paper's Vary(P_t) needs a structured, evolvable representation — Python code can't be safely mutated by an AI agent, but JSON genomes can.
- Three seed genomes created from existing strategies: `engine-3phase.json` (3-phase explore/harvest/postmortem), `orchestrator-react.json` (ReAct loop), `daily-discovery.json` (daily discovery). Why: AVO needs initial population members to start evolution from known-good strategies.
- All existing modules now accept optional `genome=` parameter with fallback to current hardcoded defaults. Files: modes.py, lexical.py, planner.py, synthesizer.py, project_experience.py, engine.py, orchestrator.py, daily.py, goal_runtime.py. Why: gradual migration — genome config is opt-in, existing behavior unchanged.
- MCP `autosearch_evolve` tool now uses genome-based evolution via `run_avo_genome()`. Why: genome evolution is the new default path for AVO.

## 2026-03-24
- Added `goal_cases/`, `goal_judge.py`, and `goal_loop.py` to test a concrete `autoresearch`-style improvement loop against project-specific problems and score deltas. Why: AutoSearch needed a measurable self-improvement path based on goal progress, not only generic search quality.
- Added `program.md`, `control_plane.py`, and `control/latest-program.json` to synthesize the current operating program from objective + capability + experience. Why: AutoSearch needed a machine-readable equivalent of the lightweight `program.md` idea from `karpathy/autoresearch`, but adapted to search work instead of model training.
- Added `sources/catalog.json`, `source_capability.py`, `doctor.py`, and `sources/latest-capability.json`, then wired daily/runtime to consume static provider availability before search. Why: AutoSearch needed a real capability layer inspired by agent-reach so it knows what sources are usable, not just what performed well recently.
- Added AlphaXiv SSE MCP server to `/Users/vimala/.mcp.json` and documented it in AutoSearch methodology/platform docs. Why: the system needed a paper-native research source that is available in the environment now, even before it becomes a first-class runtime provider.
- Added `standards/` docs for demand, search, content candidates, routeable-map handoff, and project experience. Why: AutoSearch needed atoms-style boundary docs that separate demand, search execution, routing preparation, and runtime policy without prematurely defining final admission rules.
- Added `project_experience.py` plus `experience/` runtime files (`experience-ledger/index/policy/latest-health`) and wired `daily.py` + `engine.py` to refresh them automatically after runs. Why: AutoSearch needed a lightweight runtime policy layer that can reorder providers and skip cooldown providers without changing the 3-phase core.
- Preserved `query_family` and stronger harvest provenance in engine/evolution/outcomes flow, and added minimal tests. Why: future feedback loops need stable `source_query/query_family` lineage instead of guessing only from sample titles.
- Added global CLAUDE.md reference to autosearch/CLAUDE.md. Why: AI-friendly standard requires declaring relationship to global rules.
- Fixed broken reference in docs/README.md: `AIMD/projects/search-methodology/` → `autosearch/docs/methodology/`. Why: content moved on 2026-03-23 but reference wasn't updated.

## 2026-03-23
- Moved search methodology from `AIMD/projects/search-methodology/` to `autosearch/docs/methodology/`. Why: methodology belongs with the code that implements it, not in the global experience library.
