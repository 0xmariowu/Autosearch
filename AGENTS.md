# AGENTS.md — AI Contributor Context

## Directory Layout

```
channels/          32 search channel plugins (SKILL.md + search.py each)
skills/            40+ pipeline skills (SKILL.md each)
lib/               Core runtime: judge.py, search_runner.py
commands/          Claude Code slash commands
agents/            Claude Code agent definitions
scripts/           Shell scripts (install, setup, bump-version, committer)
state/             Runtime state (gitignored except config.json, channels.json)
evidence/          Search results (gitignored except .gitkeep)
delivery/          Generated reports (gitignored except .gitkeep)
tests/             pytest test suite
docs/methodology/  Search methodology knowledge base
```

## Immutable Files (do not modify)

- `PROTOCOL.md` — agent operating protocol
- `lib/judge.py` — scoring function (the "f" in AVO)
- `skills/create-skill/`, `skills/observe-user/`, `skills/extract-knowledge/`, `skills/interact-user/`, `skills/discover-environment/` — meta-skills

## Safe to Modify

- `channels/*/search.py` — channel implementations
- `skills/*/SKILL.md` — non-meta skills
- `lib/search_runner.py` — search execution engine
- `tests/` — test files
- `state/config.json` — scoring weights and thresholds

## Naming Conventions

- Channels: lowercase, hyphens, match directory name (e.g., `github-repos`)
- Skills: lowercase, hyphens, max 64 chars (e.g., `search-github-repos`)
- Tests: `test_{module}.py` with `test_` prefix on functions

## Running Tests

```bash
PYTHONPATH=. .venv/bin/python3 -m pytest tests/ -x -q -m "not network"
```

## Key Contracts

- Every channel's `search()` returns `list[dict]` with `url`, `title`, `snippet` keys
- `judge.py` scores on 7 dimensions: quantity, diversity, relevance, freshness, efficiency, latency, adoption
- Skills use YAML frontmatter: `name` + `description` (first sentence = WHEN to use)
