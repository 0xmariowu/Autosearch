# Dedupe Repair Handoff

## Repo State

- Repo: `/Users/dev/Library/Mobile Documents/com~apple~CloudDocs/Dev/autosearch`
- Branch: `main`
- Worktree: dirty, many tracked modifications already in progress
- Do not touch:
  - `autosearch.py`
  - `goal_cases/benchmarks/`

## What Was Done

This pass focused on the `dedupe_quality` regression that appeared after the pair-structure work.

Implemented changes:

- `goal_editor.py`
  - `_weak_dimensions(...)` now prefers materially open dimensions before falling back to the lowest few scores.
  - `_repair_focus_dimensions(...)` now ignores stagnant dimensions that are already at full weight.
  - `_dimension_phrase_candidates(...)` now filters context through `_relevant_context_phrases(...)` instead of blindly absorbing all `context_notes`.
  - `_dimension_family_variants(...)` now uses only dimension-local terms for family detection; context can enrich phrases but does not decide whether a dimension is pair/validation/dedupe flavored.
  - `_active_query_templates(...)` and `_active_dimension_strategies(...)` now filter historical query templates/strategies through dimension alignment checks before reuse.
  - Added helper logic:
    - `_dimension_weight(...)`
    - `_dimension_signal_terms(...)`
    - `_query_matches_dimension(...)`
    - `_merge_dimension_queries(...)`

- `tests/test_goal_editor.py`
  - Added regressions for:
    - dedupe specialized repair staying on dedupe vocabulary
    - dedupe evidence-strengthening staying on dedupe vocabulary
    - historical misaligned dedupe queries being filtered
    - context notes not changing dimension family
    - repair focus ignoring closed stagnant dimensions

## Verified Results

Tests:

- `python3 -B -m unittest tests.test_goal_editor tests.test_research_flow tests.test_goal_judge tests.test_goal_bundle_loop -v`
- `python3 -B -m unittest discover -s tests -v`
- Result: `176 tests` passing

There are still transient Hugging Face DNS retry logs during tests, but the suite finishes green.

Direct editor probe:

- Calling `GoalSearcher(goal_case).candidate_plans(...)` directly for `atoms-auto-mining-perfect` with:
  - `extraction_completeness=15`
  - `label_separation=20`
  - `pair_extract=20`
  - `validation_release=20`
  - `dedupe_quality=10`
- now yields clean dedupe-focused plans such as:
  - `semantic deduplication implementation details`
  - `semantic deduplication and fake-Gold detection for near-duplicate code pairs`
  - `near duplicate detection and identical pair filtering`

## Latest Real Runs

Key runs:

- `goal_cases/runs/2026-03-26-104720-atoms-auto-mining-perfect-bundle.json`
  - score `85`
  - `pair_extract=20`
  - `dedupe_quality=10`

- `goal_cases/runs/2026-03-26-110241-atoms-auto-mining-perfect-bundle.json`
  - score `85`
  - `dedupe_quality=10`

- `goal_cases/runs/2026-03-26-110533-atoms-auto-mining-perfect-bundle.json`
  - score `85`
  - `dedupe_quality=10`

- `goal_cases/runs/2026-03-26-110836-atoms-auto-mining-perfect-bundle.json`
  - score `85`
  - `dedupe_quality=10`

All recent real runs still stop at:

- `extraction_completeness = 15`
- `label_separation = 20`
- `pair_extract = 20`
- `validation_release = 20`
- `dedupe_quality = 10`

## What Is Proven

These statements are now well-supported:

1. The editor layer itself is no longer the obvious source of dedupe pollution.
2. Context-driven family misclassification was real and is now covered by tests.
3. Historical `active_program` query reuse can reintroduce bad queries, and a normalization guard is now in place.
4. Closed but stagnant dimensions should not re-enter repair focus, and that is now enforced in tests and code.

## What Is Still Broken

Real `run_goal_case(...)` deep runs still show polluted round plans even though the direct `GoalSearcher` probe is clean.

In the latest real artifacts, round 2 to 4 still contain queries like:

- `validation release same benchmark instance successful and failed runs`
- `data validation implementation`
- `dedupe quality repository source`

This means the next bottleneck is below or around the runtime/archive reuse layer, not in the current pure editor call path.

## Most Likely Remaining Root Cause

The strongest current hypothesis is:

- `goal_bundle_loop.py` / `goal_runtime.py` / archive replay logic is still reusing historical branch state or program state in a way that bypasses the newly cleaned editor path.
- The runtime may be selecting or replaying older branch candidates whose query sets were generated before the new dedupe/editor cleanup.
- Because the real run artifacts still emit the old polluted query shapes, the next investigation should focus on:
  - accepted-program replay
  - archive candidate promotion
  - population snapshot reuse
  - branch candidate selection before `editor_plans` are serialized into the run artifact

## Recommended Next Steps

1. Inspect `goal_bundle_loop.py` around candidate selection, accepted-program replay, and archive promotion.
2. Inspect `goal_runtime.py` for any path that hydrates historical `query_templates`, `dimension_strategies`, `topic_frontier`, or planning state before the new editor normalization is applied.
3. Add a regression at the loop/runtime level:
   - when only `dedupe_quality` is open and `validation_release/pair_extract` are already full, real round plans must not emit pair/validation queries.
4. Only after the runtime reuse path is clean, re-evaluate whether `dedupe_quality=10` is still a query problem or has become a judge/evidence-strength problem.

## Commands Used

Focused tests:

```bash
python3 -B -m unittest tests.test_goal_editor tests.test_research_flow tests.test_goal_judge tests.test_goal_bundle_loop -v
```

Full suite:

```bash
python3 -B -m unittest discover -s tests -v
```

Real run:

```bash
python3 - <<'PY'
import sys, json
from pathlib import Path
repo = Path('/Users/dev/Library/Mobile Documents/com~apple~CloudDocs/Dev/autosearch')
sys.path.insert(0, str(repo))
from interface import AutoSearchInterface
client = AutoSearchInterface(repo)
result = client.run_goal_case(
    'atoms-auto-mining-perfect',
    mode='deep',
    max_rounds=4,
    plan_count=4,
    max_queries=4,
    target_score=90,
    plateau_rounds=2,
    persist_run=True,
)
bundle = result.get('bundle_final') or {}
print(json.dumps({
    'score': bundle.get('score'),
    'dimension_scores': bundle.get('dimension_scores'),
    'run_path': result.get('run_path'),
}, ensure_ascii=False, indent=2))
PY
```
