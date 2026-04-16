# E2B Channel Matrix Day 1

Day 1 only builds the harness, two pilot adapters, and a smoke path. It does not run the full matrix and it does not add any custom E2B templates.

## Layout

- `harness/`: shared schema, sandbox wrapper, scoring, registry
- `queries/standard.json`: the 20-query standard set from the plan
- `adapters/bilibili__nemo2011`: third-party Bilibili SDK adapter
- `adapters/seo__bing_via_ddgs`: DDGS-based SEO fallback adapter
- `runner.py`: `--dry-run`, `--smoke`, `--full`

## Commands

```bash
python tests/e2b-channel-matrix/runner.py --dry-run
python tests/e2b-channel-matrix/runner.py --smoke
python tests/e2b-channel-matrix/runner.py --full
pytest tests/e2b-channel-matrix/ -x -q
ruff check tests/e2b-channel-matrix/
ruff format --check tests/e2b-channel-matrix/
```

## Notes

- `E2B_API_KEY` is loaded from the repo root `.env` with `python-dotenv`.
- `tests/e2b-channel-matrix/reports/` is runtime output and stays out of git.
- Day 2 TODO: move pilot adapters onto purpose-built templates such as `as-python-http`.
