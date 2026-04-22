---
description: "Deep research via AutoSearch v2 tool-supplier — clarify → select channels → search → synthesize"
allowed-tools: [
  "mcp__autosearch__run_clarify",
  "mcp__autosearch__run_channel",
  "mcp__autosearch__list_skills",
  "mcp__autosearch__list_channels",
  "mcp__autosearch__health",
  "mcp__autosearch__doctor",
  "mcp__autosearch__select_channels_tool",
  "mcp__autosearch__delegate_subtask",
  "mcp__autosearch__loop_init",
  "mcp__autosearch__loop_update",
  "mcp__autosearch__loop_get_gaps",
  "mcp__autosearch__loop_add_gap",
  "mcp__autosearch__citation_create",
  "mcp__autosearch__citation_add",
  "mcp__autosearch__citation_export",
  "mcp__autosearch__citation_merge",
  "mcp__autosearch__trace_harvest",
  "mcp__autosearch__perspective_questioning",
  "mcp__autosearch__graph_search_plan",
  "mcp__autosearch__recent_signal_fusion",
  "mcp__autosearch__context_retention_policy"
]
---

Run deep research with AutoSearch v2. You are the research conductor: AutoSearch supplies channels and evidence; you synthesize the final report.

## Step 1 — Clarify

Call `run_clarify` with the user's query.

```
run_clarify(query="$ARGUMENTS")
```

If the response has `need_clarification: true`, ask the user the returned `question` verbatim and wait for their answer. Then call `run_clarify` again with the enriched query. Only ask once.

If `need_clarification: false`, proceed immediately — do not ask the user anything.

Use the returned fields:
- `mode` — "fast" or "deep": governs how many channels to run
- `channel_priority` — preferred channels (run these first)
- `channel_skip` — channels to skip for this query
- `rubrics` — binary criteria for evaluating your final report

## Step 2 — Select channels

Call `select_channels_tool(query=..., channel_priority=..., mode=...)` to get a ranked channel list.

```
select_channels_tool(query="$QUERY", channel_priority=["xiaohongshu","bilibili"], mode="fast")
```

Returns `{groups, channels, rationale}`. Use `channels` as your run list (3–5 for fast, 5–8 for deep).

Alternatively call `list_skills(group="channels")` and pick manually. For channel health, call `doctor()`.

## Step 3 — Run channels

For parallel multi-channel search, use `delegate_subtask`:

```
delegate_subtask(task_description="...", channels=["bilibili","arxiv","github"], query="$QUERY")
```

Returns `{evidence_by_channel, summary, failed_channels}`. Or call `run_channel` per channel individually.

For deep mode with gap tracking, use the loop tools:

```
state = loop_init()
# after each run_channel batch:
loop_update(state_id=state.state_id, evidence=[...], query="$QUERY")
gaps = loop_get_gaps(state_id=state.state_id)
# run additional channels for gaps, then repeat
```

## Step 4 — Synthesize

Create a citation index and build a cited report:

```
idx = citation_create()
citation_add(index_id=idx.index_id, url="https://...", title="...", source="channel_name")
# ... add all sources ...
refs = citation_export(index_id=idx.index_id)
```

Synthesize a cited markdown report from the collected evidence:

- Open with a 1-paragraph executive summary
- Use `## Section` headers for major themes
- Cite inline as `[1]`, `[2]` etc. matching the citation index
- End with the `refs` markdown as the `## References` section
- Check each rubric from Step 1 — if any are unmet, note it in `## Coverage gaps`

Do not add preamble like "Here is the report". Return the report directly.

## Fallback

If the `autosearch-mcp` MCP server is not available, run the CLI:

```bash
autosearch query "$ARGUMENTS"
```

If AutoSearch returns an error, report it briefly and stop.
