# AutoSearch Super Upgrade Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Rebuild `autosearch` into a self-hostable, free-first, deeply agentic AI search engine that can search broadly, clean and extract evidence, reason over results, iteratively improve its own search program, and expose a stable local interface to any project without depending on external product boundaries such as third-party APIs, MCP servers, or hosted search tools.

**Architecture:** Keep `autosearch` as the only product boundary. Aggressively borrow implementation patterns, internal abstractions, and proven workflows from `SearXNG`, `ddgs`, `Crawl4AI`, `GPT Researcher`, `MindSearch`, `Meilisearch`, `deep-searcher`, `search4all`, and `openperplex_backend_os`, but re-implement the durable core in our own modules and contracts. Paid APIs and MCP integrations may remain optional adapters, but the mainline system must work in a free-first, self-hostable mode.

**Tech Stack:** Python, existing `autosearch` runtime, local search/adaptation modules, optional self-hosted `SearXNG`, optional `Meilisearch`, internal fetch/render/markdown pipeline, OpenRouter judge only as an optional evaluator, local JSON artifacts, stable Python interface layer.

---

## Executive Thesis

The next version of `autosearch` should not be “a better wrapper around Exa/Tavily”. It should become a complete local research runtime with six native strengths:

1. **Search Mesh**
   - Free-first
   - Multi-engine
   - Query-routing aware
   - Source-specific when needed

2. **Acquisition**
   - URL fetch
   - Rendering fallback
   - Content cleaning
   - Citation/reference preservation

3. **Evidence Extraction**
   - Convert noisy pages into normalized evidence records
   - Separate raw hits from usable evidence

4. **Research Orchestration**
   - Plan
   - Search
   - Acquire
   - Extract
   - Synthesize
   - Route

5. **Autoresearch-Style Optimization**
   - Fixed goal
   - Fixed judge
   - Evolving search program
   - Population and selection
   - Plateau and ceiling detection

6. **Stable Product Interface**
   - One local Python boundary
   - No caller dependence on internal modules
   - Easy “optimize this goal” entrypoints

The point is not just “search more”. The point is to make `autosearch` itself into a reusable local search intelligence engine.

---

## Hard Constraints

These are non-negotiable design constraints for the upgrade.

### Constraint 1: No external product dependency at the core

The upgraded system must not require:

- hosted search APIs as the default path
- MCP servers as the primary runtime path
- third-party app surfaces as product boundaries

Allowed:

- optional adapters
- optional premium fallback
- optional self-hosted deployments we control

Not allowed:

- “this works only if Exa/Tavily/MCP is configured”

### Constraint 2: Free-first by default

If the machine has no premium API keys, the system should still be useful and complete.

### Constraint 3: Normalize everything into our own contracts

Every borrowed capability must be translated into our own:

- search hit contract
- acquisition contract
- evidence record contract
- search program contract
- benchmark contract
- interface contract

### Constraint 4: Preserve our optimization core

We already have the part most open-source search projects do not:

- `goal_case`
- `goal_judge`
- `goal_bundle_loop`
- `goal_runtime`
- `selector`
- `interface`

That must remain the center of gravity.

---

## Open-Source Borrowing Map

This section defines what to borrow from each project and what not to borrow.

## 1. `SearXNG`

Repository:
- <https://github.com/searxng/searxng>

### What it teaches us

- Multi-engine metasearch behind a single internal abstraction
- Free-first search breadth
- Engine-specific configuration without exposing that complexity to callers
- Search as a mesh, not a single backend

### What to copy

- Internal concept of engines grouped behind one search surface
- Query adaptation per backend
- Engine capability/health handling
- Provider diversity as default

### What not to copy

- Product boundary
- Full external API shape
- The assumption that HTML snippets are enough for downstream AI use

### How it should show up in `autosearch`

- Native `searxng_backend.py`
- Native `search_mesh/router.py`
- Native free-first backend tiering

## 2. `ddgs`

Repository:
- <https://github.com/deedy5/ddgs>

### What it teaches us

- Lightweight metasearch in Python
- Convenient fallback across many engines
- Good fit for local runtime code

### What to copy

- Lightweight multi-engine fallback style
- Pythonic backend adapters
- Fast text/image/news backend routing model

### What not to copy

- Treating it as the long-term core abstraction

### How it should show up in `autosearch`

- As a light search backend adapter or local fallback
- As a reference for search backend ergonomics

## 3. `Crawl4AI`

Repository:
- <https://github.com/unclecode/crawl4ai>

### What it teaches us

- Search results are not useful enough; acquisition matters
- Clean markdown matters
- Fit markdown matters
- Structured extraction matters
- Citations/references matter

### What to copy

- Fetch -> render -> clean markdown -> fit markdown -> extraction pipeline
- Citation preservation
- Noise reduction before LLM use
- Schema-driven extraction hooks

### What not to copy

- Make `Crawl4AI` itself the permanent boundary
- Hard runtime dependency if we can internalize the core pieces

### How it should show up in `autosearch`

- Native `acquisition/`
- Native `markdown_cleaner.py`
- Native `evidence/normalize.py`
- Optional `crawl4ai_adapter.py`, not mandatory

## 4. `GPT Researcher`

Repository:
- <https://github.com/assafelovic/gpt-researcher>

### What it teaches us

- Research should be a workflow, not just a query
- Planner / researcher / publisher split works
- Search results need synthesis
- Reports are end products, not just raw findings

### What to copy

- Planner / executor / synthesizer flow
- Research question decomposition
- Multi-step search plan execution
- Evidence synthesis mindset

### What not to copy

- The whole app boundary
- Its external service assumptions

### How it should show up in `autosearch`

- Native `research/planner.py`
- Native `research/executor.py`
- Native `research/synthesizer.py`

## 5. `MindSearch`

Repository:
- <https://github.com/InternLM/MindSearch>

### What it teaches us

- Search is often a graph, not a straight line
- Multi-agent reasoning over search tasks can outperform flat query loops
- Better decomposition improves result quality

### What to copy

- Search graph planning
- Branching follow-up search intents
- Tool-role separation in research flow

### What not to copy

- The exact app architecture
- Tying ourselves to its backend assumptions

### How it should show up in `autosearch`

- `research/planner.py` should be able to emit a graph or staged plan, not just a flat list
- `SearchProgram` should include branching topic frontier logic

## 6. `Meilisearch`

Repository:
- <https://github.com/meilisearch/meilisearch>

### What it teaches us

- Once data is acquired, local indexing becomes a force multiplier
- Fast hybrid/local search over our own evidence is essential
- Not every round should begin from the web

### What to copy

- Internal searchable evidence index
- Fast local retrieval over acquired docs/evidence
- Hybrid retrieval possibilities

### What not to copy

- Make Meilisearch itself the hard dependency

### How it should show up in `autosearch`

- Native `evidence_index/` abstraction
- Optional `meilisearch_adapter.py`
- Ability to search our own accumulated evidence before hitting the open web

## 7. `deep-searcher`

Repository:
- <https://github.com/zilliztech/deep-searcher>

### What it teaches us

- Private data + online search can be unified
- Search should produce reports, not just links
- Internal evaluation scaffolding matters

### What to copy

- Offline + online hybrid mindset
- Report-oriented research output
- Evaluation folder discipline

### What not to copy

- A vector-db-first product boundary

### How it should show up in `autosearch`

- A local/private evidence layer integrated into the same runtime
- Better benchmark and report outputs

## 8. `search4all` and `openperplex_backend_os`

Repositories:
- <https://github.com/fatwang2/search4all>
- <https://github.com/YassKhazzan/openperplex_backend_os>

### What they teach us

- Open search answer systems need a coherent answer assembly layer
- Search products should return useful structured outputs, not just links

### What to copy

- Answer assembly mindset
- Unified response building

### What not to copy

- Product shell
- External service dependency assumptions

---

## What Must Stay Uniquely Ours

These modules remain the identity of `autosearch`:

- `goal_cases/*.json`
- `goal_judge.py`
- `goal_bundle_loop.py`
- `goal_runtime.py`
- `selector.py`
- `project_experience.py`
- `source_capability.py`
- `interface.py`

That is the layer that makes this system “autoresearch for search” instead of “another open-source Perplexity clone”.

---

## New Target Architecture

After this upgrade, `autosearch` should look like this:

### Layer 1: Search Mesh

Responsibilities:

- route search intent to the right backend
- prefer free local/self-hosted engines
- use specialized sources when query intent is specific
- fall back to premium sources only when necessary

Target components:

- `search_mesh/backends/searxng_backend.py`
- `search_mesh/backends/ddgs_backend.py`
- `search_mesh/backends/github_backend.py`
- `search_mesh/backends/web_backend.py`
- `search_mesh/router.py`
- `search_mesh/provider_policy.py`

### Layer 2: Acquisition

Responsibilities:

- fetch URL
- render if needed
- normalize page
- preserve references
- produce clean markdown and fit markdown

Target components:

- `acquisition/fetch_pipeline.py`
- `acquisition/render_pipeline.py`
- `acquisition/markdown_cleaner.py`
- `acquisition/reference_extractor.py`
- `acquisition/crawl4ai_adapter.py`

### Layer 3: Evidence Normalization

Responsibilities:

- convert messy acquired content into evidence records
- preserve provenance
- classify evidence types
- expose judge-ready objects

Target components:

- `evidence/models.py`
- `evidence/normalize.py`
- `evidence/classify.py`
- `evidence/legacy_adapter.py`

### Layer 4: Research Orchestration

Responsibilities:

- break down research problem
- generate search graph
- execute search and acquisition
- synthesize evidence
- prepare routeable outputs

Target components:

- `research/planner.py`
- `research/executor.py`
- `research/synthesizer.py`
- `research/routeable_output.py`

### Layer 5: Optimization Runtime

Responsibilities:

- fixed goal
- fixed judge
- evolving search program
- acceptance/rejection
- plateau and ceiling handling

Target components:

- existing `goal_*` modules
- strengthened `selector.py`

### Layer 6: Local Evidence Index

Responsibilities:

- search our own accumulated evidence
- support hybrid local retrieval
- reduce repeated open-web fetches

Target components:

- `evidence_index/index.py`
- `evidence_index/query.py`
- `evidence_index/meilisearch_adapter.py`

### Layer 7: Public Product Interface

Responsibilities:

- stable local integration surface
- no caller dependence on internal modules

Target components:

- `interface.py`
- `doctor.py`

---

## Core Data Model

## `SearchHit`

Represents a raw search result before fetch.

Fields:

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

## `AcquiredDocument`

Represents the fetched and cleaned page state.

Fields:

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

Judge-ready normalized evidence unit.

Fields:

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

Current judged evidence package.

Fields:

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

Keep extending the existing program object instead of introducing a second control plane.

Fields to stabilize or add:

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

---

## Major Upgrade Strategy

The upgrade should be executed in this order:

1. free-first search mesh
2. acquisition and clean extraction
3. evidence record normalization
4. local evidence index
5. research planner/executor/synthesizer split
6. stronger program evolution
7. stable interface refinement

This order ensures we stop depending on premium search paths early, then improve information cleanliness, then improve orchestration, then improve self-optimization.

---

# Implementation Tasks

## Phase 1: Replace Paid-First Search With Free-First Search Mesh

### Task 1: Add native search mesh backend abstraction

**Files:**
- Create: `search_mesh/backends/base.py`
- Create: `search_mesh/router.py`
- Modify: `goal_services.py`
- Modify: `engine.py`
- Test: `tests/test_goal_services.py`

**Step 1: Write failing tests**

Cover:

- breadth queries route to free-first backend
- GitHub repo/code queries route to specialized backend
- provider mix is preserved after routing

**Step 2: Implement base backend contract**

The base backend contract should return our own `SearchHit` shape, not third-party raw responses.

**Step 3: Move current direct search logic behind router**

`goal_services.search_query(...)` should become a thin orchestration layer, not the place where backend knowledge lives.

**Step 4: Run tests**

```bash
python3 -m unittest tests/test_goal_services.py -v
```

**Step 5: Commit**

```bash
git add search_mesh/backends/base.py search_mesh/router.py goal_services.py engine.py tests/test_goal_services.py
git commit -m "Introduce native search mesh routing"
```

### Task 2: Add `SearXNG` backend

**Files:**
- Create: `search_mesh/backends/searxng_backend.py`
- Modify: `sources/catalog.json`
- Modify: `source_capability.py`
- Test: `tests/test_source_capability.py`

**Step 1: Write failing tests**

Test:

- configured local endpoint
- endpoint unavailable
- result normalization to `SearchHit`

**Step 2: Implement backend**

Support:

- query text
- safe params
- normalized hits

**Step 3: Mark SearXNG as free-first default**

**Step 4: Commit**

```bash
git add search_mesh/backends/searxng_backend.py sources/catalog.json source_capability.py tests/test_source_capability.py
git commit -m "Add SearXNG free-first backend"
```

### Task 3: Add `ddgs` backend

**Files:**
- Create: `search_mesh/backends/ddgs_backend.py`
- Modify: `source_capability.py`
- Test: `tests/test_source_capability.py`

**Step 1: Write failing tests**

Test:

- fallback query path
- multi-engine routing
- normalization to `SearchHit`

**Step 2: Implement backend**

Use `ddgs` only as an internal backend implementation, not a public boundary.

**Step 3: Make router use `ddgs` as local fallback**

**Step 4: Commit**

```bash
git add search_mesh/backends/ddgs_backend.py source_capability.py tests/test_source_capability.py
git commit -m "Add DDGS free fallback backend"
```

### Task 4: Re-tier premium providers as fallback only

**Files:**
- Modify: `sources/catalog.json`
- Modify: `search_mesh/router.py`
- Modify: `doctor.py`
- Test: `tests/test_source_capability.py`

**Step 1: Add provider tiers**

Use:

- `free_default`
- `specialized_free`
- `premium_fallback`

**Step 2: Update doctor output**

Doctor should clearly report which free path is active before mentioning premium fallback.

**Step 3: Commit**

```bash
git add sources/catalog.json search_mesh/router.py doctor.py tests/test_source_capability.py
git commit -m "Make premium providers fallback only"
```

---

## Phase 2: Build Native Acquisition and Extraction Pipeline

### Task 5: Introduce acquisition document model

**Files:**
- Create: `acquisition/document_models.py`
- Test: `tests/test_acquisition_pipeline.py`

**Step 1: Write failing tests**

Cases:

- basic HTML doc
- redirected URL
- markdown-only page

**Step 2: Implement `AcquiredDocument`**

This model is the boundary between fetch and extraction.

**Step 3: Commit**

```bash
git add acquisition/document_models.py tests/test_acquisition_pipeline.py
git commit -m "Add acquired document model"
```

### Task 6: Implement native fetch/render/markdown pipeline inspired by Crawl4AI

**Files:**
- Create: `acquisition/fetch_pipeline.py`
- Create: `acquisition/render_pipeline.py`
- Create: `acquisition/markdown_cleaner.py`
- Create: `acquisition/reference_extractor.py`
- Test: `tests/test_acquisition_pipeline.py`

**Step 1: Write failing tests**

Cover:

- raw fetch
- rendered fetch fallback
- clean markdown generation
- fit markdown trimming
- reference extraction

**Step 2: Implement native pipeline**

Do not require `Crawl4AI` to exist. Reproduce the essential pattern ourselves.

**Step 3: Add optional `crawl4ai_adapter.py`**

This is allowed as an optimization path, but the native pipeline must already work.

**Step 4: Commit**

```bash
git add acquisition/fetch_pipeline.py acquisition/render_pipeline.py acquisition/markdown_cleaner.py acquisition/reference_extractor.py tests/test_acquisition_pipeline.py
git commit -m "Add native acquisition and markdown pipeline"
```

---

## Phase 3: Replace Loose Findings With Evidence Records

### Task 7: Introduce evidence record contracts

**Files:**
- Create: `evidence/models.py`
- Create: `evidence/normalize.py`
- Create: `evidence/classify.py`
- Test: `tests/test_evidence_normalize.py`

**Step 1: Write failing tests**

Cases:

- repo result -> evidence record
- article result -> evidence record
- dataset result -> evidence record

**Step 2: Implement normalization**

Convert:

- raw `SearchHit`
- `AcquiredDocument`

into:

- `EvidenceRecord`

**Step 3: Commit**

```bash
git add evidence/models.py evidence/normalize.py evidence/classify.py tests/test_evidence_normalize.py
git commit -m "Introduce evidence record normalization"
```

### Task 8: Make the judge consume evidence records, not loose findings

**Files:**
- Modify: `goal_judge.py`
- Modify: `evaluation_harness.py`
- Modify: `goal_bundle_loop.py`
- Test: `tests/test_goal_judge.py`

**Step 1: Write failing tests**

Judge should work over evidence records and still preserve stable return shape.

**Step 2: Implement harness conversion**

Judge input should be standardized and versionable.

**Step 3: Commit**

```bash
git add goal_judge.py evaluation_harness.py goal_bundle_loop.py tests/test_goal_judge.py
git commit -m "Judge normalized evidence records"
```

---

## Phase 4: Add Internal Evidence Index Inspired by Meilisearch

### Task 9: Add index abstraction

**Files:**
- Create: `evidence_index/index.py`
- Create: `evidence_index/query.py`
- Test: `tests/test_evidence_index.py`

**Step 1: Write failing tests**

Cover:

- add evidence
- query evidence
- hybrid lexical lookup

**Step 2: Implement local index**

First native/simple implementation can be file-backed or SQLite-backed.

**Step 3: Commit**

```bash
git add evidence_index/index.py evidence_index/query.py tests/test_evidence_index.py
git commit -m "Add local evidence index abstraction"
```

### Task 10: Add optional `Meilisearch` adapter

**Files:**
- Create: `evidence_index/meilisearch_adapter.py`
- Modify: `doctor.py`
- Test: `tests/test_evidence_index.py`

**Step 1: Write failing tests**

**Step 2: Implement optional adapter**

Again: optional accelerator, not mandatory boundary.

**Step 3: Commit**

```bash
git add evidence_index/meilisearch_adapter.py doctor.py tests/test_evidence_index.py
git commit -m "Add optional Meilisearch evidence adapter"
```

---

## Phase 5: Upgrade Search To Research Workflow

### Task 11: Split the flow into planner / executor / synthesizer

**Files:**
- Create: `research/planner.py`
- Create: `research/executor.py`
- Create: `research/synthesizer.py`
- Modify: `goal_bundle_loop.py`
- Test: `tests/test_research_flow.py`

**Step 1: Write failing tests**

Test:

- planner produces search intents
- executor returns evidence records
- synthesizer produces judged bundle inputs

**Step 2: Implement planner**

Planner should borrow from `GPT Researcher` and `MindSearch`:

- staged plan
- branchable intents
- topic frontier

**Step 3: Implement executor**

Executor should run:

- search mesh
- acquisition
- evidence normalization

**Step 4: Implement synthesizer**

Synthesizer should produce:

- bundle evidence
- routeable map
- repair hints

**Step 5: Commit**

```bash
git add research/planner.py research/executor.py research/synthesizer.py goal_bundle_loop.py tests/test_research_flow.py
git commit -m "Split research runtime into planner executor synthesizer"
```

---

## Phase 6: Make SearchProgram More Like Autoresearch

### Task 12: Evolve acquisition policy and backend policy, not just query text

**Files:**
- Modify: `goal_runtime.py`
- Modify: `goal_editor.py`
- Modify: `selector.py`
- Test: `tests/test_goal_runtime.py`
- Test: `tests/test_goal_editor.py`
- Test: `tests/test_selector.py`

**Step 1: Add new program fields**

- `search_backends`
- `backend_roles`
- `acquisition_policy`
- `evidence_policy`
- `repair_policy`
- `population_policy`

**Step 2: Make searcher mutate those fields**

Examples:

- which backend to use for breadth
- how aggressive fit-markdown should be
- whether to favor code evidence or article evidence

**Step 3: Make selector reward weakest-dimension repair**

This is the main path from 90 to 100.

**Step 4: Commit**

```bash
git add goal_runtime.py goal_editor.py selector.py tests/test_goal_runtime.py tests/test_goal_editor.py tests/test_selector.py
git commit -m "Evolve search program beyond query text"
```

---

## Phase 7: Refine Stable Public Interface

### Task 13: Keep the public surface small and durable

**Files:**
- Modify: `interface.py`
- Modify: `README.md`
- Test: `tests/test_interface.py`

**Stable public surface should remain:**

- `doctor(...)`
- `run_search_task(...)`
- `build_searcher_judge_session(...)`
- `run_goal_case(...)`
- `optimize_goal(...)`
- `optimize_goals(...)`
- `run_goal_benchmark(...)`

**Step 1: Add only product-level convenience**

No new internal complexity should leak into the interface.

**Step 2: Update README contract**

Make clear:

- stable boundary
- minimal guaranteed fields
- internal modules remain internal

**Step 3: Commit**

```bash
git add interface.py README.md tests/test_interface.py
git commit -m "Stabilize public search and optimization interface"
```

---

## Phase 8: Migration and Compatibility

### Task 14: Add adapters for legacy findings and legacy runs

**Files:**
- Create: `evidence/legacy_adapter.py`
- Modify: `goal_services.py`
- Modify: `goal_bundle_loop.py`
- Test: `tests/test_evidence_normalize.py`

**Step 1: Write failing tests**

**Step 2: Implement adapters**

So old `findings` and prior goal artifacts continue to work while the system transitions to evidence records.

**Step 3: Commit**

```bash
git add evidence/legacy_adapter.py goal_services.py goal_bundle_loop.py tests/test_evidence_normalize.py
git commit -m "Add compatibility adapters for legacy findings and runs"
```

---

## Acceptance Criteria

This upgrade is done only when all of these are true:

- `autosearch` can search effectively in a free-first mode without premium APIs.
- Search results are normalized into `EvidenceRecord`, not just passed around as loose findings.
- At least one native acquisition path produces:
  - `clean_markdown`
  - `fit_markdown`
  - `references`
  - stable evidence extraction
- The research flow is planner / executor / synthesizer based.
- `optimize_goal(...)` and `optimize_goals(...)` are enough for external projects to use the system without touching internals.
- Benchmark summaries always expose:
  - `goal_reached`
  - `score_gap`
  - `stop_reason`
  - `practical_ceiling`
- The core optimization loop still preserves:
  - fixed goal
  - fixed judge
  - evolving search program
  - population and selection
- Full test suite passes.

---

## Recommended Execution Order

1. Search mesh
2. Acquisition
3. Evidence normalization
4. Evidence index
5. Research orchestration
6. Program evolution
7. Interface refinement
8. Migration

This order maximizes leverage from borrowed open-source patterns while keeping `autosearch` itself as the final product.

---

## Final Rule

We are allowed to:

- borrow implementation patterns
- borrow internal abstractions
- borrow workflows
- borrow optional adapters

We are not allowed to:

- make our product depend on someone else’s product boundary
- require hosted APIs in the default path
- require MCP in the default path
- let foreign data models become our public contract

The final system must feel like:

**our own search engine, our own acquisition engine, our own evidence engine, and our own autoresearch runtime.**

