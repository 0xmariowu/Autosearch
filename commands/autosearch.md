---
description: "Self-evolving deep research system. Use when the user wants deep research on any topic."
user-invocable: true
---

# /autosearch — Self-Evolving Deep Research System

Run an AutoSearch research session.

## Arguments

$ARGUMENTS — the research task (e.g., "find AI agent frameworks", "research vector databases")

If no arguments provided, ask the user what to research.

## Execution

### Phase A: Configure (runs in current model — cheap)

1. Set working directory to `${CLAUDE_PLUGIN_ROOT}`
2. **Ask the user 2 questions before searching** (use AskUserQuestion, all in one call):
   - **How deep?**: Quick (~5 min, fast scan, no learning) / Standard (~10 min, full report + learning) / Deep (~20 min, exhaustive + self-evolution)
   - **Report format?**: Markdown / Rich HTML (tables + diagrams) / Presentation slides
3. **Auto-determine content structure from Depth** (do not ask the user):
   - Quick → executive summary (1 page, key insights + recommendation)
   - Standard → full report (framework + evidence tables + analysis)
   - Deep → full report + evidence appendix + gap declaration
4. **Auto-detect language from topic**: Chinese topic → Chinese output + prioritize Chinese channels. English topic → English output. Mixed → follow the dominant language.
   **Auto-detect focus from topic**: infer domain (academic/commercial/community/Chinese/mixed) from the topic text. No need to ask the user.
5. **Generate session ID**: `YYYYMMDD-{topic-slug}` (e.g., `20260403-self-evolving-search`)
6. **Read version**: `python3 -c "import json; print(json.load(open('${CLAUDE_PLUGIN_ROOT}/.claude-plugin/plugin.json'))['version'])"` — pass this to Block 4 for the report footer.
7. **Set time budget and search params** (user does NOT see these — internal only):

| Mode | Time budget | Channels | Query cap | Gap-fill | Evolution |
|------|------------|----------|-----------|----------|-----------|
| Quick | 5 min | 8 best-match | 8 | skip | skip |
| Standard | 10 min | 15 | 15 | 1 round | patterns only |
| Deep | 20 min | all 34 | 25 | gap-fill + reflect | full evolution |

Track wall-clock start time. If elapsed > budget, graceful stop: deliver what we have.

### Phase B: Orchestrated Research (6 blocks with visible progress)

Execute the pipeline in 6 blocks. Between blocks, output a progress line the user can see. Each block uses the correct model per the pipeline-flow routing contract.

**Why 6 blocks?** Correct model routing (Haiku for classification, Sonnet for reasoning) + visible progress + no single block exceeds 5 minutes. The previous 4-block design used Sonnet for everything, wasting 5x cost on classification tasks and running 15+ minutes per block.

**Time budget enforcement**: After each block, check elapsed time. If elapsed > budget, skip gap-fill and evolve phases — go straight to synthesis with what we have. A thinner on-time report beats a comprehensive 40-minute report.

#### Block 1: Prepare (Phase 0 + 1) — Sonnet

Spawn a Sonnet agent (`model: "sonnet"`) with this task:

> Working directory: `${CLAUDE_PLUGIN_ROOT}`
> Topic: {topic}. Depth: {depth}. Focus: {focus}. Session ID: {session_id}.
>
> Read `skills/pipeline-flow/SKILL.md` for context, then execute Phase 0 and Phase 1:
>
> 1. Read `skills/generate-rubrics/SKILL.md` and generate rubrics. Write to `evidence/rubrics-{topic-slug}.jsonl`.
> 2. Write `state/timing.json` with `{"start_ts": "{ISO 8601 now}"}`.
> 3. Read `skills/systematic-recall/SKILL.md` and run 9-dimension recall. Write the full output to `state/session-{id}-knowledge.md` (this file is consumed by the synthesis phase).
> 4. Read `skills/select-channels/SKILL.md` and pick channels based on depth and focus.
> 5. Read `state/patterns-v2.jsonl` to inform query strategy with winning patterns from prior sessions.
> 6. Read `skills/gene-query/SKILL.md` and generate gap-driven queries.
> 7. **Enforce query cap**: Quick=8, Standard=15, Deep=25. If more queries generated, keep the most diverse subset (maximize unique channels and content_type variety). Drop duplicate-intent queries first.
> 8. Write the final capped query JSON array to `state/session-{id}-queries.json`.
>
> At the end, output a JSON summary: `{"rubrics": N, "knowledge_items": N, "gaps": N, "queries": N, "channels": ["list"]}`

After Block 1 returns, parse its summary and output:
```
[Phase 1/6] ✓ Prepare — {rubrics} rubrics, {knowledge_items} items recalled, {queries} queries planned
```

**Query cap guard**: If `queries` exceeds the depth cap (Quick=8, Standard=15, Deep=25), log a warning but continue — the cap should have been enforced in the agent, this is a safety net.

**Zero-query guard**: If `queries == 0`, warn the user: "All knowledge dimensions are HIGH confidence — no search needed. Proceed with knowledge-only synthesis?" If user confirms, skip Blocks 2-3 and go to Block 4. If user declines, abort.

#### Block 2: Search (Phase 2) — Sonnet

Spawn a Sonnet agent (`model: "sonnet"`) with this task:

> Working directory: `${CLAUDE_PLUGIN_ROOT}`
> Session ID: {session_id}. Topic: {topic}.
>
> **CRITICAL: Do NOT use the WebSearch or WebFetch tools.** ALL searches MUST go through `lib/search_runner.py` via the Bash tool. WebSearch bypasses the 32-channel connectors and produces untagged results. Using WebSearch defeats the entire purpose of AutoSearch.
>
> 1. Read `state/session-{id}-queries.json` for the query array.
> 2. Find Python: `PYTHON=$(.venv/bin/python3 2>/dev/null || python3)`
> 3. Run search: `PYTHONPATH=. $PYTHON lib/search_runner.py state/session-{id}-queries.json > evidence/{session_id}-results.jsonl 2>evidence/{session_id}-search-errors.log`
> 4. Read the results file. Verify source diversity: count unique `source` values. If all results have the same source, the search failed — report the error.
> 5. Read `evidence/{session_id}-search-errors.log` for any channel failures. Report failed channels in the summary.
> 6. Update `state/timing.json` with `end_ts`.
>
> At the end, output a JSON summary: `{"total_results": N, "channels_searched": N, "channels_failed": ["list"], "unique_sources": N}`

After Block 2 returns, parse its summary and output:
```
[Phase 2/6] ✓ Search — {total_results} results from {unique_sources} channels ({channels_failed} failed)
```

**Source diversity check**: If `unique_sources <= 1`, output a warning: "Search fell back to a single channel. Multi-channel search may have failed." Continue but flag.

#### Block 3: Evaluate (Phase 3) — Haiku

Spawn a Haiku agent (`model: "haiku"`) with this task:

> Working directory: `${CLAUDE_PLUGIN_ROOT}`
> Session ID: {session_id}. Topic: {topic}.
>
> Read `skills/llm-evaluate/SKILL.md` for context.
>
> 1. Read `evidence/{session_id}-results.jsonl`.
> 2. For each result, judge relevance against the topic. Tag with `metadata.llm_relevant` (true/false) and `metadata.llm_reason`.
> 3. Work in batches of 10. Evaluate the highest-leverage results first.
> 4. Write evaluated results back to `evidence/{session_id}-results.jsonl`.
> 5. Track per-query outcomes: append to `state/query-outcomes.jsonl` per pipeline-flow Phase 3a.
> 6. If critical gaps remain (dimensions with <= 1 relevant result), write up to 5 gap-fill queries to `evidence/{session_id}-next-queries.jsonl`. Otherwise write an empty file.
>
> At the end, output a JSON summary: `{"relevant": N, "filtered": N, "gap_queries": N}`

After Block 3 returns, parse its summary and output:
```
[Phase 3/6] ✓ Evaluate — {relevant} relevant, {filtered} filtered, {gap_queries} gap queries
```

**Gap-fill (conditional, time-permitting)**: If `gap_queries > 0` AND elapsed time < 80% of budget, run one Bash call:
```bash
PYTHONPATH=. $PYTHON lib/search_runner.py evidence/{session_id}-next-queries.jsonl >> evidence/{session_id}-results.jsonl
```
Then re-evaluate ONLY the new results (spawn another Haiku agent). Skip gap-fill if over time budget.

#### Block 4: Synthesize + Deliver (Phase 4) — Sonnet

Spawn a Sonnet agent (`model: "sonnet"`) with this task:

> Working directory: `${CLAUDE_PLUGIN_ROOT}`
> Session ID: {session_id}. Topic: {topic}. Delivery format: {delivery_format}. Language: {language}. Content structure: {content_structure}. AutoSearch version: {version}.
>
> Read `skills/pipeline-flow/SKILL.md` Phase 4 for context.
>
> 1. Read `state/session-{id}-knowledge.md` for Claude's own knowledge backbone.
> 2. Read `evidence/{session_id}-results.jsonl` for search results (only `metadata.llm_relevant == true` items).
> 3. Compile a numbered citation index from all search result URLs.
> 4. Read `skills/synthesize-knowledge/SKILL.md` and produce the delivery:
>    - Blend knowledge backbone with search discoveries
>    - Organize by concept, not by source
>    - Mark provenance: [knowledge] vs [discovered] vs [verified]
>    - If Rich HTML: produce a standalone HTML file with tables, styling, and diagrams
>    - If Markdown: produce a .md report
>    - Report footer: "Generated by AutoSearch v{version}" (use the version passed above, NOT "v2.2")
> 5. Read `skills/evaluate-delivery/SKILL.md` and self-check. Revise if needed.
> 6. Write delivery to `delivery/{session_id}.html` (or `.md`).
> 7. Run `PYTHONPATH=. python3 lib/judge.py evidence/{session_id}-results.jsonl` and capture the score.
>
> At the end, output a JSON summary: `{"citations": N, "delivery_path": "path", "judge_score": N}`

After Block 4 returns, parse its summary and output:
```
[Phase 4/6] ✓ Deliver — report ready ({citations} citations, judge score {judge_score})
```

#### Block 5: Quality Check (Phase 5) — Haiku

Spawn a Haiku agent (`model: "haiku"`) with this task:

> Working directory: `${CLAUDE_PLUGIN_ROOT}`
> Session ID: {session_id}. Topic slug: {topic_slug}.
>
> Read `skills/check-rubrics/SKILL.md` for context.
>
> 1. Read the delivery file from `delivery/{session_id}.*` — read it ONCE into memory.
> 2. Read `evidence/rubrics-{topic-slug}.jsonl`.
> 3. Check each rubric pass/fail against the delivery text. Work through ALL rubrics in a single pass (do not re-read the delivery file per rubric).
> 4. Write results to `evidence/checked-rubrics-{topic-slug}.jsonl`.
> 5. Append summary to `state/rubric-history.jsonl`.
>
> At the end, output a JSON summary: `{"rubrics_passed": N, "rubrics_total": N}`

After Block 5 returns, parse its summary and output:
```
[Phase 5/6] ✓ Quality — {rubrics_passed}/{rubrics_total} rubrics passed
```

#### Block 6: Evolve (Phase 6) — Sonnet

**Skip if over time budget.** Evolution is valuable but not worth making the user wait.

Spawn a Sonnet agent (`model: "sonnet"`) with this task:

> Working directory: `${CLAUDE_PLUGIN_ROOT}`
> Session ID: {session_id}. Topic slug: {topic_slug}.
>
> Read `skills/pipeline-flow/SKILL.md` Phase 6 for context.
>
> 1. Read `skills/knowledge-map/SKILL.md` and save updated knowledge map.
> 2. Append winning patterns to `state/patterns-v2.jsonl`.
> 3. Read `skills/auto-evolve/SKILL.md` and run one evolution step.
> 4. Append to `state/worklog.jsonl`: task_spec, search_run, reflection, delivery entries.
>
> At the end, output a JSON summary: `{"patterns_saved": N, "evolved": true/false}`

After Block 6 returns, parse its summary and output:
```
[Phase 6/6] ✓ Evolve — {patterns_saved} patterns saved, evolved: {evolved}
```

#### Error Handling

If any block's agent returns an error or fails to produce a valid summary:
```
[Phase N/6] ✗ {phase_name} — ERROR: {brief description from agent output}
```
Stop and report to the user immediately. Do not silently continue to the next block.

### Phase C: Present

After all blocks complete:

1. Output the full progress summary:
```
✓ AutoSearch complete
  Phase 1: Prepare — {details}
  Phase 2: Search — {details}
  Phase 3: Evaluate — {details}
  Phase 4: Deliver — {details}
  Phase 5: Quality — {details}
  Phase 6: Evolve — {details}
  Total: {elapsed} minutes
```

2. Show the delivery path and offer to open it.
3. If Rich HTML delivery, suggest: `open delivery/{session_id}.html`

## Key constraints

- `lib/judge.py` is the only evaluator — run it, never self-assess quality
- State files in `state/` are append-only
- Config/skill changes go through git commit/revert
- Each block agent must read the relevant `skills/*/SKILL.md` before executing
- Use Python 3.10+ for `lib/judge.py` and `lib/search_runner.py`
- Block model routing: Sonnet for reasoning/synthesis (1, 2, 4, 6), Haiku for classification (3, 5)
- All blocks spawn with `mode: "acceptEdits"` — NOT `mode: "auto"` (which maps to `default` for plugins and causes permission hangs)
- **NEVER use WebSearch/WebFetch in search blocks** — always use `lib/search_runner.py` via Bash
