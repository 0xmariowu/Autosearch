---
name: pipeline-flow
description: "Use at the start of every AutoSearch session to follow the correct 7-phase pipeline. Ensures rubric-defined quality, Claude-first architecture, gap-driven search, and AVO evolution."
---

# Model Routing

Not all phases need the same model. Use cheaper models for structured/batch tasks:

| Phase | Model | Reason |
|---|---|---|
| Phase 0: Generate rubrics | Haiku | Structured output, fixed schema |
| Phase 1: Own knowledge | Session model | Needs full reasoning for 9-dimension recall |
| Phase 2: Generate queries | Haiku | Structured expansion, no deep reasoning needed |
| Phase 3: Search + evaluate | Free (HTTP) + Haiku | Search is HTTP; relevance scoring is classification |
| Phase 4: Reflect on gaps | Session model | Needs reasoning about what's missing |
| Phase 5: Synthesize | Sonnet | Quality-critical, needs strong writing |
| Phase 6: Check rubrics | Haiku | Pass/fail classification |
| Phase 7: AVO evolution | Sonnet | Needs diagnostic reasoning |

**This table is not advisory — it is the routing contract. Violation is severity=major.**

For every Haiku-designated phase: you MUST spawn a sub-agent with `model: "haiku"` via the Agent tool. Do NOT execute these phases in your own Sonnet context — it wastes 5x cost for zero quality gain. "I'll just do it myself since I'm already here" is the exact failure mode this rule prevents.

**Self-check**: before moving to the next phase, verify: if the current phase is Haiku-designated, did I spawn a Haiku agent? If no → STOP, spawn one, get results, then proceed.

**Verification output**: in your final summary, list which model executed each phase (e.g., "Phase 0: Haiku (agent abc123)"). This lets the caller audit compliance.

| Model | When to use |
|---|---|
| Haiku | Structured/classification tasks: rubrics, queries, scoring, pass/fail |
| Sonnet | Reasoning + writing: synthesis, evolution diagnosis |
| Session model | Deep recall, gap analysis (inherits from researcher agent) |
| No model | HTTP search via search_runner.py — pure network calls |

# Progress Output

After completing each phase, output a one-line progress summary the user can read. Use this exact format:

```
[Phase N/6] ✓ {phase name} — {key metric or finding}
```

Examples:
- `[Phase 1/6] ✓ Recall — 47 items mapped, 8 gaps identified`
- `[Phase 2/6] ✓ Search — 38 results from 8 channels (12 new discoveries)`
- `[Phase 3/6] ✓ Evaluate — 31 relevant, 7 filtered out`
- `[Phase 4/6] ✓ Synthesize — report drafted, 24 cited sources`
- `[Phase 5/6] ✓ Rubrics — 21/25 passed (84%)`
- `[Phase 6/6] ✓ Learn — 3 patterns saved, 1 skill evolved`

This solves the "15-minute black hole" problem. Users need to see progress, not silence.

# Purpose

This skill defines the 7-phase pipeline that makes AutoSearch produce results better than native Claude. Follow these phases in order.

# Phase 0: Define Rubrics (what does a complete answer look like?)

1. Run `generate-rubrics.md` — produces 20-30 binary rubrics
2. Store to `evidence/rubrics-{topic-slug}.jsonl`
3. These rubrics become the session's quality contract

Time: ~15 seconds

# Phase 0.5: Timing (auto-write, never manual)

At session start, write `state/timing.json` with `{"start_ts": "<ISO 8601 now>"}`.
After Phase 2 (search) completes, update the file: `{"start_ts": "<original>", "end_ts": "<ISO 8601 now>"}`.
This ensures the latency dimension is always measured. Never write timing.json manually elsewhere.

# Phase 1: Recall + Plan (Claude's knowledge leads)

1. Run `systematic-recall.md` — 9-dimension knowledge scan with confidence levels
2. Load `knowledge-map.md` if prior session data exists for this topic
3. Run `research-mode.md` — define scope (in/out/done) and budget (speed/balanced/deep)
4. If topic is complex: run `decompose-task.md` to break into sub-questions
5. Run `select-channels.md` — pick 5-10 channels from 30+ available
6. Run `gene-query.md` in gap-driven mode — queries only for GAPs and LOW confidence items

After Phase 1, you should have:
- A knowledge backbone (60-70% of the final report content)
- A list of specific gaps to fill
- Selected channels and targeted queries

## Search Depth Configuration

The user chooses a depth level that controls search scope:

| Depth | Channels | max_results/channel | Total queries | Time budget |
|---|---|---|---|---|
| ⚡ Quick (1) | 5 best-match | 5 | 8 max | 2 minutes |
| ⚖️ Standard (2) | 10 | 10 | 15 max | 5 minutes |
| 🔬 Deep (3) | 15+ | 15 | 25 max | 10+ minutes |

Quick mode: select only Tier 1 channels. Standard: Tier 1 + Tier 2. Deep: all relevant channels.

Apply this configuration when generating the queries JSON array for search_runner.

# Phase 2: Incremental Search (only search what Claude doesn't know)

Generate a queries JSON array for search_runner.py:

```json
[
  {"channel": "zhihu", "query": "自进化 AI agent 框架", "max_results": 10},
  {"channel": "github-repos", "query": "self-evolving agent", "max_results": 15},
  {"channel": "producthunt", "query": "AI agent 2026", "max_results": 10}
]
```

Execute all searches in one Bash call:

```bash
python lib/search_runner.py 'THE_JSON_ARRAY' > results.jsonl
```

search_runner.py handles: parallel execution, URL normalization, dedup, date extraction.
All channels searched simultaneously in 5-15 seconds.

After search_runner returns, read results.jsonl. Use `fetch-webpage.md` for high-value pages needing full content. Use `follow-links.md` for awesome-lists.

Key principles:
- Do NOT search for things you already know with HIGH confidence
- Focus search budget on: fresh content, real-time data, community voice, verification
- Let search_runner.py do the mechanical work. Claude decides WHAT to search.

After Phase 2, you should have clean, deduplicated search results.

# Phase 3: Evaluate (quality control)

search_runner.py already did normalization, dedup, and date extraction. Claude only needs to:

1. Run `llm-evaluate.md` — relevance judgment + gap detection on search results
   - Do NOT evaluate own-knowledge items (they are relevant by definition)
   - Focus on: is this result genuinely new? Does it add something Claude doesn't know?
   - Tag each result: metadata.llm_relevant + metadata.llm_reason
2. Identify remaining gaps — what did the search NOT find?

Do NOT re-run normalize or extract-dates — search_runner.py already handled those.

After Phase 3, you should have evaluated search results and a next-queries file ready.

# Phase 3a: Per-Query Outcome Tracking

After llm-evaluate completes, compute per-query metrics from the evaluated results.

For each unique `query` value in the results:
1. `results_count` = total results with this query
2. `relevant_count` = results where `metadata.llm_relevant == true`
3. `relevant_rate` = relevant_count / results_count
4. `new_urls_count` = results whose URLs were not in prior sessions (approximate: set to results_count if no prior data exists)
5. `channel` = the `source` field from the first result with this query

Append one record per query to `state/query-outcomes.jsonl` (create if absent):

```json
{"session": "{session_id}", "ts": "{ISO 8601 now}", "query": "{query text}", "channel": "{channel}", "results_count": 12, "relevant_count": 8, "relevant_rate": 0.67, "new_urls_count": 8, "topic_type": "{academic|tool|general}"}
```

This file is append-only. It feeds `gene-query` in future sessions to boost high-performing query patterns.

Time: ~10 seconds (arithmetic on existing data, no API calls)

# Phase 3b: Gap-Driven Loop-Back (conditional, at most once)

Read `evidence/{session_id}-next-queries.jsonl` (written by llm-evaluate in Phase 3).

**If the file is empty or absent**: skip Phase 3b, proceed to Phase 4.

**If the file contains queries**:
1. Keep only queries targeting CRITICAL gaps: `current_relevant <= 1`
2. Drop queries for dimensions with 2+ relevant results (already adequate)
3. Cap at 5 queries maximum

**If no queries remain after filtering**: skip Phase 3b, proceed to Phase 4.

**Run the gap queries**:
```bash
python lib/search_runner.py '[{...filtered queries...}]' >> results.jsonl
```

Re-run `llm-evaluate.md` on the NEW results only (those not already evaluated).
Append new per-query tracking records to `state/query-outcomes.jsonl`.

**Rules**:
- Run Phase 3b at most ONCE per session — no recursive loops
- If Phase 3b produces 0 new relevant results, log the gap as "unfillable this session"
- Do NOT update `state/timing.json` end_ts after Phase 3b (latency measures the initial pipeline)

Time: ~15-30 seconds (5 queries max)

# Phase 4: Synthesize + Deliver

### Citation Lock (before synthesis)

Compile all search result URLs into a numbered reference list:
[1] Title — URL
[2] Title — URL
...

This list is the ONLY source of URLs for the synthesis phase. Pass it to synthesize-knowledge.md as the citation index.

1. Run `synthesize-knowledge.md` to produce the delivery:
   - Blend knowledge backbone (Phase 1) with search discoveries (Phase 2-3)
   - Organize by concept, not by source
   - Mark each item's provenance: [knowledge] vs [discovered] vs [verified]
   - Include citations for all discovered items
   - Flag what AutoSearch found that native Claude would miss
2. Run `evaluate-delivery.md` — 4-dimension quality check
   - If fails: revise and re-check
3. Present to user

The delivery should clearly show AutoSearch's incremental value:
- "AutoSearch discovered N items not in Claude's training data"
- "Verified M items with real-time data (star counts, funding, etc.)"
- "Searched N platforms including [Chinese platforms / video / commercial]"

# Phase 5: Rubric Check (did we deliver what we promised?)

**MANDATORY — never skip this phase.** Run it even if the user has already seen the delivery. The rubric check feeds Phase 6 which is how the system improves. Skipping Phase 5 means AVO has no signal to evolve on.

1. Run `check-rubrics.md` — checks each rubric pass/fail with evidence
2. Output `checked-rubrics.jsonl`
3. Append summary to `rubric-history.jsonl`

Time: ~30 seconds

# Phase 6: Learn + Evolve

**MANDATORY — never skip this phase.** This is the only place where self-evolution happens. A session without Phase 6 is a search session, not a self-evolving session. Run it immediately after Phase 5 completes, before the session ends.

1. Save updated knowledge map via `knowledge-map.md`
2. Record which channels produced incremental discoveries
3. Record which query patterns worked best
4. Append patterns to `state/patterns-v2.jsonl`
5. Run `auto-evolve.md`
   - AVO performs one evolution step: diagnose failed rubrics -> modify one skill or create a new one -> commit -> record
   - If the diagnosis identifies a missing capability (not just a weak existing one), use `create-skill.md` instead of modifying an existing skill

This data makes the next session on the same topic faster and better.

Time: ~30 seconds

# Time Budget

| Phase | Target time | Notes |
|-------|------------|-------|
| Phase 0 | 15 seconds | Rubric generation |
| Phase 1 | 30-60 seconds | Claude recalls from memory |
| Phase 2 | 10-20 seconds | search_runner.py parallel |
| Phase 3 | 30-60 seconds | Evaluation |
| Phase 4 | 1-2 minutes | Synthesis |
| Phase 5 | 30 seconds | Rubric checking |
| Phase 6 | 30 seconds | Write state + auto-evolve |
| **Total** | **3-5 minutes** | |

# Quality Bar

The pipeline is working when:
- Phase 0 produces 20-30 topic-specific rubrics
- Phase 1 produces 30+ knowledge items before any search
- Phase 2 searches only GAPs (fewer queries than search-first mode)
- Phase 4 delivery clearly shows incremental value over native Claude
- Phase 5 produces strict pass/fail verdicts for every rubric
- Phase 6 produces one evolution step (or a logged skip)
- Total time is under 10 minutes
