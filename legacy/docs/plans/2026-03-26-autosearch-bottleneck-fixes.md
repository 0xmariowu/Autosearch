# AutoSearch Bottleneck Fixes Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Remove the current score ceiling caused by correctness drift in handoff artifacts, noisy contradiction detection, and weak heuristic scoring for cross-project evidence.

**Architecture:** Keep the existing goal-loop and deep-runtime architecture. Fix correctness first so final artifacts reflect the accepted/best round, then tighten claim/contradiction logic, then upgrade bundle judging from raw keyword coverage toward evidence-strength-aware scoring. Only after those two layers are correct should retrieval/planning heuristics be tuned for the hard atoms goal.

**Tech Stack:** Python 3, unittest, existing `goal_*` runtime, `research/*` deep-runtime modules, JSON goal-case fixtures.

---

## Scope

This plan targets the 4 concrete bottlenecks visible in the current `atoms-auto-mining-perfect` run:

1. Final handoff artifacts do not always reflect the accepted/best round.
2. `routeable_output.score_gap` is computed from static goal-case target score, not the effective runtime target score.
3. Claim alignment marks same-source / same-URL material as contradictions, lowering consensus quality.
4. Heuristic bundle scoring underweights strong cross-project evidence and overweights literal keyword overlap.

Out of scope for this pass:

- new providers
- UI
- replacing the whole planner/executor architecture
- new benchmark suites unrelated to goal loops

## Task 1: Lock In The Current Failures As Regression Tests

**Files:**
- Modify: `tests/test_goal_bundle_loop.py`
- Modify: `tests/test_research_flow.py`
- Modify: `tests/test_goal_judge.py`

**Step 1: Add a regression test for accepted-round artifact selection**

- Build a small `run_goal_bundle_loop(...)` fixture where:
  - round N is accepted
  - round N+1 exists but is not accepted
  - their `routeable_output`, `research_packet`, and `deep_steps` differ
- Assert top-level result uses the accepted/best round artifacts, not blindly `rounds[-1]`.

**Step 2: Add a regression test for effective target-score propagation**

- Call `run_goal_bundle_loop(...)` with `target_score_override=90` against a goal case whose JSON still says `target_score=100`.
- Assert:
  - top-level `score_gap` uses `90`
  - `routeable_output["score_gap"]` also uses `90`
  - `research_packet` remains consistent with the same accepted round.

**Step 3: Add a regression test for contradiction self-collisions**

- In `tests/test_research_flow.py`, create a bundle where the same URL/source produces multiple extracted sentences with mixed stance words.
- Assert contradiction pairs do not include:
  - same `left_url == right_url`
  - same `left_source == right_source` when there is no cross-source disagreement.

**Step 4: Add a regression test for low-score cross-project evidence**

- In `tests/test_goal_judge.py`, create a goal dimension like `extraction_completeness` with multiple aliases and one strong repository/dataset pair that uses different wording than the goal keywords.
- Assert the new heuristic does not bottom out at a token-match score like `5` when the evidence is clearly implementation-grade.

**Step 5: Run focused tests**

Run:

```bash
python3 -B -m unittest tests.test_goal_bundle_loop tests.test_research_flow tests.test_goal_judge -v
```

Expected:

- new tests fail before code changes
- existing unaffected tests stay green

**Step 6: Commit**

```bash
git add tests/test_goal_bundle_loop.py tests/test_research_flow.py tests/test_goal_judge.py
git commit -m "test: lock in autosearch bottleneck regressions"
```

## Task 2: Make Final Handoff Artifacts Reflect Accepted Reality

**Files:**
- Modify: `goal_bundle_loop.py`
- Modify: `research/routeable_output.py`
- Test: `tests/test_goal_bundle_loop.py`

**Step 1: Introduce a single source of truth for final round artifacts**

- In `goal_bundle_loop.py`, derive the final artifact source from:
  - accepted/best candidate round when one exists
  - fallback to the last round only when there is no accepted round
- Replace direct `rounds[-1]` reads for:
  - `routeable_output`
  - `research_bundle`
  - `search_graph`
  - `research_packet`
  - `deep_steps`

**Step 2: Propagate effective target score into routeable output**

- In `research/routeable_output.py`, stop reading target score only from raw goal JSON.
- Add an explicit effective target score input, or pass it via repair hints, then compute `score_gap` from runtime target score.

**Step 3: Keep top-level and handoff gap numbers aligned**

- Assert these values are identical for the accepted round:
  - top-level `score_gap`
  - `routeable_output["score_gap"]`

**Step 4: Run focused tests**

Run:

```bash
python3 -B -m unittest tests.test_goal_bundle_loop -v
```

Expected:

- accepted-round artifact test passes
- target-score propagation test passes

**Step 5: Commit**

```bash
git add goal_bundle_loop.py research/routeable_output.py tests/test_goal_bundle_loop.py
git commit -m "fix: align final handoff artifacts with accepted goal state"
```

## Task 3: Make Cross-Verification Measure Real Disagreement

**Files:**
- Modify: `research/synthesizer.py`
- Test: `tests/test_research_flow.py`

**Step 1: Deduplicate claim-source rows before contradiction pairing**

- In `_align_claims(...)`, dedupe repeated `(cluster, source, url, stance, normalized_claim)` rows.
- Avoid counting the same source sentence multiple times as separate support/oppose evidence.

**Step 2: Exclude self-contradictions from contradiction pairs**

- When building `contradiction_pairs`, skip pairs where:
  - `left_url == right_url`
  - or both `left_source == right_source` and there is no distinct URL evidence

**Step 3: Tighten contradiction detection threshold**

- Mark a cluster as contradictory only when disagreement crosses a real diversity threshold:
  - at least 2 distinct evidence rows
  - and at least 2 distinct URLs or 2 distinct sources
- Keep single-source noisy text from collapsing consensus to `contested`.

**Step 4: Recompute consensus strength from clean evidence**

- In `_cross_verification_summary(...)`, derive `consensus_strength` after contradiction cleanup.
- Preserve current labels (`high`, `medium`, `low`, `contested`) to avoid API churn.

**Step 5: Run focused tests**

Run:

```bash
python3 -B -m unittest tests.test_research_flow -v
```

Expected:

- self-collision contradiction test passes
- existing contradiction/consensus tests still pass

**Step 6: Commit**

```bash
git add research/synthesizer.py tests/test_research_flow.py
git commit -m "fix: require real evidence diversity for contradiction detection"
```

## Task 4: Upgrade Heuristic Bundle Scoring To Evidence Strength

**Files:**
- Modify: `goal_judge.py`
- Modify: `goal_cases/atoms-auto-mining-perfect.json`
- Test: `tests/test_goal_judge.py`

**Step 1: Keep the current dimension structure, but stop relying only on literal keyword counts**

- Preserve existing `dimensions[*].weight`.
- Extend each dimension to optionally support additive metadata such as:
  - `aliases`
  - `strong_signals`
  - `content_type_preferences`
  - `source_preferences`
- Keep old `keywords` working as fallback.

**Step 2: Add evidence-strength tiers to heuristic bundle scoring**

- In `goal_judge.py`, score each dimension from a combination of:
  - lexical/alias hit
  - strong-signal hit
  - implementation-strength bonus for repository/code/issue evidence
  - cross-source corroboration bonus
  - markdown/acquired-text bonus when evidence was actually enriched
- Cap at the existing dimension weight to preserve 0-100 semantics.

**Step 3: Penalize generic benchmark pages relative to implementation evidence**

- Generic dataset-card text alone should not max out a dimension.
- Repository/code evidence that maps strongly to the dimension should outrank generic dataset summaries.

**Step 4: Add atoms-specific alias coverage where the current rubric is too literal**

- Update `goal_cases/atoms-auto-mining-perfect.json` so the two weak dimensions can recognize strong neighboring vocabulary:
  - `extraction_completeness`
  - `label_separation`
- Keep this additive and narrow; do not rewrite the whole goal.

**Step 5: Run focused tests**

Run:

```bash
python3 -B -m unittest tests.test_goal_judge -v
```

Expected:

- new cross-project evidence test passes
- existing heuristic and OpenRouter fallback tests stay green

**Step 6: Commit**

```bash
git add goal_judge.py goal_cases/atoms-auto-mining-perfect.json tests/test_goal_judge.py
git commit -m "feat: score bundle dimensions by evidence strength"
```

## Task 5: Tune Retrieval Toward Strong Evidence, Not More Volume

**Files:**
- Modify: `goal_editor.py`
- Modify: `research/planner.py`
- Modify: `research/executor.py`
- Test: `tests/test_goal_editor.py`
- Test: `tests/test_research_flow.py`

**Step 1: Specialize follow-up planning for weak dimensions**

- When `weakest_dimension` is `extraction_completeness` or `label_separation`, prefer plans that bias toward:
  - implementation/code/repo/issue evidence
  - acquisition-enabled reads
  - cross-project comparison queries
- Do not increase breadth blindly.

**Step 2: Prefer acquisition and stronger evidence on weak-dimension repair branches**

- In planner/executor decision payloads, raise:
  - `acquire_pages`
  - `prefer_acquired_text`
  - `preferred_content_types`
for those weak-dimension branches.

**Step 3: Reduce low-value dataset-card repetition**

- Add planning or execution filters that avoid replaying semantically equivalent dataset-summary queries once they have already saturated the bundle.

**Step 4: Run focused tests**

Run:

```bash
python3 -B -m unittest tests.test_goal_editor tests.test_research_flow -v
```

Expected:

- planner chooses stronger repair branches for weak dimensions
- existing deep follow-up and provider-mix behavior still passes

**Step 5: Commit**

```bash
git add goal_editor.py research/planner.py research/executor.py tests/test_goal_editor.py tests/test_research_flow.py
git commit -m "feat: bias repair branches toward stronger implementation evidence"
```

## Task 6: Full Validation On The Hard Goal

**Files:**
- No code changes required unless a bug is found
- Artifacts: `goal_cases/runs/*.json`

**Step 1: Run the full regression suite**

Run:

```bash
python3 -B -m unittest discover -s tests -v
```

Expected:

- full suite green

**Step 2: Re-run the hard goal with deep mode**

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
print(json.dumps({
    'score': (result.get('bundle_final') or {}).get('score'),
    'dimension_scores': (result.get('bundle_final') or {}).get('dimension_scores'),
    'matched_dimensions': (result.get('bundle_final') or {}).get('matched_dimensions'),
    'missing_dimensions': (result.get('bundle_final') or {}).get('missing_dimensions'),
    'top_score_gap': result.get('score_gap'),
    'routeable_score_gap': (result.get('routeable_output') or {}).get('score_gap'),
    'consensus_strength': ((result.get('routeable_output') or {}).get('cross_verification') or {}).get('consensus_strength'),
    'contradiction_detected': ((result.get('routeable_output') or {}).get('cross_verification') or {}).get('contradiction_detected'),
    'run_path': result.get('run_path'),
}, ensure_ascii=False, indent=2))
PY
```

**Step 3: Acceptance checklist**

- Top-level and routeable score gaps match.
- Final handoff artifacts come from the accepted/best round.
- No same-URL contradiction pairs appear.
- `extraction_completeness` and `label_separation` improve materially from `5`.
- Overall score moves above the current plateau of `70`, ideally into the `80+` band.

**Step 4: Commit**

```bash
git add goal_cases/runs/*.json
git commit -m "chore: validate hard-goal improvements after bottleneck fixes"
```

## Recommended Execution Order

1. Task 1
2. Task 2
3. Task 3
4. Task 4
5. Task 5
6. Task 6

Reason:

- Tasks 2 and 3 fix correctness.
- Task 4 improves scoring quality only after correctness is trustworthy.
- Task 5 tunes retrieval after the judge and contradiction logic stop lying.
- Task 6 is the real-world proof step.
