---
name: autosearch:context-retention-policy
description: Session-level policy for keeping the runtime AI's context window healthy across long research — keep-last-k tool results, offload older evidence to disk, trigger compaction at thresholds. Borrows MiroThinker's keep_tool_result, deepagents' summarization middleware, and deer-flow's SummarizationEvent pattern. Orthogonal to assemble-context (which is per-synthesis-step); this is per-session.
version: 0.1.0
layer: meta
domains: [workflow, context-management]
scenarios: [long-session, token-budget, context-overflow, compaction-trigger]
trigger_keywords: [keep last k, compact context, offload evidence, context policy]
model_tier: Fast
auth_required: false
cost: free
experience_digest: experience.md
---

# Context Retention Policy — Session-Level Context Governance

A research session can generate more evidence / tool results than any reasonable context window. This skill tells the runtime AI **what to keep, what to offload, and when to compact**.

## Policy Parameters (defaults)

```yaml
policy:
  keep_last_k_tool_results: 12         # inline, full
  keep_all_citations_index: true       # citation_index stays in context always
  keep_all_rubrics: true               # rubrics stay in context always
  offload_trigger_token_ratio: 0.7     # compact when context ≥ 70% full
  offload_target_token_ratio: 0.4      # after compact, aim for 40% full
  offload_archive_path: "session/<id>/offloaded/<ts>.jsonl"
  prefer_compact_over_drop: true       # summarize instead of silently drop
  never_compact:
    - clarify_result
    - reflective_loop_state
    - graph_plan
    - citation_index
    - rubrics
```

## Compaction Procedure

When `current_tokens / max_tokens >= offload_trigger_token_ratio`:

1. **Sort evidence / tool_results by age** (oldest first).
2. **Identify candidates** — everything NOT in `never_compact` and older than the last K results.
3. **For each candidate batch** (every ~3 evidence items):
   - If `prefer_compact_over_drop`: use a Fast-tier LLM to summarize the batch into a single "digest" item (5-10 lines max, preserves URLs + key specifics verbatim).
   - Else: drop the batch but write full content to `offload_archive_path` for later recovery.
4. **Replace** the original items with the digest. Keep URLs in the citation_index so citations still resolve.
5. **Recheck token ratio**. If still above `offload_target_token_ratio`, iterate.

## Preservation Rules (never compact these)

- The current **reflective-search-loop state** (gaps, visited, bad_urls).
- The current **graph-search-plan graph** structure.
- The **citation-index entries** (they're short and referenced by all sections).
- The **rubrics** from run_clarify.
- The **original query** + **clarify verification message**.
- The **last 3 tool results** regardless of K.

Compacting these breaks the session's ability to finish correctly.

## Offload Archive Format

Each compacted batch writes a JSONL record:

```json
{
  "ts": "2026-04-22T03:10:00+08:00",
  "session_id": "...",
  "batch_id": "offload_0007",
  "reason": "token_budget_exceeded",
  "items": [
    {"kind": "tool_result", "tool_name": "run_channel", "args": {...}, "result": {...}},
    ...
  ],
  "digest_replacing_inline": "... 5-10 line summary ...",
  "original_token_count": 4200,
  "digest_token_count": 210
}
```

Archive is session-scoped; persist across process restarts in `session/<id>/offloaded/`. Used by `trace-harvest` and user-initiated "show me what got dropped" commands.

## When to Use

- Every long research session (>= 10 tool calls expected).
- When runtime AI detects context bloat.
- When user asks "what do you still have in context?" — this skill's state answers.

## When NOT to Use

- Short one-shot research (single decompose → 3 channel calls → synthesize). Overhead not justified.
- When the underlying runtime has its own compaction (check `discover-environment` first).

## Cost

Fast-tier LLM per compaction batch (low per-call). Triggered only when token budget crosses threshold, typically 1-2× per long session.

## Interactions

- Reads ← current session state (tool_results, evidence, citation_index, rubrics, loop state).
- Writes → digest items back into context + offload archive on disk.
- Complements ← `assemble-context` (per-synthesis-step context preparation).
- Triggered by → any tool-call that measurably grows the context beyond the trigger ratio.

## Boss Rule Alignment

- Digest entries must preserve specifics verbatim (numbers, error codes, issue numbers, URLs, version strings, benchmark scores) — same rule that drove the m3 deprecation. A digest that loses specifics is worse than dropping the batch entirely.
- Context retention is a **policy**, not a pipeline — runtime AI enforces it when useful, skips it when not.

# Quality Bar

- Evidence items have non-empty title and url.
- No crash on empty or malformed API response.
- Source channel field matches the channel name.
