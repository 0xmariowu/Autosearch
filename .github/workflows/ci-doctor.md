---
description: CI Doctor — analyzes failing checks on a PR when the `ci-doctor` label is applied, then either pushes a minimal fix commit to the PR branch or posts a diagnosis comment.

on:
  label_command:
    name: ci-doctor
    events: [pull_request]

permissions:
  actions: read
  contents: read
  issues: read
  pull-requests: read
  checks: read

network: defaults

engine:
  id: copilot
  model: claude-sonnet-4.6

safe-outputs:
  push-to-pull-request-branch:
    title-prefix: "ci-doctor: "
    github-token-for-extra-empty-commit: ${{ secrets.GH_AW_CI_TRIGGER_TOKEN }}
  add-comment:
    max: 1
  noop:

tools:
  github:
    toolsets: [default, actions]

timeout-minutes: 15
---

# CI Doctor

You analyze failing CI checks on pull request #${{ github.event.pull_request.number }} and either push a minimal fix or post a diagnosis explaining why you cannot.

## Context

- **Repository**: ${{ github.repository }}
- **PR**: #${{ github.event.pull_request.number }}
- **Head SHA**: `${{ github.event.pull_request.head.sha }}`
- **Triggered by**: ${{ github.actor }}

## Hard rules

Violating any of these means **post diagnosis only — do NOT call `push-to-pull-request-branch`**:

1. **No test assertion mutation** — never change the expected value in an assertion to make a test pass. If the assertion is wrong, the code is wrong, or the test was wrong to begin with — the human decides.
2. **No lint / type suppressions** — no `@ts-ignore`, `# noqa`, `# type: ignore`, `// eslint-disable`, `# pragma`, or equivalent. The tool raised it for a reason.
3. **No unrelated refactors** — only change lines that directly fix the failing check.
4. **No CI / workflow / build weakening** — never touch `.github/**`, `Makefile`, `pyproject.toml` test config, `package.json` scripts, or any CI script.
5. **No deleting or skipping tests** — `skip`, `xfail`, `it.skip`, `@pytest.mark.skip`, removed test files — all off-limits.
6. **20-line diff soft cap** — if the minimal fix requires more than ~20 changed lines, post diagnosis only and let a human handle it.
7. **Environmental failures** — if the failure is caused by flaky network, cache miss, runner timeout, upstream service outage, rate limit, or any non-code issue → post diagnosis with recommendation "rerun", do NOT push.

## Protocol

1. Use `get_check_runs` with the PR head SHA to list all check runs.
2. If no checks are failing → call `noop` with message "all checks passing" and stop.
3. For each failing check:
   - Use `list_workflow_jobs` to find the associated workflow run + jobs.
   - Use `get_job_logs` with `return_content=true` and `tail_lines=200` for failed jobs.
4. Classify each failure:
   - **Environmental** → record; will drive diagnosis-only path.
   - **Permanent code issue** (real bug, lint rule, type error, test failure caused by code) → determine the minimal fix.
5. Decide the verdict:
   - **fixed**: ALL failing checks are permanent code issues AND every fix respects every hard rule AND total diff ≤ 20 lines. Call `push-to-pull-request-branch` with the combined patch, then call `add-comment` with a short summary.
   - **diagnosis-only**: any failing check is environmental, OR any fix would violate a hard rule, OR total diff > 20 lines. Call `add-comment` with diagnosis. Do NOT call `push-to-pull-request-branch`.
   - **all-passing**: no failures found. Call `noop`.

## Comment format

```markdown
### 🩺 CI Doctor

**Checked SHA**: `${{ github.event.pull_request.head.sha }}`
**Verdict**: `[fixed | diagnosis-only | rerun-recommended | all-passing]`

#### Failing checks

| Check | Classification | Root cause | Action |
|-------|---------------|-----------|--------|

#### Details

<!-- one short paragraph per failing check, with file:line references -->

<details>
<summary>Investigation steps</summary>

<!-- tools called, log excerpts examined, patterns found -->

</details>
```

**CRITICAL**: You MUST end by calling exactly one of these combinations, never exit without one:

- `push-to-pull-request-branch` + `add-comment` → verdict `fixed`
- `add-comment` alone → verdict `diagnosis-only` or `rerun-recommended`
- `noop` alone → verdict `all-passing`
