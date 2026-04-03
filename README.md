# AutoSearch

**Research better than Claude alone.** A self-evolving research agent that searches 32+ free channels in parallel, synthesizes cited reports, and gets smarter after every session.

```
/autosearch "compare vector databases for RAG applications"
```

## Install

**One-liner** (paste in terminal):

```bash
claude plugin marketplace add 0xmariowu/autosearch && claude plugin install autosearch@autosearch
```

Or use the install script:

```bash
curl -fsSL https://raw.githubusercontent.com/0xmariowu/autosearch/main/scripts/install.sh | bash
```

Then open Claude Code and run:

```
/autosearch:setup
```

Setup creates a lightweight Python venv at `~/.autosearch/venv/` with two dependencies (`ddgs`, `httpx`). Requires Python 3.10+.

## Benchmark: AutoSearch vs Native Claude

Tested on 5 topics across academic, tools, business, Chinese, and how-to categories:

| Topic | AutoSearch | Native Claude | Delta |
|---|---|---|---|
| Self-evolving AI agents | 88% | 76% | +12% |
| Vector databases for RAG | 100% | 70% | +30% |
| AI coding market 2026 | 87% | 67% | +20% |
| Chinese LLM ecosystem | 92% | 83% | +8% |
| Production RAG systems | 93% | 67% | +27% |
| **Overall** | **92%** | **72%** | **+20%** |

Scored with auto-generated rubrics measuring information recall, analysis depth, and citation quality.

## Why AutoSearch?

| | Native Claude | AutoSearch |
|---|---|---|
| Knowledge | Training data only | Real-time search across 32+ channels |
| Citations | Often hallucinated URLs | Every URL verified from search results |
| Chinese content | Limited | Zhihu, Bilibili, CSDN, WeChat, 36kr, and more |
| GitHub projects | From memory (outdated) | Live search sorted by stars |
| Community voice | None | Reddit, HN, Twitter discussions |
| Cost efficiency | Uses one model for everything | Haiku for scoring, Sonnet for synthesis |
| Improvement | Static | Self-evolving after each session |

## Usage

```bash
/autosearch "your research topic"
```

AutoSearch asks 3 questions before searching:

1. **Depth** — Quick (2 min, 5 channels) / Standard (5 min, 10 channels) / Deep (10+ min, 15+ channels)
2. **Focus** — Open source / Academic / Commercial / Chinese / Community / Video / All
3. **Format** — Executive summary / Comparison table / Full report / Resource list

Then runs a 7-phase pipeline: recall gaps, generate queries, search 32+ channels in parallel, evaluate relevance, synthesize with citation lock, check quality rubrics, learn and evolve.

## 32 Free Search Channels

No API keys required. Every channel has a capability profile and dedicated search implementation.

| Category | Channels |
|---|---|
| Code | github-repos, github-issues, npm-pypi, stackoverflow |
| Academic | arxiv, semantic-scholar, google-scholar, citation-graph |
| Community | reddit, hn, twitter/x, devto |
| Chinese | zhihu, bilibili, csdn, juejin, 36kr, wechat, weibo, xiaohongshu, douyin, xiaoyuzhou, xueqiu, infoq-cn |
| Video | youtube, bilibili, conference-talks |
| Business | producthunt, crunchbase, g2, linkedin |
| General | web-ddgs, rss |

## How It Works

```
You: /autosearch "topic"
 |
 v
[1] Claude recalls what it knows → identifies gaps
 |
[2] Generates targeted queries (only for gaps, not what Claude already knows)
 |
[3] Searches 32+ channels in parallel via search_runner.py (10 seconds)
 |
[4] Evaluates relevance with Haiku (cheap, fast)
 |
[5] Synthesizes report with Sonnet (citation lock: every URL from search results)
 |
[6] Checks quality against auto-generated rubrics
 |
[7] AVO evolution: diagnoses weakest point, updates channel scores or skills
```

## Self-Evolution

After each session, AutoSearch:
1. Checks which quality rubrics passed/failed
2. Diagnoses the root cause (wrong channels? missed queries? weak synthesis?)
3. Updates data files (channel scores) or skill rules
4. Commits improvements, reverts if they don't help

The system gets better at channel selection, query formulation, and report synthesis over time.

## Adding a Channel

Each channel is a directory with two files:

```
channels/my-channel/
  SKILL.md      # Capability profile: what it finds, blind spots, quality signals
  search.py     # async def search(query: str, max_results: int = 10) -> list[dict]
```

See `channels/STANDARD.md` for the full spec.

## Architecture

```
autosearch/
  .claude-plugin/     Plugin manifest + marketplace catalog
  commands/           /autosearch, /autosearch:setup
  agents/             Researcher agent definition
  skills/             70+ skills (pipeline, synthesis, evaluation, evolution)
  channels/           32 channel plugins (SKILL.md + search.py each)
    _engines/         Shared backends (baidu, ddgs)
  lib/                search_runner.py (149 lines), judge.py
  state/              Append-only learning data (patterns, scores, evolution log)
  scripts/            setup.sh, run_search.sh
  hooks/              SessionStart dependency check
```

## License

MIT
