# Pair Extract Structural Evidence Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Raise `pair_extract` from partial lexical hits to stable high-confidence scoring by introducing structure-aware evidence extraction, scoring, and sampling for same-instance success/failure trajectory claims.

**Architecture:** Keep the current deep runtime, planner, synthesizer, and public API shape intact. Add a narrow vertical slice for `pair_extract`: first codify the missing structure in tests, then add a pair-specific claim model in the judge, then preserve pair-strong evidence through sampling and selection, and finally teach planner/editor to repair against the missing pair sub-claims rather than against the flat dimension id.

**Tech Stack:** Python 3, `unittest`, existing `goal_judge.py`, `goal_bundle_loop.py`, `goal_editor.py`, `research/planner.py`, `research/synthesizer.py`, `goal_cases/atoms-auto-mining-perfect.json`.

---

## Scope

This plan addresses the current ceiling visible in:

- `goal_cases/runs/2026-03-26-103247-atoms-auto-mining-perfect-bundle.json`

Observed failure pattern:

1. `pair_extract` improved from `5` to `14`, so low-score reopen + public query vocabulary helped.
2. The remaining gap is structural, not architectural.
3. The current judge still scores `pair_extract` as flat keyword coverage.
4. The final bundle sample under-represents pair-strong evidence and over-represents shallow benchmark/trajectory mentions.
5. New pair-specific repair queries still do not reliably add stronger `same-instance + dual-outcome + trajectory` evidence to the final accepted bundle.

Out of scope for this pass:

- adding new providers
- replacing the whole judge with an LLM-first contract
- broad claim-engine generalization for every dimension
- UI or API surface changes

## Target Outcome

After this plan:

1. `pair_extract` should score by structure, not just token count.
2. Weak evidence like `SWE-bench` + `trajectory` without explicit pairing semantics should not dominate the score.
3. Strong evidence that expresses the four required sub-signals should survive sampling into the final bundle artifacts.
4. Planner/editor repair should target whichever pair sub-signal is still missing.
5. `atoms-auto-mining-perfect` should have a credible path from `89` to `90+` without inflating unrelated dimensions.

## Pair Extract Structure Contract

For this implementation, treat `pair_extract` as satisfied only when the evidence bundle can support most of these sub-signals:

- `shared_unit`: same task / same instance / same benchmark case
- `dual_outcome`: success + failure, or resolved + unresolved
- `trajectory_form`: trajectory / run / trace / rollout / pair
- `artifact_link`: dataset / repository / issue / benchmark artifact that grounds the claim

The first pass can keep this contract internal to `goal_judge.py`, but the names above should be stable so planner and tests can target them.

## Task 1: Lock The Structural Failure Into Tests

**Files:**
- Modify: `tests/test_goal_judge.py`
- Modify: `tests/test_goal_bundle_loop.py`
- Modify: `tests/test_research_flow.py`

**Step 1: Add a judge regression for weak-vs-strong pair evidence**

Add a test where:

- weak evidence only mentions `SWE-bench`, `trajectory`, and `SWE-agent`
- strong evidence explicitly states same-instance paired successful/failed or resolved/unresolved trajectories

Assert:

- strong evidence scores higher than weak evidence
- weak evidence stays below a high-confidence threshold

**Step 2: Add a regression for structure-aware pair sub-signal extraction**

Add a unit test around the new pair helper in `goal_judge.py` that asserts the helper identifies:

- `shared_unit`
- `dual_outcome`
- `trajectory_form`
- `artifact_link`

from a single strong evidence record.

**Step 3: Add a regression for sample preservation**

Add a test that ensures a structurally strong pair finding survives bundle sampling over a shallow benchmark-title-only finding when both exist in the same bundle.

**Step 4: Run focused tests**

Run:

```bash
python3 -B -m unittest tests.test_goal_judge tests.test_goal_bundle_loop tests.test_research_flow -v
```

Expected:

- new tests fail before implementation
- existing pair tests still pass

**Step 5: Commit**

```bash
git add tests/test_goal_judge.py tests/test_goal_bundle_loop.py tests/test_research_flow.py
git commit -m "test: lock pair extract structural evidence regressions"
```

## Task 2: Add Pair-Extract Structural Scoring

**Files:**
- Modify: `goal_judge.py`
- Test: `tests/test_goal_judge.py`

**Step 1: Add a pair-structure helper**

Implement a helper that inspects bundle findings and returns a shape like:

```python
{
    "shared_unit": bool,
    "dual_outcome": bool,
    "trajectory_form": bool,
    "artifact_link": bool,
    "matched_terms": [...],
    "supporting_urls": [...],
}
```

**Step 2: Add a pair-specific scoring path**

Inside `_heuristic_bundle_dimension_score(...)`, when `dimension["id"] == "pair_extract"`:

- score by sub-signal coverage
- keep additive bonus for multiple supporting sources
- keep existing keyword/alias matching only as auxiliary evidence

Use a conservative ladder such as:

- `0-5`: shallow anchor only
- `6-10`: anchor + one structural signal
- `11-15`: at least two core structural signals
- `16-20`: three or four structural signals with grounded artifact evidence

**Step 3: Keep generic scoring unchanged for other dimensions**

Do not introduce new behavior for unrelated dimensions in this pass.

**Step 4: Run focused tests**

Run:

```bash
python3 -B -m unittest tests.test_goal_judge -v
```

Expected:

- structural pair tests pass
- existing heuristic-bundle tests stay green

**Step 5: Commit**

```bash
git add goal_judge.py tests/test_goal_judge.py
git commit -m "feat: score pair extract with structural evidence"
```

## Task 3: Preserve Strong Pair Evidence In Bundle Sampling

**Files:**
- Modify: `goal_judge.py`
- Modify: `goal_bundle_loop.py`
- Test: `tests/test_goal_bundle_loop.py`

**Step 1: Add a pair-evidence strength ranker**

Add a narrow helper that ranks findings for `pair_extract` by:

- same-instance terms
- dual-outcome terms
- trajectory terms
- concrete artifact grounding

**Step 2: Use that ranker when building bundle samples**

Adjust `_bundle_sample(...)` and top-level sample emission so that for pair-relevant bundles:

- structure-strong findings are sampled before shallow title-only hits
- per-query fairness remains, but not at the expense of losing the strongest pair evidence

**Step 3: Keep output shape stable**

Do not change `sample_findings` or `sample_bundle` schema in this pass.

**Step 4: Run focused tests**

Run:

```bash
python3 -B -m unittest tests.test_goal_bundle_loop tests.test_goal_judge -v
```

Expected:

- strong pair evidence is preserved in sampling
- accepted artifact shape remains unchanged

**Step 5: Commit**

```bash
git add goal_judge.py goal_bundle_loop.py tests/test_goal_bundle_loop.py tests/test_goal_judge.py
git commit -m "fix: preserve strong pair evidence in bundle samples"
```

## Task 4: Repair Against Missing Pair Sub-Signals

**Files:**
- Modify: `research/synthesizer.py`
- Modify: `goal_editor.py`
- Modify: `research/planner.py`
- Test: `tests/test_research_flow.py`

**Step 1: Surface pair sub-signal gaps in judge output**

Allow the heuristic bundle result for `pair_extract` to expose a lightweight diagnostic payload, for example:

```python
"pair_extract_detail": {
    "shared_unit": false,
    "dual_outcome": true,
    "trajectory_form": true,
    "artifact_link": true,
}
```

**Step 2: Carry this into gap synthesis**

In `research/synthesizer.py`, when `pair_extract` is still open, preserve this detail so planner/editor can see which sub-signal is missing.

**Step 3: Make editor/planner query the missing sub-signal**

Examples:

- missing `shared_unit` -> `same benchmark instance`, `same task id`
- missing `dual_outcome` -> `resolved unresolved subset`, `successful and failed runs`
- missing `trajectory_form` -> `verified trajectories`, `run traces`, `execution trajectories`
- missing `artifact_link` -> `dataset`, `repo`, `issue`, `benchmark release`

Keep at least 75% of pair repair queries anchored to the missing sub-signal.

**Step 4: Run focused tests**

Run:

```bash
python3 -B -m unittest tests.test_research_flow -v
```

Expected:

- follow-up and decomposition queries reflect the missing pair sub-signal
- pair repair no longer falls back to generic validation drift

**Step 5: Commit**

```bash
git add research/synthesizer.py goal_editor.py research/planner.py tests/test_research_flow.py
git commit -m "fix: repair pair extract against missing structural signals"
```

## Task 5: Re-Run Atoms And Inspect The Ceiling

**Files:**
- Runtime artifact only: `goal_cases/runs/*.json`

**Step 1: Run the focused hard-goal check**

Run:

```bash
python3 - <<'PY'
import sys, json
from pathlib import Path
repo = Path('/Users/vimala/Projects/autosearch')
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
    'pair_extract': (bundle.get('dimension_scores') or {}).get('pair_extract'),
    'extraction_completeness': (bundle.get('dimension_scores') or {}).get('extraction_completeness'),
    'matched_dimensions': bundle.get('matched_dimensions'),
    'run_path': result.get('run_path'),
}, ensure_ascii=False, indent=2))
PY
```

**Step 2: Inspect the resulting run**

Verify:

- `pair_extract` moved above the current `14`
- final sample contains stronger pair evidence than generic benchmark mentions
- later rounds are still targeting the pair gap for valid reasons, not because the judge regressed

**Step 3: Run the full suite**

Run:

```bash
python3 -B -m unittest discover -s tests -v
```

Expected:

- full suite green
- no regression in deep runtime artifacts or public API wrappers

**Step 4: Commit**

```bash
git add .
git commit -m "feat: improve pair extract structural evidence scoring"
```

## Notes

- `autosearch.py` and `goal_cases/benchmarks/` are out of scope and must remain untouched.
- Keep the implementation narrow. Do not generalize to a full claim engine until `pair_extract` proves the pattern.
- Prefer test-first changes. Each task should land with focused green tests before moving to the next stage.
