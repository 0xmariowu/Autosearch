---
name: autosearch:trace-harvest
description: Distill reusable knowledge from successful session tool-call traces. Reads runtime tool-call logs + Evidence outputs + user acceptance signals, filters successful paths, and writes compact patterns to per-skill experience/patterns.jsonl. Differs from outcome-tracker (which only records downstream acceptance) by parsing the full trace structure — inputs, tool choices, branches, recoveries.
version: 0.1.0
layer: meta
domains: [workflow, self-adaptive, learning]
scenarios: [trace-analysis, pattern-extraction, session-post-mortem]
trigger_keywords: [trace, harvest, post-mortem, session-review, winning-path]
model_tier: Standard
auth_required: false
cost: free
experience_digest: experience.md
---

# Trace Harvest — Distill Successful Sessions

MiroThinker's `collect-trace` + DeepResearchAgent's `general_memory_system` patterns adapted for autosearch. Analyzes a session's tool-call trace, identifies what worked, and turns it into promote-candidate patterns for `experience-capture` to store.

## Input

A completed autosearch session's trace:

```yaml
trace:
  session_id: str
  query: str
  clarify_result: ClarifyResult (from run_clarify)
  tool_calls: list[{name, args, result_summary, success, latency_ms, cost}]
  final_answer: str | null
  user_feedback: "accepted" | "rejected" | "unknown" | null
  rubrics_passed: list[str]
  rubrics_failed: list[str]
```

## Selection Rules

Only harvest traces where ANY of:

1. `user_feedback == "accepted"` (explicit positive).
2. `len(rubrics_passed) >= 0.6 * (rubrics_passed + rubrics_failed)` (objective quality gate).
3. Session finished within budget AND generated >= 5 unique evidence citations.

Reject traces where:

- User rejected the final answer.
- Session hit a budget-exhausted error.
- More than 3 tool calls failed consecutively.

## Harvest Output

Per successful trace, emit patterns keyed by leaf skill:

```json
{
  "ts": "...",
  "session_id": "...",
  "skill": "search-xiaohongshu",
  "winning_pattern": "brand + pain_word + recent_date_window",
  "good_query": "品牌 痛点词 近30天",
  "context": {
    "task_domain": "product-research",
    "clarify_had_rubrics": 4,
    "subsequent_channels_used": ["search-douyin", "search-zhihu"]
  },
  "metrics": {
    "relevant_out_of_returned": "9/18",
    "led_to_user_acceptance": true
  },
  "promote_candidate": true,
  "trace_ref": "traces/<session_id>.jsonl"
}
```

Each emitted pattern is appended via `experience-capture` to the relevant skill's `patterns.jsonl`. Trace-harvest does NOT write `experience.md` directly — that's `experience-compact`'s job.

## When Run

- At session end (if session had `user_feedback` signal).
- Batch mode: process the trace archive nightly, harvest successful sessions from the last 24h.

## Anti-Pattern Filters

- Single tool call leading to answer → not a pattern, do not harvest (too narrow).
- Tool call sequence exactly matched the router's default recommendation → not interesting; harvest only when the trace diverges from defaults and still succeeds.
- Query was trivially answerable by Claude's parametric knowledge → reject (we are trying to learn autosearch patterns, not Claude patterns).

## Privacy / Hygiene

- Sanitize query text before storing: replace specific identifiers (names, emails, IDs) with placeholders (`{user_name}`, `{issue_id}`).
- Never record cookies / API keys even transitively from tool-call args.
- Truncate tool-call result snippets to the 500-char summary; long text belongs in session trace archives, not in patterns.jsonl.

## Related Skills

- Consumes ← session trace files + user feedback events.
- Feeds → `experience-capture` (append pattern events).
- Complements ← `outcome-tracker` (downstream acceptance) and `experience-compact` (promotion).
- Does NOT replace them — trace-harvest is trace-structure analysis; outcome-tracker is result-use analysis.
