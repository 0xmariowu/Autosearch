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
> **Time limit: 5 minutes.** Record start time. After each tool call, check elapsed. If > 5 min, skip remaining steps and return summary with what you have.
>
> Read `skills/pipeline-flow/SKILL.md` for context, then execute Phase 0 and Phase 1:
>
> 1. **Check for prior research context**: If `state/research-contexts/{topic-slug}.json` exists, load it. This contains knowledge items, search results, and citations from a previous session on the same topic. Skip recall dimensions already covered with HIGH confidence in the prior context. This makes repeat-topic sessions faster and smarter.
> 2. Read `skills/generate-rubrics/SKILL.md` and generate rubrics. Write to `evidence/rubrics-{topic-slug}.jsonl`.
> 3. Write `state/timing.json` with `{"start_ts": "{ISO 8601 now}"}`.
> 4. Read `skills/systematic-recall/SKILL.md` and run 9-dimension recall. If prior context was loaded in step 1, merge: keep prior HIGH-confidence items, add new recall items, re-evaluate items that may have changed. Write the full output to `state/session-{id}-knowledge.md`.
> 5. Read `skills/select-channels/SKILL.md` and pick channels based on depth and focus.
> 6. Read `state/patterns-v2.jsonl` to inform query strategy with winning patterns from prior sessions. Count how many patterns were loaded and how many were applicable to this topic.
> 7. Read `skills/gene-query/SKILL.md` and generate gap-driven queries. Apply any relevant patterns from step 6 (e.g., channel preferences, query structures that worked before).
> 8. **Enforce query cap**: Quick=8, Standard=15, Deep=25. If more queries generated, keep the most diverse subset (maximize unique channels and content_type variety). Drop duplicate-intent queries first.
> 9. Write the final capped query JSON array to `state/session-{id}-queries.json`.
>
> At the end, output a JSON summary: `{"rubrics": N, "knowledge_items": N, "gaps": N, "queries": N, "channels": ["list"], "patterns_loaded": N, "patterns_applied": N}`

After Block 1 returns, parse its summary and output:
```
[Phase 1/6] ✓ Prepare — {rubrics} rubrics, {knowledge_items} items recalled, {queries} queries planned
```

**Query cap guard**: If `queries` exceeds the depth cap (Quick=8, Standard=15, Deep=25), log a warning but continue — the cap should have been enforced in the agent, this is a safety net.

**Zero-query guard**: If `queries == 0`, do NOT ask the user. Instead, auto-generate 4 freshness-check queries: `["{topic} latest 2026", "{topic} new developments", "{topic} recent news", "{topic} trends"]` across the selected channels. Write them to the queries file and continue. Reason: the user chose to search — 0 queries means the query generation failed, not that search is unnecessary.

#### Block 2: Search (Phase 2) — Sonnet

Spawn a Sonnet agent (`model: "sonnet"`) with this task:

> Working directory: `${CLAUDE_PLUGIN_ROOT}`
> Session ID: {session_id}. Topic: {topic}.
>
> **Time limit: 5 minutes.** Record start time. If search_runner takes > 4 min, kill it and proceed with partial results.
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
> **Time limit: 5 minutes.** Record start time. After each batch, check elapsed. If > 5 min, finish current batch and skip remaining.
>
> Read `skills/llm-evaluate/SKILL.md` for context.
>
> 1. Read `evidence/{session_id}-results.jsonl`.
> 2. For each result, judge relevance against the topic. Tag with `metadata.llm_relevant` (true/false) and `metadata.llm_reason`.
> 3. Work in batches of 10. Evaluate the highest-leverage results first.
> 4. Write evaluated results back to `evidence/{session_id}-results.jsonl`.
> 5. Track per-query outcomes: append to `state/query-outcomes.jsonl` per pipeline-flow Phase 3a.
> 6. **Reflect**: After evaluation, ask yourself: "What knowledge dimensions are still poorly covered?" Output a `gap_dimensions` list — each entry is a dimension name + what's missing + why it matters. This is NOT just "which queries returned nothing" — it's a higher-level assessment of conceptual gaps in the evidence.
> 7. If critical gaps remain (dimensions with <= 1 relevant result), write up to 5 gap-fill queries to `evidence/{session_id}-next-queries.jsonl`. Use the gap_dimensions from step 6 to generate targeted queries. Otherwise write an empty file.
> 8. **REQUIRED — Compress**: For each relevant result (llm_relevant=true), write a one-sentence structured claim: `{"url": "...", "claim": "one sentence key finding", "source": "...", "dimension": "which knowledge dimension this covers"}`. Write to `evidence/{session_id}-claims.jsonl`. This compressed view is consumed by Block 4 instead of raw results. **Do not skip this step** — Block 4 depends on claims.jsonl to stay within output size limits.
>
> At the end, output a JSON summary: `{"relevant": N, "filtered": N, "gap_queries": N, "gap_dimensions": ["list"], "claims": N}`

After Block 3 returns, parse its summary and output:
```
[Phase 3/6] ✓ Evaluate — {relevant} relevant, {filtered} filtered, {claims} claims compressed, {gap_dimensions} gaps identified
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
> **Time limit: 8 minutes.** Record start time. After each tool call, check elapsed. If > 8 min, finish with what you have and return summary immediately.
>
> Read `skills/pipeline-flow/SKILL.md` Phase 4 for context.
>
> 1. Read `state/session-{id}-knowledge.md` for Claude's own knowledge backbone.
> 2. Read `evidence/{session_id}-claims.jsonl` for compressed search findings (one claim per line — much smaller than raw results). If claims file doesn't exist, fall back to reading `evidence/{session_id}-results.jsonl` via Bash: `python3 -c "import json; [print(json.dumps({'url':r.get('url',''),'title':r.get('title',''),'claim':r.get('snippet','')[:200],'source':r.get('source','')})) for r in (json.loads(l) for l in open('evidence/{session_id}-results.jsonl')) if r.get('metadata',{}).get('llm_relevant')]"` — this extracts only relevant results as compact JSON.
> 3. Compile a numbered citation index from all search result URLs (read from results file for URLs, use claims for content).
> 4. Read `skills/synthesize-knowledge/SKILL.md` and produce the delivery:
>    - Blend knowledge backbone with search discoveries
>    - Organize by concept, not by source
>    - Mark provenance: [knowledge] vs [discovered] vs [verified]
>    - If Rich HTML: produce a standalone HTML file with tables, styling, and diagrams
>    - If Markdown: produce a .md report
>    - If Slides: produce a standalone reveal.js HTML file
>    - Report footer: "Generated by AutoSearch v{version}" (use the version passed above, NOT "v2.2")
> 5. Read `skills/evaluate-delivery/SKILL.md` and self-check. Revise if needed (max 1 revision).
> 6. Write delivery to `delivery/{session_id}.html` (or `.md` or `-slides.html`).
> 7. Run `PYTHONPATH=. .venv/bin/python3 lib/judge.py evidence/{session_id}-results.jsonl` and capture the score.
> 8. **Save research context** for future sessions on the same topic. Write `state/research-contexts/{topic-slug}.json` with:
>    - `topic`: the topic text
>    - `timestamp`: ISO 8601 now
>    - `session_id`: this session's ID
>    - `knowledge_dimensions`: list of 9 dimensions with confidence levels from the knowledge backbone
>    - `search_urls`: list of all relevant result URLs (so next session can skip them)
>    - `citations_used`: list of citation URLs actually used in the report
>    - `gap_dimensions`: carried forward from Block 3's reflect output
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
> **Time limit: 3 minutes.** Record start time. If > 3 min, return what you have.
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

**Always run.** Evolution is the session's core value, not an optional add-on. If time is tight, do minimal evolution (patterns + query-outcomes only), but never skip entirely.

Spawn a Sonnet agent (`model: "sonnet"`) with this task:

> Working directory: `${CLAUDE_PLUGIN_ROOT}`
> Session ID: {session_id}. Topic slug: {topic_slug}.
>
> **Time limit: 3 minutes.** Record start time. If > 3 min, return what you have.
>
> Read `skills/pipeline-flow/SKILL.md` Phase 6 for context.
>
> 1. **Write query outcomes**: Read `evidence/{session_id}-results.jsonl`. For each unique query+channel combination, compute results_count and relevant_count (from `metadata.llm_relevant`). Append to `state/query-outcomes.jsonl`.
> 2. **Write winning patterns**: From query-outcomes just written, extract combinations with relevant_rate > 0.5. Append to `state/patterns-v2.jsonl` with type `winning_pattern`, channel, topic_type, and confidence.
> 3. Read `skills/auto-evolve/SKILL.md` and run one evolution step (diagnose failed rubrics → modify one skill/data file → git commit → record in evolution-log.jsonl).
> 4. Append to `state/worklog.jsonl`: task_spec, search_run, reflection, delivery entries.
> 5. Read `skills/knowledge-map/SKILL.md` and save updated knowledge map.
>
> At the end, output a JSON summary: `{"patterns_saved": N, "query_outcomes_written": N, "evolved": true/false, "evolution_file": "path or null"}`

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

**Timeout**: Each block has a time limit (documented in its prompt). If an agent exceeds its limit, it should self-terminate and return partial results. If the orchestrator detects a block has been running significantly past its limit (e.g., no response after 2x the stated limit), interrupt the agent and output:
```
[Phase N/6] ✗ {phase_name} — TIMEOUT after {elapsed} min (limit: {limit} min)
```

**Claims check**: After Block 3 returns, verify `evidence/{session_id}-claims.jsonl` exists and is non-empty. If missing, output a warning: "Claims file missing — Block 4 will use raw results (slower)." Continue execution.

### Phase C: Present

After all blocks complete:

1. **Verify deliverables exist** before declaring success:
   - `delivery/{session_id}.*` exists and is non-empty → report is ready
   - `evidence/{session_id}-results.jsonl` exists → search ran
   - If delivery file is missing, output: `⚠ Pipeline completed but no report was generated. Check Block 4 output above for errors.`

2. Output the full progress summary:
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

3. Show the delivery path and offer to open it.
4. If Rich HTML delivery, suggest: `open delivery/{session_id}.html`

## Key constraints

- `lib/judge.py` is the only evaluator — run it, never self-assess quality
- State files in `state/` are append-only
- Config/skill changes go through git commit/revert
- Each block agent must read the relevant `skills/*/SKILL.md` before executing
- Use Python 3.10+ for `lib/judge.py` and `lib/search_runner.py`
- Block model routing: Sonnet for reasoning/synthesis (1, 2, 4, 6), Haiku for classification (3, 5)
- All blocks spawn with `mode: "acceptEdits"` — NOT `mode: "auto"` (which maps to `default` for plugins and causes permission hangs)
- **NEVER use WebSearch/WebFetch in search blocks** — always use `lib/search_runner.py` via Bash
