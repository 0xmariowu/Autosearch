# Changelog

## Unreleased

- fix(ci): update 6 sync-pack files to v1.4.1 canonical — shellcheck/actionlint/gitleaks/@copilot/tools[] fixes (Closes #208)
- feat(ci): bootstrap AI-native dev environment from sync pack v1.4 (Closes #203)
- docs(mcp): add per-client MCP config guide for Claude Code / Cursor / Zed / Continue; document `research` + `health` tools and the full input schema.
- chore(ci): port E2B validation orchestrator (`run_validation.py`, `bench_channels.py`, `bench_variance.py`, `lib/`) into repo `scripts/e2b/` so nightly/weekly CI workflows stop short-circuiting. Also fixes bench bugs — host-only E2B_API_KEY, null-safe variance summarize, docstring/CLI alignment.
- fix(ci): pin e2b nightly/weekly workflow `content-filepath` to a concrete date (was a glob peter-evans-create-issue-from-file silently ignored) + add a fallback "failure summary" step so auto-issues always have real content, even when the orchestrator crashed before writing summary.md.
