---
date: 2026-03-22
project: autosearch
type: experience
tags: [autosearch, scout, merge, perception-system, outcome-tracking, code-review]
---

## Done

- Merged AutoSearch (self-evolving search engine) and Armory Scout (daily discovery pipeline) into a unified perception system
- Produced 5 Python files: `engine.py` (650 lines, 7 classes, 11 platform connectors), `cli.py`, `daily.py`, `pipeline.py`, `outcomes.py`
- Built outcome feedback loop: query -> repo -> WHEN/USE blocks -> patterns.jsonl boost
- Updated launchd wrapper with reverse rsync for state persistence
- 3 rounds of code review, fixed 7 CRITICAL + 8 IMPORTANT issues

## Produced

- `~/Dev/autosearch/engine.py` — search engine core (PatternStore, LLMEvaluator, PlatformConnector x11, QueryGenerator, Scorer, SessionDoc, Engine)
- `~/Dev/autosearch/cli.py` — manual search CLI entry
- `~/Dev/autosearch/daily.py` — daily discovery mode (queries.json seed genes, Sonnet 4.6 LLM eval, 3 rounds)
- `~/Dev/autosearch/pipeline.py` — unified orchestrator (engine -> adapter -> score-and-stage.js -> intake -> email)
- `~/Dev/autosearch/outcomes.py` — outcome feedback loop (record_intakes + track_outcomes + pattern weight update)
- `~/.local/bin/armory-scout.sh` — launchd wrapper (forward + reverse rsync)
- `~/.claude/plans/global-0322-autosearch-scout-merge.md` — execution plan (F001-F007)
- `AIMD/projects/autosearch/2026-03-22-system-architecture.md` — system architecture doc (see below)

## Discovered

- [discovery] Scout and AutoSearch use completely different platform connectors for 4 out of 5 platforms: Scout uses xreach for Twitter (AutoSearch uses Exa), Scout uses Exa site:reddit.com (AutoSearch uses Reddit API directly), etc. Engine now supports all 10 variants.
- [insight] mcporter returns plain text (Title/URL/Published blocks), not JSON. The original run-template.py's JSON parsing was dead code — it never worked with the current mcporter version. The text parser in the new engine is the correct approach.
- [insight] Seed queries (85 from queries.json) get silently truncated by LLM suggestion recency cap (max 30). Fixed by adding a separate `seed_queries` list in QueryGenerator that is never capped. Pattern: **when mixing stable seeds with dynamic suggestions, use separate pools**.
- [insight] `_WORD_MAP` for topic inference had last-writer-wins collision — common words like "agent" or "framework" get overwritten to whichever topic_group appears last in queries.json. Fixed by making word_map multi-valued and using voting. Pattern: **word->category maps need many-to-many, not many-to-one**.
- [mistake] First version of armory-scout.sh rsync'd iCloud -> local with `--delete` but never synced state back. Patterns/evolution/outcomes written to local copy would be erased on next run. Fixed by adding reverse rsync for state files.
- [decision] score-and-stage.js (30K, Node) kept as-is for now. Changed only the input interface (adapter in pipeline.py writes per-platform JSONL to tmpDir). Full Python rewrite deferred — not worth the risk for the merge milestone.
- [decision] Daily LLM eval uses Sonnet 4.6 (~$0.03-0.05/session) instead of Haiku. One run per day, quality matters more than cost.
- [decision] Unified directory is `~/Dev/autosearch/` (perception is an independent pillar, not a subdirectory of Armory). Scout tools stay in `Armory/scripts/scout/` as Armory's API surface.

## Pending

- F005: score-and-stage.js Python rewrite — deferred, merge with evolution plan when ready
- F006: daily digest upgrade to "四大金刚 ecosystem evolution report" — covered by evolution-0322 plan
- First real daily run via launchd is tomorrow (2026-03-23) 6AM — check logs at `~/.local/log/armory-scout/scout.log`
- outcome-tracker.py weekly run not yet scheduled — needs launchd plist or manual trigger
- 13 historical intakes recorded in outcomes.jsonl with `source_query: ""` (no query provenance from Scout era). Future intakes will have query tracing from evolution.jsonl.
