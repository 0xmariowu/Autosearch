---
title: "AutoSearch Search Standard"
date: 2026-03-24
project: autosearch
type: standard
tags: [autosearch, search, runtime, discovery, standard]
status: active
---

# AutoSearch Search Standard

> Search is the execution layer of AutoSearch.
>
> It consumes briefs, queries providers, records outcomes, and produces
> candidate findings.
>
> Search does **not** decide final knowledge admission.

---

## 1. Scope Boundary

Search is responsible for:

- consuming demand briefs
- generating and selecting queries
- executing provider searches
- collecting raw findings
- preserving provenance such as provider, query, and query family
- applying lightweight runtime guidance from experience policy

Search is **not** responsible for:

- deciding final destination admission
- rewriting the system's demand model
- replacing Armory or AIMD truth sources
- performing final synthesis or full content processing

If a workflow is deciding whether a result becomes canonical knowledge, it is
already beyond the search layer.

---

## 2. Search Inputs

Search should consume:

- demand briefs
- search methodology and platform playbooks
- source capability report
- runtime experience policy
- existing dedupe state and historical outcomes where relevant

Search should not depend on:

- raw chat memory
- hidden session assumptions
- ad hoc per-run logic that is not captured in code or policy

---

## 3. Search Truth Layers

Search should keep three kinds of outputs separate:

### 3.1 Raw Run Artifacts

Examples:

- per-run findings JSONL
- session docs
- experiment logs

These are operational outputs and evidence artifacts.

### 3.2 Search History

Examples:

- `patterns.jsonl`
- `evolution.jsonl`
- `outcomes.jsonl`
- `playbook-final.jsonl`

These remain historical materials, experiments, and domain memory.

### 3.3 Runtime Experience

Examples:

- `experience/library/experience-ledger.jsonl`
- `experience/library/experience-index.json`
- `experience/library/experience-policy.json`

This is the reusable runtime guidance layer.

Search should consume the derived policy, not parse raw events directly.

### 3.4 Source Capability

Examples:

- `sources/catalog.json`
- `sources/latest-capability.json`

This is the static environment and configuration layer.

It answers:

- which sources exist
- which are runtime providers
- which are currently available

This is different from runtime experience:

- capability = can we use it
- experience = should we prefer it

---

## 4. Required Provenance

Every harvested finding should preserve enough provenance for later routing and
feedback.

Minimum fields:

- `url`
- `title`
- `source`
- `query`
- `query_family`
- `topic_group`
- `brief_id` when available
- `collected`

If exact query text cannot be preserved, search should still preserve:

- `query_family`
- `topic_group`

Losing both breaks the feedback chain.

---

## 5. Runtime Guidance Rules

Search runtime guidance should stay intentionally light.

Experience may affect only:

- provider ordering
- cooldown skipping
- light query-family provider preference

Static capability may affect only:

- pre-run observability
- provider skipping when a source is unavailable
- light ordering degradation for warned providers

Experience must not directly rewrite:

- demand briefs
- target intent
- query text generation logic

This keeps the search layer adaptive without turning it into an opaque policy engine.

---

## 6. Error Accounting

Search must distinguish:

- empty result sets
- execution failures
- provider availability or auth failures

These are not the same signal.

If execution errors are collapsed into "no results", the experience layer will
cool down the wrong providers.

Error aliases may be stored for observability and negative policy signals, but
runtime scheduling should still operate on canonical provider identities.

---

## 7. Search Deliverable

The direct output of search is not canonical knowledge.

The direct output of search is:

- candidate findings with preserved provenance
- enough structure for downstream routing preparation

Search is operating correctly when a downstream routing step can answer:

- what did we find
- why was it found
- which need did it serve
- which provider and query family produced it

without re-reading raw logs or reconstructing session context by hand.
