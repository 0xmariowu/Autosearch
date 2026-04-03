# Pair Extract Repair Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Raise the `pair_extract` dimension from the current token-hit floor to a real evidence-backed score by keeping low-confidence hits open, forcing repair queries to stay on-dimension, and teaching the judge to recognize public pair-trajectory vocabulary.

**Architecture:** Keep the current goal loop, deep runtime, and public API shape. Fix the failure as a control-loop problem: first stop the system from marking `pair_extract` as done at score `5`, then force planner/editor repair branches to remain bound to the target dimension, then widen the judge/goal-case vocabulary so public evidence about paired success/failure trajectories on the same benchmark instance actually counts.

**Tech Stack:** Python 3, `unittest`, existing `goal_editor.py`, `goal_bundle_loop.py`, `research/planner.py`, `research/synthesizer.py`, `goal_judge.py`, `goal_cases/atoms-auto-mining-perfect.json`.

---

## Scope

This plan addresses the specific failure visible in:

- `goal_cases/runs/2026-03-26-101552-atoms-auto-mining-perfect-bundle.json`

Observed failure pattern:

1. `pair_extract` scores only `5/20`.
2. The score comes from a weak lexical hit (`"SWE-bench"`) rather than same-instance paired-trajectory evidence.
3. `gap_queue` still marks `pair_extract` as `satisfied`.
4. Later repair rounds target `pair_extract` in metadata but generate off-dimension queries like validation or generic internal phrasing.
5. Bundle evidence is dominated by dataset-card style summaries instead of implementation-grade or trace-grade pairing evidence.

Out of scope for this pass:

- new providers
- UI changes
- broad benchmark tuning unrelated to `pair_extract`
- changing OpenRouter behavior

## Task 1: Lock The Pair-Extract Failure Into Regression Tests

**Files:**
- Modify: `tests/test_goal_bundle_loop.py`
- Modify: `tests/test_goal_judge.py`
- Modify: `tests/test_goal_editor.py`

**Step 1: Add a regression test for low-score dimensions staying open**

- Build a focused `run_goal_bundle_loop(...)` fixture where:
  - `pair_extract` scores `5`
  - `missing_dimensions` is empty
  - `gap_queue` currently marks it satisfied
- Assert the new behavior keeps `pair_extract` open when the score is below a configurable repair threshold.

**Step 2: Add a regression test for editor repair staying on-dimension**

- In `tests/test_goal_editor.py`, create a case where the selected weak dimension is `pair_extract`.
- Assert `dimension_repair-specialized-repair` and `dimension_repair-context-followup` emit queries containing pair-trajectory concepts instead of drifting to validation-only terms.

**Step 3: Add a regression test for pair-extract public vocabulary**

- In `tests/test_goal_judge.py`, use evidence with terms like:
  - `issue-pull request pair`
  - `resolved and unresolved subsets`
  - `successful and failed runs on the same task`
  - `verified trajectories`
- Assert `pair_extract` scores above the token-floor and is not satisfied only by a lone `SWE-bench` mention.

**Step 4: Run focused tests**

Run:

```bash
python3 -B -m unittest tests.test_goal_bundle_loop tests.test_goal_editor tests.test_goal_judge -v
```

Expected:

- new tests fail before code changes
- unrelated tests stay green

**Step 5: Commit**

```bash
git add tests/test_goal_bundle_loop.py tests/test_goal_editor.py tests/test_goal_judge.py
git commit -m "test: lock in pair extract regressions"
```

## Task 2: Keep Low-Confidence Pair-Extract Hits Open

**Files:**
- Modify: `goal_bundle_loop.py`
- Modify: `research/synthesizer.py`
- Test: `tests/test_goal_bundle_loop.py`

**Step 1: Introduce a weak-dimension repair threshold**

- Add a helper that decides whether a dimension is:
  - `missing`
  - `weak but hit`
  - `satisfied`
- Use the dimension weight to compute a minimum close threshold.
- For this pass, use a conservative rule like:
  - if score is less than half the dimension weight, keep it open

**Step 2: Rebuild top-level gap state from score strength, not just missing list**

- In `goal_bundle_loop.py`, when producing `gap_queue`, keep `pair_extract` open if its score is below threshold even when `matched_dimensions` contains it.
- Preserve existing `gap_id` and priority shape to avoid API churn.

**Step 3: Ensure repair targets are derived from weak-open dimensions**

- When later rounds choose `branch_targets`, prefer dimensions that are still open by threshold, not dimensions that merely disappeared from `missing_dimensions`.

**Step 4: Run focused tests**

Run:

```bash
python3 -B -m unittest tests.test_goal_bundle_loop -v
```

Expected:

- pair-extract weak-hit test passes
- existing goal bundle loop tests still pass

**Step 5: Commit**

```bash
git add goal_bundle_loop.py research/synthesizer.py tests/test_goal_bundle_loop.py
git commit -m "fix: keep weak pair extract hits open for repair"
```

## Task 3: Bind Repair Queries To The Target Dimension

**Files:**
- Modify: `goal_editor.py`
- Modify: `research/planner.py`
- Test: `tests/test_goal_editor.py`
- Test: `tests/test_research_flow.py`

**Step 1: Add dimension-specific pair-extract query builders**

- In `goal_editor.py`, create a focused helper for `pair_extract` that emits public-facing query shapes such as:
  - `same task successful and failed runs swe-bench`
  - `resolved unresolved subset same benchmark instance`
  - `issue pull request pairs same task swe-bench`
  - `verified trajectories successful failed runs`

**Step 2: Prevent context drift when a target dimension is explicitly selected**

- When `current_role == "dimension_repair"` and the weak focus is `pair_extract`, do not allow context-only validation terms to dominate the selected queries.
- Keep at least 75% of emitted repair queries anchored to pair-extract phrases.

**Step 3: Carry dimension intent into planner follow-ups**

- In `research/planner.py`, when `branch_targets` contains `pair_extract`, generate follow-up and decomposition templates using pair-trajectory vocabulary instead of generic `repository source` / `release blocker`.
- Keep acquisition and strong evidence preferences on, but do not change branch counts or ranking policy.

**Step 4: Run focused tests**

Run:

```bash
python3 -B -m unittest tests.test_goal_editor tests.test_research_flow -v
```

Expected:

- editor pair-extract drift test passes
- planner follow-up tests still pass

**Step 5: Commit**

```bash
git add goal_editor.py research/planner.py tests/test_goal_editor.py tests/test_research_flow.py
git commit -m "fix: keep pair extract repair queries on-dimension"
```

## Task 4: Teach The Judge Public Pair-Trajectory Vocabulary

**Files:**
- Modify: `goal_judge.py`
- Modify: `goal_cases/atoms-auto-mining-perfect.json`
- Test: `tests/test_goal_judge.py`

**Step 1: Add additive aliases for pair-extract**

- Extend the `pair_extract` dimension in `goal_cases/atoms-auto-mining-perfect.json` with additive public vocabulary such as:
  - `issue pull request pair`
  - `successful and failed runs`
  - `same task`
  - `same benchmark instance`
  - `resolved unresolved subset`
  - `verified trajectories`

**Step 2: Keep goal-case aliases data-driven**

- Do not hardcode `pair_extract`-specific strings only inside `goal_judge.py`.
- Reuse generic scoring hooks so new dimension aliases remain configurable in JSON.

**Step 3: Add a weak-evidence ceiling**

- If evidence only hits one shallow anchor like `SWE-bench`, do not let that alone mark the dimension as fully satisfied.
- Require either:
  - multiple pair-extract concepts
  - or one pair concept plus stronger evidence type bonus

**Step 4: Run focused tests**

Run:

```bash
python3 -B -m unittest tests.test_goal_judge -v
```

Expected:

- pair-extract public-vocabulary test passes
- existing heuristic tests stay green

**Step 5: Commit**

```bash
git add goal_judge.py goal_cases/atoms-auto-mining-perfect.json tests/test_goal_judge.py
git commit -m "feat: score pair extract with public trajectory vocabulary"
```

## Task 5: Re-Run The Hard Goal And Inspect The New Ceiling

**Files:**
- Runtime artifact only: `goal_cases/runs/*.json`

**Step 1: Run the focused hard-goal check**

Run:

```bash
python3 - <<'PY'
import sys, json
from pathlib import Path
repo = Path('/Users/dev/Projects/autosearch')
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
print(json.dumps({
    'score': (result.get('bundle_final') or {}).get('score'),
    'pair_extract': ((result.get('bundle_final') or {}).get('dimension_scores') or {}).get('pair_extract'),
    'matched_dimensions': (result.get('bundle_final') or {}).get('matched_dimensions'),
    'missing_dimensions': (result.get('bundle_final') or {}).get('missing_dimensions'),
    'run_path': result.get('run_path'),
}, ensure_ascii=False, indent=2))
PY
```

Expected:

- `pair_extract` rises above `5`
- repair rounds stay on-dimension
- bundle includes stronger same-instance pairing evidence

**Step 2: Inspect the run artifact**

- Verify:
  - `gap_queue` does not close `pair_extract` prematurely
  - `query_runs` remain pair-focused after the first weak hit
  - accepted bundle contains more than a dataset-card mention

**Step 3: Run full regression suite**

Run:

```bash
python3 -B -m unittest discover -s tests -v
```

Expected:

- all tests pass

**Step 4: Commit**

```bash
git add goal_editor.py goal_bundle_loop.py research/planner.py research/synthesizer.py goal_judge.py goal_cases/atoms-auto-mining-perfect.json tests/test_goal_bundle_loop.py tests/test_goal_editor.py tests/test_research_flow.py tests/test_goal_judge.py
git commit -m "fix: repair pair extract scoring and query control loop"
```

## Success Criteria

- `pair_extract` is not considered done at score `5`
- repair branches targeting `pair_extract` emit pair-trajectory queries, not validation drift
- public pair-trajectory evidence scores materially above the token floor
- the next `atoms-auto-mining-perfect` deep run improves `pair_extract` over `5`
- full test suite remains green
