# AutoSearch Super Search V4 Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Turn `autosearch` into a generic, autonomous, self-evolving super AI search backend by porting proven execution patterns from competitor repos with 1:1 implementation detail, while keeping `autosearch` backend-only and free-first.

**Architecture:** Preserve the current `search_mesh -> acquisition -> evidence -> research -> goal/watch` stack, but harden it around six operational pillars: `ResearchMode`, `ProviderRegistry`, `CrossVerification`, `CheapRerank`, `GoalWatch`, and `Think/Act + Bounded Planning`. Every new capability must land behind our own contracts and data models, not external APIs or UI products.

**Tech Stack:** Python, existing `search_mesh`, `acquisition`, `evidence`, `research`, local evidence index, optional self-hosted SearXNG, optional crawl4ai, lexical/hybrid rerank, stable Python interface.

---

## Why V4 Exists

V3 set the right direction, but it still described the future state too abstractly. This plan is stricter:

- every major upgrade names the source repo we are copying from
- every upgrade names the exact `autosearch` file(s) to touch
- every upgrade defines the target data shape
- every upgrade includes explicit tests and acceptance criteria

This is not a product-vision document. It is a direct porting spec.

---

## Product Boundary

`autosearch` remains:

- a backend research/search runtime
- a reusable local Python interface
- a goal/watch execution engine

`autosearch` does **not** become:

- a chat UI
- a Perplexity clone
- an unconstrained LLM agent that invents tools at runtime

Public interface still stays small:

- `doctor(...)`
- `run_search_task(...)`
- `build_searcher_judge_session(...)`
- `run_goal_case(...)`
- `optimize_goal(...)`
- `optimize_goals(...)`
- `run_goal_benchmark(...)`
- `run_watch(...)`
- `run_watches(...)`

---

## Direct Port Matrix

This is the core "抄作业" table.

| Capability | Copy From | Exact Pattern to Port | Where It Lands in AutoSearch |
|---|---|---|---|
| Research modes | Vane | Speed / Balanced / Quality as distinct runtime recipes | `research/modes.py`, `goal_runtime.py`, `goal_bundle_loop.py` |
| Provider interface | Scira, Swirl | Strategy/registry based provider execution | `search_mesh/backends/*`, `search_mesh/registry.py`, `search_mesh/router.py` |
| Query transform | Swirl, SearXNG | Per-engine/per-platform query rewriting | `search_mesh/backends/*.py`, config layer if needed |
| URL dedup | Swirl, Scira | URL/domain dedup before expensive scoring | `rerank/lexical.py`, `goal_services.py` |
| Cheap rerank | Swirl, SearXNG | Pre-judge lexical/hybrid scoring | `rerank/hybrid.py`, `goal_services.py` |
| Intelligent extraction | Fireplexity, crawl4ai | Intro + relevant middle + conclusion, query-aware extraction | `acquisition/markdown_cleaner.py`, later `acquisition/content_filter.py` |
| Think/Act split | OpenManus, LangChain ODR | planner emits decision, executor only executes | `research/decision.py`, `research/planner.py`, `research/executor.py` |
| Bounded planning | OpenManus | plan mutation only through fixed operations | `research/planning_ops.py`, `goal_bundle_loop.py` |
| Cross verification | Scira, node-deepresearch | re-query same topic with alternate framing and compare | `research/planner.py`, `research/executor.py`, `research/synthesizer.py` |
| Gap queue | node-deepresearch | dynamic repair queue, separate from scoring dimensions | `research/gap_queue.py`, `goal_bundle_loop.py`, `research/planner.py` |
| Diary context | node-deepresearch | step log passed into next think step | `research/diary.py`, `research/planner.py`, `goal_bundle_loop.py` |
| Action disabling | node-deepresearch, Vane | disable search/reflect/answer based on state | `research/action_policy.py`, `research/planner.py` |
| Token budget | node-deepresearch | reserve answer budget and cap exploration budget | `research/budget.py`, `goal_runtime.py`, `goal_bundle_loop.py` |
| Async search | LangChain ODR, ddgs | gather+timeout+partial results | `goal_services.py`, maybe later `search_mesh/router.py` |
| Engine auto-suspension | SearXNG | consecutive-error suspension and cooldown | `source_capability.py`, `project_experience.py`, `doctor.py` |
| Semantic query dedup | Jina node-deepresearch | cosine dedup for near-duplicate queries | `query_dedup.py`, `research/planner.py` |
| Embedding chunk filter | GPT Researcher, Jina | keep semantically relevant chunks only | `acquisition/content_filter.py`, `evidence/normalize.py` |
| Goal watch runtime | Scira Lookouts | independent scheduled topic/goal watchers | `watch/models.py`, `watch/runtime.py`, `interface.py` |

---

## Target Runtime Objects

These are the internal contracts that must become stable inside the implementation.

### 1. `SearchProvider`

```python
class SearchProvider(Protocol):
    name: str
    roles: set[str]
    capabilities: set[str]
    supports_cross_verification: bool
    supports_acquisition_hints: bool

    def transform_query(self, query: str, context: dict[str, Any]) -> str: ...
    def search(self, query: str, config: dict[str, Any]) -> SearchHitBatch: ...
```

### 2. `ResearchModePolicy`

```python
@dataclass
class ResearchModePolicy:
    name: Literal["speed", "balanced", "deep"]
    enable_planning: bool
    enable_cross_verification: bool
    enable_acquisition: bool
    enable_recursive_repair: bool
    emit_research_packet: bool
    max_branch_depth: int
    max_plan_count: int
    max_queries: int
    rerank_profile: Literal["none", "lexical", "hybrid"]
```

### 3. `SearchDecision`

This is the explicit Think output.

```python
@dataclass
class SearchDecision:
    role: str
    mode: str
    provider_mix: list[str]
    search_backends: list[str]
    backend_roles: dict[str, list[str]]
    sampling_policy: dict[str, Any]
    acquisition_policy: dict[str, Any]
    evidence_policy: dict[str, Any]
    cross_verify: bool
    cross_verification_queries: list[dict[str, Any]]
    stop_if_saturated: bool
    rationale: str
```

### 4. `PlanningOp`

This is the only allowed plan mutation channel.

```python
TypedDict("PlanningOp", {
    "op": Literal[
        "add_branch",
        "retire_branch",
        "raise_budget",
        "mark_saturated",
        "request_cross_check",
    ],
    "target": str,
    "role": NotRequired[str],
    "mode": NotRequired[str],
    "amount": NotRequired[int],
    "mutation_kind": NotRequired[str],
})
```

### 5. `GapQueueItem`

```python
TypedDict("GapQueueItem", {
    "gap_id": str,
    "question": str,
    "dimension": str,
    "priority": int,
    "status": Literal["open", "satisfied", "retired"],
    "created_round": int,
})
```

### 6. `WatchSpec`

```python
@dataclass
class GoalWatch:
    watch_id: str
    goal_id: str
    mode: str
    frequency: str
    budget: dict[str, int]
    target_score: int
    plateau_rounds: int
    stop_rules: dict[str, Any]
    provider_preferences: list[str]
    success_threshold: int
```

---

## Upgrade Track 1: Research Modes

### What we are copying

From `Vane`:

- `Speed` is not "same pipeline but fewer rounds"
- `Balanced` requires some reasoning before action
- `Quality` changes search depth, search breadth, prompt shape, and output shape

### What we are implementing

We already have mode basics. V4 makes them strict and visible:

- `speed`
  - no cross verification by default
  - no acquisition by default
  - no recursive follow-up by default
  - rerank profile = `lexical`
- `balanced`
  - planning on
  - selective cross verification
  - selective acquisition
  - rerank profile = `hybrid`
- `deep`
  - mandatory `SearchDecision`
  - mandatory bounded planning ops
  - mandatory cross verification for weak branches
  - acquisition on follow-up/research branches
  - routeable research packet

### Files

- Modify: `research/modes.py`
- Modify: `research/mode_policy.py`
- Modify: `goal_runtime.py`
- Modify: `goal_bundle_loop.py`
- Modify: `interface.py`
- Test: `tests/test_modes.py`
- Test: `tests/test_interface.py`

### Remaining work

- Add mode-specific branch budget defaults
- Add mode-specific `action_policy`
- Add mode-specific stop heuristics

### Acceptance

- `mode="speed"` visibly disables cross-verification and acquisition unless explicitly overridden
- `mode="deep"` visibly enables both in planner/executor/synthesizer path

---

## Upgrade Track 2: Provider Registry + Per-Platform Query Transform

### What we are copying

From `Scira`:

- Strategy pattern for search backend

From `Swirl` and `SearXNG`:

- provider-specific query rewrite before execution

### What we are implementing

Already started. V4 finishes the "1:1 port" quality:

- every provider advertises:
  - `roles`
  - `capabilities`
  - `supports_cross_verification`
  - `supports_acquisition_hints`
  - `provider_family`
- every provider can rewrite queries using provider-native syntax

### Required transforms

- GitHub repos:
  - append `stars:>20` if no star filter exists
  - quote long entities
- GitHub issues/code:
  - quote framework names / repo names
- Reddit:
  - append `sort:relevance`
  - prefer discussion phrasing
- HN:
  - quote company/product names
  - bias to short noun phrases
- free web (`searxng`, `ddgs`):
  - keep broad text, but preserve extracted entities

### Files

- Modify: `search_mesh/backends/base.py`
- Modify: `search_mesh/backends/github_backend.py`
- Modify: `search_mesh/backends/web_backend.py`
- Modify: `search_mesh/backends/searxng_backend.py`
- Modify: `search_mesh/backends/ddgs_backend.py`
- Modify: `search_mesh/registry.py`
- Modify: `search_mesh/router.py`
- Test: `tests/test_search_mesh.py`

### Remaining work

- add `provider_family` for provider-aware dedup
- add classification-gated provider selection

### Acceptance

- same logical query produces different provider-native query strings
- runtime only depends on provider interface, not backend-specific branching

---

## Upgrade Track 3: Cheap Rerank + Dedup

### What we are copying

From `Swirl`, `Scira`, `SearXNG`, `Jina node-deepresearch`:

- pre-judge URL dedup
- hostname/domain constraints
- cheap ranking before expensive reasoning

### What we are implementing

Current lexical/hybrid rerank is phase one. V4 extends it to:

1. exact URL dedup
2. normalized URL dedup
3. optional domain cap
4. harmonic position scoring
5. optional semantic query dedup

### New scoring stack

```text
raw hits
-> normalize_url
-> dedup exact/normalized
-> lexical_score(query, title/snippet)
-> harmonic position bonus
-> provider/role bonus
-> optional embedding similarity
-> top-k to judge
```

### Files

- Modify: `rerank/lexical.py`
- Modify: `rerank/hybrid.py`
- Add: `query_dedup.py`
- Modify: `goal_services.py`
- Test: `tests/test_rerank.py`

### Remaining work

- semantic query dedup
- domain cap policy
- harmonic position weighting

### Acceptance

- duplicate URLs never reach expensive judge path
- low-value broad hits are filtered before bundle construction

---

## Upgrade Track 4: Intelligent Content Extraction

### What we are copying

From `Fireplexity` and `crawl4ai`:

- select intro
- select best matching middle paragraphs
- keep conclusion
- favor query-aware extraction over naive truncation

### What we are implementing

Current `fit_markdown` heuristic is phase one. V4 finishes it with two levels:

1. cheap keyword overlap scoring
2. optional embedding/BM25 chunk filter

### Files

- Modify: `acquisition/markdown_cleaner.py`
- Add: `acquisition/content_filter.py`
- Modify: `evidence/normalize.py`
- Modify: `research/executor.py`
- Test: `tests/test_acquisition_pipeline.py`
- Test: `tests/test_evidence_normalize.py`

### Acceptance

- extracted content preserves intro + best evidence paragraphs + conclusion
- deep mode prefers acquired, filtered content over raw snippets

---

## Upgrade Track 5: Think / Act Split

### What we are copying

From `OpenManus`, `Vane`, `open_deep_research`:

- reasoning happens before action
- decision is explicit
- action layer does not silently re-reason

### What we are implementing

This track is already partially done. V4 completes the split:

- planner emits:
  - `queries`
  - `decision`
  - `planning_ops`
- executor consumes:
  - `decision`
  - `planning_ops`
  - current state
- loop orchestrates only:
  - selected candidate
  - acceptance
  - evolution feedback

### Files

- Modify: `research/planner.py`
- Modify: `research/executor.py`
- Modify: `goal_bundle_loop.py`
- Test: `tests/test_research_flow.py`

### Acceptance

- executor can run solely from planner output
- decision object is persisted in round artifacts
- planning ops are visible in runtime state

---

## Upgrade Track 6: Bounded Planning Operations

### What we are copying

From `OpenManus` planning flow:

- plans can change during runtime
- but only through explicit, controlled operations

### Allowed ops

- `add_branch`
- `retire_branch`
- `raise_budget`
- `mark_saturated`
- `request_cross_check`

### Files

- Modify: `research/planning_ops.py`
- Modify: `goal_bundle_loop.py`
- Modify: `goal_runtime.py`
- Test: `tests/test_research_flow.py`
- Test: `tests/test_goal_bundle_loop.py`

### Remaining work

- persist op history per round in runtime lineage
- expose op summary in routeable output

### Acceptance

- no direct arbitrary plan mutation
- all runtime plan mutations happen through op schema

---

## Upgrade Track 7: Cross Verification

### What we are copying

From `Scira` and `node-deepresearch`:

- search same topic from multiple angles
- ask contrast/comparison/limitations style follow-ups
- track disagreement / contradiction signals

### What we are implementing

- planner generates alternate framing queries
- executor executes them as verification branch
- synthesizer reports:
  - provider diversity
  - domain diversity
  - contradiction signals
  - consensus strength

### Files

- Modify: `research/planner.py`
- Modify: `research/executor.py`
- Modify: `research/synthesizer.py`
- Modify: `research/routeable_output.py`
- Test: `tests/test_research_flow.py`

### Acceptance

- deep/balanced modes can explicitly mark branches as cross-verified
- routeable output exposes verification summary

---

## Upgrade Track 8: Gap Queue + Action Policy

### What we are copying

From `node-deepresearch`:

- FIFO gap queue
- action disabling based on current state
- diary context to carry narrative state

### Important rule

Do **not** replace dimension scoring with gap queue.

- dimensions stay in judge
- gap queue drives repair work

### New modules

- `research/gap_queue.py`
- `research/action_policy.py`
- `research/diary.py`

### Files

- Add: `research/gap_queue.py`
- Add: `research/action_policy.py`
- Add: `research/diary.py`
- Modify: `goal_bundle_loop.py`
- Modify: `research/planner.py`
- Modify: `research/synthesizer.py`
- Test: `tests/test_research_flow.py`
- Test: `tests/test_goal_bundle_loop.py`

### Acceptance

- planner can say “don’t search again, too many unread URLs”
- diary summary feeds into next think step
- gap queue tracks open/satisfied/retired gaps per run

---

## Upgrade Track 9: Token Budget + Async/Partial Execution

### What we are copying

From `node-deepresearch`, `LangChain open_deep_research`, `ddgs`:

- explicit budget split
- parallel search
- timeout + partial results

### New policy

```python
{
  "explore_budget_pct": 0.85,
  "answer_budget_pct": 0.15,
  "provider_timeout_seconds": 10,
  "parallel_provider_limit": 6,
}
```

### Files

- Add: `research/budget.py`
- Modify: `goal_services.py`
- Modify: `search_mesh/router.py`
- Modify: `goal_runtime.py`
- Test: `tests/test_goal_bundle_loop.py`
- Test: `tests/test_search_mesh.py`

### Acceptance

- slow providers do not block the round
- runtime can stop on budget, not just plateau

---

## Upgrade Track 10: Watch Runtime Hardening

### What we are copying

From `Scira Lookouts`:

- each topic watch has its own cadence, budget, mode, threshold

### What we are implementing

Current watch runtime exists. V4 completes it with:

- explicit stop policies
- success threshold semantics
- independent provider preferences
- run summary fields usable by external schedulers

### Files

- Modify: `watch/models.py`
- Modify: `watch/runtime.py`
- Modify: `interface.py`
- Test: `tests/test_watch_runtime.py`

### Acceptance

- each watch can be tuned independently
- watch output contains enough fields for a scheduler/reporting layer

---

## Upgrade Track 11: Final Purification

### Goal

Make the hot path:

```text
SearchHit -> EvidenceRecord -> ResearchBundle -> Judge -> RouteableOutput
```

with legacy compatibility only at the outermost edge.

### Files

- Modify: `goal_services.py`
- Modify: `evaluation_harness.py`
- Modify: `research/executor.py`
- Modify: `interface.py`
- Test: `tests/test_evidence_normalize.py`
- Test: `tests/test_search_mesh.py`

### Acceptance

- legacy adapters are edge-only
- research runtime operates on native evidence objects

---

## Phase Order

### Phase 1: Finish the current runtime contracts

- Track 2
- Track 3
- Track 4
- Track 11

### Phase 2: Finish the agentic core

- Track 5
- Track 6
- Track 7
- Track 8

### Phase 3: Harden runtime economics

- Track 1 remaining work
- Track 9
- Track 10

---

## Final Acceptance Criteria

The plan is complete only when all of the following are true:

1. `mode="speed"` / `mode="balanced"` / `mode="deep"` visibly change runtime behavior, not just parameters.
2. Search providers are registered and swappable without editing the loop.
3. Same-topic cross-verification is part of the runtime, not a manual tactic.
4. Cheap rerank filters candidates before expensive judge calls.
5. Independent watches run with their own mode/budget/threshold.
6. Think/act split is explicit through `SearchDecision`.
7. Planning mutations happen only through bounded ops.
8. Gap queue, diary, and action policy exist for deep runs.
9. Timeout + partial results prevent slow providers from blocking rounds.
10. Hot path is native `SearchHit -> EvidenceRecord -> ResearchBundle`.

If a feature does not move one of those ten statements closer to truth, it is not part of this upgrade.
