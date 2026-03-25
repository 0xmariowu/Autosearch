---
title: "AutoSearch Routeable Map Standard"
date: 2026-03-24
project: autosearch
type: standard
tags: [autosearch, routing, handoff, map, standard]
status: active
---

# AutoSearch Routeable Map Standard

> The final deliverable of search is not a findings dump.
>
> The final deliverable of the search side is a continuously refreshed
> **routeable map**:
> a narrow, explicit handoff that tells downstream workflows what is worth
> processing now, why, and where it likely belongs first.

---

## 1. Purpose

Search may produce many useful intermediate outputs:

- raw findings
- daily reports
- experiment logs
- candidate tables
- outcome history

But those are not the final search-side handoff.

The end goal is a derived view that answers:

- what is routeable now
- why it is routeable
- what the first downstream action should be
- where it should probably go first

If the search side cannot answer those questions, it has not finished its job.

---

## 2. Truth Model

The routeable map is a **derived view**, not an independent truth source.

Canonical input should remain:

- the content candidate truth table

Derived outputs may include:

- `routeable-map.jsonl`
- `routeable-map.md`
- `routeable-map.json`

Rules:

- never hand-edit the routeable map
- always regenerate it from candidates
- if candidate truth changes, the routeable map must refresh in the same cycle

---

## 3. What Counts as Routeable

A candidate is routeable only when all of the following are true:

- provenance is preserved
- a demand linkage exists or is narrowly inferred
- `destination_hint` is present
- `reason_to_keep` is present
- `processing_status` is ready for downstream action
- the next downstream step is actionable, not vague

This is intentionally stricter than "captured".

The candidate table answers:

- what is still under consideration

The routeable map answers:

- what should actually move next

Do not mix these two layers.

---

## 4. Required Routeable Fields

Every routeable row should carry:

- `candidate_id`
- `url`
- `title`
- `content_kind`
- `topic_group`
- `brief_id`
- `project_hint`
- `destination_hint`
- `route_status`
- `reason_to_keep`
- `why_routeable`
- `first_processing_action`
- `source`
- `source_query`
- `query_family`

Optional health-oriented fields:

- `urgency`
- `freshness_requirement`
- `provider_snapshot`

The purpose is simple:

- downstream routing should not need to reverse-engineer why this item is here

---

## 5. Meaning of Key Fields

### 5.1 `route_status`

Allowed values:

- `ready_for_routing`
- `already_routed`
- `ready_for_review`

Meanings:

- `ready_for_routing`
  downstream processing can start immediately

- `already_routed`
  a downstream workflow has already taken ownership

- `ready_for_review`
  routing intent is clear, but a human or stricter gate is still expected

### 5.2 `why_routeable`

Short explanation of why the candidate belongs in the routeable map now.

It should mention:

- demand linkage
- destination hint
- content type
- why this is worth spending downstream effort on

### 5.3 `first_processing_action`

Short description of the first practical downstream step.

Examples:

- `summarize article into AIMD note draft`
- `prepare Armory intake candidate with why-now context`
- `attach to project evidence folder and extract implementation takeaways`

This field exists so downstream handling can start immediately.

---

## 6. Required Outputs

The markdown map should show:

- total routeable candidate count
- count by `destination_hint`
- count by `route_status`
- top routeable items with concise reasons

The JSON map should expose the same information in machine-readable form.

The JSONL map should contain one row per routeable candidate.

This is the file a downstream routing or synthesis session should be able to consume directly.

---

## 7. Success Condition

The routeable map is operating correctly when a downstream session can open the
machine-readable map and answer immediately:

- what should be processed now
- why this item is active
- where it should probably go first
- what the first concrete action is

If that still requires reading raw search logs, the search-side handoff is incomplete.
