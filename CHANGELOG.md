# Changelog

## Unreleased

- fix(ci): update 6 sync-pack files to v1.4.1 canonical — shellcheck/actionlint/gitleaks/@copilot/tools[] fixes (Closes #208)
- feat(ci): bootstrap AI-native dev environment from sync pack v1.4 (Closes #203)
- docs(mcp): add per-client MCP config guide for Claude Code / Cursor / Zed / Continue; document `research` + `health` tools and the full input schema.
- chore(ci): port E2B validation orchestrator (`run_validation.py`, `bench_channels.py`, `bench_variance.py`, `lib/`) into repo `scripts/e2b/` so nightly/weekly CI workflows stop short-circuiting. Also fixes bench bugs — host-only E2B_API_KEY, null-safe variance summarize, docstring/CLI alignment.
- fix(ci): pin e2b nightly/weekly workflow `content-filepath` to a concrete date (was a glob peter-evans-create-issue-from-file silently ignored) + add a fallback "failure summary" step so auto-issues always have real content, even when the orchestrator crashed before writing summary.md.
- chore(nightly): add `scripts/nightly-local.sh` + macOS launchd / Linux systemd recipes in `docs/local-nightly.md` so Gate 13 observation-period evidence can be collected without GitHub Actions secrets.
- fix(clarify): add `AUTOSEARCH_BYPASS_CLARIFY` env var so batch / non-interactive callers can proceed past `need_clarification=true` instead of halting with CLI exit 2. Unblocks `zh_tech_moe`-class queries in the F203 variance bench.
- fix(m7): synthesizer prompt now enforces content-substance rules — concrete specifics (numbers, error codes, benchmarks, issue #s), no generic/meaningless conclusions, no repetition.
- fix(m3): evidence-compaction prompt now preserves specifics verbatim (numbers, error codes, issue numbers, benchmarks, version strings, named entities) instead of collapsing to 5-15 concise bullets. Aligns with the compress-research prompt pattern in open_deep_research.
