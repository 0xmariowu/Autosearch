---
name: research-mode
description: "Use at the start of a task to choose speed, balanced, or deep research depth from the user's urgency and complexity."
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

# Quality Bar

Mode choice is a strategy decision.
Pick the smallest mode that still has a credible path to a correct, useful answer.
