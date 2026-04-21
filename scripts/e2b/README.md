# E2B Validation Orchestrator

Run reusable validation matrices against parallel E2B sandboxes.

## Quickstart

1. Define phases and tasks in a matrix YAML under `phases:`.
2. Put secrets in `~/.config/ai-secrets.env` as plain `KEY=VALUE` lines.
3. Run `.venv/bin/python run_validation.py --project my-project --matrix tests/sample-matrix.yaml --output /tmp/e2b-run`.
4. Use `--parallel N` to set the default phase fanout, capped at `20`.
5. Use `--phase F002_install,F003_smoke` to run only selected phases.
6. Use `--tarball dist/src.tar.gz` to upload one shared tarball to every sandbox at `/tmp/<filename>`.
7. Use `--source-dir PATH` instead to build a temporary tarball with `.git`, `.venv`, `__pycache__`, `.pytest_cache`, and `*.egg-info` excluded.
8. `--source-dir` and `--tarball` are mutually exclusive.
9. Phases run sequentially; sandboxes inside a phase run via `ThreadPoolExecutor`.
10. Each sandbox executes the full phase task list in order.
11. `setup_env_keys` forwards named secrets into the phase setup command once per sandbox.
12. `env_keys` forwards only named secrets for each task, resolving from the secrets file first and then the host environment; `unset_env` removes overlapping keys.
13. Reports land in `summary.md`, `summary.json`, and per-phase task JSON/stdout/stderr files.
