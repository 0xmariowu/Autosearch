# AutoSearch

A self-evolving research agent for Claude Code. Searches 32+ free channels, synthesizes cited reports, and learns from each session.

## What it does

You ask a research question. AutoSearch searches GitHub, arXiv, Reddit, Twitter, Hacker News, Zhihu, Bilibili, and 25+ other channels in parallel, evaluates results, and synthesizes a cited report with conceptual frameworks — not just a list of links.

```
/autosearch "compare vector databases for RAG applications"
```

## Why not just ask Claude?

| | Native Claude | AutoSearch |
|---|---|---|
| Knowledge cutoff | Training data only | Real-time search across 32+ channels |
| Citations | Often hallucinated URLs | Every URL verified from search results |
| Chinese content | Limited | Zhihu, Bilibili, CSDN, WeChat, and more |
| GitHub projects | From memory (may be outdated) | Live search sorted by stars |
| Community sentiment | None | Reddit, HN, Twitter discussions |
| Improves over time | No | AVO self-evolution after each session |

## Install

```bash
claude plugin install autosearch
/autosearch:setup
```

Setup creates a lightweight Python virtual environment at `~/.autosearch/venv/` with two dependencies (`ddgs`, `httpx`). Requires Python 3.10+.

## Usage

```bash
/autosearch "your research topic"
```

AutoSearch asks 3 quick questions before searching:

1. **Search depth** — Quick (2 min) / Standard (5 min) / Deep (10+ min)
2. **Focus areas** — Open source, academic, commercial, Chinese content, etc.
3. **Output format** — Executive summary / Comparison table / Full report / Resource list

Then it runs a 7-phase pipeline:

1. Recall what Claude already knows (identifies gaps)
2. Generate targeted queries (only for gaps)
3. Search 32+ channels in parallel (5-15 seconds)
4. Evaluate results for relevance
5. Synthesize into a cited report
6. Check quality against rubrics
7. Learn and evolve for next session

## Channels

32 search channels, all free, no API keys required:

| Category | Channels |
|---|---|
| Code | github-repos, github-issues, npm-pypi, stackoverflow |
| Academic | arxiv, semantic-scholar, google-scholar, citation-graph |
| Community | reddit, hn, twitter/x, devto |
| Chinese | zhihu, bilibili, csdn, juejin, 36kr, wechat, weibo, and more |
| Video | youtube, bilibili, conference-talks |
| Business | producthunt, crunchbase, g2, linkedin |
| General | web-ddgs, rss |

Each channel is a plugin with its own capability profile (`SKILL.md`) and search implementation (`search.py`). Add new channels by creating a directory under `channels/`.

## How it works

```
User question
    |
    v
[Phase 1] Claude recalls knowledge, identifies gaps
    |
    v
[Phase 2] search_runner.py searches all channels in parallel
    |        (32+ channels, 100+ results in 10 seconds)
    v
[Phase 3] LLM evaluates relevance (Haiku — fast and cheap)
    |
    v
[Phase 4] Synthesize report (Sonnet — quality writing)
    |        Two-stage citation lock: every URL from search results
    v
[Phase 5] Check rubrics (auto-generated quality contract)
    |
    v
[Phase 6] AVO evolution (learn from this session)
```

## Model routing

AutoSearch uses cheaper models for batch tasks to minimize cost:

| Task | Model |
|---|---|
| Query generation, scoring, rubric check | Haiku |
| Synthesis, AVO evolution | Sonnet |
| Search (HTTP requests) | No LLM needed |

## Self-evolution (AVO)

After each search session, AutoSearch:
1. Checks which quality rubrics passed/failed
2. Diagnoses the weakest point
3. Updates channel scores or skill rules
4. Commits the change (reverts if it doesn't help)

This means the system gets better at selecting channels, formulating queries, and synthesizing reports over time.

## Architecture

```
autosearch/
├── commands/          # /autosearch, /autosearch:setup
├── agents/            # Researcher agent definition
├── skills/            # 70+ skills (pipeline, synthesis, evaluation, evolution)
├── channels/          # 32 channel plugins (SKILL.md + search.py each)
│   ├── _engines/      # Shared backends (baidu, ddgs)
│   └── {channel}/     # One directory per channel
├── lib/               # search_runner.py (149 lines), judge.py
├── state/             # Append-only learning data
├── scripts/           # setup.sh, run_search.sh
└── hooks/             # SessionStart dependency check
```

## Adding a channel

```
channels/my-channel/
├── SKILL.md      # When to use, quality signals, blind spots
└── search.py     # async def search(query, max_results) -> list[dict]
```

See `channels/STANDARD.md` for the full spec.

## License

MIT
