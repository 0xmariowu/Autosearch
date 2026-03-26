# AutoSearch Public Interface Contract

This document describes the public compatibility surface exposed by
`interface.py` as of 2026-03-26. It is intentionally narrower than the full
internal architecture.

## Product Envelope

- Public product name: `autosearch-public-api`
- Public version: `v1alpha1`
- Contract revision: `2026-03-26`
- Dict-returning public methods include additive `_api` metadata.

Stable `_api` fields:

- `name`
- `version`
- `revision`
- `method`
- `stability`
- `result_kind`
- `doc_path`

## Compatibility Boundary

- Public compatibility target:
  - `AutoSearchInterface`
  - `SearcherJudgeSession`
- Internal modules such as `goal_bundle_loop.py`, `research/*.py`,
  `goal_services.py`, and `acquisition/*.py` are implementation details.
- If internals change, compatibility is measured against exported behavior in
  `interface.py`.

## Public Entry Points

### `AutoSearchInterface`

- `api_info()`
  - Returns product metadata and the public method catalog.
- `api_method(method)`
  - Returns one public method contract summary.
- `list_goal_cases()`
  - Returns discovered goal-case metadata from `goal_cases_root`.
- `resolve_goal_case(goal_case)`
  - Accepts a goal id, a JSON path, or an inline dict payload.
  - Returns a goal-case dict.
- `build_searcher_judge_session(goal_case)`
  - Returns a `SearcherJudgeSession`.
- `goal_capability_report(goal_case)`
  - Returns `{"capability_report": ..., "_api": ...}`.
- `goal_platforms(goal_case)`
  - Returns `{"platforms": [...], "_api": ...}`.
- `normalize_query(query)`
  - Returns `{"query_spec": {...}, "_api": ...}`.
- `search_goal_query(goal_case, query, ...)`
  - Executes one query against the goal-scoped provider set.
- `replay_goal_queries(goal_case, queries, ...)`
  - Replays multiple normalized queries through the same goal-scoped search stack.
- `fetch_document(url, ...)`
  - Returns `{"document": {...}, "_api": ...}`.
- `enrich_record(record, ...)`
  - Enriches one evidence-like record through acquisition.
- `build_markdown_views(text, ...)`
  - Builds clean/fit markdown and ranked chunk metadata.
- `chunk_document(text, ...)`
  - Returns `{"chunks": [...], "_api": ...}`.
- `normalize_result_record(result, query)`
  - Returns `{"record": {...}, "_api": ...}`.
- `normalize_acquired_document(document, ...)`
  - Returns `{"record": {...}, "_api": ...}`.
- `normalize_evidence_record(record)`
  - Returns `{"record": {...}, "_api": ...}`.
- `coerce_evidence_record(item)`
  - Returns `{"record": {...}, "_api": ...}`.
- `coerce_evidence_records(items)`
  - Returns `{"records": [...], "_api": ...}`.
- `build_research_plan(goal_case, ...)`
  - Returns `{"plans": [...], "_api": ...}`.
- `execute_research_plan(goal_case, plan, ...)`
  - Executes one research plan against the goal-scoped provider set.
- `synthesize_research_round(goal_case, ...)`
  - Synthesizes bundle, graph, and routeable artifacts for one round.
- `build_routeable_output(goal_case, ...)`
  - Builds the routeable handoff artifact from a bundle and judge result.
- `build_research_packet(goal_case, ...)`
  - Builds the standalone routeable research packet.
- `run_goal_case(...)`
  - Runs the full goal loop for one goal.
- `optimize_goal(...)`
  - Convenience wrapper over `run_goal_case(...)` with target-oriented naming.
- `run_goal_benchmark(...)`
  - Runs multiple goal cases and returns the benchmark payload.
  - Accepts goal ids or goal-case file paths.
  - Does not accept inline dict goal cases.
  - Returns `{payload, results}` when `include_results=True`.
- `optimize_goals(...)`
  - Convenience wrapper over `run_goal_benchmark(...)`.
- `run_search_task(...)`
  - Plain engine search interface for non-goal workflows.
- `doctor(providers=None)`
  - Returns the current source capability report.
- `run_watch(watch)`
  - Runs one watch profile.
- `run_watches(watches)`
  - Runs multiple watch profiles.

### `SearcherJudgeSession`

- `initial_queries()`
  - Returns normalized seed queries.
- `searcher_propose(...)`
  - Returns candidate plans from the searcher role.
- `searcher_execute(...)`
  - Executes normalized query specs and returns findings.
- `judge_bundle(findings)`
  - Scores findings against the goal rubric/dimensions.
- `run_searcher_round(...)`
  - Runs one propose/execute/judge cycle.

## `run_goal_case(...)` Result Contract

Top-level stable fields:

- `generated_at`
- `goal_id`
- `problem`
- `target_score`
- `plateau_rounds_limit`
- `providers_used`
- `judge_model`
- `evaluation_harness`
- `accepted_program`
- `stop_reason`
- `plateau_state`
- `practical_ceiling`
- `goal_reached`
- `score_gap`
- `budget_policy`
- `gap_queue`
- `diary_summary`
- `warm_start`
- `baseline_best`
- `bundle_final`
- `routeable_output`
- `research_bundle`
- `search_graph`
- `research_packet`
- `deep_steps`
- `rounds`
- `run_path` when `persist_run=True`

Notes:

- `research_packet` is promoted to the top level from
  `routeable_output.research_packet`.
- `deep_steps` reflects the final round payload when deep execution is enabled.
- `search_graph` may include `deep_loop` metadata in deep mode.

### `bundle_final`

Stable fields:

- `score`
- `dimension_scores`
- `missing_dimensions`
- `matched_dimensions`
- `accepted_query_count`
- `accepted_finding_count`
- `sample_findings`
- `rationale`

### `routeable_output`

Stable fields:

- `goal_id`
- `goal_title`
- `score`
- `score_gap`
- `matched_dimensions`
- `missing_dimensions`
- `weakest_dimension`
- `routes`
- `next_actions`
- `citations`
- `keywords`
- `handoff_packets`
- `research_packet`
- `graph_handoff`
- `planning_ops_summary`
- `gap_queue`
- `cross_verification`

### `research_packet`

Stable fields:

- `packet_id`
- `goal_id`
- `query`
- `mode`
- `score`
- `citations`
- `claims`
- `contradictions`
- `next_actions`
- `evidence_refs`

### `deep_steps`

Stable item fields:

- `kind`
- `summary`
- `metadata`

Observed `kind` values in current code:

- `search`
- `read`
- `reason`

## Goal-Scoped Query Execution Contract

### `search_goal_query(...)`

Stable result fields:

- `query`
- `query_spec`
- `baseline_score`
- `findings`
- `partial_results`
- `timed_out_providers`

### `replay_goal_queries(...)`

Stable result fields:

- `queries`
- `query_runs`
- `findings`

## `run_goal_benchmark(...)` Result Contract

Stable top-level fields:

- `generated_at`
- `max_rounds`
- `plan_count`
- `max_queries`
- `target_score`
- `plateau_rounds`
- `goals`

Stable fields for each `goals[*]` summary:

- `goal_id`
- `problem`
- `target_score`
- `final_score`
- `goal_reached`
- `score_gap`
- `stop_reason`
- `practical_ceiling`
- `accepted_rounds`
- `rounds_run`
- `providers_used`
- `accepted_program_id`
- `matched_dimensions`
- `missing_dimensions`

When `include_results=True`, the return shape is:

- `payload`
- `results`

`results[*]` items are the full `run_goal_case(...)` result payloads for each
goal.

## `run_watch(...)` And `run_watches(...)`

### `run_watch(...)`

Stable input fields:

- `watch_id`
- `goal_id`
- `mode`
- `budget`
- `target_score`
- `plateau_rounds`
- `provider_preferences`

Stable result fields:

- `watch_id`
- `goal_id`
- `mode`
- `frequency`
- `run_at`
- `target_score`
- `success_threshold`
- `goal_reached`
- `score_gap`
- `stop_policy`
- `provider_preferences`
- `budget`
- `scheduler_summary`
- `final_score`
- `result`

### `run_watches(...)`

Stable top-level fields:

- `watch_count`
- `reached_count`
- `results`

## `run_search_task(...)` Result Contract

This method is the stable facade for plain engine search.

Minimal stable fields:

- `run_id`
- `experiments`
- `unique_urls`
- `harvested`
- `patterns_written`
- `confidence`
- `session_doc`

Callers should treat the method signature in `interface.py` as the public API
and should not depend on `EngineConfig` internals beyond exposed arguments.

## Research Phase Contract

### `build_research_plan(...)`

Stable resource fields:

- `plans`

Stable plan item fields:

- `label`
- `queries`
- `intents`
- `role`
- `branch_type`
- `branch_subgoal`
- `graph_node`
- `graph_edges`
- `branch_targets`
- `program_overrides`
- `decision`
- `planning_ops`

### `execute_research_plan(...)`

Stable result fields:

- `label`
- `queries`
- `role`
- `branch_type`
- `branch_subgoal`
- `stage`
- `graph_node`
- `graph_edges`
- `branch_targets`
- `branch_depth`
- `decision`
- `planning_ops`
- `cross_verification`
- `deep_steps`
- `local_evidence_hits`
- `query_keys`
- `query_runs`
- `findings`

### `synthesize_research_round(...)`

Stable result fields:

- `bundle`
- `research_bundle`
- `judge_result`
- `harness_metrics`
- `search_graph`
- `repair_hints`
- `gap_queue`
- `routeable_output`

## Evidence Enrichment Contract

Classic fields that remain backward-compatible:

- `title`
- `url`
- `body`
- `source`
- `query`

Stable additive evidence fields:

- `domain`
- `content_type`
- `snippet`
- `canonical_text`
- `clean_markdown`
- `fit_markdown`
- `chunk_scores`
- `selected_chunks`
- `references`

Chunking notes:

- `chunk_scores` is an ordered list of ranked chunk metadata.
- `selected_chunks` is the subset of chunk text chosen for the fitted markdown
  view.
- `fit_markdown` is the query-aligned compact markdown representation used to
  strengthen downstream reasoning.

## Acquisition Helper Contract

### `fetch_document(...)`

Returns `{"document": {...}, "_api": ...}`.

Stable document fields include:

- `url`
- `final_url`
- `content_type`
- `title`
- `text`
- `clean_markdown`
- `fit_markdown`
- `chunk_scores`
- `selected_chunks`
- `references`

### `enrich_record(...)`

Returns the original record plus additive acquisition fields such as:

- `acquired`
- `acquired_title`
- `acquired_text`
- `acquired_content_type`
- `clean_markdown`
- `fit_markdown`
- `chunk_scores`
- `selected_chunks`
- `references`

## Session Contract

`run_searcher_round(...)` returns:

- `goal_id`
- `plans`
- `capability_report`

Each `plans[*]` item guarantees:

- `label`
- `program_overrides`
- `queries`
- `query_runs`
- `finding_count`
- `judge_result`

It does not currently include `routeable_output`.
