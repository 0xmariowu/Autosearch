---
name: llm-evaluate
description: "Use after collecting raw results when you need semantic relevance judgment instead of keyword overlap."
---

# Model Recommendation

This is a batch scoring task. Use Haiku when possible — it handles relevance classification well at much lower cost. When spawning an agent for scoring, set `model: "haiku"`.

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

Additionally, always extract and populate date metadata for freshness scoring:

- `metadata.published_at`: publication or creation date in ISO 8601 format
- `metadata.updated_at`: last update date in ISO 8601 format
- `metadata.created_utc`: creation date in ISO 8601 format

Extract dates from: snippet text, title year mentions, URL path date segments (e.g. `/2026/03/`), known publication dates of referenced papers (arXiv IDs encode submission date), GitHub `updatedAt` fields, and any other available signals.
For arXiv papers, derive the date from the paper ID: `YYMM.NNNNN` means year 20YY, month MM.
For GitHub repos, use the `updated_at` or `updatedAt` field from the search result.
For web results, look for date patterns in URLs and snippets.
Always extract a date for every result. Use all available signals: arXiv IDs (YYMM.NNNNN = 20YY-MM), GitHub updatedAt fields, URL path date segments (/2026/03/), year mentions in titles or snippets, conference year (ICLR 2025 = 2025-04), blog post dates. Only omit the field when truly zero date signals exist in the entire record.
Missing date fields score as zero freshness in judge.py — date extraction has the highest ROI of any metadata operation.

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

# Structured Gap Detection

After evaluating a batch, perform an explicit gap analysis:

1. List the task dimensions (from research-mode scope or decompose-task sub-questions)
2. For each dimension, count how many relevant results cover it
3. Identify dimensions with 0-2 results — these are critical gaps
4. Identify dimensions with only snippet-level coverage (no fetched full content) — these are depth gaps
5. Check content type distribution: are we heavy on repos but missing papers? Heavy on papers but missing tutorials?

Output the gap analysis as part of `next_queries` reasoning.
Gaps should directly drive follow-up query generation: each gap becomes a targeted query.

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
