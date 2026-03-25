---
title: "AutoSearch Experience Standard"
date: 2026-03-24
project: autosearch
type: standard
tags: [autosearch, experience, search, routing, policy, standard]
status: active
---

# AutoSearch Experience Standard

> How project-level experience is stored, indexed, and reused.
>
> This standard exists to prevent search, routing, and downstream preparation
> from each inventing their own long-lived memory store.

---

## 1. Scope

AutoSearch experience has two forms:

- **human-readable notes**
- **machine-readable experience library**

Both live under `experience/`.

This keeps project memory in one place instead of scattering it across:

- run output directories
- temporary search artifacts
- chat history
- AIMD-only notes

---

## 2. Canonical Layout

Paths:

- `experience/INDEX.jsonl`
- `experience/*.md`
- `experience/library/experience-ledger.jsonl`
- `experience/library/experience-index.json`
- `experience/library/experience-policy.json`

Meanings:

- `experience/*.md`
  session notes, retrospectives, lessons, and handoff documents

- `experience/INDEX.jsonl`
  project-local index of experience notes and key experience assets

- `experience/library/experience-ledger.jsonl`
  append-only machine event stream

- `experience/library/experience-index.json`
  current aggregated execution index, regenerated from the ledger

- `experience/library/experience-policy.json`
  current reusable policy derived from the index

---

## 3. Relationship to Existing Search History

AutoSearch already has durable historical materials:

- `patterns.jsonl`
- `evolution.jsonl`
- `outcomes.jsonl`
- `playbook-final.jsonl`

These should remain.

Their role is:

- domain memory
- experiment history
- query and outcome evidence

They are **not** the runtime experience layer.

The runtime experience layer is:

- ledger
- index
- policy

This separation keeps history rich and runtime guidance simple.

---

## 4. Rules

### 4.1 One Project, One Experience Home

Reusable AutoSearch experience must live under this project's `experience/` directory.

Do not create parallel long-lived experience stores in:

- `/tmp`
- ad hoc run folders
- provider-specific scratch files
- downstream destination folders

Subsystems may emit operational logs elsewhere, but reusable experience should
roll up into `experience/`.

### 4.2 Human Notes Are Append-Only

Experience notes:

- are written as dated markdown files
- record lessons, mistakes, decisions, and reusable heuristics
- should not be silently overwritten

### 4.3 Machine Experience Is Derived and Reusable

Machine experience should:

- append raw events to `experience-ledger.jsonl`
- regenerate `experience-index.json`
- regenerate `experience-policy.json`
- organize guidance by `aspect`

Current supported aspect:

- `search`

Expected future aspects:

- `routing`
- `admission-prep`

### 4.4 AIMD Is an Index, Not the Home

Project experience notes live here first.

`AIMD/experience/INDEX.jsonl` should only receive a pointer entry, not the full
note or private machine state.

---

## 5. Simple Guidance Model

Experience should stay intentionally simple.

For search, machine experience should answer only:

- what happened
- what status each provider is in
- what simple provider guidance follows for a query family

### 5.1 Three Allowed Statuses

Search guidance should use only:

- `preferred`
- `active`
- `cooldown`

Meaning:

- `preferred`
  move earlier in scheduling

- `active`
  run normally

- `cooldown`
  skip for now

### 5.2 Minimum Sample Rule

Do not promote a provider to `preferred` on tiny evidence.

Promotion requires:

- a recent sample window
- enough recent attempts
- strong enough new-value rate

If the sample count is too small, keep it `active`.

### 5.3 Error Signals Are Negative-Only

Signals like:

- `*_error`
- `*_unavailable`

may trigger:

- degradation
- cooldown
- observability

They must never become preferred playbook entries.

---

## 6. Runtime Consumption Rule

Runtime code should consume:

- `experience-policy.json`

Runtime code should not directly consume:

- raw ledger rows
- `patterns.jsonl`
- `evolution.jsonl`
- `outcomes.jsonl`

Those files may help build the policy, but they should not become implicit runtime state.

---

## 7. Query Family Contract

Search experience may maintain simple query-family playbooks.

For AutoSearch this should stay narrow:

- `preferred_providers`
- `cooldown_providers`

Do not expand this into:

- admission logic
- complex family state machines
- content routing rules

The experience layer is for runtime guidance, not whole-system governance.

---

## 8. Operational Contract

When AutoSearch gains durable experience logic:

1. keep raw operational artifacts in the subsystem working area
2. write reusable machine experience under `experience/library/`
3. write at least one human note when the mechanism changes materially

The experience layer is operating correctly when later runs can reuse guidance
without parsing markdown or replaying raw search history.
