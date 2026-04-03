# AutoSearch Super Search V3 Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Upgrade `autosearch` into a generic, autonomous, self-evolving super AI search backend with explicit execution modes, provider registry, cross-verification, cheap reranking, and independent goal watches.

**Architecture:** Keep `autosearch` as backend infrastructure, not a Perplexity-style frontend product. Center the system on five runtime layers: `ResearchMode`, `ProviderRegistry`, `CrossVerification`, `CheapRerank`, and `GoalWatch`, while preserving free-first search, evidence-first processing, and goal-driven optimization.

**Tech Stack:** Python, existing `search_mesh`, acquisition and evidence runtime, local evidence index, optional self-hosted SearXNG, optional crawl4ai, native rerank pipeline, stable Python interface.

---

## Why This Plan Exists

The previous plans moved `autosearch` from a broad scout loop toward a stronger research runtime:

- free-first search mesh
- acquisition and evidence normalization
- local evidence index
- research planner / executor / synthesizer
- evolving search program
- stable interface

That was necessary, but it still leaves one product-level weakness:

`autosearch` behaves like a strong internal runtime, but not yet like a clearly mode-driven, provider-agnostic, verification-aware super search system.

The most useful competitor patterns are not UI patterns. They are backend execution patterns:

- `Vane`: three distinct research modes
- `Scira`: provider strategy pattern, extreme/deep search, cross-angle search
- `Khoj`: memory-backed multi-step research loop, light retrieval before expensive reasoning
- `Swirl`: query transformation, dedup, connector discipline
- `OpenManus`: think/act split and bounded plan mutation

This plan absorbs those ideas without turning `autosearch` into a user-facing search app.

---

## Product Boundary

`autosearch` remains:

- a backend search and research runtime
- a reusable local Python interface
- a goal/watch execution engine

`autosearch` does **not** become:

- a frontend chat app
- a Perplexity clone
- an unconstrained LLM agent that controls everything

Public interface remains small:

- `doctor(...)`
- `run_search_task(...)`
- `build_searcher_judge_session(...)`
- `run_goal_case(...)`
- `optimize_goal(...)`
- `optimize_goals(...)`
- `run_goal_benchmark(...)`

New capability should be exposed through these contracts, not through scattered internal modules.

---

## New Target Product Thesis

The target product is:

**a generic, mode-aware, provider-pluggable, evidence-first, self-evolving search backend**

The runtime should work like this:

1. Caller starts a search or goal/watch task.
2. Runtime selects a `ResearchMode`.
3. Think phase decides:
   - what to search next
   - which providers/backends to use
   - whether to cross-verify
   - whether to acquire pages
   - whether to stop
4. Act phase executes search, acquisition, rerank, and evidence extraction.
5. Cross-verification checks same topic from multiple angles.
6. Cheap rerank trims obvious junk before LLM judge.
7. Evidence bundle is judged.
8. Search program and watch state evolve.
9. Runtime stops on target, plateau, or budget limit.

---

## Non-Negotiable Constraints

### 1. Free-first remains default

Default path must prefer free/open sources and self-hosted options.

### 2. Backend, not frontend

We can emit cited answers and research packets, but must not recenter the project around interactive UI.

### 3. Goal and judge remain fixed

Search evolves. Scoring standards do not drift during a run.

### 4. LLM autonomy remains bounded

The runtime may plan, reprioritize, and mutate searches, but only through controlled policy objects and bounded planning operations.

### 5. Generic first

Improvements must help:

- broad discovery
- code search
- research synthesis
- project goals
- standing watches

No feature should only make sense for one benchmark.

---

## Core Upgrades

## Upgrade 1: `ResearchMode`

Add explicit runtime modes:

- `speed`
- `balanced`
- `deep`

These are not just loop-count presets. They define whole execution strategies.

### `speed`

Use for:

- lightweight discovery
- broad scouting
- cheap periodic watches

Behavior:

- minimal planning
- no cross-verification by default
- no acquisition by default
- no recursive repair graph
- cheap rerank only
- short output

### `balanced`

Use for:

- most goal cases
- moderate-depth research
- targeted watches

Behavior:

- planning enabled
- selective acquisition
- selective cross-verification
- limited repair depth
- judge-backed keep/discard
- routeable output

### `deep`

Use for:

- hard goals
- difficult benchmarks
- high-value recurring watches

Behavior:

- explicit think/act loop
- decomposition branches
- cross-verification required for weak dimensions
- acquisition on priority branches
- recursive repair
- routeable research packet output
- budget-aware stop rules

### Required code changes

- Add `mode` to `SearchProgram`
- Add `mode` to goal/watch config
- Add `ModePolicy` module under `research/`
- Teach planner, executor, synthesizer, selector to branch on mode
- Document mode semantics in README and standards

### What We Are Copying

From `Vane`, copy the idea that each mode is a **different runtime recipe**, not a simple round-count.

What we are explicitly porting:

- `speed` as low-cost direct search mode
- `balanced` as default research mode
- `deep` as explicit multi-step research mode

What we are **not** porting:

- frontend chat UX
- report formatting as product center

### Concrete implementation

Add:

- `research/modes.py`
- `research/mode_policy.py`

Define:

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
    rerank_profile: str
```

`SearchProgram` must gain:

- `mode`
- `mode_policy_overrides`

`goal_cases/*.json` and future watch configs must allow:

- `"mode": "speed" | "balanced" | "deep"`

### Files to touch

- Modify: `goal_runtime.py`
- Modify: `goal_bundle_loop.py`
- Modify: `research/planner.py`
- Modify: `research/executor.py`
- Modify: `research/synthesizer.py`
- Modify: `selector.py`
- Modify: `interface.py`
- Modify: `README.md`

### Tests

- `tests/test_modes.py`
- `tests/test_goal_runtime.py`
- `tests/test_interface.py`

Assertions:

- `speed` disables acquisition and cross-verification by default
- `balanced` enables selective planning and limited repair
- `deep` enables recursive branches and emits research packet output

---

## Upgrade 2: `ProviderRegistry + SearchProvider`

Make provider integration fully registry-driven.

### Target contract

Each provider/backend should register:

- `name`
- `roles`
- `capabilities`
- `search(query, config) -> SearchHitBatch`
- `transform_query(...)`
- `supports_cross_verification`
- `supports_acquisition_hints`

### Why

Current `search_mesh` is much better than the old hardcoded `engine.py`, but the next step is to make provider integration feel native and composable, not just routed.

### Design

- `search_mesh/registry.py`
- `search_mesh/providers/base.py`
- provider files register themselves
- runtime consumes registry metadata, not hand-maintained provider name lists

### Required code changes

- Move remaining provider-specific branching out of `goal_services.py` / `engine.py`
- Attach platform-specific query transforms directly to provider implementations
- Attach provider role metadata:
  - `breadth`
  - `code`
  - `discussion`
  - `academic`
  - `web`
  - `verification`

### What We Are Copying

From `Scira`, copy the strategy pattern.
From `Swirl`, copy connector discipline and query transformation.

What we are porting:

- registry-owned provider lookup
- provider-specific query transforms
- provider role metadata
- runtime choosing providers by role/capability, not hardcoded names

### Concrete implementation

Add:

- `search_mesh/providers/__init__.py`
- `search_mesh/providers/base.py`
- `search_mesh/registry.py`

Define:

```python
class SearchProvider(Protocol):
    name: str
    roles: set[str]
    capabilities: dict[str, Any]

    def transform_query(self, query: str, context: dict[str, Any]) -> str: ...
    def search(self, query: str, config: dict[str, Any]) -> SearchHitBatch: ...
```

Registry API:

```python
register_provider(provider: SearchProvider) -> None
get_provider(name: str) -> SearchProvider
providers_for_role(role: str) -> list[SearchProvider]
```

Per-provider transforms to implement first:

- GitHub:
  - quote repo/entity names when confidence is high
  - append repo/code-friendly qualifiers
- Reddit:
  - relevance-friendly framing
- HN:
  - quoted product/entity search
- academic/web:
  - longer noun-phrase preservation, fewer noisy suffixes

### Files to touch

- Modify: `search_mesh/router.py`
- Modify: `search_mesh/provider_policy.py`
- Modify: `goal_services.py`
- Modify: `engine.py`
- Add/modify provider backend files under `search_mesh/backends/`

### Tests

- `tests/test_search_mesh.py`
- `tests/test_provider_registry.py`

Assertions:

- provider registration works without core-loop edits
- provider query transforms are applied before dispatch
- role-based provider selection works

---

## Upgrade 3: `CrossVerification`

This is the highest-value quality upgrade.

The runtime must stop treating “found something relevant” as sufficient.

### Required behaviors

For the same topic or weak dimension, the runtime should:

- query from multiple angles
- query with multiple providers
- compare evidence for agreement vs contradiction
- emit explicit gap/contradiction signals

### Verification patterns

- `framing variation`
  - different query phrasings for same topic
- `source variation`
  - code source + discussion source + web source
- `evidence contradiction`
  - detect disagreement or incomplete support
- `coverage gap`
  - identify subclaims with only one weak source

### Runtime placement

This belongs in:

- `research/planner.py`
- `research/executor.py`
- `research/synthesizer.py`

It should not be an afterthought in scoring.

### New artifacts

- `verification_groups`
- `contradictions`
- `unsupported_claims`
- `cross_verified_claims`

### What We Are Copying

From `Scira Extreme Search`, copy:

- same-topic multi-angle search
- contradiction-seeking behavior
- multi-source verification before synthesis

### Concrete implementation

Add cross-verification branch types:

- `verification-framing`
- `verification-source`
- `verification-contradiction`

Planner behavior:

- when a dimension is weak, generate 2-3 framing variants
- assign at least two different provider roles
- add contradiction-check branch if claims disagree or only one source supports them

Synthesizer must produce:

```python
{
  "verification_groups": [...],
  "cross_verified_claims": [...],
  "unsupported_claims": [...],
  "contradictions": [...]
}
```

Judge input must include these explicitly so score depends on verified coverage, not just evidence count.

### Files to touch

- Modify: `research/planner.py`
- Modify: `research/executor.py`
- Modify: `research/synthesizer.py`
- Modify: `research/routeable_output.py`
- Modify: `goal_judge.py`

### Tests

- `tests/test_research_flow.py`
- `tests/test_goal_judge.py`

Assertions:

- same topic generates more than one framing in deep mode
- contradictions surface in synthesized bundle
- verified claims are distinguishable from single-source claims

---

## Upgrade 4: `Cheap Rerank Before Judge`

This is mandatory for cost and speed.

### Target pipeline

1. raw search hits
2. exact URL dedup
3. cheap lexical/hybrid scoring
4. optional semantic rerank
5. acquisition/evidence extraction
6. LLM judge on top candidates only

### Cheap rerank layers

- exact URL dedup
- normalized query dedup
- lexical relevance score
- provider confidence hints
- domain penalties/bonuses
- optional embedding similarity
- optional cross-encoder rerank

### Why

Right now the expensive layer still sees too much junk.

### Required code changes

- new `rerank/` package
- `lexical.py`
- `hybrid.py`
- optional `semantic.py`
- integrate ahead of evidence/judge hot path

### Success condition

LLM judge should see:

- fewer candidates
- higher relevance density
- lower duplicate rate

### What We Are Copying

From `Khoj`, copy the layered retrieval mindset:

- cheap retrieval first
- expensive rerank second
- LLM last

From `Swirl` and `open_deep_research`, copy pre-judge URL dedup.

### Concrete implementation

Add:

- `rerank/__init__.py`
- `rerank/lexical.py`
- `rerank/hybrid.py`
- `rerank/semantic.py` (optional)

Pipeline:

1. normalize URL
2. exact URL dedup
3. normalized query dedup
4. lexical score:
   - query term overlap
   - title weight
   - snippet weight
   - provider/domain priors
5. hybrid score:
   - lexical + provider confidence + source role fit
6. semantic rerank only in `balanced/deep`
7. pass top-N to acquisition / judge

First milestone should be **purely non-LLM**:

- exact URL dedup
- lexical rerank
- hybrid rerank

Semantic rerank comes second.

### Files to touch

- Modify: `goal_services.py`
- Modify: `search_mesh/router.py`
- Modify: `research/executor.py`
- Modify: `interface.py`

### Tests

- `tests/test_rerank.py`
- `tests/test_search_mesh.py`

Assertions:

- duplicate URLs are removed before evidence extraction
- cheap rerank changes ordering
- LLM judge receives a smaller candidate pool in `balanced/deep`

---

## Upgrade 5: `GoalWatch / Lookout`

Turn goals into independent, scheduled watches.

### Each watch must own

- `goal_id`
- `mode`
- `frequency`
- `budget`
- `target_score`
- `plateau_rules`
- `stop_rules`
- `provider preferences`
- `watch history`

### Why

Not all goals should share one daily runtime behavior.

### Watch types

- `discovery_watch`
- `repair_watch`
- `verification_watch`
- `deep_research_watch`

### Required code changes

- new `watch/` package
- watch config schema
- watch state persistence
- watch scheduler entrypoint
- interface support for:
  - `run_watch(...)`
  - `run_watches(...)`

### What We Are Copying

From `Scira Lookouts`, copy:

- topic/watch independence
- per-watch cadence and budget
- watch-specific research behavior

### Concrete implementation

Add:

- `watch/models.py`
- `watch/runtime.py`
- `watch/scheduler.py`

Watch contract:

```python
{
  "watch_id": "goal-capability-doctor-daily",
  "goal_id": "autosearch-capability-doctor",
  "mode": "balanced",
  "frequency": "daily",
  "budget": {"queries": 12, "pages": 6},
  "target_score": 90,
  "plateau_rules": {...},
  "stop_rules": {...}
}
```

State contract:

- last run time
- last accepted score
- score trend
- retired families
- next scheduled run

### Files to touch

- Modify: `interface.py`
- Modify: `README.md`
- Add watch package

### Tests

- `tests/test_watch_runtime.py`
- `tests/test_interface.py`

Assertions:

- watches run independently
- mode/budget/threshold differ per watch
- one watch reaching plateau does not block others

---

## Upgrade 6: `Think / Act Split`

Borrow the right part of OpenManus without over-agentifying the runtime.

### Think phase decides

- next branch
- next provider set
- next query family
- whether to acquire pages
- whether to cross-check
- whether to deepen or stop

### Act phase performs

- search dispatch
- rerank
- acquisition
- evidence normalization
- local indexing

### Why

Current loop has planning and execution mixed in too many places.

### Required structure

- `research/reasoning.py`
- `research/actions.py`
- `SearchDecision` contract

The think phase should not execute tools.
The act phase should not decide policy.

### What We Are Copying

From `OpenManus`, copy:

- think/act separation
- not the conversational agent shell

### Concrete implementation

Define:

```python
@dataclass
class SearchDecision:
    branch_id: str
    query_specs: list[dict[str, Any]]
    provider_names: list[str]
    mode: str
    acquire_pages: bool
    cross_verify: bool
    stop: bool = False
    reason: str | None = None
```

`research/reasoning.py` owns:

- convert current bundle/evolution state into `SearchDecision`
- decide next branch/provider/query family
- apply bounded planning ops

`research/actions.py` owns:

- provider dispatch
- rerank
- acquisition
- evidence normalization
- local evidence indexing

### Files to touch

- Modify: `goal_bundle_loop.py`
- Modify: `research/planner.py`
- Modify: `research/executor.py`
- Add `research/reasoning.py`
- Add `research/actions.py`

### Tests

- `tests/test_reasoning.py`
- `tests/test_research_flow.py`

Assertions:

- decisions are serializable/stable
- act layer executes without policy branching
- think layer makes no provider/network calls

---

## Upgrade 7: `Bounded Planning Operations`

Planning should be mutable, but only through safe operations.

### Allowed plan ops

- `add_branch`
- `retire_branch`
- `raise_priority`
- `lower_priority`
- `request_cross_check`
- `mark_saturated`
- `raise_acquisition`
- `reduce_budget`

### Why

We want adaptive planning without letting the runtime become an unconstrained agent.

### Required code changes

- `research/planning_ops.py`
- planner outputs op lists
- runtime validates and applies ops

### What We Are Copying

From `OpenManus PlanningTool`, copy:

- plan mutation during execution

What we are **not** copying:

- unconstrained arbitrary plan editing

### Concrete implementation

Define op schema:

```python
@dataclass
class PlanningOp:
    op: Literal[
        "add_branch",
        "retire_branch",
        "raise_priority",
        "lower_priority",
        "request_cross_check",
        "mark_saturated",
        "raise_acquisition",
        "reduce_budget",
    ]
    payload: dict[str, Any]
    reason: str
```

Runtime must validate:

- branch target exists or can be created
- budget changes remain inside mode policy bounds
- cross-check is only requested for active branches

### Files to touch

- Add `research/planning_ops.py`
- Modify `research/planner.py`
- Modify `goal_runtime.py`
- Modify `goal_bundle_loop.py`

### Tests

- `tests/test_planning_ops.py`

Assertions:

- invalid ops are rejected
- valid ops mutate plan state deterministically

---

## Upgrade 8: `Evidence-First Purity`

Finish the migration so hot paths are natively:

`SearchHit -> EvidenceRecord -> ResearchBundle`

### Remaining cleanup goals

- remove legacy `SearchResult` assumptions from search hot path
- keep legacy compatibility only at outer adapters
- make judge/harness consume only normalized evidence/bundle objects

### Concrete implementation

Formalize:

- `SearchHit` as search-only contract
- `EvidenceRecord` as acquired/normalized evidence contract
- `ResearchBundle` as synthesis/judge contract

Legacy adapters should remain only in:

- `evidence/legacy_adapter.py`
- interface compatibility helpers

Not in:

- `research/executor.py`
- `evaluation_harness.py`
- `goal_judge.py`

### Files to touch

- Modify: `goal_services.py`
- Modify: `evaluation_harness.py`
- Modify: `research/executor.py`
- Modify: `goal_judge.py`

### Tests

- `tests/test_evidence_pipeline.py`

Assertions:

- judge only consumes normalized bundle objects
- legacy objects do not appear in research hot path

---

## Upgrade 9: `Research Graph Strengthening`

Current graph is useful but still too heuristic.

### Add

- branch scheduler
- branch budget enforcement
- recursive depth policy
- merge policy
- prune policy
- branch family inheritance

### New graph artifacts

- `branch_priority`
- `branch_budget`
- `branch_status`
- `merge_group`
- `prune_reason`
- `graph_scheduler_hints`

### What We Are Copying

From `MindSearch` and `deep-research`, copy:

- explicit subproblem graphing
- deeper follow-up decomposition
- graph-driven scheduling instead of flat cycling

### Concrete implementation

Add scheduler behavior:

- weighted branch queue
- recursive depth guard
- merge groups for similar subgoals
- prune groups for saturated or duplicated branches

Planner should produce:

- branch node
- branch type
- branch subgoal
- branch priority
- branch budget
- merge group

Synthesizer should produce:

- `merge_candidates`
- `prune_candidates`
- `next_branch_mode`
- `graph_scheduler_hints`

### Files to touch

- Modify: `research/planner.py`
- Modify: `research/synthesizer.py`
- Modify: `research/routeable_output.py`
- Modify: `goal_runtime.py`

### Tests

- `tests/test_research_graph.py`

Assertions:

- graph scheduler prefers highest priority under budget
- saturated branches can be pruned
- related branches can be merged

---

## Upgrade 10: `Program Evolution That Feeds Back`

Current evolution is strong but still too observational.

### Evolution stats should drive:

- provider promotion/demotion
- branch family retirement
- mutation kind retirement
- mode switching suggestions
- watch escalation or cooldown

### New policy outputs

- `effective_mutation_families`
- `retired_mutation_families`
- `mode_success_rates`
- `provider_role_success_rates`
- `verification_payoff_stats`

### Concrete implementation

Evolution stats must influence:

- planner branch family selection
- provider role promotion/demotion
- mode escalation from `speed -> balanced -> deep`
- family retirement and reactivation

Add:

- `evolution/provider_stats.py`
- `evolution/mutation_stats.py`

At minimum, `goal_runtime.py` should persist:

- success count by mode
- success count by provider role
- success count by verification branch type

### Files to touch

- Modify: `goal_runtime.py`
- Modify: `selector.py`
- Modify: `research/planner.py`
- Modify: `goal_bundle_loop.py`

### Tests

- `tests/test_evolution_feedback.py`

Assertions:

- retired mutation families are deprioritized
- strong provider roles are promoted
- mode suggestions change with performance

---

## Upgrade 11: `Competitor Techniques We Should Port Immediately`

These are the highest-value copyable ideas from competitor analysis.

### Immediate ports

- exact URL dedup before judge
- per-provider query transformation
- intelligent paragraph selection for acquisition
- FIFO gap queue as repair layer
- information-dense evidence extraction

### Second-wave ports

- semantic query dedup
- stronger contradiction extraction
- deeper follow-up query synthesis

### Exact ports to do first

1. **Per-platform query transformation**
   - land in provider implementations, not `engine.py`
   - first targets:
     - GitHub
     - Reddit
     - HN
     - academic/web

2. **URL dedup before scoring**
   - land at search mesh / executor boundary
   - exact dedup first, semantic near-dup later

3. **Intelligent content extraction**
   - paragraph scoring by query keywords
   - preserve intro/conclusion
   - replace naive `fit_markdown` truncation

4. **Information-dense evidence extraction**
   - enforce via schema and extraction pipeline
   - not only via prompt wording

5. **FIFO gap queue**
   - use as repair axis
   - do not replace dimension scoring axis

6. **Embedding-based query dedup**
   - second wave after cheap normalized dedup

---

## Implementation Order

## Phase 1: Modes + Registry

1. add `ResearchMode`
2. add `ModePolicy`
3. formalize `ProviderRegistry`
4. move provider query transforms into providers

Deliverables:

- `research/modes.py`
- `research/mode_policy.py`
- `search_mesh/registry.py`
- provider-native query transforms
- tests for mode behavior and provider registration

## Phase 2: Verification + Cheap Rerank

1. URL dedup before judge
2. lexical/hybrid rerank
3. optional semantic rerank
4. cross-verification artifacts in research flow

Deliverables:

- `rerank/`
- exact URL dedup
- lexical/hybrid rerank
- cross-verification bundle fields
- paragraph-level intelligent extraction

## Phase 3: Watch Runtime

1. watch config/state
2. watch scheduler
3. interface support
4. mode-aware watch execution

Deliverables:

- `watch/`
- watch state files
- watch scheduler
- interface methods

## Phase 4: Think/Act + Planning Ops

1. `SearchDecision`
2. reasoning/actions split
3. bounded planning ops
4. migrate deep mode to think/act loop

Deliverables:

- `SearchDecision`
- `research/reasoning.py`
- `research/actions.py`
- `research/planning_ops.py`

## Phase 5: Graph + Evolution Hardening

1. stronger graph scheduler
2. branch merge/prune
3. evolution feedback into planner
4. deeper repair on hard goals

Deliverables:

- stronger graph scheduler
- merge/prune logic
- evolution-fed planning
- family/provider/mode performance stats

## Phase 6: Final Purification

1. move remaining compatibility bridges to edge adapters
2. finish evidence-first hot path
3. refresh docs and benchmarks

Deliverables:

- hot path only uses `SearchHit -> EvidenceRecord -> ResearchBundle`
- compatibility bridges live only at adapters
- refreshed benchmark reports

---

## Acceptance Criteria

The upgrade is complete when all of the following are true:

1. `autosearch` supports `speed`, `balanced`, and `deep` modes with materially different execution behavior.
2. Providers are registry-driven and strategy-driven; new providers do not require core loop edits.
3. Same-topic cross-verification is part of the main research flow.
4. Cheap rerank happens before LLM judge.
5. Goals can run as independent watches with their own frequency, budget, and stop rules.
6. Deep mode uses bounded think/act planning rather than one fixed loop.
7. Hot path is natively `SearchHit -> EvidenceRecord -> ResearchBundle`.
8. Hard goals improve because of stronger graph/evolution behavior, not only because more sources were added.
9. Public interface stays small and stable.

---

## What We Explicitly Will Not Build Now

- a frontend chat/search product
- a Perplexity clone
- unconstrained all-tool autonomous agents
- a giant MCP-dependent runtime
- premium-API-first defaults

---

## End State

At the end of this plan, `autosearch` should feel like:

- a generic search backend
- a deep research backend
- a self-evolving goal/watch optimizer
- a free-first evidence engine

In short:

**自主进化的超级 AI 搜索**
