---
name: outcome-tracker
description: "Use after intake and during follow-up review to learn which queries produced results that were actually used, then boost those queries in future runs."
---

# Purpose

Not all relevant results create value.
This skill closes the loop between retrieval and actual usage so future query generation can favor queries that led to adopted outcomes.

# Two Phases

Phase 1 is intake recording.
Phase 2 is outcome counting.

Do both. Recording intakes without later usage counts creates noise. Counting usage without provenance makes learning impossible.

# Phase 1: Record Intakes

Whenever a result is accepted into a meaningful downstream artifact, append a record to `state/outcomes.jsonl`.
Keep provenance from the start:

- repo or canonical URL
- intake date
- score or acceptance strength
- `source_query`
- optional `query_family`
- session or generation identifiers if available

If a result came from multiple queries, record the best-supported provenance instead of pretending provenance is unknown.

# Phase 2: Count Real Usage

Later, revisit those intake records and count actual usage signals.
The exact downstream artifact can vary, but the principle is stable: measure whether the result was really used.

Useful signals include:

- cited in delivery
- turned into a reusable pattern
- adopted into workflow or tooling
- produced concrete WHEN/USE style guidance

Update outcome understanding by appending new records or append-only follow-up facts.
Do not delete prior outcome history.

# Outcome Scoring

Roll usage back up to the query level.
The point is to learn:

- which exact queries produced useful results
- which query families repeatedly produce usable outcomes
- which queries only produce intake noise

Queries with strong downstream usage deserve a boost even if they were not the highest-volume retrievers.

# Write-Back To Patterns

When a query or family has proven outcome value, append a pattern entry to `state/patterns.jsonl`.
Make the write-back explicit enough that `gene-query.md` can use it later.

Good write-back content includes:

- the winning query text
- its aggregate outcome score
- the kind of value it produced
- any transferable pattern behind it

# Boosting Rules

Boost high-outcome queries in future generations.
Boost the underlying pattern when it generalizes beyond one exact string.
Do not boost queries that merely produced clicks, duplicates, or low-value intakes with no downstream use.

# Failure Modes

The main failure is missing provenance.
If `source_query` is blank, future learning degrades sharply.
When provenance is partial, reconstruct it while the session context is still fresh.

# Quality Bar

Search quality should be judged by what gets used, not just what gets found.
This skill turns real adoption into a durable query advantage.
