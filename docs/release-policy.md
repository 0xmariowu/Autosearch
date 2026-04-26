# Release Policy

> Source of truth for which checks gate a release vs. which checks merely
> inform. The release pipeline (`.github/workflows/release.yml`) wires the
> mandatory checks; nightly workflows run the advisory ones separately.

## Principle

CI gates **regression**, not **quality**. A release pipeline must refuse to
publish anything that fails a deterministic correctness check, but it must
not block on slow / probabilistic / network-dependent quality benches —
those drift from green-to-red for reasons unrelated to the artifact under
release. Quality measurements live in nightly and weekly cadence.

## Mandatory checks (release MUST fail if any of these fail)

These run inside `release.yml` after the build job and before publish. They
are wired through `scripts/validate/pre_release_check.py` (mandatory subset)
plus `scripts/release-gate.sh --quick --pypi`. Failure stops the publish
step.

| Check | Where defined | Why mandatory |
|---|---|---|
| Version 4-file consistency | `pre_release_check.py:_check_version_consistency` | A mismatch ships a broken artifact (different version in wheel vs. plugin manifest). |
| SKILL.md format compliance | `pre_release_check.py:_check_skill_format` | Unloadable skill files break runtime channel routing. |
| Channel experience dirs initialized | `pre_release_check.py:_check_experience_dirs` | Missing dirs cause silent runtime failures the moment a user invokes a channel. |
| MCP tools registered (10 v2 contract tools) | `pre_release_check.py:_check_mcp_tools` | A fresh install where the MCP layer is missing tools is unusable. |
| Open PR release blockers (label-gated) | `pre_release_check.py:_check_open_prs` | A release while a `release-blocker` PR is open ships a known-broken artifact. |
| Git working tree clean | `pre_release_check.py:_check_git_clean` | Releasing with uncommitted changes means the published artifact does not match any commit. |
| Local version uniqueness | `release-gate.sh --quick` (`check_version_uniqueness.py --mode=local`) | Tag collision destroys the release. |
| PyPI version uniqueness | `release-gate.sh --pypi` (`check_version_uniqueness.py --mode=pypi`) | PyPI rejects upload of an already-published version; release fails halfway. |
| Lint + format (ruff) | `release-gate.sh --quick` | Already enforced on every PR; serves as belt-and-braces here. |
| CLI surface smoke (`autosearch --help`, `mcp-check`, `doctor --json`) | `release-gate.sh --quick` | Catches packaging breakage that unit tests miss. |

## Advisory checks (release continues; failures are reported but not fatal)

These appear in `pre_release_check.py` output prefixed with `[WARN]
[advisory]` and are summarized in the `ADVISORY: N/M passed` line. They
surface signal but do not change the script's exit code; the release
pipeline keeps going.

| Check | Where defined | Why advisory |
|---|---|---|
| Gate 12 bench ≥ 50% (augment-vs-bare) | `pre_release_check.py:_check_gate12_bench` | Real-LLM bench, slow + probabilistic. A green bench costs ~$5 and 15 min; running it inside release.yml every patch release is wasteful. Drift between bench and HEAD is normal. Failures here flag *quality regression candidates* for human triage, not release blockers. |

## Nightly / out-of-band checks (NOT in release.yml; run on schedule)

These run in dedicated workflows. They do not block any PR or release; they
post results (or open an issue on failure) for engineering follow-up.

| Check | Workflow | Cadence | Why out of band |
|---|---|---|---|
| E2B matrix release gate | `.github/workflows/e2b-nightly.yml` | Daily 02:00 UTC | E2B sandbox runs cost ~$0.25 each and 5-10 min wall time. The matrix exercises real install + first-use across multiple scenarios. Catches install-path regressions that only show up in a clean OS image. Daily cadence is enough — main gets at most a few merges per day. |
| Cross-platform install (Windows / macOS) | `.github/workflows/cross-platform.yml` | Weekly Monday 03:00 UTC | Slow runners (~15 min) and rarely catches anything new. Weekly is enough for Tier-2 platforms. |
| Live integration tests (real APIs) | `.github/workflows/nightly.yml` | Daily 02:00 UTC | Hits external APIs (Anthropic, OpenAI, GitHub, etc.). Real spend, real rate limits — cannot be on every PR. |

## How to change this policy

1. Edit this file.
2. If a check moves from mandatory → advisory, move it from
   `MANDATORY_CHECKS` to `ADVISORY_CHECKS` in
   `scripts/validate/pre_release_check.py`. Mandatory failures set the exit
   code to 1; advisory failures only emit a `[WARN] [advisory]` line.
   Reverse direction: move it back into `MANDATORY_CHECKS`.
3. If a check moves into / out of `release.yml`, edit the workflow.
4. Open one PR with all three changes. Title: `policy(release): <what>`.
   Reference this doc in the PR body.

## Audit trail

| Date | Change | Driver |
|---|---|---|
| 2026-04-26 | Initial version. Gate 12 → advisory. E2B matrix → nightly. | P0-4 from `autosearch-0425-p0-scan-report.md`. The release pipeline was bypassing `pre_release_check.py` entirely; this policy spells out exactly which subset must fire. |
