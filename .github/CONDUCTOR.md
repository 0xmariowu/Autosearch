# Conductor Mode

Conductor mode is this repo's four-agent collaboration pattern for AI-assisted delivery:

- Claude Code is the local orchestrator for tasks that need a real checkout, local CLIs, or longer multi-step execution.
- Codex is the fix-forward local executor when a PR gets blocked by mechanical review or CI signals.
- Copilot handles cloud-async issue triage and can pick up small, well-scoped tasks that do not require local state.
- CodeRabbit provides review coverage and flags correctness, maintainability, and risk concerns on pull requests.

The goal is simple: let cloud agents handle fast asynchronous work, and route anything environment-bound back to the local conductor without losing context.

## Workflows in this PR

- `issue-greeter.yml` comments on newly opened issues to ask Copilot to triage them and decide whether the work fits cloud-async execution or should be handed back to the local conductor.
- `three-commit-required.yml` enforces the repo rule that behavior changes must be paired with a separate test commit and a separate docs commit.
- `pr-closes-issue-check.yml` verifies that pull request descriptions include a closing reference such as `Closes #123` so issue state stays connected to delivered code.
- `codex-autofix-dispatch.yml` posts an `@codex` fix request when a bot review blocks the PR or when selected mechanical gates fail on a pull-request-triggered workflow run.

## Supporting files

- `.github/ISSUE_TEMPLATE/task.md` gives maintainers a structured way to define Goal, Done-when, and verification expectations for conductor-routed work.
- `.github/copilot-instructions.md` defines the hard rules all cloud agents must follow before they open or repair a PR.
- `.github/agents/test-sufficiency.md` gives review automation a consistent rubric for checking whether new behavior has enough test coverage.

## How maintainers use it

1. Create work through the task issue template and write a clear Goal, Done-when, and verification path.
2. Let `issue-greeter.yml` route the issue. Copilot either picks it up directly or labels it for a local Claude session when the task needs local execution.
3. Open pull requests with a `Closes #N` reference and keep the three-commit structure intact for behavior, tests, and docs.
4. If a bot review or mechanical check blocks the PR, `codex-autofix-dispatch.yml` can ask Codex to push a minimal repair commit.
5. Merge only after the workflows are green and the review signal is acceptable.

## Maintenance notes

- Keep agent instructions in `.github/copilot-instructions.md` aligned with these workflows so routing and repair behavior do not drift.
- Prefer narrow, mechanical triggers for auto-dispatch. If a gate is flaky or advisory, do not wire it into Codex autofix.
- Do not add internal codenames, local filesystem paths, or private planning references to public workflow files.
