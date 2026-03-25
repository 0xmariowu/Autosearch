# AutoSearch

Self-improving search system. Finds repos, articles, and tools for Armory intake.

## Quick Lookup

| I need... | Go here |
|----------|---------|
| Current high-level architecture | `docs/2026-03-22-system-architecture.md` |
| Search methodology and platform playbooks | `docs/methodology/` |
| Stable contracts for demand, search, routing handoff, and experience | `standards/` |
| Runtime search code | `engine.py`, `daily.py`, `pipeline.py` |
| Feedback loop and outcome tracking | `outcomes.py`, `outcomes.jsonl` |

## How It Works

3-phase loop: Explore → Harvest → Post-mortem. Each phase uses LLM evaluation (Sonnet 4.6) to score relevance against a target spec. The post-mortem writes patterns to `patterns.jsonl` — accumulated intelligence that makes the next session smarter.

## Files

| File | Purpose |
|------|---------|
| `engine.py` | Core: 3-phase search (explore → harvest → post-mortem), gene pool + LLM eval |
| `daily.py` | Daily mode: reads queries.json as seed genes, 3 rounds |
| `cli.py` | Manual mode: AI fills genes/target/platforms per task |
| `pipeline.py` | Orchestrator: engine → adapter → score-and-stage.js → intake → email |
| `outcomes.py` | Feedback loop: query→repo tracking + WHEN/USE outcome scoring |
| `project_experience.py` | Runtime experience layer: ledger → index → policy → health |
| `source_capability.py` | Static source capability layer: catalog → doctor → latest-capability |
| `control_plane.py` | Current operating program: objective + capability + experience |
| `goal_judge.py` | Goal-specific evaluator with heuristic / OpenRouter modes |
| `goal_loop.py` | Goal-driven search loop with keep/discard by score delta |
| `interface.py` | Stable Python interface for other projects to call goal loops, doctor, and search tasks |
| `standard.json` | Default config (early-stop thresholds, platform list) |
| `patterns.jsonl` | Accumulated search intelligence (winning/losing words, outcome boosts) |
| `evolution.jsonl` | Per-query experiment log across all sessions |
| `outcomes.jsonl` | Query→repo→WHEN/USE outcome tracking |
| `platforms.md` | Platform connector status and capabilities |
| `standards/` | Stable contracts for demand, search, candidate storage, routeable handoff, and experience |
| `tests/` | Minimal regression tests for runtime experience and outcome provenance |

## Commands

```bash
python cli.py "search query"           # manual search
python daily.py                         # daily automated run
python pipeline.py                      # full pipeline (search → score → intake → email)
python doctor.py                        # static source/provider capability report
python goal_loop.py                     # goal-driven loop for one concrete project problem
```

## Python Interface

**Stable boundary**

- External projects should depend only on `interface.py`.
- All other modules should be treated as internal implementation by default, including `goal_*`, `pipeline.py`, `daily.py`, and `engine.py`.

Other projects can import a stable interface instead of wiring internal modules:

```python
from interface import AutoSearchInterface

client = AutoSearchInterface("/path/to/autosearch")
health = client.doctor()
result = client.run_goal_case("atoms-auto-mining-perfect", max_rounds=1)
```

### Integration Guide

Use the smallest entry point that matches your need:

- If you just want to call search:
  `AutoSearchInterface.run_search_task(...)`
- If you have a fixed goal plus fixed judge and want explicit `搜索员 + 打分员` roles:
  `AutoSearchInterface.build_searcher_judge_session(...)`
- If you want to run the full goal loop directly:
  `AutoSearchInterface.run_goal_case(...)`
- If you want the simplest “push this goal toward a target score” entry:
  `AutoSearchInterface.optimize_goal(...)`
- If you want to run the same runtime across multiple goals:
  `AutoSearchInterface.run_goal_benchmark(...)`

If another project wants the explicit `搜索员 + 打分员` split, use a session:

```python
from interface import AutoSearchInterface

client = AutoSearchInterface("/path/to/autosearch")
session = client.build_searcher_judge_session("atoms-auto-mining-perfect")
plans = session.searcher_propose()
round_result = session.run_searcher_round()
```

Current runtime default:

- Searcher uses the local AutoSearch runtime and heuristic goal searcher.
- Judge can use OpenRouter when `OPENROUTER_API_KEY` is configured.
- Current default judge model is `google/gemini-3-flash-preview`.
- The OpenRouter editor/searcher is disabled by default; enable it only intentionally with `OPENROUTER_ENABLE_EDITOR=1`.
- Rubric-only goal cases are supported; if a goal does not define explicit `dimensions`, the runtime derives stable bundle dimensions from `rubric`.
- The main bundle loop now supports rubric-only goals even when they have no `seed_queries`; round 1 falls back to synthesized candidate plans instead of terminating early.
- Session mode now follows the same provider restrictions as the main loop; `provider_mix` limits both default platforms and structured per-query platform overrides.

Cross-goal benchmark example:

```python
from interface import AutoSearchInterface

client = AutoSearchInterface("/path/to/autosearch")
benchmark = client.run_goal_benchmark(
    ["atoms-auto-mining-perfect", "autosearch-capability-doctor"],
    max_rounds=1,
    plan_count=1,
    max_queries=1,
)
```

Optimize-to-target example:

```python
from interface import AutoSearchInterface

client = AutoSearchInterface("/path/to/autosearch")
result = client.optimize_goal(
    "autosearch-capability-doctor",
    target_score=100,
    max_rounds=8,
    plateau_rounds=3,
    persist_run=False,
)
```

### Stable Return Shapes

`doctor()`

- Returns the capability report produced by `source_capability.py`.
- Stable fields to rely on:
  - top-level provider/source availability state
  - per-provider decision data used for skip / priority

`run_search_task(...)`

- This is the stable facade for plain engine search.
- Minimal return keys:
  - `run_id`
  - `experiments`
  - `unique_urls`
  - `harvested`
  - `patterns_written`
  - `confidence`
  - `session_doc`
- Contract note:
  - callers should treat the method signature in `interface.py` as the stable API
  - callers should not depend on raw `EngineConfig` internals beyond the exposed arguments

`run_goal_case(...)`

- Returns the full goal-loop result payload.
- Stable keys to rely on:
  - `goal_id`
  - `target_score`
  - `plateau_rounds_limit`
  - `providers_used`
  - `judge_model`
  - `accepted_program`
  - `stop_reason`
  - `plateau_state`
  - optional `practical_ceiling`
  - `bundle_final`
  - `rounds`
  - optional `run_path` when `persist_run=True`
- Stable tuning arguments:
  - `max_rounds`
  - optional `plan_count`
  - optional `max_queries`
  - optional `target_score`
  - optional `plateau_rounds`

`optimize_goal(...)`

- Convenience wrapper around `run_goal_case(...)` for the common case:
  “keep pushing this goal toward a target score until success or plateau”.
- Stable arguments:
  - `target_score`
  - `max_rounds`
  - `plateau_rounds`
  - optional `plan_count`
  - optional `max_queries`
  - optional `persist_run`

`run_goal_benchmark(...)`

- Returns a benchmark summary payload for multiple goal cases.
- Stable keys to rely on:
  - `generated_at`
  - `max_rounds`
  - `plan_count`
  - `max_queries`
  - optional `target_score`
  - optional `plateau_rounds`
  - `goals`
- Each `goals[*]` item guarantees:
  - `goal_id`
  - `problem`
  - `target_score`
  - `final_score`
  - `accepted_rounds`
  - `rounds_run`
  - `providers_used`
  - `accepted_program_id`

`build_searcher_judge_session(...)`

- Returns a `SearcherJudgeSession` object with stable methods:
  - `initial_queries()`
  - `searcher_propose()`
  - `searcher_execute()`
  - `judge_bundle()`
  - `run_searcher_round()`

`run_searcher_round(...)`

- Stable top-level keys:
  - `goal_id`
  - `plans`
  - `capability_report`
- Each `plans[*]` item guarantees:
  - `label`
  - `queries`
  - `query_runs`
  - `finding_count`
  - `judge_result`
  - optional `program_overrides`
- Execution notes:
  - `program_overrides.provider_mix` is applied during search execution
  - `program_overrides.sampling_policy` is applied during per-query sampling and bundle construction

### Maintenance Note

- `interface.py` is the public compatibility target.
- Internal goal-loop helpers are routed through internal service modules such as `goal_services.py`.
- Those internal modules are still implementation details and are not part of the public contract.
- If the internal implementation changes later, compatibility is measured against the exported surface of `interface.py`, not the modules underneath it.

## Dependencies

Pipeline depends on scripts in `Armory/scripts/scout/`:
- `score-and-stage.js` — scoring + dedup + diversity + Chinese translation + daily report
- `auto-intake.sh` — clone high-score repos + generate deep-research + rebuild indexes
- `send-email.sh` — Resend API email delivery
- `queries.json` — 15 topic groups (seed genes)
- `state.json` — persistent state (seen URLs, trends, run history)

## Scheduling

- LaunchAgent: `com.autosearch.armory-scout`
- Trigger: `~/.local/bin/armory-scout.sh` → rsync to local → `python pipeline.py`
- Output: `AIMD/recs/{YYYY-MM-DD}.md`

## Search Methodology

Evidence principles, search methods, and per-platform playbooks: `docs/methodology/`
- `principles.md` — evidence reliability framework
- `platforms/*.md` — GitHub, Reddit, HN, Exa, Twitter, HuggingFace patterns
- `methods/*.md` — specific search techniques (e.g., reverse fingerprint search)

Additional research MCP sources can be documented there even before they become runtime providers. Current example: `docs/methodology/platforms/alphaxiv.md`.

## Standards

AutoSearch standards define narrow contracts, not general architecture:

- `standards/demand-standard.md` — how global demand becomes search briefs
- `standards/search-standard.md` — what search owns and what it must preserve
- `standards/content-candidate-standard.md` — the truth layer between findings and admission
- `standards/routeable-map-standard.md` — the final search-side handoff to downstream routing
- `standards/experience-standard.md` — how runtime experience is stored and consumed

## Runtime Experience Files

The runtime experience layer lives under `experience/`:

- `experience/library/experience-ledger.jsonl` — append-only search events
- `experience/library/experience-index.json` — aggregated recent index
- `experience/library/experience-policy.json` — current runtime guidance
- `experience/latest-health.json` — machine-readable provider/query-family health

## Source Capability Files

The static capability layer lives under `sources/`:

- `sources/catalog.json` — source/provider registry
- `sources/latest-capability.json` — machine-readable availability and doctor output

Current runtime providers include `exa`, `tavily`, GitHub providers, `twitter_xreach`, and `huggingface_datasets`.

## Control Plane Files

The current operating program lives under `control/`:

- `program.md` — human-readable operating brief
- `control/latest-program.json` — machine-readable merged control plane

## Goal Loop Files

Goal-driven self-improvement lives under `goal_cases/` and the goal loop modules:

- `goal_cases/*.json` — concrete project problems with target score + rubric
- `goal_cases/runs/*.json` — run artifacts for baseline vs goal-judged comparisons
- `goal_judge.py` — independent evaluator
- `goal_loop.py` — iterative search / judge / keep-discard runner
