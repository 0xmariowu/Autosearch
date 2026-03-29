---
name: llm-evaluate
description: "Use after collecting raw results when you need semantic relevance judgment instead of keyword overlap."
---

# Purpose

Use this skill to decide whether a result found the right thing, not merely matching words from the query.
`judge.py` treats `metadata.llm_relevant` as the relevance signal, so this skill directly affects score quality.

# Read First

Read the current task spec, goal case, or user objective before evaluating any result.
Read the query that produced the result, but do not let the query text define relevance by itself.
If prior batches already produced `next_queries`, read them so you do not keep suggesting the same follow-up.

# Core Behavior

Work in batches of at most 10 results.
Evaluate the highest-leverage results first: strongest titles, diverse sources, and items most likely to affect the bundle.
For each result, judge the title, snippet, source, and any freshness clues against the actual task.

Ask the real question:
- If the user saw only this result, would it materially help complete the task?
- Does it contain evidence about the target, not just mention the same nouns?
- Is it on-topic, actionable, and likely to survive scrutiny in final delivery?

Use `true` for results that are genuinely relevant.
Use `false` for tangential, generic, duplicate, bait, or keyword-matching noise.
Favor precision over generosity. False negatives are cheaper than polluting the bundle with false positives.

# What To Write

Preserve all existing record fields.
Add or update these metadata fields on each evaluated result:

- `metadata.llm_relevant`: `true` or `false`
- `metadata.llm_reason`: one short sentence explaining the judgment
- `metadata.llm_evaluated_at`: evaluation timestamp if you need provenance

At batch level, extract a small list of concrete follow-up queries:

- `next_queries` should come from missing concepts, missing entities, missing evidence types, or overly broad framing
- Suggest 0 to 3 queries per batch, not per result
- Deduplicate aggressively and keep them short enough to run directly

# Judgment Rules

Mark `false` when a result:

- repeats the query language without adding evidence
- matches the domain but wrong subproblem
- is about a neighboring concept instead of the requested one
- is a duplicate URL or near-duplicate title already covered elsewhere
- looks popular or fresh but does not help satisfy the task

Mark `true` when a result:

- directly answers a requested dimension
- supplies concrete evidence, examples, code, data, or strong synthesis
- is likely to be cited or used in delivery
- closes a known gap in the current bundle

# Next Query Strategy

`next_queries` are for steering the loop, not for brainstorming endlessly.
Generate them from observed gaps such as:

- missing dimension in the rubric
- right entity, wrong evidence type
- right topic, wrong timeframe
- right problem, missing implementation detail
- recurring false positives caused by ambiguous wording

Prefer queries that increase discrimination, such as adding a missing entity, symptom, constraint, or context term.
Do not suggest cosmetic rewrites that are unlikely to change retrieval.

# Failure Handling

If model output is messy, recover the structured judgment instead of abandoning evaluation.
Use a layered parse strategy:

- parse clean JSON directly
- strip markdown fences and retry
- extract the first plausible JSON object or array with a regex fallback

If extraction still fails, keep going with your own explicit per-result judgments rather than leaving relevance unset.

# Quality Bar

This skill exists because keyword overlap confuses "found matching keywords" with "found the right thing."
Be strict enough that a high relevance score means the evidence bundle is actually useful.
