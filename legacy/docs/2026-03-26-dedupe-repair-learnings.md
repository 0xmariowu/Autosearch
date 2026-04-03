# Dedupe Repair Learnings

## Summary

This document records what the `dedupe_quality` debugging work established, what fixes were real, and what assumptions turned out to be incomplete.

## Main Lessons

### 1. `dedupe_quality` was not just a search-vocabulary problem

The first visible symptom was a score drop from `20` to `10`, but the actual failure was a control-loop problem:

- the weakest dimension was correctly identified as `dedupe_quality`
- the runtime still emitted pair- and validation-flavored repair queries
- the resulting runs gathered little or no dedupe evidence

So the score drop was downstream of branch/query misalignment, not only downstream of missing dedupe terms.

### 2. Low-score repair systems must distinguish "open" from merely "low-ranked"

`_weak_dimensions(...)` originally fell back to the lowest few dimension scores even when some of those dimensions were already at full weight.

That is a bad invariant for long-running repair loops:

- a closed dimension can still be among the numerically lowest scores
- once it re-enters the focus set, it pollutes the repair pack
- then specialized repair no longer means "repair the weakest open dimension"

The fix was to prioritize materially open dimensions first and only use lowest-score fallback when nothing open remains.

### 3. Stagnation signals cannot override current truth

`plateau_state.dimension_stagnation` is useful, but stale dimensions should not be allowed to re-enter repair once their current score is already full.

This was one of the key hidden loops:

- old stagnant `validation_release` / `pair_extract` state remained in program memory
- runtime repair focus kept dragging those dimensions forward
- `dedupe_quality` never got a clean isolated repair pass

Practical rule:

- stagnation is only meaningful for dimensions that are still open right now

### 4. Context should enrich wording, not decide dimension family

The important design distinction is:

- context can provide better phrasing
- context must not decide whether a dimension is pair-like, validation-like, or dedupe-like

Before the fix, `context_notes` could cause:

- `validation_release` to look pair-like because of `trajectory`, `same benchmark instance`
- `extraction_completeness` to look validation-like because of `validation should run after extraction`

That was the wrong abstraction boundary.

After the fix:

- family detection uses dimension-local signals
- context only adds extra phrases after the family is already decided

### 5. Historical query reuse is dangerous unless normalized at the boundary

One of the most important findings from this pass:

- even if fresh `GoalSearcher.candidate_plans(...)` output is clean
- historical `active_program.query_templates` and `dimension_strategies` can still reintroduce polluted queries

That means any long-running search product with replay/archive behavior needs boundary normalization when rehydrating strategy state.

Otherwise, old mistakes keep surviving after the generation logic has already been fixed.

### 6. Unit-level fixes do not prove runtime-level correctness

This was the most important execution lesson.

We reached a point where:

- direct editor probes were clean
- focused tests were green
- full test suite was green

but real `run_goal_case(...)` artifacts still emitted polluted plans.

So there are two separate truths:

- the editor module is cleaner
- the runtime path that actually produces round artifacts is still reusing old branch/program state somewhere else

For this repo, real run artifacts remain the final source of truth for bottleneck analysis.

## What Fixes Were Real

These fixes are real and test-backed:

- open-vs-closed dimension focus handling
- ignoring closed stagnant dimensions
- filtering relevant context more aggressively
- keeping context out of family classification
- filtering historical query templates and dimension strategies through dimension alignment

These changes improved the editor layer and made its direct outputs defensible.

## What Did Not Solve The End-to-End Problem

These were useful but not sufficient:

- adding more dedupe vocabulary alone
- cleaning only `specialized-repair`
- cleaning only `context-followup`
- filtering only fresh query generation

Why not:

- real runs still produced old polluted plans
- therefore the remaining defect is in runtime reuse/selection, not only in query wording

## Current Best Hypothesis

The next real bottleneck is in one of these runtime paths:

- accepted-program replay
- archive candidate promotion
- population snapshot reuse
- branch candidate selection before clean editor output becomes the chosen round plan

Until that runtime layer is cleaned, `dedupe_quality` will likely remain pinned even if the editor keeps improving.

## Practical Guidance For Future Work

1. When a real run disagrees with a direct module probe, trust the real run.
2. Add loop-level regressions, not only editor-level regressions.
3. Treat historical planning state as untrusted input that must be normalized on load.
4. Separate:
   - query generation bugs
   - runtime replay bugs
   - evidence acquisition bugs
   - judge scoring bugs
5. Do not assume a dimension score plateau means the current weakest-dimension query logic is still the culprit.

## Current Status Snapshot

As of the latest verified state:

- direct editor probes produce dedupe-focused repair plans
- test suite is green
- real `atoms-auto-mining-perfect` runs still stop at:
  - `score = 85`
  - `dedupe_quality = 10`
  - `pair_extract = 20`

So the next stage of debugging should move one layer lower than `goal_editor.py`.
