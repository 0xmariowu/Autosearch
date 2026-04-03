# AutoSearch Autonomous Super Search Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Upgrade `autosearch` from a strong free-first research runtime into a truly autonomous, self-evolving super AI search engine that can decompose hard problems, recurse into subtopics, accumulate reusable evidence, and drive complex goals toward high scores without depending on external product boundaries.

**Architecture:** Keep the existing `autosearch` product boundary and optimization core, but shift the center of gravity from “broad scout loop” to “research graph + evolving search program”. Maximize borrowing from `GPT Researcher` for recursive deep research, `MindSearch` for graph decomposition and branch execution, `SearXNG/ddgs` for free-first breadth, `Crawl4AI` for acquisition, and `Meilisearch/deep-searcher` for local evidence reuse, while re-implementing durable contracts in our own modules.

**Tech Stack:** Python, existing `autosearch` runtime, native `search_mesh`, native acquisition and evidence pipeline, local evidence index, optional self-hosted `SearXNG`, optional `Meilisearch`, optional `crawl4ai`, stable Python interface, benchmark JSON artifacts.

---

## Why A New Plan Exists

The previous super-upgrade plan mostly solved the **infrastructure gap**:

- free-first search mesh
- acquisition and evidence normalization
- local evidence index
- planner / executor / synthesizer skeleton
- stronger `SearchProgram`
- stable interface

That plan was necessary, and most of it now exists in code.

But the system still reflects its origin:

- originally optimized for **breadth-first scouting**
- originally optimized for **daily discovery and intake**
- originally centered on **platform loops**, not deep recursive research

That is why two capabilities are still underpowered compared with the best open-source systems:

1. **Recursive deepening**
   - `GPT Researcher` can keep drilling into subtopics and process large evidence surfaces
   - `autosearch` still tends to stop at shallow branch follow-ups

2. **Structured problem decomposition**
   - `MindSearch` turns hard questions into explicit branchable subproblems
   - `autosearch` has graph-like planning, but still relies too much on heuristic branch generation

This new plan is therefore not “Phase 1 again”. It is the **closing plan** that turns the current codebase into the target product:

**自主进化的超级 AI 搜索**

---

## Current State Summary

These are already present and should be treated as foundations, not open questions:

- `search_mesh/`
- `acquisition/`
- `evidence/`
- `evidence_index/`
- `research/`
- `goal_runtime.py`
- `goal_bundle_loop.py`
- `selector.py`
- `interface.py`

The remaining work is not “add basic modules”. It is:

1. make search mesh truly native
2. make evidence-first flow truly pure
3. make research planning strongly decompositional
4. make recursive deepening a first-class behavior
5. make program evolution enforce lineage/population policy, not just record it
6. prove the runtime on difficult goals

---

## Product Thesis

The final system should behave like this:

1. A caller gives a hard goal.
2. `autosearch` decomposes the goal into research branches.
3. Each branch chooses the right search backend and acquisition policy.
4. Raw search hits are converted into evidence records.
5. Evidence is indexed locally and reused in later rounds.
6. The runtime recursively deepens weak branches instead of only broadening search.
7. The judge scores the current research bundle.
8. The search program evolves:
   - search backends
   - backend roles
   - acquisition policy
   - evidence policy
   - repair policy
   - population policy
9. The runtime stops only when:
   - target score is reached
   - practical ceiling is detected
   - benchmark policy says plateau is real

The system should feel like:

- part `GPT Researcher`
- part `MindSearch`
- part `autoresearch`
- but with `autosearch` as the only product boundary

---

## Non-Negotiable Constraints

### Constraint 1: Free-first remains default

The main path must still work without premium APIs.

### Constraint 2: We own all durable contracts

No foreign project data model becomes our runtime truth.

### Constraint 3: Goal + Judge remain fixed

Search may evolve.
Scoring standards may not drift.

### Constraint 4: Interface remains small

External projects must still only need:

- `doctor(...)`
- `run_search_task(...)`
- `build_searcher_judge_session(...)`
- `run_goal_case(...)`
- `optimize_goal(...)`
- `optimize_goals(...)`
- `run_goal_benchmark(...)`

### Constraint 5: New depth must not regress broad scout utility

We are not replacing the system with a deep-only researcher.
We are adding a second stronger mode inside the same runtime.

---

## What We Must Borrow More Aggressively

## From `GPT Researcher`

We still need to copy more of the following internal behavior:

- recursive question expansion
- deeper follow-up chains
- evidence accumulation over many pages
- stronger synthesis discipline

What this means in our code:

- planner emits deeper follow-up branches, not just one-step graph followup
- executor can continue a branch for multiple rounds
- synthesizer merges branch evidence into a coherent research bundle

## From `MindSearch`

We still need to copy more of the following internal behavior:

- explicit question decomposition
- branch-oriented execution
- subproblem graphing
- structured branch merge

What this means in our code:

- planner must generate typed branch nodes
- branch nodes must carry subgoal intent
- branch outputs must merge through a real graph-aware synthesis step

## From `deep-searcher`

We should borrow more of:

- report-oriented execution
- evidence reuse before re-searching the open web
- evaluation discipline

## From `Meilisearch`

We should borrow more of:

- local-first retrieval before remote search
- evidence recall as part of planning, not just storage

---

## New Target Architecture

This plan adds four stronger target layers on top of what already exists.

## Layer A: Native Search Mesh Contract

Current weakness:
- `SearchHit` still wraps old engine results

Target:
- backends produce native `SearchHit`
- search mesh owns hit ranking and hit normalization
- engine compatibility becomes adapter-only

## Layer B: Pure Evidence-First Runtime

Current weakness:
- old finding compatibility is still on the hot path

Target:
- judge/harness/runtime operate over `EvidenceRecord` and `ResearchBundle`
- legacy findings are converted only at edges

## Layer C: Research Graph Runtime

Current weakness:
- graph planning exists, but remains shallow and heuristic

Target:
- decomposition graph
- branch types
- recursive follow-up planning
- branch-level synthesis and routing

## Layer D: Strong Program Evolution Runtime

Current weakness:
- population policy is partly descriptive

Target:
- branch pruning
- stale family retirement
- repair depth limits
- family inheritance
- evolution statistics that influence future selection

---

## Core Data Contracts To Finish

## `SearchHit`

Must become fully native.

Required fields:

- `hit_id`
- `url`
- `title`
- `snippet`
- `source`
- `provider`
- `query`
- `query_family`
- `backend`
- `rank`
- `score_hint`

No dependency on `engine.SearchResult` in the core contract.

## `AcquiredDocument`

Must be upgraded to match the intended boundary.

Required fields:

- `document_id`
- `url`
- `final_url`
- `status_code`
- `content_type`
- `fetch_method`
- `title`
- `raw_html_path`
- `clean_markdown`
- `fit_markdown`
- `references`
- `metadata`

## `EvidenceRecord`

Must become the actual hot-path evidence unit.

Required fields:

- `evidence_id`
- `url`
- `title`
- `source`
- `provider`
- `query`
- `query_family`
- `backend`
- `evidence_type`
- `summary`
- `extract`
- `citations`
- `keywords`
- `repo`
- `dataset`
- `author`
- `published_at`
- `doc_quality`

## `ResearchBundle`

This must become explicit, not just implicit dicts.

Required fields:

- `goal_id`
- `bundle_id`
- `evidence_records`
- `dimension_scores`
- `missing_dimensions`
- `matched_dimensions`
- `score`
- `judge`
- `score_gap`

## `SearchProgram`

This is the evolving object. It must keep growing stronger.

Required enforced fields:

- `search_backends`
- `backend_roles`
- `provider_mix`
- `topic_frontier`
- `query_templates`
- `dimension_strategies`
- `acquisition_policy`
- `evidence_policy`
- `repair_policy`
- `round_roles`
- `current_role`
- `sampling_policy`
- `stop_rules`
- `plateau_state`
- `population_policy`
- `mutation_history`
- `lineage`
- `family_id`
- `branch_id`
- `branch_root_program_id`
- `repair_depth`
- `evolution_stats`

---

## Definition Of Done

This plan is done only when all of the following are true:

- free-first remains the default runtime path
- search mesh backends return native `SearchHit`, not legacy engine objects
- hot-path runtime operates on `EvidenceRecord` and `ResearchBundle`
- legacy finding adapters are edge-only
- planner can decompose a complex goal into multiple branchable subproblems
- executor can recursively deepen weak branches
- synthesizer can merge branch evidence into routeable outputs
- population policy is actively enforced
- lineage and family evolution affect selection
- difficult goals improve across multiple rounds under default runtime
- benchmark artifacts demonstrate this behavior on more than one complex goal

---

# Implementation Tasks

## Phase 1: Finish Native Search Mesh

### Task 1: Remove legacy engine types from search mesh core

**Files:**
- Modify: `search_mesh/models.py`
- Modify: `search_mesh/backends/base.py`
- Modify: `search_mesh/backends/searxng_backend.py`
- Modify: `search_mesh/backends/ddgs_backend.py`
- Modify: `search_mesh/backends/github_backend.py`
- Modify: `search_mesh/backends/web_backend.py`
- Modify: `search_mesh/router.py`
- Modify: `goal_services.py`
- Test: `tests/test_search_mesh.py`

**Step 1: Write failing tests**

Cover:

- backend returns native `SearchHit`
- router returns `SearchHitBatch` without `PlatformSearchOutcome`
- `goal_services.search_query(...)` still works after native hit conversion

**Step 2: Introduce native backend output**

Backends should build `SearchHit` directly.
No `SearchHitBatch.from_platform_outcome(...)` in the main path.

**Step 3: Move engine compatibility into adapter code**

If we still need old `SearchResult`, convert only at the boundary.

**Step 4: Run tests**

```bash
python3 -m unittest tests/test_search_mesh.py -v
```

**Step 5: Commit**

```bash
git add search_mesh/models.py search_mesh/backends/base.py search_mesh/backends/*.py search_mesh/router.py goal_services.py tests/test_search_mesh.py
git commit -m "Make search mesh fully native"
```

### Task 2: Make search mesh the real broad-search runtime

**Files:**
- Modify: `engine.py`
- Modify: `goal_services.py`
- Modify: `doctor.py`
- Modify: `source_capability.py`
- Modify: `sources/catalog.json`
- Test: `tests/test_source_capability.py`

**Step 1: Write failing tests**

Cover:

- free breadth path prefers semantic free tiers
- doctor clearly reports active free path and fallback path

**Step 2: Replace numeric tiers with semantic tiers**

Use:

- `free_default`
- `specialized_free`
- `premium_fallback`

**Step 3: Make doctor reflect the new semantics**

Doctor output should say which free path is active before listing premium fallback.

**Step 4: Run tests**

```bash
python3 -m unittest tests/test_source_capability.py -v
```

**Step 5: Commit**

```bash
git add engine.py goal_services.py doctor.py source_capability.py sources/catalog.json tests/test_source_capability.py
git commit -m "Promote search mesh to primary runtime path"
```

---

## Phase 2: Finish Acquisition And Evidence Contracts

### Task 3: Upgrade `AcquiredDocument` to the planned model

**Files:**
- Modify: `acquisition/document_models.py`
- Modify: `acquisition/fetch_pipeline.py`
- Modify: `acquisition/render_pipeline.py`
- Test: `tests/test_acquisition_pipeline.py`

**Step 1: Write failing tests**

Cover:

- `document_id`
- `status_code`
- `fetch_method`
- `raw_html_path`
- `metadata`

**Step 2: Implement the missing fields**

The model should match the plan contract, not just a minimal page snapshot.

**Step 3: Run tests**

```bash
python3 -m unittest tests/test_acquisition_pipeline.py -v
```

**Step 4: Commit**

```bash
git add acquisition/document_models.py acquisition/fetch_pipeline.py acquisition/render_pipeline.py tests/test_acquisition_pipeline.py
git commit -m "Complete acquired document contract"
```

### Task 4: Upgrade `EvidenceRecord` to the planned model

**Files:**
- Modify: `evidence/models.py`
- Modify: `evidence/normalize.py`
- Modify: `evidence/classify.py`
- Test: `tests/test_evidence_normalize.py`

**Step 1: Write failing tests**

Cover:

- repo evidence fields
- article evidence fields
- dataset evidence fields
- `query_family`
- `backend`
- `evidence_type`
- `summary`
- `extract`
- `citations`
- `keywords`
- `doc_quality`

**Step 2: Fill the missing schema**

Move from “enriched finding” to actual evidence contract.

**Step 3: Run tests**

```bash
python3 -m unittest tests/test_evidence_normalize.py -v
```

**Step 4: Commit**

```bash
git add evidence/models.py evidence/normalize.py evidence/classify.py tests/test_evidence_normalize.py
git commit -m "Complete evidence record schema"
```

### Task 5: Introduce explicit `ResearchBundle`

**Files:**
- Create: `research/bundle.py`
- Modify: `evaluation_harness.py`
- Modify: `goal_judge.py`
- Modify: `goal_bundle_loop.py`
- Modify: `research/synthesizer.py`
- Test: `tests/test_goal_judge.py`
- Test: `tests/test_research_flow.py`

**Step 1: Write failing tests**

Judge and synthesizer should pass through a first-class bundle object.

**Step 2: Implement `ResearchBundle`**

Bundle construction and judging should become explicit and versionable.

**Step 3: Run tests**

```bash
python3 -m unittest tests/test_goal_judge.py tests/test_research_flow.py -v
```

**Step 4: Commit**

```bash
git add research/bundle.py evaluation_harness.py goal_judge.py goal_bundle_loop.py research/synthesizer.py tests/test_goal_judge.py tests/test_research_flow.py
git commit -m "Introduce explicit research bundle model"
```

---

## Phase 3: Make Evidence-First Runtime Pure

### Task 6: Push legacy adapters to the edges only

**Files:**
- Modify: `goal_services.py`
- Modify: `goal_bundle_loop.py`
- Modify: `research/executor.py`
- Modify: `evaluation_harness.py`
- Modify: `evidence/legacy_adapter.py`
- Test: `tests/test_evaluation_harness.py`
- Test: `tests/test_goal_bundle_loop.py`

**Step 1: Write failing tests**

Cover:

- main loop consumes `EvidenceRecord` and `ResearchBundle`
- legacy findings are accepted only through explicit adapter boundaries

**Step 2: Remove legacy normalization from the hot path**

The runtime should normalize once, then stay in the new model.

**Step 3: Run tests**

```bash
python3 -m unittest tests/test_evaluation_harness.py tests/test_goal_bundle_loop.py -v
```

**Step 4: Commit**

```bash
git add goal_services.py goal_bundle_loop.py research/executor.py evaluation_harness.py evidence/legacy_adapter.py tests/test_evaluation_harness.py tests/test_goal_bundle_loop.py
git commit -m "Make evidence-first runtime the primary path"
```

---

## Phase 4: Build Strong Research Graph

### Task 7: Replace shallow follow-up with typed decomposition graph

**Files:**
- Modify: `research/planner.py`
- Modify: `research/executor.py`
- Modify: `research/synthesizer.py`
- Modify: `research/routeable_output.py`
- Test: `tests/test_research_flow.py`

**Step 1: Write failing tests**

Cover:

- hard goal decomposes into typed branch nodes
- branches carry subgoal intent
- planner can emit branch families such as:
  - `breadth`
  - `implementation_probe`
  - `discussion_probe`
  - `dataset_probe`
  - `repair_followup`

**Step 2: Add branch node model and graph metadata**

The planner should emit a real graph-ready plan, not only label + queries.

**Step 3: Make synthesizer merge branch outputs**

Synthesis should preserve:

- branch evidence
- branch rationale
- branch routing

**Step 4: Run tests**

```bash
python3 -m unittest tests/test_research_flow.py -v
```

**Step 5: Commit**

```bash
git add research/planner.py research/executor.py research/synthesizer.py research/routeable_output.py tests/test_research_flow.py
git commit -m "Upgrade planner into typed research graph"
```

### Task 8: Add recursive deepening policy

**Files:**
- Modify: `research/planner.py`
- Modify: `goal_bundle_loop.py`
- Modify: `goal_runtime.py`
- Test: `tests/test_goal_bundle_loop.py`
- Test: `tests/test_goal_runtime.py`

**Step 1: Write failing tests**

Cover:

- low-scoring branches recurse
- already strong branches stop broadening
- recursion respects ceiling and branch depth

**Step 2: Add explicit recursive deepening rules**

Borrow from `GPT Researcher`:

- weak branch deepening
- follow-up query generation from branch evidence
- recursive page/evidence accumulation

**Step 3: Run tests**

```bash
python3 -m unittest tests/test_goal_bundle_loop.py tests/test_goal_runtime.py -v
```

**Step 4: Commit**

```bash
git add research/planner.py goal_bundle_loop.py goal_runtime.py tests/test_goal_bundle_loop.py tests/test_goal_runtime.py
git commit -m "Add recursive branch deepening runtime"
```

---

## Phase 5: Finish Strong Program Evolution

### Task 9: Make `population_policy` actively enforced

**Files:**
- Modify: `goal_runtime.py`
- Modify: `goal_bundle_loop.py`
- Modify: `selector.py`
- Test: `tests/test_goal_runtime.py`
- Test: `tests/test_selector.py`

**Step 1: Write failing tests**

Cover:

- stale branches are retired
- branch depth limits are enforced
- family diversity influences selection

**Step 2: Enforce, don’t just record**

Implement:

- branch pruning
- stale family retirement
- family inheritance preference
- diversity-aware candidate culling

**Step 3: Run tests**

```bash
python3 -m unittest tests/test_goal_runtime.py tests/test_selector.py -v
```

**Step 4: Commit**

```bash
git add goal_runtime.py goal_bundle_loop.py selector.py tests/test_goal_runtime.py tests/test_selector.py
git commit -m "Enforce population and lineage policies"
```

### Task 10: Deepen multi-round repair mutation

**Files:**
- Modify: `goal_editor.py`
- Modify: `goal_bundle_loop.py`
- Modify: `selector.py`
- Test: `tests/test_goal_editor.py`
- Test: `tests/test_selector.py`

**Step 1: Write failing tests**

Cover:

- repair mutation shifts backend roles
- repair mutation shifts acquisition policy
- repair mutation shifts evidence policy
- repair mutation targets weakest dimensions over multiple rounds

**Step 2: Improve mutation families**

The searcher should evolve more than query text:

- branch intent
- backend role usage
- acquisition aggressiveness
- evidence type preference

**Step 3: Run tests**

```bash
python3 -m unittest tests/test_goal_editor.py tests/test_selector.py -v
```

**Step 4: Commit**

```bash
git add goal_editor.py goal_bundle_loop.py selector.py tests/test_goal_editor.py tests/test_selector.py
git commit -m "Deepen multi-round repair mutation"
```

### Task 11: Add evolution statistics that affect runtime decisions

**Files:**
- Modify: `goal_runtime.py`
- Modify: `goal_bundle_loop.py`
- Modify: `research/planner.py`
- Test: `tests/test_goal_runtime.py`

**Step 1: Write failing tests**

Cover:

- family best-score history affects future planning
- dead-end branches stop getting budget
- productive families get higher branch priority

**Step 2: Make evolution stats feed planning**

Do not keep them as passive reporting only.

**Step 3: Run tests**

```bash
python3 -m unittest tests/test_goal_runtime.py -v
```

**Step 4: Commit**

```bash
git add goal_runtime.py goal_bundle_loop.py research/planner.py tests/test_goal_runtime.py
git commit -m "Use evolution stats to steer future search"
```

---

## Phase 6: Prove The Runtime On Difficult Goals

### Task 12: Build hard-goal benchmark suite

**Files:**
- Modify: `goal_benchmark.py`
- Create: `goal_cases/benchmarks/README.md`
- Modify: `README.md`
- Test: `tests/test_goal_benchmark.py`

**Step 1: Write failing tests**

Cover:

- benchmark always emits:
  - `goal_reached`
  - `score_gap`
  - `stop_reason`
  - `practical_ceiling`
- benchmark can run multiple difficult goals

**Step 2: Add difficult-goal suite discipline**

At minimum include:

- one code/research-heavy goal
- one architecture/design goal
- one evidence-sparse goal

**Step 3: Run tests**

```bash
python3 -m unittest tests/test_goal_benchmark.py -v
```

**Step 4: Commit**

```bash
git add goal_benchmark.py goal_cases/benchmarks/README.md README.md tests/test_goal_benchmark.py
git commit -m "Add hard-goal benchmark discipline"
```

### Task 13: Run acceptance benchmarks and archive results

**Files:**
- Use existing benchmark output paths
- Update: `docs/plans/2026-03-25-autosearch-autonomous-super-search-v2.md`

**Step 1: Run complex-goal benchmark set**

Run:

```bash
python3 goal_benchmark.py --goals atoms-auto-mining-perfect autosearch-goal-judge autosearch-capability-doctor --max-rounds 4 --plan-count 3 --max-queries 3 --target-score 90 --plateau-rounds 2
```

**Step 2: Review benchmark outputs**

Check:

- multi-round score improvement
- branch diversity
- routeable outputs
- practical ceiling behavior

**Step 3: Record acceptance summary**

Append a short acceptance section to this plan with:

- what improved
- what plateaued
- what still fails

**Step 4: Commit**

```bash
git add docs/plans/2026-03-25-autosearch-autonomous-super-search-v2.md
git commit -m "Record autonomous super search acceptance benchmark results"
```

---

## Acceptance Criteria

This plan is complete only when all of these are true:

- `search_mesh` backends return native `SearchHit`
- `AcquiredDocument` matches the intended contract
- `EvidenceRecord` matches the intended contract
- `ResearchBundle` exists as an explicit runtime model
- evidence-first is the hot path
- legacy adapters are edge-only
- planner emits typed research graph branches
- runtime can recursively deepen weak branches
- `population_policy` is enforced, not just logged
- evolution statistics affect future search decisions
- benchmark evidence shows difficult goals improving over multiple rounds
- external callers still only need `interface.py`

---

## Final Rule

Do not stop when the modules merely exist.

Stop only when:

- the runtime is structurally aligned with the target architecture
- the hot path is native and evidence-first
- the search program actually evolves as a strong object
- difficult goals can be shown to improve under the default runtime

This plan is about finishing the transformation from:

**广度型 scout**

into:

**自主进化的超级 AI 搜索**
