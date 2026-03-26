# Dedupe Quality Repair Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Restore `dedupe_quality` from the current degraded `10/20` back to stable high-confidence scoring by preventing dimension contamination, keeping repair focus on still-open dimensions, prioritizing dedupe-specific search templates, and keeping dedupe evidence in the accepted bundle.

**Architecture:** Keep the current goal loop and public API unchanged. Repair the failure as a query-selection and evidence-retention bug: first lock the regression in tests, then stop global context from polluting dedupe specialization, then make the editor prefer explicit dedupe templates over synthetic fallback text, and finally verify the hard goal with a fresh deep run.

**Tech Stack:** Python 3, `unittest`, existing `goal_editor.py`, `research/planner.py`, `goal_bundle_loop.py`, `goal_cases/atoms-auto-mining-perfect.json`.

---

## Scope

This plan addresses the regression visible between:

- `goal_cases/runs/2026-03-26-103247-atoms-auto-mining-perfect-bundle.json`
- `goal_cases/runs/2026-03-26-104720-atoms-auto-mining-perfect-bundle.json`

Observed failure pattern:

1. `dedupe_quality` dropped from `20` to `10`.
2. Warm-start replay did not recover previous dedupe findings.
3. `branch_targets` correctly point at `dedupe_quality`, but the selected repair plans still mix in `pair_extract` queries.
4. The root mechanism is not only context pollution. `_weak_dimensions(...)` falls back to the lowest `N` dimensions even when the secondary dimensions are already at full weight, so `pair_extract=20` still gets dragged into the repair pack with `dedupe_quality=10`.
5. When the system finally emits dedupe follow-ups, they degrade to generic internal phrases like `dedupe quality repository source`, which return zero findings.

Out of scope for this pass:

- redesigning warm-start replay
- adding new providers
- changing judge semantics for non-dedupe dimensions
- broad planner refactors unrelated to weak-dimension query binding

## Task 1: Lock The Dedupe Regression Into Tests

**Files:**
- Modify: `tests/test_goal_editor.py`
- Modify: `tests/test_research_flow.py`

**Step 1: Add a regression for dedupe specialized repair staying on-dimension**

Create a goal case that includes:

- context notes mentioning pair, validation, and dedupe concepts
- explicit `dimension_queries["dedupe_quality"]`
- a low `dedupe_quality` score

Assert the `dimension_repair-specialized-repair` plan:

- contains dedupe terms like `semantic deduplication`, `semhash`, `near duplicate`
- does not contain pair phrases like `same benchmark instance`
- does not switch to validation phrases like `validation release`

**Step 2: Add a regression for planner follow-up not degrading dedupe to internal jargon**

If the weakest dimension is `dedupe_quality`, assert recursive follow-up plans do not emit bare internal strings like:

- `dedupe quality repository source`
- `dedupe quality release blocker`

and instead stay anchored to public dedupe vocabulary.

**Step 3: Run focused tests**

Run:

```bash
python3 -B -m unittest tests.test_goal_editor tests.test_research_flow -v
```

Expected:

- new tests fail before implementation
- existing pair and planner tests stay green

## Task 2: Keep Closed Dimensions Out Of Repair Focus

**Files:**
- Modify: `goal_editor.py`
- Test: `tests/test_goal_editor.py`

**Step 1: Treat repair focus as "still open dimensions", not just "lowest few dimensions"**

Update `_weak_dimensions(...)` so it prefers dimensions whose score is still below that dimension's full weight.

Desired behavior:

- if a dimension is below its full weight, it remains eligible for repair
- if a dimension is already at full weight, it should not be pulled back into the repair focus just because it is one of the two lowest scores
- close-threshold logic can still prioritize more urgent dimensions, but closed dimensions should not backfill ahead of still-open ones

This is the core fix for the current regression:

- `dedupe_quality = 10/20` should stay open
- `pair_extract = 20/20` should stay closed
- specialized repair should not blend them together

**Step 2: Restrict context phrases to dimension-relevant overlap**

Update `_dimension_family_variants(...)` so global `context_notes` cannot inject pair tokens into unrelated dimensions like `dedupe_quality`.

Only context phrases that overlap with the current dimension’s own keywords / aliases / id terms should influence specialization.

**Step 3: Keep pair-specific behavior only for actual pair dimensions**

Ensure `has_pair_extract` is triggered by pair-local phrases, not by unrelated global context.

**Step 4: Run focused tests**

Run:

```bash
python3 -B -m unittest tests.test_goal_editor -v
```

Expected:

- dedupe specialized plan no longer emits pair or validation phrases
- fully scored dimensions are not mixed back into dedupe specialization

## Task 3: Prefer Explicit Dedupe Templates Over Synthetic Fallbacks

**Files:**
- Modify: `goal_editor.py`
- Test: `tests/test_goal_editor.py`

**Step 1: Seed specialized repair from current dimension strategies/templates**

When a weak dimension has explicit configured queries in `dimension_queries` / `query_templates`, use those first for `specialized-repair`.

For `dedupe_quality`, this should surface the existing strong templates:

- `semantic deduplication and fake-Gold detection for near-duplicate code pairs`
- `near duplicate detection and identical pair filtering`
- `text dedup and semantic hashing for near duplicate datasets`

**Step 2: Keep synthetic generation only as backfill within the same active repair dimension**

Generated phrases should fill gaps only after explicit configured templates are exhausted, and only for the same still-open repair dimension.

Do not use a half-full dedupe specialized plan as permission to backfill with pair queries from another dimension.

**Step 3: Run focused tests**

Run:

```bash
python3 -B -m unittest tests.test_goal_editor -v
```

Expected:

- dedupe specialized repair now uses explicit semhash/dedup queries first
- if only `dedupe_quality` is still open, the specialized plan should contain only dedupe queries

## Task 4: Improve Dedupe Follow-Up Vocabulary

**Files:**
- Modify: `research/planner.py`
- Test: `tests/test_research_flow.py`

**Step 1: Add dedupe-specific recursive follow-up templates**

When the weakest dimension is dedupe-related, follow-up and decomposition queries should use public terms such as:

- `semantic deduplication`
- `semantic hashing`
- `near duplicate detection`
- `duplicate detection`
- `fake gold`

instead of internal phrases like `dedupe quality repository source`.

**Step 2: Keep branch behavior stable**

Do not change branch counts, only the query wording and selection quality.

**Step 3: Run focused tests**

Run:

```bash
python3 -B -m unittest tests.test_research_flow -v
```

Expected:

- dedupe follow-up tests pass
- pair-specific follow-up tests remain green

## Task 5: Verify The Hard Goal Again

**Files:**
- Runtime artifact only: `goal_cases/runs/*.json`

**Step 1: Run the hard goal**

Run:

```bash
python3 - <<'PY'
import sys, json
from pathlib import Path
repo = Path('/Users/vimala/Library/Mobile Documents/com~apple~CloudDocs/Dev/autosearch')
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
    'matched_dimensions': bundle.get('matched_dimensions'),
    'run_path': result.get('run_path'),
}, ensure_ascii=False, indent=2))
PY
```

**Step 2: Inspect success criteria**

Verify:

- `dedupe_quality` rises above `10`
- specialized repair queries are dedupe-specific
- final sample retains at least one strong dedupe artifact
- total score recovers toward or above the previous `89`

**Step 3: Run the full suite**

Run:

```bash
python3 -B -m unittest discover -s tests -v
```

Expected:

- full suite green
- no regressions in pair_extract or deep runtime
