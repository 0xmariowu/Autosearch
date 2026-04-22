---
description: "Deep research via AutoSearch v2 tool-supplier — clarify → select channels → search → synthesize"
allowed-tools: ["mcp__autosearch__run_clarify", "mcp__autosearch__run_channel", "mcp__autosearch__list_skills", "mcp__autosearch__health"]
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

Use `channel_priority` from Step 1 as your starting list. If it is empty or you need more coverage, call `list_skills(group="channels")` and pick 3–5 channels for "fast" mode, 5–8 for "deep" mode.

Prefer channels that match the query language and domain:
- Chinese UGC queries → bilibili, xiaohongshu, zhihu, weibo
- Academic / papers → arxiv, google_scholar, papers (papers-with-code)
- Code / repos → github, package_search
- English community → hackernews, reddit, stackoverflow
- General web → ddgs, exa

## Step 3 — Run channels

Call `run_channel` for each selected channel, in parallel where possible:

```
run_channel(channel_name="bilibili", query="$QUERY", rationale="$WHY_THIS_CHANNEL")
```

Collect all `evidence` lists. If a channel returns `ok: false`, note the reason and continue.

For "deep" mode: after first-pass results, identify gaps in coverage and run 1–2 additional channels to fill them.

## Step 4 — Synthesize

Synthesize a cited markdown report from the collected evidence:

- Open with a 1-paragraph executive summary
- Use `## Section` headers for major themes
- Cite evidence inline: `[source title](url)` or `[N]` footnotes
- End with a `## Sources` section listing all URLs
- Check each rubric from Step 1 — if any are unmet, note it in a `## Coverage gaps` section

Do not add preamble like "Here is the report". Return the report directly.

## Fallback

If the `autosearch-mcp` MCP server is not available, run the CLI:

```bash
autosearch query "$ARGUMENTS"
```

If AutoSearch returns an error, report it briefly and stop.
