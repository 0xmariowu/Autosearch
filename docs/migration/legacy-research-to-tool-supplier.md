# Migration: Legacy `research()` → Tool-Supplier Trio

> Status: wave-3 migration guide.
> Audience: runtime AI (Claude Code / Cursor / Zed) and their developers.
> Supersedes: direct use of `research()` MCP tool for new code.

## TL;DR

The legacy `research()` MCP tool runs autosearch's full pipeline (clarify → decompose → channel fan-out → m3 compaction → m7 synthesis) and returns a finished markdown report. The **v2 tool-supplier architecture** replaces that with three discoverable atomic tools:

- `list_skills(group?, domain?)` — discover what autosearch can do.
- `run_clarify(query, mode_hint?)` — get clarification envelope + rubrics + channel priorities.
- `run_channel(channel_name, query, k?)` — fetch raw evidence from one channel.

The runtime AI synthesizes the final report itself. Autosearch no longer hides judgment inside a pipeline.

## Why Migrate

| Problem with `research()` | How the trio fixes it |
|---|---|
| Gate 12 loses 0 / 62 to native Claude — pipeline wraps runtime AI's strong synthesis and replaces it with autosearch's weaker synthesizer | Runtime AI keeps its own synthesis step |
| Users can't see intermediate state (only final report) | Runtime AI decides every step, state is explicit |
| m3 compaction strips concrete specifics before m7 sees them | No compaction; evidence goes straight to runtime AI |
| Pipeline retries / fan-out / rounds are invisible cost | Runtime AI sees every tool call; budget is user-visible |
| Skill discovery hidden — runtime AI can't reach channels directly | `list_skills` + `run_channel` make all channels first-class tools |

## Minimum Migration

Old:

```python
# MCP tool call
research(query="XGP 香港服和国服区别", mode="fast")
# → ResearchResponse(content="<finished markdown report>", ...)
```

New (runtime AI does it, no autosearch synthesis):

```python
# Step 1: discover
skills = list_skills(group="channels", domain="chinese-ugc")
# → filters down to bilibili / weibo / xiaohongshu / douyin / zhihu / etc.

# Step 2: clarify
clarify = run_clarify(query="XGP 香港服和国服区别", mode_hint="fast")
# → ClarifyToolResponse{need_clarification, rubrics, channel_priority, ...}
if clarify.need_clarification:
    # ask user clarify.question, then re-call with enriched query
    ...

# Step 3: execute channels (parallel, runtime-controlled)
evidence_bundle = []
for channel in clarify.channel_priority[:5]:  # top 5 from clarifier
    resp = run_channel(channel_name=channel, query=query, k=10)
    if resp.ok:
        evidence_bundle.extend(resp.evidence)

# Step 4: synthesize — runtime AI does this with its own model
# No autosearch tool needed; Claude writes the report directly from evidence_bundle
```

## Patterns for the Middle Ground

If the runtime AI wants to mimic the old `research()` behavior quickly (but better):

```python
# "Quick research" pattern
clarify = run_clarify(query)
if clarify.need_clarification:
    return clarify.question  # ask user

top_channels = clarify.channel_priority[:3]
evidence = [ev for ch in top_channels
            for ev in run_channel(ch, query, k=5).evidence]

# Runtime AI synthesizes. Keep specifics verbatim (numbers, error codes,
# issue numbers, benchmarks, version strings). Do not compact evidence
# before synthesizing — runtime has enough context; autosearch no longer
# does m3-style compaction.
report = runtime_ai.synthesize(query, evidence, rubrics=clarify.rubrics)
```

## Patterns for Deep Research

For deep research workflows, compose with wave-3 meta skills:

1. `run_clarify` — get scope + rubrics.
2. `decompose-task` or `graph-search-plan` — break into sub-questions.
3. `perspective-questioning` (optional) — widen coverage.
4. `delegate-subtask` per sub-question (or per graph node).
5. Each sub-task calls `run_channel` + optional `fetch-jina` / `fetch-crawl4ai`.
6. `reflective-search-loop` — iterate until rubrics pass or budget exhausted.
7. `citation-index` — consolidate citations across sub-answers.
8. Runtime AI synthesizes final report.
9. `evaluate-delivery` + `check-rubrics` — self-check before delivery.
10. `experience-capture` — log per-skill outcomes to experience/patterns.jsonl.

## Deprecation Timeline

- **Today**: `research()` still works. `list_skills` / `run_clarify` / `run_channel` are live next to it.
- **Runtime-AI side**: start using the trio for new integrations; keep calling `research()` for existing flows until you have time to switch.
- **Future (wave 3 part 2)**: `research()` becomes a thin wrapper that internally uses the trio + a simple evidence concatenation (no synthesis). Users invoking it get a deprecation warning in the response.
- **Eventually**: `research()` tool is removed from the MCP server, along with `autosearch/core/context_compaction.py`, `autosearch/core/iteration.py`, `autosearch/synthesis/section.py`, and all `m3_*` / `m7_*` prompts. Backward-compat window pending real usage evidence.

The deprecation notices on `m3_evidence_compaction.md`, `m7_section_write.md`, `m7_section_write_v2.md`, `m7_outline.md`, and the three Python caller modules already point at this plan.

## Cost Comparison

| Scenario | `research()` (legacy) | Trio (v2) |
|---|---|---|
| Same query | One large Pipeline.run call ~ $0.10-0.50 per query | Sum of run_clarify + N × run_channel + runtime synthesis ~ $0.03-0.20 per query |
| Failed query (budget exhausted) | Pipeline returns partial report; cost already spent | Each tool call is a discrete cost; user can cancel anytime |
| Repeated query | Full pipeline runs again | `list_skills` / per-channel experience.md can cache scope decisions |

## FAQ

**Q: Can I still use `research()`?**
A: Yes. It's not removed. It carries the legacy pipeline, which has the known Gate 12 weakness. For new integrations, prefer the trio.

**Q: Does the trio support the same channels as `research()`?**
A: Yes — all 31 channels plus the new v2 tools (`fetch-jina`, `fetch-crawl4ai`, `fetch-playwright`, `mcporter`, the three `video-to-text-*`).

**Q: What about clarification flow?**
A: `run_clarify` returns a `need_clarification` boolean + a `question` string. If true, the runtime AI should ask the user the question and then re-call `run_clarify` with the enriched query.

**Q: How do I know which channels to call?**
A: `run_clarify` returns `channel_priority` + `channel_skip`. Or call `list_skills(group="channels", domain="<your-domain>")` to see the full catalog with `model_tier` and `scenarios`.

**Q: Where is the pipeline's iteration / reflection loop now?**
A: If you want it, compose `reflective-search-loop` meta skill manually. If you don't, don't — one round of channel fan-out usually suffices.

## Related Docs

- `docs/proposals/2026-04-21-v2-tool-supplier-architecture.md` — the architecture proposal.
- `docs/proposals/2026-04-22-wave-2-status-and-wave-3-plan.md` — wave 3 rollout plan.
- `docs/bench/gate-12-augment-vs-bare.md` — the success metric for this migration.
- Wave 3 skills under `autosearch/skills/meta/` — the workflow vocabulary for composing research.
