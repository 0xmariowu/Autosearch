# AutoSearch Deep Runtime V5 Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Push `autosearch` from a strong generic search backend into a generic deep-research runtime that can reliably lift difficult goals by porting concrete execution patterns from proven open-source deep-search engines.

**Architecture:** Keep the current `search_mesh -> acquisition -> evidence -> research -> goal/watch` layering, but replace the weak “search a few rounds then judge” behavior with a strict `Search -> Read -> Reason -> Search` loop, graph decomposition, stronger contradiction handling, and memory-backed deep sessions. All new logic must land behind AutoSearch-owned contracts (`SearchHit`, `EvidenceRecord`, `ResearchBundle`, `SearchDecision`, `PlanningOp`) rather than external APIs or UI products.

**Tech Stack:** Python, existing `search_mesh`, `acquisition`, `evidence`, `research`, local evidence index, optional local `sentence_transformers`, optional self-hosted SearXNG, optional Crawl4AI adapter, lexical/hybrid/semantic rerank, stable Python interface.

---

## Why V5 Exists

`v4` largely completed the structural upgrade:

- `ResearchMode`
- `ProviderRegistry`
- `CrossVerification`
- `Cheap Rerank`
- `GoalWatch`
- `Think/Act + Bounded Planning`
- `GapQueue + Diary`
- `Budget`

But difficult goals still plateau because the runtime is still too shallow:

- search results are not read deeply enough before the next action
- verification is still mostly result-summary oriented
- the graph is not yet a true recursive research graph
- difficult missing dimensions are not escalated into focused deep investigations

This plan is for the final shift:

- from “iterative search runtime”
- to “generic autonomous deep-research runtime”

---

## Product Boundary

`autosearch` remains:

- a backend runtime
- a local Python interface
- a goal/watch optimization engine

`autosearch` does **not** become:

- a front-end chat product
- a Perplexity clone
- an unconstrained agent that invents arbitrary tools

---

## Source Port Matrix

This is the exact “抄作业” mapping. Implementation must preserve the behavior, but land behind our contracts.

| Source Repo | Source Files / Modules | Exact Pattern to Port | Target AutoSearch Files |
|---|---|---|---|
| `jina-ai/node-DeepResearch` | `src/agent.ts`, `src/tools/research-planner.ts`, `src/tools/read.ts`, `src/tools/reducer.ts`, `src/tools/jina-dedup.ts`, `src/utils/token-tracker.ts`, `src/utils/action-tracker.ts` | `Search -> Read -> Reason -> Search` loop, query rewrite, reducer, step budget, action tracker | `research/deep_loop.py`, `research/decision.py`, `research/planner.py`, `research/executor.py`, `research/budget.py`, `research/diary.py`, `query_dedup.py` |
| `assafelovic/gpt-researcher` | `backend/server/multi_agent_runner.py`, `backend/memory/research.py`, `backend/report_type/deep_research/main.py` | planner/executor/publisher split, research memory, long-running report packets | `research/report_packet.py`, `evidence_index/index.py`, `research/routeable_output.py`, `watch/runtime.py` |
| `unclecode/crawl4ai` | `crawl4ai/async_webcrawler.py`, `crawl4ai/content_filter_strategy.py`, `crawl4ai/chunking_strategy.py`, `crawl4ai/markdown_generation_strategy.py`, `crawl4ai/extraction_strategy.py`, `crawl4ai/models.py` | read full pages, clean markdown, fit markdown, query-aware chunking, extraction schema | `acquisition/fetch_pipeline.py`, `acquisition/content_filter.py`, `acquisition/chunking.py`, `acquisition/markdown_strategy.py`, `acquisition/document_models.py`, `evidence/normalize.py` |
| `InternLM/MindSearch` | `mindsearch/agent/graph.py`, `mindsearch/agent/mindsearch_agent.py`, `mindsearch/agent/mindsearch_prompt.py`, `mindsearch/agent/models.py` | graph-based decomposition, branch nodes, async search branches, graph summary | `research/graph_models.py`, `research/graph_scheduler.py`, `research/planner.py`, `research/synthesizer.py` |
| `swirlai/swirl-search` | connector/routing concepts | federated provider routing, provider-family routing, per-provider query transformation | `search_mesh/registry.py`, `search_mesh/router.py`, `search_mesh/backends/*.py` |
| `searxng/searxng` + `deedy5/ddgs` | provider/search engine patterns | free-first breadth search foundation | already present; refine in `search_mesh/router.py`, `search_mesh/provider_policy.py` |

---

## Success Criteria

The plan is complete only when all of these are true:

1. `deep` mode runs a true `Search -> Read -> Reason -> Search` loop.
2. Graph decomposition creates explicit branch nodes and branch-level summaries.
3. Read/acquisition output is used in planning, not only in final synthesis.
4. Contradiction output includes:
   - `claim_alignment`
   - `contradiction_clusters`
   - `source_dispute_map`
5. Routeable output can emit:
   - `CitedAnswer`
   - `RouteableResearchPacket`
6. A difficult goal run no longer plateaus because of shallow snippet-only evidence.
7. Full test suite passes.
8. New deep-runtime tests pass.

---

## Task 1: Lock in Deep Runtime Contracts

**Files:**
- Create: `research/deep_loop.py`
- Create: `research/decision.py`
- Create: `research/graph_models.py`
- Create: `research/report_packet.py`
- Modify: `research/planner.py`
- Modify: `research/executor.py`
- Modify: `research/synthesizer.py`
- Modify: `research/routeable_output.py`
- Test: `tests/test_research_flow.py`
- Test: `tests/test_interface.py`

**Source to copy:**
- `node-DeepResearch/src/agent.ts`
- `MindSearch/mindsearch/agent/models.py`
- `GPT Researcher/backend/report_type/deep_research/main.py`

**Step 1: Write the failing tests**

Add tests that require:
- a `SearchDecision` object returned from planning
- a `ResearchBundle` with explicit `search_graph`
- a `RouteableResearchPacket` object in routeable output for deep mode

Example assertions:

```python
self.assertIn("decision", result["rounds"][0])
self.assertIn("search_graph", result["bundle_final"])
self.assertIn("research_packet", result["routeable_output"])
```

**Step 2: Run tests to verify failure**

Run:

```bash
cd '/Users/vimala/Library/Mobile Documents/com~apple~CloudDocs/Dev/autosearch'
python3 -B -m unittest tests.test_research_flow tests.test_interface -v
```

Expected:
- missing keys / missing modules

**Step 3: Implement minimal contracts**

Implement:
- `SearchDecision`
- `DeepLoopState`
- `GraphNode`
- `GraphEdge`
- `RouteableResearchPacket`

Use plain dataclasses / typed dicts, no framework.

**Step 4: Adapt planner/executor/synthesizer to use contracts**

Required behaviors:
- planner emits `SearchDecision`
- executor consumes `SearchDecision`
- synthesizer produces `search_graph`
- routeable output emits `research_packet` in deep mode

**Step 5: Re-run tests**

Run:

```bash
python3 -B -m unittest tests.test_research_flow tests.test_interface -v
```

Expected:
- PASS

**Step 6: Commit**

```bash
git add research/deep_loop.py research/decision.py research/graph_models.py research/report_packet.py research/planner.py research/executor.py research/synthesizer.py research/routeable_output.py tests/test_research_flow.py tests/test_interface.py
git commit -m "feat: add deep runtime contracts"
```

---

## Task 2: Port `Search -> Read -> Reason -> Search` as the Actual Deep Loop

**Files:**
- Modify: `research/deep_loop.py`
- Modify: `research/planner.py`
- Modify: `research/executor.py`
- Modify: `research/budget.py`
- Modify: `goal_bundle_loop.py`
- Test: `tests/test_research_flow.py`
- Test: `tests/test_goal_bundle_loop.py`

**Source to copy:**
- `node-DeepResearch/src/agent.ts`
- `node-DeepResearch/src/tools/research-planner.ts`
- `node-DeepResearch/src/tools/read.ts`
- `node-DeepResearch/src/tools/reducer.ts`
- `node-DeepResearch/src/utils/token-tracker.ts`

**Step 1: Write the failing tests**

Add tests that require:
- deep mode does at least one explicit read step before next search step
- budget exhaustion stops the loop
- read results alter the next generated queries

Example assertions:

```python
self.assertIn("read", round_state["diary_summary"])
self.assertTrue(any(step["kind"] == "read" for step in round_state["deep_steps"]))
```

**Step 2: Run tests to verify failure**

Run:

```bash
python3 -B -m unittest tests.test_research_flow tests.test_goal_bundle_loop -v
```

**Step 3: Implement the loop**

Loop order in deep mode must become:
1. search
2. pick candidate URLs
3. acquire/read
4. summarize/claim-extract
5. generate follow-up `SearchDecision`
6. continue until stop or budget exhaustion

Do not fake this in a single function call. Persist step history into round state.

**Step 4: Wire budget logic**

Use `research/budget.py` to enforce:
- max exploration steps
- answer reserve budget
- provider timeout
- per-branch budget

**Step 5: Re-run tests**

Expected: PASS

**Step 6: Commit**

```bash
git add research/deep_loop.py research/planner.py research/executor.py research/budget.py goal_bundle_loop.py tests/test_research_flow.py tests/test_goal_bundle_loop.py
git commit -m "feat: run deep mode as search-read-reason loop"
```

---

## Task 3: Port Crawl4AI-Style Read/Chunk/Extract Pipeline

**Files:**
- Create: `acquisition/chunking.py`
- Create: `acquisition/markdown_strategy.py`
- Modify: `acquisition/fetch_pipeline.py`
- Modify: `acquisition/content_filter.py`
- Modify: `acquisition/document_models.py`
- Modify: `evidence/normalize.py`
- Test: `tests/test_acquisition.py`
- Test: `tests/test_evidence.py`

**Source to copy:**
- `crawl4ai/async_webcrawler.py`
- `crawl4ai/content_filter_strategy.py`
- `crawl4ai/chunking_strategy.py`
- `crawl4ai/markdown_generation_strategy.py`
- `crawl4ai/extraction_strategy.py`
- `crawl4ai/models.py`

**Step 1: Write the failing tests**

Add tests that require:
- acquired document contains:
  - `clean_markdown`
  - `fit_markdown`
  - `chunk_scores`
  - `references`
- query-aware extraction returns intro + relevant middle + conclusion chunks

**Step 2: Run tests to verify failure**

```bash
python3 -B -m unittest tests.test_acquisition tests.test_evidence -v
```

**Step 3: Implement chunking + markdown strategies**

Required behavior:
- split article into semantic-ish chunks
- rank chunks by query relevance
- keep:
  - intro chunk
  - top relevant chunks
  - conclusion chunk
- preserve links/references

**Step 4: Normalize into evidence**

`EvidenceRecord` should gain:
- extracted claims
- chosen chunks
- extraction rationale
- doc quality

**Step 5: Re-run tests**

Expected: PASS

**Step 6: Commit**

```bash
git add acquisition/chunking.py acquisition/markdown_strategy.py acquisition/fetch_pipeline.py acquisition/content_filter.py acquisition/document_models.py evidence/normalize.py tests/test_acquisition.py tests/test_evidence.py
git commit -m "feat: add crawl4ai-style chunked extraction"
```

---

## Task 4: Port MindSearch Graph Scheduling

**Files:**
- Create: `research/graph_scheduler.py`
- Modify: `research/graph_models.py`
- Modify: `research/planner.py`
- Modify: `research/synthesizer.py`
- Test: `tests/test_research_flow.py`

**Source to copy:**
- `MindSearch/mindsearch/agent/graph.py`
- `MindSearch/mindsearch/agent/mindsearch_agent.py`

**Step 1: Write the failing tests**

Add tests that require:
- branch nodes
- branch priority
- branch merge candidates
- branch prune candidates
- branch summary in final bundle

**Step 2: Run tests to verify failure**

```bash
python3 -B -m unittest tests.test_research_flow -v
```

**Step 3: Implement scheduler**

Required behavior:
- root question decomposes into branch questions
- each branch accumulates evidence separately
- scheduler decides:
  - expand
  - merge
  - prune
  - saturate

**Step 4: Push branch summary into synthesis**

Final `search_graph` must include:
- node list
- edge list
- branch status
- branch evidence counts

**Step 5: Re-run tests**

Expected: PASS

**Step 6: Commit**

```bash
git add research/graph_scheduler.py research/graph_models.py research/planner.py research/synthesizer.py tests/test_research_flow.py
git commit -m "feat: add graph scheduler for deep research branches"
```

---

## Task 5: Port GPT Researcher Memory + Report Packet

**Files:**
- Modify: `evidence_index/index.py`
- Modify: `watch/runtime.py`
- Modify: `research/routeable_output.py`
- Modify: `interface.py`
- Modify: `README.md`
- Test: `tests/test_interface.py`
- Test: `tests/test_watch_runtime.py`

**Source to copy:**
- `gpt-researcher/backend/server/multi_agent_runner.py`
- `gpt-researcher/backend/memory/research.py`
- `gpt-researcher/backend/report_type/deep_research/main.py`

**Step 1: Write the failing tests**

Add tests that require:
- deep mode emits reusable research packet
- watch runtime persists report packet metadata
- routeable output includes memory-backed citations and next actions

**Step 2: Run tests to verify failure**

```bash
python3 -B -m unittest tests.test_interface tests.test_watch_runtime -v
```

**Step 3: Implement memory-backed report packet**

Required fields:
- `packet_id`
- `query`
- `mode`
- `citations`
- `claims`
- `contradictions`
- `next_actions`
- `evidence_refs`

**Step 4: Surface through interface/watch**

Expose:
- `run_goal_case(...)[\"research_packet\"]`
- `run_watch(...)[\"latest_packet\"]`

**Step 5: Re-run tests**

Expected: PASS

**Step 6: Commit**

```bash
git add evidence_index/index.py watch/runtime.py research/routeable_output.py interface.py README.md tests/test_interface.py tests/test_watch_runtime.py
git commit -m "feat: add memory-backed deep research packets"
```

---

## Task 6: Strengthen Verification into Claim Alignment, Not Just Summary

**Files:**
- Modify: `research/synthesizer.py`
- Modify: `research/routeable_output.py`
- Modify: `evidence/normalize.py`
- Test: `tests/test_research_flow.py`

**Source to copy:**
- `node-DeepResearch/src/tools/evaluator.ts`
- `GPT Researcher` synthesis/reporting style

**Step 1: Write the failing tests**

Require:
- `claim_alignment`
- `contradiction_clusters`
- `source_dispute_map`
- `consensus_strength`

**Step 2: Run tests to verify failure**

```bash
python3 -B -m unittest tests.test_research_flow -v
```

**Step 3: Implement claim grouping**

Given normalized evidence claims:
- cluster similar claims
- detect disagreeing stances
- map each cluster to URLs/providers

**Step 4: Emit structured contradiction output**

Required shape:

```python
{
  "claim_alignment": [...],
  "contradiction_clusters": [...],
  "source_dispute_map": {...},
  "consensus_strength": 0.0,
}
```

**Step 5: Re-run tests**

Expected: PASS

**Step 6: Commit**

```bash
git add research/synthesizer.py research/routeable_output.py evidence/normalize.py tests/test_research_flow.py
git commit -m "feat: add claim alignment and contradiction clustering"
```

---

## Task 7: Hard-Goal Escalation Policy

**Files:**
- Modify: `goal_editor.py`
- Modify: `research/planner.py`
- Modify: `research/action_policy.py`
- Modify: `goal_runtime.py`
- Test: `tests/test_goal_editor.py`
- Test: `tests/test_goal_runtime.py`

**Source to copy:**
- `node-DeepResearch` repeated query family / read-before-answer discipline
- `MindSearch` branch decomposition discipline

**Step 1: Write the failing tests**

Add tests that require:
- missing dimensions with repeated stagnation are escalated into:
  - dedicated branch
  - deeper acquisition
  - mandatory cross verification
- difficult branch stops only on evidence saturation, not simple round count

**Step 2: Run tests to verify failure**

```bash
python3 -B -m unittest tests.test_goal_editor tests.test_goal_runtime -v
```

**Step 3: Implement escalation**

Rules:
- if a dimension is missing for `>=2` deep rounds:
  - create focused branch
  - raise branch budget
  - enable acquisition
  - enable contradiction-aware verification

**Step 4: Re-run tests**

Expected: PASS

**Step 5: Commit**

```bash
git add goal_editor.py research/planner.py research/action_policy.py goal_runtime.py tests/test_goal_editor.py tests/test_goal_runtime.py
git commit -m "feat: escalate stubborn missing dimensions into deep branches"
```

---

## Task 8: Prove the Runtime with Difficult Benchmarks

**Files:**
- Modify: `goal_benchmark.py`
- Modify: `interface.py`
- Modify: `README.md`
- Test: `tests/test_interface.py`

**Step 1: Write the failing tests**

Add tests that require benchmark output to include:
- `mode`
- `deep_steps`
- `claim_alignment`
- `contradiction_clusters`
- `research_packet`
- `practical_ceiling`

**Step 2: Run tests to verify failure**

```bash
python3 -B -m unittest tests.test_interface -v
```

**Step 3: Implement benchmark reporting**

Benchmark output must persist enough information to answer:
- did deep loop actually read pages?
- did graph branch?
- did contradiction engine run?
- did the score plateau because of evidence saturation or runtime weakness?

**Step 4: Run real benchmark**

```bash
cd '/Users/vimala/Library/Mobile Documents/com~apple~CloudDocs/Dev/autosearch'
KMP_DUPLICATE_LIB_OK=TRUE python3 - <<'PY'
import json
from interface import AutoSearchInterface
client = AutoSearchInterface('/Users/vimala/Library/Mobile Documents/com~apple~CloudDocs/Dev/autosearch')
result = client.run_goal_benchmark(
    [
        'autosearch-goal-judge',
        'autosearch-capability-doctor',
        'atoms-auto-mining-perfect',
    ],
    mode='deep',
    max_rounds=3,
    target_score=90,
    plateau_rounds=2,
)
print(json.dumps(result, indent=2))
PY
```

Expected:
- difficult goal run includes deep-runtime artifacts
- benchmark output clearly explains ceiling

**Step 5: Commit**

```bash
git add goal_benchmark.py interface.py README.md tests/test_interface.py
git commit -m "feat: expose deep benchmark artifacts"
```

---

## Task 9: Final Documentation Sync

**Files:**
- Modify: `docs/README.md`
- Modify: `docs/plans/2026-03-25-autosearch-super-search-v4.md`
- Test: none

**Step 1: Update docs index**

Add this plan to `docs/README.md`.

**Step 2: Mark V4 as superseded by V5**

Add a note near the top of `2026-03-25-autosearch-super-search-v4.md` that V5 is the execution-grade deep-runtime plan.

**Step 3: Commit**

```bash
git add docs/README.md docs/plans/2026-03-25-autosearch-super-search-v4.md docs/plans/2026-03-26-autosearch-deep-runtime-v5.md
git commit -m "docs: add v5 deep runtime execution plan"
```

---

## Execution Order

Run tasks strictly in this order:

1. `Task 1` contracts
2. `Task 2` deep loop
3. `Task 3` Crawl4AI-style extraction
4. `Task 4` graph scheduler
5. `Task 6` contradiction alignment
6. `Task 7` hard-goal escalation
7. `Task 5` report packet and memory
8. `Task 8` benchmark proof
9. `Task 9` docs sync

Reason:
- contracts first
- then loop
- then read/extract
- then graph
- then contradiction
- then hard-goal escalation
- then memory/report packaging
- then prove it in benchmark

---

## What Not to Do

- Do **not** add UI/product features from `Fireplexity`, `Scira`, or `Vane`.
- Do **not** add MCP-first or API-key-first assumptions.
- Do **not** re-centralize logic back into `engine.py`.
- Do **not** bypass `SearchDecision` and `PlanningOp` with ad-hoc planner side effects.
- Do **not** add a second parallel runtime; extend the current runtime.

---

## Final Acceptance Checklist

- [ ] Deep mode uses a true `Search -> Read -> Reason -> Search` loop
- [ ] Read results materially alter the next decision
- [ ] Query-aware chunk selection is active
- [ ] Deep graph creates and prunes branches
- [ ] Contradiction output includes clustered claims and dispute maps
- [ ] Routeable output emits reusable research packets
- [ ] Watch runtime can persist deep research packets
- [ ] Difficult benchmark output contains deep-runtime artifacts
- [ ] Full test suite passes
- [ ] Difficult goal ceiling improves or at minimum becomes clearly diagnosable from persisted artifacts

