# AutoSearch Experience

This directory is the project-level memory home for AutoSearch.

It has two layers:

- human notes such as retrospectives and handoffs
- machine-readable runtime experience

## Canonical Layout

- `INDEX.jsonl`
  project-local index of experience assets
- `*.md`
  dated experience notes
- `latest-health.json`
  current machine-readable health summary for the runtime experience layer
- `library/experience-ledger.jsonl`
  append-only raw event stream
- `library/experience-index.json`
  regenerated aggregate index
- `library/experience-policy.json`
  regenerated runtime policy

## Role Separation

- `patterns.jsonl`, `evolution.jsonl`, `outcomes.jsonl`, `playbook-final.jsonl`
  domain data and experiment history
- `experience/library/*`
  current runtime experience layer

Runtime code should consume:

- `experience/library/experience-policy.json`

Runtime code should not directly consume raw ledger rows.
