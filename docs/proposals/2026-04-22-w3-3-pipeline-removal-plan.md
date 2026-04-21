# W3.3 Pipeline Removal — Multi-PR Plan

> Status: **plan** (auto-loop closes at plan commit; execution requires explicit boss go).
> Date: 2026-04-22.
> Supersedes: the single-line W3.3 entry in `docs/proposals/2026-04-22-wave-2-status-and-wave-3-plan.md`.
> Pre-requisite done: PR #231 (migration guide + DeprecationWarning).

## Why a Plan Instead of a Single PR

Survey of dependencies on the pipeline (`autosearch/core/pipeline.py`, `iteration.py`, `context_compaction.py`, `synthesis/report.py`, `synthesis/section.py`, `delegation.py`) reveals:

- **7 source modules** import pipeline internals: `cli/main.py` + `server/main.py` + `mcp/server.py` + the 4 pipeline modules themselves.
- **31 test files** directly import pipeline internals.
- Entry points (`research()` MCP tool, `autosearch` CLI, `/autosearch` slash command) all call `Pipeline.run()`.

A single "delete everything" PR would break all 31 tests + all 3 entry points simultaneously. CI would red-light. Revert cost high. Per CLAUDE.md "Do not take overly destructive actions" rule, this must be sequenced.

## Goals

1. Remove m3 / m7 prompts and their callers from autosearch — the pipeline's synthesis is permanently inferior to runtime AI's synthesis (Gate 12 0 / 62 evidence).
2. Leave `research()` MCP tool semantically working (either a thin shim over the trio or a clean "deprecated, use trio" error).
3. Leave the `autosearch` CLI usable or clearly deprecated.
4. Every step: tests green, main mergeable.
5. Total chg`ed-lines cap per PR: ~1000. Prevents unreviewable mega-PRs.

## Acceptance Criteria

- All 9 `m3_*` + `m7_*` prompt markdown files removed.
- `autosearch/core/iteration.py`, `autosearch/core/context_compaction.py`, `autosearch/synthesis/section.py` removed.
- `autosearch/core/pipeline.py` either removed or reduced to a thin deprecated shim that raises `NotImplementedError` pointing at trio.
- `autosearch/synthesis/report.py` rewired to not depend on `section.py` OR removed if it only existed to feed the pipeline.
- `autosearch/core/delegation.py` removed if it only existed for iteration.
- `research()` MCP tool: either deleted or returns a structured "deprecated, use list_skills + run_clarify + run_channel" response.
- `autosearch` CLI: `research` subcommand either deleted or prints deprecation + migration guide URL.
- All 31 test files: either (a) deleted if exclusively testing removed internals, (b) rewritten to target v2 trio, or (c) kept with behavioral guarantees still met.
- Full `pytest -x -q tests/` green throughout.
- Full ruff check + format green throughout.

## Multi-PR Sequence

Each PR is self-contained, green after merge, rollbackable.

### PR A — Freeze `research()` surface (non-destructive)

**Scope**: make `research()` MCP tool call path return a structured deprecation response WITHOUT running the pipeline. Mark CLI `research` subcommand to print a deprecation message and exit.

**Changes**:

- `autosearch/mcp/server.py`: `research()` body → build a `ResearchResponse` with `content="This tool is deprecated. Use list_skills + run_clarify + run_channel (see docs/migration/legacy-research-to-tool-supplier.md)."`, `delivery_status="deprecated"`. Do NOT call `Pipeline.run()`.
- `autosearch/cli/main.py`: add `--legacy-pipeline` flag that re-enables old behavior for emergencies; default behavior prints deprecation + trio migration.
- Tests: update `test_mcp_research_scope.py`, `test_mcp_server.py`, `test_cli_interactive_prompt.py`, `test_cli_query.py`, `test_cli_scope_flags.py` to assert the deprecation response pattern.

**Deleted**: nothing yet.

**Validation**: pytest full suite green; `claude plugin install autosearch` still works; `research()` returns the deprecation content; `autosearch research "..."` CLI prints deprecation.

**Rollback**: revert single commit.

**Files changed**: ~6 src + ~5 test. ~300 lines.

### PR B — Delete orphan pipeline-only tests

**Scope**: delete tests that exclusively test removed pipeline internals. Leaves the tests for CLI / MCP / trio alone.

**Deleted** (13 test files):

- `tests/unit/core/test_context_compaction.py`
- `tests/unit/core/test_delegation.py`
- `tests/unit/core/test_perspectives.py`
- `tests/unit/synthesis/test_section.py`
- `tests/unit/test_iteration.py`
- `tests/unit/test_iteration_empty_counts.py`
- `tests/unit/test_iteration_routing.py`
- `tests/unit/test_m3_compaction_prompt_preserves_specifics.py`
- `tests/unit/test_m7_prompt_substance.py`
- `tests/unit/test_pipeline_channel_error.py`
- `tests/unit/test_pipeline_channel_scope.py`
- `tests/unit/test_pipeline_events.py`
- `tests/unit/test_pipeline_initial_subquery_count.py`
- `tests/unit/test_pipeline_tokens.py`
- `tests/unit/test_synthesis.py`
- `tests/integration/test_full_synthesis.py`
- `tests/integration/test_iteration_e2e.py`
- `tests/integration/test_pipeline_clarification_exit.py`
- `tests/integration/test_pipeline_e2e.py`
- `tests/integration/test_pipeline_with_session.py`
- `tests/perf/test_pipeline_large_evidence.py`
- `tests/real_llm/test_pipeline_demo.py`

**Validation**: `pytest -q tests/` green with the above removed; test count drops by ~200 cases but coverage of v2 trio + channel skills + meta skills stays intact.

**Rollback**: revert single commit restores files.

**Files changed**: 0 src + ~22 test deletions.

### PR C — Delete m3 / m7 prompt markdown files

**Scope**: delete all 9 prompt files. No code is imported from these markdowns; they are loaded by `load_prompt(...)` at callsite. After PR A, callsites are no longer invoked (CLI + MCP paths both short-circuit to deprecation). After PR B, no tests reference them directly.

**Deleted** (9 files):

- `autosearch/skills/prompts/m3_evidence_compaction.md`
- `autosearch/skills/prompts/m3_follow_up_query.md`
- `autosearch/skills/prompts/m3_gap_reflection.md`
- `autosearch/skills/prompts/m3_gap_reflection_perspective.md`
- `autosearch/skills/prompts/m3_perspective_labels.md`
- `autosearch/skills/prompts/m3_search_reflection.md`
- `autosearch/skills/prompts/m7_outline.md`
- `autosearch/skills/prompts/m7_section_write.md`
- `autosearch/skills/prompts/m7_section_write_v2.md`

**Validation**: `pytest -q tests/` still green. `load_prompt("m3_...")` would raise — but no live codepath calls it after PR A.

**Rollback**: revert single commit.

**Files changed**: 0 src / 0 test / 9 prompt md deletions.

### PR D — Gut pipeline internals

**Scope**: delete the three pipeline-internal Python modules. Rewire `Pipeline.run()` to raise `NotImplementedError`. Remove `Pipeline` → `ReportSynthesizer` dependency (rewriting `synthesis/report.py` to not need `synthesis/section.py`, or stubbing it).

**Deleted**:

- `autosearch/core/iteration.py`
- `autosearch/core/context_compaction.py`
- `autosearch/synthesis/section.py`
- `autosearch/core/delegation.py` (if exclusively used by iteration — verify)

**Gutted**:

- `autosearch/core/pipeline.py`: `Pipeline.__init__` keeps the signature; `Pipeline.run` raises `NotImplementedError("Pipeline is removed under v2. Use list_skills + run_clarify + run_channel.")`.
- `autosearch/synthesis/report.py`: if it references `synthesis/section.py`, either rewrite to emit a placeholder "legacy report removed" string or delete the module entirely.

**Validation**: pytest green (all tests dependent on these modules were removed in PR B; remaining tests continue to pass since CLI / MCP paths short-circuited in PR A). Import the MCP server, invoke `research()` — returns deprecation, does not attempt to call `Pipeline.run()`.

**Rollback**: revert single commit restores files; PR A's deprecation path still valid so entry points remain stable.

**Files changed**: 4-5 src deletions + 1-2 src gut/rewrite. ~800 deleted lines, ~20 kept/modified.

### PR E — Delete `Pipeline` class entirely (optional; requires boss sign-off)

**Scope**: final cleanup. Remove `Pipeline` class + imports from CLI / MCP / server. Update the deprecation stub to not even import `Pipeline`.

**Deleted**:

- `autosearch/core/pipeline.py` (already gutted in PR D; this removes the file)
- `autosearch/synthesis/report.py` (if not already removed in PR D)

**Rewired**:

- `autosearch/mcp/server.py`: remove `Pipeline` import; keep `research()` deprecation body (no longer needs to reference Pipeline at all).
- `autosearch/cli/main.py`: remove `Pipeline` import; keep deprecation path.
- `autosearch/server/main.py`: remove `Pipeline` import or delete the module if only used for pipeline.

**Validation**: pytest green. `autosearch/__init__.py` still imports cleanly.

**Rollback**: revert single commit.

**Files changed**: 3-5 src. ~500 deleted lines.

## Out of Scope for This Plan

- Removing channel skills or channel infrastructure (those are the tool-supplier's core).
- Removing the `experience-*` or `autosearch:router` or meta skills (those are wave 3 additions, not legacy).
- Removing `scripts/bench/judge.py` or `docs/bench/gate-12-augment-vs-bare.md`.
- Rewriting plugin marketplace / `.claude-plugin/` config.
- Running the first Gate 12 augment-vs-bare bench (W3.4 — separate task).

## Dependencies / Prerequisites

- ✅ PR #231 landed (DeprecationWarning + migration guide).
- ✅ W3.1 trio live on main (list_skills + run_channel + run_clarify).
- ❓ Boss sign-off that no external user depends on `Pipeline` directly (autosearch is 0.0.1a1 alpha; likely none).
- ❓ Bench runner in place (W3.2) for post-deletion regression check — nice to have, not blocking.

## Validation Gates Per PR

Each PR must pass before the next one opens:

1. `ruff check && ruff format --check` green.
2. `pytest -x -q tests/` green (excluding perf/e2b which need external resources).
3. `claude plugin install autosearch@autosearch` + invoke MCP tools via `claude -p --dangerously-skip-permissions` in a dev shell — verify `research()` deprecation path, `list_skills` / `run_clarify` / `run_channel` still work.
4. No CI workflow changes required (existing three-commit-required, changelog-required, and closes-issue-check continue to apply).

## Rollback Procedure

Each PR is a single squash commit. Rollback = `git revert <sha>`. Since entries are sequential, rolling back PR D without reverting PRs E+later first is safe (they reference the deleted modules, but since the modules stay gutted-stub in PR D, any rollback of D alone restores the deleted files and the gutted stub + empty shim continues running).

## Off-Ramp / No-Go Signals

Abort the plan (back out PRs in reverse order) if:

- A real user reports their `research()` call breaks and autosearch has no migration path for them.
- Gate 12 augment-vs-bare bench (once implementable) shows the v2 trio regressing against legacy `research()` — would indicate the replacement is worse than the thing being deleted.
- The `Clarifier` class (`autosearch/core/clarify.py`) turns out to depend on something in the removal set — re-scope and re-check.
- CI develops an implicit dependency on any of the to-be-deleted files.

## Timing (no time estimates per boss rule; order only)

PR sequence: A → B → C → D → (E pending separate sign-off).

Each PR requires its predecessor to be merged first. Parallel merge = rebase conflicts. Hard-sequence only.

## Related Docs

- `docs/proposals/2026-04-21-v2-tool-supplier-architecture.md` — the architecture proposal (§11 wave-3 pipeline removal).
- `docs/proposals/2026-04-22-wave-2-status-and-wave-3-plan.md` — the overall wave-3 rollout plan.
- `docs/migration/legacy-research-to-tool-supplier.md` — the migration guide shipped by PR #231.
- `docs/bench/gate-12-augment-vs-bare.md` — the success metric.

## Summary

This plan turns "delete the pipeline" from a single unreviewable mega-PR into five sequenced PRs. Each is ≤1000 changed lines. Each leaves the repo green and mergeable. Each is rollbackable. The plan respects CLAUDE.md "Do not take overly destructive actions" — destruction is paced, validated, and reversible.

**Next action** (after this plan merges): boss gives explicit go, PR A opens first.
