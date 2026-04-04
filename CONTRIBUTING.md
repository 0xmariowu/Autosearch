# Contributing to AutoSearch

## Development Setup

```bash
git clone https://github.com/0xmariowu/Autosearch.git
cd Autosearch

# Create venv and install deps
bash scripts/setup.sh

# Activate hooks
npx husky

# Run tests
PYTHONPATH=. .venv/bin/python3 -m pytest tests/ -x -q -m "not network"

# Lint
ruff check . && ruff format --check .
```

## Adding a Channel

1. Create `channels/{name}/SKILL.md` — follow `channels/web-ddgs/SKILL.md` as template
2. Create `channels/{name}/search.py` — export `async def search(query: str, max_results: int) -> list[dict]`
3. Each result must have `url`, `title`, `snippet` keys
4. Run `PYTHONPATH=. .venv/bin/python3 -m pytest tests/test_channels_smoke.py -x` to verify

## PR Rules

- One logical change per commit
- Source code first, tests second, docs third
- `ruff check && ruff format --check` must pass
- `pytest -x -q -m "not network"` must pass
- PR stays under 5 commits
- Feature commits need corresponding test commits
- Bump version with `scripts/bump-version.sh` if source files changed

## What We Won't Accept

- PRs that only refactor without fixing a bug or adding a feature
- PRs that remove channels (channels are a competitive advantage)
- PRs that modify `PROTOCOL.md`, `lib/judge.py`, or meta-skills without prior discussion
- PRs with secrets, API keys, or personal paths

## Commit Convention

This project uses [Conventional Commits](https://www.conventionalcommits.org/):

```
feat: add new channel
fix: correct search result dedup
test: add channel contract tests
chore: update dependencies
docs: improve README
```

Use `scripts/committer "type: message" file1 file2` to commit (enforced by pre-commit hook).
