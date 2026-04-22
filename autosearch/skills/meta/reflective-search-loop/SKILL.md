---
name: autosearch:reflective-search-loop
description: Explicit loop state for multi-round research — maintains gaps, visited URLs, bad URLs, failed-evaluator feedback, and decides whether to fire another round of queries or stop. Inspired by WebThinker's in-band search protocol, node-deepresearch's agent.ts state, and Scira's extreme-search.
version: 0.1.0
layer: meta
domains: [workflow, planning, reflection]
scenarios: [deep-research, gap-driven-followup, multi-round-search, evaluator-feedback]
trigger_keywords: [reflective, search loop, gaps, visited, iterate, follow-up]
model_tier: Best
auth_required: false
cost: free
experience_digest: experience.md
---

# Reflective Search Loop — Explicit Loop State

Most autosearch leaf skills are one-shot: call, get evidence, done. This meta skill codifies a **multi-round** loop that the runtime AI drives when the task is deeper than one query round can settle.

## Loop State

```yaml
loop:
  round: int                         # 0, 1, 2, ...
  budget_remaining:
    rounds: int                      # hard cap, e.g. 5
    cost_usd: float
    latency_seconds: int
  context:
    query: str                       # original user query
    rubrics: list[str]               # from run_clarify
  progress:
    gaps: list[str]                  # outstanding sub-questions, grows/shrinks
    answered_gaps: list[str]         # resolved this round
    all_questions: list[str]         # every question asked across all rounds
    visited_urls: list[str]          # URLs already fetched
    bad_urls: list[str]              # URLs that 404'd / were blocked / returned junk
    evidence: list[dict]             # accumulated Evidence items
    evaluator_failures: list[str]    # rubric/quality failures from previous round
  decision:
    next_action: "search_more" | "fetch_more" | "finalize" | "escalate_budget" | "abort"
    next_queries: list[str] | null
    next_urls_to_fetch: list[str] | null
    stop_reason: str | null
```

## Round Structure

Each loop iteration:

1. **Reflect** (Best tier LLM): given current `loop` state, decide `next_action`.
2. **Act**: call `run_channel(...)` or `fetch-jina`/`fetch-crawl4ai` for the chosen next step.
3. **Integrate**: update `progress` (visited URLs, evidence list, new gaps discovered).
4. **Evaluate** (if enabled): run `check-rubrics` or `evaluate-delivery`; record failures in `evaluator_failures`.
5. **Loop** or **stop**: check budget + stop conditions.

## Stop Conditions

ANY of:

- `round >= budget_remaining.rounds` (hard cap).
- `len(gaps) == 0` AND `len(evaluator_failures) == 0` (task complete).
- `len(new_evidence_this_round) == 0` for 2 consecutive rounds (stalled).
- `cost_usd` > allocated budget.
- User explicitly aborts.

## What This Skill Is NOT

- Not a replacement for the deleted-wave-3 m3 iteration. That was an **implicit** loop inside the autosearch pipeline. This is an **explicit** protocol the runtime AI follows — state is visible to the user/runtime, not buried inside `autosearch research()`.
- Not a sub-agent orchestrator — that's `delegate-subtask`. This is single-agent, single-session multi-round.

## Interactions

- Starts from → `run_clarify` result (rubrics, initial gaps from query_type).
- Fans out to → `run_channel` per round.
- Uses → `fetch-jina` / `fetch-crawl4ai` for URL reads in each round.
- Finalizes via → `synthesize-knowledge` + `evaluate-delivery`.

## Cost Discipline

Reflective loops are expensive (Best tier × N rounds). Runtime AI should:

- Default to 2-3 rounds for most research tasks.
- Escalate to 5 rounds only when `rubrics_failed > 30%` after round 3.
- Never exceed 8 rounds without user confirmation (escalate_budget).

## MCP Tool Usage

Full reflective loop using MCP tools:

```
# Initialize loop
result = loop_init()
state_id = result["state_id"]

# Round 1
evidence = run_channel(channel_name="arxiv", query="RAG survey 2026")["evidence"]
loop_update(state_id=state_id, evidence=evidence, query="RAG survey 2026")

# Check gaps after round 1
gaps = loop_get_gaps(state_id=state_id)["gaps"]
# gaps might be: ["no benchmarks found", "missing 2026 papers"]

# Manually add a gap if you spot one
loop_add_gap(state_id=state_id, gap="no industry deployment case studies")

# Round 2: search specifically for gaps
for gap in gaps:
    evidence2 = run_channel(channel_name="semantic-scholar", query=gap)["evidence"]
    loop_update(state_id=state_id, evidence=evidence2, query=gap)
```

Loop state is in-memory per server process. State is lost on server restart (use within one session).

## Prior Art Anchors

- **WebThinker**: in-band `<|begin_search_query|>` / `<|begin_click_link|>` protocol — we do not reproduce the tokens, but preserve the explicit state tracking of executed queries / clicked URLs.
- **node-deepresearch**: `gaps / allQuestions / allKnowledge / visitedURLs / badURLs / weightedURLs / evaluationMetrics` state — adopted verbatim.
- **Scira extreme-search**: forced `thinking -> tool` alternation and mandatory date injection for time-sensitive queries — adopt the date-anchor rule.

# Quality Bar

- Evidence items have non-empty title and url.
- No crash on empty or malformed API response.
- Source channel field matches the channel name.
