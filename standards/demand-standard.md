---
title: "AutoSearch Demand Standard"
date: 2026-03-24
project: autosearch
type: standard
tags: [autosearch, demand, global-needs, briefs, standard]
status: active
---

# AutoSearch Demand Standard

> AutoSearch should not search only because a daily timer fired.
>
> It should search because the system can state what is needed now, for whom,
> and why the search matters.

---

## 1. Scope

This standard defines:

- how global demand is assembled before search
- which upstream systems contribute demand signals
- what the canonical search brief should contain
- what AutoSearch is allowed to infer vs what it must preserve

This standard does **not** define:

- provider scheduling rules
- search methodology details
- final content admission into Armory, AIMD, or project knowledge stores

Those belong to:

- `standards/search-standard.md`
- `docs/methodology/`
- a future admission standard

---

## 2. Purpose

AutoSearch is the perception layer for the larger system.

Its job is not only:

- find interesting URLs

Its job is:

- identify the most relevant external evidence for current system needs

If AutoSearch cannot explain:

- what need a search run serves
- which project or knowledge layer it serves
- why that need is active now

then the run is incomplete at the demand layer.

---

## 3. Demand Inputs

Global demand should be assembled from three upstream signal classes:

### 3.1 Project Demand

Examples:

- active projects under `Dev/Projects/`
- open design questions
- evidence gaps in current implementation work
- recurring unresolved TODO themes

### 3.2 Armory Gap Demand

Examples:

- weak topic coverage in `armory-index.json`
- sparse or stale `when-blocks.jsonl` coverage
- freshness gaps for fast-moving topics
- missing evidence for a known decision area

### 3.3 AIMD Demand

Examples:

- current recommendation queues
- repeated themes in experience notes
- open synthesis threads
- recent reports indicating a missing external evidence source

These inputs are upstream demand signals.
They are not themselves search briefs.

---

## 4. Demand Truth Model

AutoSearch should distinguish:

### 4.1 Input Truth

Upstream truth remains in the source systems:

- project files
- Armory indexes
- AIMD records

AutoSearch must not copy and redefine those truth sources.

### 4.2 Derived Demand View

AutoSearch may derive:

- `demand briefs`
- `priority bands`
- `topic_group` mappings
- `destination hints`

These are search-side working views.
They should be regenerated from upstream signals, not hand-edited as canonical knowledge.

---

## 5. Canonical Handoff Object

The output of demand assembly should be a narrow **search brief**.

A brief should answer:

- what we need
- for whom
- how urgent it is
- what kind of evidence is preferred
- where the result is likely to go next

Minimum brief fields:

- `brief_id`
- `project`
- `topic_group`
- `need_type`
- `urgency`
- `freshness_requirement`
- `destination_hint`
- `why_now`
- `source_signals`

Suggested `need_type` examples:

- `repo`
- `article`
- `discussion`
- `benchmark`
- `method`
- `comparison`

The point of the brief is simple:

- search should not have to reverse-engineer demand from raw project state

---

## 6. Inference Rules

AutoSearch may infer:

- topic grouping
- urgency bands
- preferred evidence types
- likely destination hints

AutoSearch should not silently invent:

- fake project ownership
- fake evidence gaps
- fake downstream destinations

When uncertain:

- preserve source signals
- mark the brief narrower, not broader
- keep unknowns explicit

---

## 7. Operational Contract

Before a substantial search run:

1. read current demand inputs
2. derive briefs
3. schedule search from briefs, not from timer alone

The demand layer is operating correctly when a downstream search run can answer:

- what problem am I searching for
- which topic group does it belong to
- what kind of result is most useful
- where should a good hit probably go next

If the search run still depends on a human remembering those answers from chat,
the demand layer is not complete.
