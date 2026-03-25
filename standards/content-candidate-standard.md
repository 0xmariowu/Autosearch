---
title: "AutoSearch Content Candidate Standard"
date: 2026-03-24
project: autosearch
type: standard
tags: [autosearch, candidates, routing, content, standard]
status: active
---

# AutoSearch Content Candidate Standard

> AutoSearch needs a stable layer between:
>
> - "a URL was found"
> - "this should probably go somewhere"
> - "this is now canonical knowledge"
>
> This standard defines that middle layer.

---

## 1. Purpose

Raw findings are too noisy to act as long-lived knowledge candidates.

Canonical admission is too strict to happen at search time.

Therefore AutoSearch needs a candidate layer that:

- preserves provenance
- stores routing-relevant metadata
- remains upstream of final admission

If a system only has raw findings and final admission, it has no stable place
to accumulate search results that are promising but not yet accepted.

---

## 2. Scope

This standard defines:

- what a content candidate is
- what the candidate truth table should represent
- which lifecycle states belong to candidates
- what metadata must survive before final admission

This standard does **not** define:

- final Armory admission
- final AIMD admission
- project-local ingestion rules
- final content transformation rules

Those should be defined later by a stricter admission standard.

---

## 3. Candidate Truth Model

The candidate layer should have one canonical current table.

It should answer:

- which findings are still worth considering
- what they are for
- where they probably belong
- what step should happen next

This table is the candidate truth source.

Derived views may exist for:

- routeable-now subsets
- destination-specific slices
- health summaries

But those should be regenerated from the canonical candidate table.

---

## 4. What Counts as a Content Candidate

A content candidate is a search result that has enough structure to survive
past the current run.

Minimum conditions:

- stable URL or durable source reference exists
- basic title or identifier exists
- source provenance exists
- demand linkage exists or can be inferred narrowly
- routing metadata is present enough for a next action

A finding without provenance may still be logged as a raw artifact, but it is
not yet a strong candidate.

---

## 5. Required Candidate Fields

Every candidate row should carry:

- `candidate_id`
- `url`
- `title`
- `content_kind`
- `source`
- `source_query`
- `query_family`
- `topic_group`
- `brief_id`
- `project_hint`
- `destination_hint`
- `reason_to_keep`
- `processing_status`
- `collected_at`
- `last_updated_at`

Optional but useful fields:

- `engagement`
- `created`
- `provider_status_snapshot`
- `outcome_linkage_status`

The purpose is simple:

- later systems should not need to reverse-engineer why the result still exists

---

## 6. Candidate Status Rules

Candidate status should stay narrow and operational.

Suggested `processing_status` values:

- `captured`
- `enriched`
- `routeable`
- `routed`
- `archived`

Meanings:

- `captured`
  found and preserved, but not yet enriched enough for routing

- `enriched`
  provenance and destination hints are attached

- `routeable`
  enough structure exists for downstream handoff

- `routed`
  handed to a downstream destination-specific workflow

- `archived`
  intentionally retained as history, but not active for routing

These are candidate-layer states only.
They must not be overloaded as final knowledge-base admission states.

---

## 7. Relationship to Final Admission

The candidate table is upstream of admission.

Expected flow:

1. search finds result
2. result becomes candidate
3. candidate is enriched with demand and destination context
4. candidate becomes routeable
5. downstream admission workflow decides whether it becomes canonical knowledge

If a row becomes canonical knowledge without passing through candidate truth,
the AutoSearch routing layer is bypassed.

---

## 8. Success Condition

The candidate layer is operating correctly when a downstream session can inspect
the candidate table and answer:

- why are we keeping this
- which need did it serve
- where should it probably go
- what is the next processing step

without reopening search logs or guessing from memory.
