---
name: research-mode
description: "Use when the user asks for a quick lookup, a brief answer, a deep dive, thorough research, or a comprehensive analysis to select speed, balanced, or deep search depth before querying. Use when you need to decide how many search rounds and queries to budget for a research task."
---

# Purpose

Pick a research budget that matches the task.
Mode selection prevents both over-searching simple asks and under-searching hard ones.

# Modes

Use these base budgets:

- `speed`: 3 queries, 1 round
- `balanced`: 5 queries, 3 rounds
- `deep`: 7 queries, 5 rounds

Treat these as default ceilings for the search loop.

# Selection Heuristics

Choose `speed` when:

- the user wants a quick answer
- the task is narrow and factual
- latency matters more than exhaustive coverage

Choose `balanced` when:

- the task is standard research
- the scope is bounded but not trivial
- you need some iteration, comparison, and follow-up

Choose `deep` when:

- the user wants a thorough survey
- the task has many dimensions or high ambiguity
- the answer will drive a consequential decision
- earlier rounds plateaued but the problem remains unsolved

If the user gives no clear signal, default to `balanced`.

# Examples

**"What year was Python 3.10 released?"**
→ `speed` — narrow factual question, one query is enough, answer in seconds.

**"Compare the top three open-source vector databases for a RAG pipeline."**
→ `balanced` — bounded comparison across a few products, needs iteration and follow-up but scope is clear.

**"Give me a comprehensive survey of federated learning techniques, their trade-offs, and which frameworks implement them."**
→ `deep` — multi-dimensional topic, high ambiguity, the user explicitly wants thoroughness, and the answer will inform an architecture decision.

# Mode Behavior

`speed` should minimize planning and avoid expensive exploration.
`balanced` should allow normal planning, a few follow-ups, and measured refinement.
`deep` should spend more budget on coverage, validation, and acquisition when available.

Do not run a deep workflow out of habit.
Earn the extra rounds by task complexity or by evidence that shallow search is insufficient.

# Interaction With Other Skills

Research mode sets the search budget used by:

- `gene-query.md` for query count
- `goal-loop.md` for maximum rounds
- provider selection and acquisition depth when those decisions are flexible

If anti-cheat rejects a round or the rubric still has major holes, mode may justify another round only up to its ceiling.

# Auto-Adjustment

You can escalate one level when the task proves harder than first estimated.
You can de-escalate when a target is already reached cleanly.
Do not keep changing modes every round without a clear reason.

# Scope Definition

Before starting any search, answer three questions:

- **What's in scope?** — the specific aspects of the topic to investigate
- **What's out of scope?** — what to explicitly exclude (adjacent topics, time periods, etc.)
- **What does done look like?** — concrete criteria for a complete answer (e.g., "covers open-source projects, papers, and commercial products with a conceptual framework")

If the task is complex enough for decompose-task.md, the scope definition informs the sub-question generation.

Write the scope answers in the worklog before searching.
If mid-search you discover the scope was wrong, update it and note the change.

# Quality Bar

Mode choice is a strategy decision.
Pick the smallest mode that still has a credible path to a correct, useful answer.
