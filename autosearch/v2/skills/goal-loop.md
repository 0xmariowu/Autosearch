---
name: goal-loop
description: "Use for focused research tasks that need multi-round searching against a weighted rubric and explicit stop conditions."
---

# Purpose

Use this skill when the task has a real target, not just open-ended browsing.
A goal loop turns "search more" into a measurable control loop:

search -> evaluate against dimensions -> mutate queries toward missing coverage -> repeat

# Goal Case Shape

Work from a goal case with this conceptual structure:

- `problem`
- `providers`
- `seed_queries`
- `rubric`
- `target_score`

Each rubric dimension should have:

- an identifier or name
- a weight
- keywords, aliases, or signals that indicate coverage
- a clear notion of what missing evidence looks like

# Round Logic

Each round should do four things:

1. Search using the best current query set.
2. Evaluate the cumulative bundle against rubric dimensions, not just raw result count.
3. Identify the weakest or still-missing dimensions.
4. Mutate queries to target those missing dimensions in the next round.

Evaluate against the whole bundle so the loop can see what is already covered.
Also keep round-local notes so you know which queries actually moved a weak dimension.

# Scoring Mindset

Use weighted dimension coverage, not vague impressions.
A strong bundle covers the rubric broadly and concretely.
A weak bundle often has high volume but obvious holes in one or two important dimensions.

Treat the weighted rubric as the steering signal.
High-weight missing dimensions deserve more query budget than already-saturated low-weight ones.

# Query Mutation

Mutation should usually start from the best-performing current query.
Append 1 to 3 missing concrete terms, aliases, or evidence-type hints tied to the weak dimension.

Good mutation:

- adds a missing entity
- adds a missing mechanism or symptom
- adds a source or artifact type that the bundle lacks
- sharpens ambiguous framing

Bad mutation:

- rewrites the whole query for no reason
- appends generic filler words
- keeps chasing dimensions that are already saturated

If multiple dimensions are weak, spend most mutations on the highest-weight missing one and a smaller share on the next gap.

# Stop Conditions

Stop when any of these is true:

- target score reached
- two consecutive rounds with no improvement
- mode or budget limit reached

If anti-cheat hard-fails the candidate bundle, do not count that round as a successful improvement.

# State And Records

Record enough information that the next session can resume intelligently:

- current round number
- bundle score and dimension breakdown
- strongest queries
- weakest dimensions
- mutation terms chosen for the next round

If a mutation pattern clearly works, append a reusable lesson to `state/patterns.jsonl`.

# Quality Bar

This loop is for disciplined progress.
Do not keep exploring aimlessly once the rubric says the bundle is flat, saturated, or failing for the same reason twice.
