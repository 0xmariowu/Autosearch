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
2. **Ask the user 3 questions before searching** (use AskUserQuestion, all in one call):
   - **Depth**: Quick (5 channels, 1 round) / Standard (10 channels, 3 rounds) / Deep (15+ channels, 5 rounds)
   - **Focus**: Open source / Academic / Commercial / Chinese / Community / All
   - **Delivery**: Markdown report (.md) / Rich HTML report (tables + diagrams) / Presentation slides (reveal.js)
3. **Auto-determine content structure from Depth** (do not ask the user):
   - Quick → executive summary (1 page, key insights + recommendation)
   - Standard → full report (framework + evidence tables + analysis)
   - Deep → full report + evidence appendix + gap declaration
4. **Auto-detect language from topic**: Chinese topic → Chinese output + prioritize Chinese channels. English topic → English output. Mixed → follow the dominant language.
5. **Generate session ID**: `YYYYMMDD-{topic-slug}` (e.g., `20260403-self-evolving-search`)

### Phase B: Orchestrated Research (4 blocks with visible progress)

Execute the pipeline in 4 blocks. Each block is a Sonnet agent. Between blocks, output a progress line in the main context so the user sees real-time updates.

**Why orchestrated instead of a single researcher agent?** A single researcher agent runs 5-11 minutes inside the Agent tool. During that time the user sees zero semantic progress — just an expanding list of collapsed tool calls. By splitting into blocks, the user sees `[Phase N/6]` progress between each block. If a block fails, the user sees immediately which phase broke instead of waiting 11 minutes for a cryptic error.

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
> 6. Read `skills/gene-query/SKILL.md` and generate gap-driven queries. Write the query JSON array to `state/session-{id}-queries.json`.
>
> At the end, output a JSON summary: `{"rubrics": N, "knowledge_items": N, "gaps": N, "queries": N, "channels": ["list"]}`

After Block 1 returns, parse its summary and output:
```
[Phase 1/6] ✓ Prepare — {rubrics} rubrics, {knowledge_items} items recalled, {queries} queries planned
```

**Zero-query guard**: If `queries == 0`, warn the user: "All knowledge dimensions are HIGH confidence — no search needed. Proceed with knowledge-only synthesis?" If user confirms, skip Block 2 and go directly to Block 3. If user declines, abort.

#### Block 2: Search + Evaluate (Phase 2 + 3) — Sonnet

Spawn a Sonnet agent (`model: "sonnet"`) with this task:

> Working directory: `${CLAUDE_PLUGIN_ROOT}`
> Session ID: {session_id}. Topic: {topic}.
>
> Read `skills/pipeline-flow/SKILL.md` Phase 2 and Phase 3 for context.
>
> 1. Read `state/session-{id}-queries.json` for the query array.
> 2. Run: `python3 lib/search_runner.py state/session-{id}-queries.json > evidence/{session_id}-results.jsonl`
> 3. Read `skills/llm-evaluate/SKILL.md` and evaluate results. Tag each with `metadata.llm_relevant`.
>    Write evaluated results back to `evidence/{session_id}-results.jsonl`.
> 4. Track per-query outcomes: append to `state/query-outcomes.jsonl` per pipeline-flow Phase 3a.
> 5. Check for gap-driven loop-back (Phase 3b): if critical gaps remain, run at most 5 more queries and append results.
> 6. Update `state/timing.json` with `end_ts`.
>
> At the end, output a JSON summary: `{"total_results": N, "relevant": N, "channels_searched": N, "gap_queries": N}`

After Block 2 returns, parse its summary and output:
```
[Phase 2/6] ✓ Search — {total_results} results from {channels_searched} channels
[Phase 3/6] ✓ Evaluate — {relevant} relevant, {gap_queries} gap queries
```

#### Block 3: Synthesize + Deliver (Phase 4) — Sonnet

Spawn a Sonnet agent (`model: "sonnet"`) with this task:

> Working directory: `${CLAUDE_PLUGIN_ROOT}`
> Session ID: {session_id}. Topic: {topic}. Delivery format: {delivery_format}. Language: {language}. Content structure: {content_structure}.
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
> 5. Read `skills/evaluate-delivery/SKILL.md` and self-check. Revise if needed.
> 6. Write delivery to `delivery/{session_id}.html` (or `.md`).
> 7. Run `python3 lib/judge.py evidence/{session_id}-results.jsonl` and capture the score.
>
> At the end, output a JSON summary: `{"citations": N, "delivery_path": "path", "judge_score": N}`

After Block 3 returns, parse its summary and output:
```
[Phase 4/6] ✓ Deliver — report ready ({citations} citations, judge score {judge_score})
```

#### Block 4: Quality + Evolve (Phase 5 + 6) — Sonnet

Spawn a Sonnet agent (`model: "sonnet"`) with this task:

> Working directory: `${CLAUDE_PLUGIN_ROOT}`
> Session ID: {session_id}. Topic slug: {topic_slug}.
>
> Read `skills/pipeline-flow/SKILL.md` Phase 5 and Phase 6 for context.
>
> Phase 5 — Rubric Check:
> 1. Read the delivery file from `delivery/{session_id}.*`
> 2. Read `evidence/rubrics-{topic-slug}.jsonl`
> 3. Read `skills/check-rubrics/SKILL.md` and check each rubric pass/fail.
> 4. Write results to `evidence/checked-rubrics-{topic-slug}.jsonl`.
> 5. Append summary to `state/rubric-history.jsonl`.
>
> Phase 6 — Learn + Evolve:
> 6. Read `skills/knowledge-map/SKILL.md` and save updated knowledge map.
> 7. Append winning patterns to `state/patterns-v2.jsonl`.
> 8. Read `skills/auto-evolve/SKILL.md` and run one evolution step.
> 9. Append to `state/worklog.jsonl`: task_spec, search_run, reflection, delivery entries.
>
> At the end, output a JSON summary: `{"rubrics_passed": N, "rubrics_total": N, "patterns_saved": N, "evolved": true/false}`

After Block 4 returns, parse its summary and output:
```
[Phase 5/6] ✓ Quality — {rubrics_passed}/{rubrics_total} rubrics passed
[Phase 6/6] ✓ Evolve — {patterns_saved} patterns saved, evolved: {evolved}
```

#### Error Handling

If any block's agent returns an error or fails to produce a valid summary:
```
[Phase N/6] ✗ {phase_name} — ERROR: {brief description from agent output}
```
Stop and report to the user immediately. Do not silently continue to the next block.

### Phase C: Present

After all 4 blocks complete:

1. Output the full progress summary:
```
✓ AutoSearch complete
  Phase 1: Prepare — {details}
  Phase 2: Search — {details}
  Phase 3: Evaluate — {details}
  Phase 4: Deliver — {details}
  Phase 5: Quality — {details}
  Phase 6: Evolve — {details}
```

2. Show the delivery path and offer to open it.
3. If Rich HTML delivery, suggest: `open delivery/{session_id}.html`

## Key constraints

- `lib/judge.py` is the only evaluator — run it, never self-assess quality
- State files in `state/` are append-only
- Config/skill changes go through git commit/revert
- Each block agent must read the relevant `skills/*/SKILL.md` before executing
- Use Python 3.10+ for `lib/judge.py` and `lib/search_runner.py`
- All block agents run in Sonnet (`model: "sonnet"`) — do NOT inherit parent model
