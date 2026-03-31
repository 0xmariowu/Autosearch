---
name: gene-query
description: "Use when you need to expand a task into diverse search queries built from entity, pain_verb, object, symptom, and context genes."
---

# Purpose

Generate queries from five gene dimensions instead of improvising all search text from scratch.
This restores a reusable query grammar that turns vague tasks into targeted searches.

# The Six Dimensions

- `entity` = WHO is involved
- `pain_verb` = ACTION or failure mode
- `object` = WHAT artifact, tool, concept, or target is involved
- `symptom` = HOW the problem appears
- `context` = WHERE or under what condition it happens
- `content_type` = WHAT KIND of result you want (repo, paper, blog, tutorial, company, video, awesome-list)

Good queries usually need only 2 or 3 dimensions.
Do not cram all six into every query.

Use `content_type` to steer queries toward underrepresented evidence.
If the current bundle is heavy on repos and light on papers or blogs, generate queries that explicitly target the missing types.
Examples: "self-evolving agent tutorial", "self-improving AI startup company", "self-evolving agent survey paper".

# Input Sources

Build the gene pool from three places:

- The task itself: entities, artifacts, constraints, and pain language from the user or goal case
- Winning history: patterns from `state/patterns.jsonl` and proven queries from `state/outcomes.jsonl`
- Your own judgment: missing synonyms, domain terms, and alternate framings not yet present in state

# Mix Ratio

Generate candidate queries with this mix:

- 20% LLM suggestions
- 20% winning patterns
- 60% gene combinations

Keep the ratio in spirit, not as rigid bookkeeping.
If one source is exhausted, backfill from the others without collapsing into a single style.

# Combination Rule

For each gene-combination query:

- pick 2 or 3 dimensions
- pick exactly 1 value from each chosen dimension
- join them into a terse search phrase

Examples of the shape:

- `entity + object`
- `pain_verb + object`
- `entity + symptom + context`
- `pain_verb + object + context`

Prefer specific combinations that narrow meaning without becoming long natural-language sentences.

# Query Construction Heuristics

Keep one anchor term that strongly binds the topic.
Add one discriminator that changes what results appear.
Add a third term only when it meaningfully sharpens retrieval.

Prefer concrete tokens over generic prose.
Prefer symptoms over emotional adjectives.
Prefer observable failures over abstract aspirations.

Use winning query patterns from state when they clearly transfer.
Boost queries whose words or families have proven outcomes.
Keep seed queries from the task or config in the set even if they are not gene-generated.

# Diversity Rules

Do not emit many trivial variations of the same query.
Vary the dimension mix across the set:

- some entity-led
- some pain-led
- some object-led
- some context-led

Avoid a pool where every query starts from the same noun phrase.
Deduplicate semantically, not only by exact string match.

# Freshness And Time

Do not hard-cap all generated queries by recency.
Add time qualifiers only when the task explicitly needs freshness or the prior round showed stale retrieval.

# Suggested Output Shape

For each query, keep lightweight provenance if useful:

- query text
- source bucket: `llm`, `pattern`, or `gene`
- chosen dimensions
- optional `query_family` label for provider-health or outcome tracking

# Quality Bar

The goal is not "many queries."
The goal is a compact set of queries that attack the task from different angles and produce non-overlapping evidence.
