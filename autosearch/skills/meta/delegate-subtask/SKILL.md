---
name: autosearch:delegate-subtask
description: Define the execution contract for isolating a research sub-task — input schema, budget, return summary, evidence list, failure status. Complements decompose-task (which only splits the problem) by giving each split a bounded, auditable execution unit the runtime AI can farm out to a sub-agent or parallel session.
version: 0.1.0
layer: meta
domains: [workflow, delegation]
scenarios: [subagent-execution, isolated-subtask, budgeted-research]
trigger_keywords: [delegate, subtask, sub-agent, parallel, isolate, budget]
model_tier: Standard
auth_required: false
cost: free
experience_digest: experience.md
---

# Delegate Subtask — Execution Contract

`decompose-task` splits a problem into sub-questions. This skill says how to **execute** each sub-question with a stable, auditable contract: inputs, budget, outputs, failure modes. Borrowed from MiroThinker + DeepAgents + deer-flow + DeepResearchAgent subagent patterns.

## Contract

```yaml
input:
  id: str                     # stable subtask id, e.g. "sub_1" / "sub_1a"
  parent_id: str | null       # linking back to the decompose-task output
  question: str               # one specific sub-question
  rationale: str              # why this subtask matters for the parent goal
  scope: list[str]            # channels / tools the subtask may touch
  budget:
    latency_seconds: int
    cost_usd: float
    tool_calls: int           # max total tool invocations
  context_seed: list[dict]    # evidence already gathered the subtask should start with
  stop_conditions: list[str]  # e.g. "answer rubrics satisfied" / "budget exhausted"

output:
  id: str                     # echoes input.id
  status: "success" | "partial" | "failure"
  summary: str                # 3-6 sentences; what was found
  evidence: list[dict]        # slim-dict Evidence items the subtask produced
  citations: list[str]        # URL list, matched to evidence
  follow_ups: list[str]       # open questions, if partial
  metrics:
    latency_ms: int
    cost_usd: float
    tool_calls: int
    channels_hit: list[str]
  failure_reason: str | null
```

## Invocation Policy

- **One subtask per thread/session** — isolation matters. Do not merge two subtasks' tool calls into one session.
- **Budget is the governor**. Subtask must halt when ANY budget axis is exhausted and report `status: "partial"`.
- **Read `context_seed`, don't re-search it**. Seed is evidence the parent already has; subtask should build on, not duplicate.
- **Return slim evidence** — use autosearch's `Evidence.to_slim_dict()` shape so the parent can dedupe/merge.
- **Follow-ups are first-class**. If a subtask runs out of budget but finds a promising lead, emit that in `follow_ups` for the parent planner to decide.

## Concurrency Guard

Delegate subtasks are cheap in parallel but expensive in total cost. Runtime AI should apply:

- `max_parallel_subtasks: 4` — hard cap, inspired by deer-flow's `subagent_limit_middleware`.
- `max_subtasks_per_session: 12` — escalate to user if the plan generates more.
- `subtask_timeout_headroom: 1.2x` — if any axis exceeds 1.2× its budget, kill immediately.

## When This Skill Is Used

- Runtime AI decomposed a complex research question into 3+ sub-questions and wants to execute them in parallel sessions.
- A single sub-question is so expensive that the parent planner wants it quarantined (cost / time).
- The parent planner wants per-subtask accountability (which sub-questions succeeded; which were over-budget; where to follow up).

## When NOT Used

- Trivial single-query research — overkill; just call a channel directly.
- Cross-cutting reflection / synthesis — that's `synthesize-knowledge`, not a subtask boundary.

## Related Skills

- Produces input from → `decompose-task`.
- Feeds output to → `assemble-context` / `synthesize-knowledge` / `citation-index`.
- Cost controlled by → `autosearch:model-routing` (Standard tier default for the subtask body; Best for the final consolidation).

## MCP Tool Usage

Use the `delegate_subtask` MCP tool to run a query across multiple channels in parallel:

```
delegate_subtask(
  task_description="Find Chinese UGC discussions about Cursor AI editor",
  channels=["xiaohongshu", "zhihu", "bilibili"],
  query="Cursor AI 编程助手 用户体验",
  max_per_channel=5
)
```

Returns `{evidence_by_channel: {"xiaohongshu": [...], "zhihu": [...]}, summary: "15 results from 3 channels", failed_channels: [], budget_used: {...}}`.
Feed `evidence_by_channel` values directly into `citation_add` or your synthesis.

## Failure Modes

- Budget exhausted before any evidence collected → `status: failure`, `failure_reason: "budget_exhausted_before_first_result"`.
- Subagent crashed mid-execution → `status: failure`, `failure_reason: "subagent_crash: <exception>"`. Parent planner decides retry vs. give up.
- Partial success → `status: partial`, `follow_ups` populated. Parent planner decides whether to escalate budget or accept partial.
