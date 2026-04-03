# AutoSearch

**Self-evolving deep research.** Gets smarter every time you use it.

Zero API keys. \
Claude Code plugin.

```
/autosearch "compare vector databases for RAG applications"
```

AutoSearch is a self-evolving research agent. It searches across channels you'd never check manually — Chinese tech blogs, academic papers, GitHub repos, Reddit threads, conference talks — synthesizes everything into a cited report, and then learns from the experience. Next time you research a similar topic, it already knows which queries work and which channels matter.

## Self-Evolution

This is the core differentiator. After every session, AutoSearch:

1. **Tracks per-query performance** — which queries found relevant results, which returned nothing
2. **Detects and fills gaps** — if a dimension has zero coverage, it automatically runs targeted follow-up searches
3. **Checks quality against rubrics** — auto-generated pass/fail criteria for every delivery
4. **Evolves its own skills** — diagnoses the weakest point, modifies search rules or channel selection, commits the improvement

The system uses a fixed evaluator (`judge.py`) that it cannot modify — evolution happens in the search strategy, not the scoring. This prevents Goodhart's Law (optimizing the metric instead of actual quality).

```
Session 1: searches "vector database" → finds 30 results, misses pricing info
Session 2: same topic → automatically includes pricing queries (learned from Session 1)
Session 3: new topic → applies winning query patterns across topics
```

## How It Works

```
You: /autosearch "topic"
 │
 ▼
[1] Recalls what Claude already knows → identifies gaps
 │
[2] Generates targeted queries (only for gaps, not what Claude already knows)
 │
[3] Searches channels in parallel via search_runner.py (~10 seconds)
 │
[4] Evaluates relevance, extracts dates, writes per-query outcomes
 │
[5] Detects critical gaps → runs follow-up search if needed (at most once)
 │
[6] Synthesizes report with citation lock (every URL from search results)
 │
[7] Checks quality rubrics → AVO evolution step → commits improvements
```

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

## Install

```bash
claude plugin marketplace add 0xmariowu/autosearch && claude plugin install autosearch@autosearch
```

Dependencies install automatically on first use (Python 3.10+ required).

## Usage

```bash
/autosearch "your research topic"
```

AutoSearch asks 3 questions before searching:

1. **Depth** — Quick (2 min) / Standard (5 min) / Deep (10+ min)
2. **Focus** — Open source / Academic / Commercial / Chinese / Community / All
3. **Format** — Executive summary / Comparison table / Full report / Resource list

## Search Channels

No API keys required. Every channel has a dedicated search implementation.

| Category | Channels |
|---|---|
| Code | github-repos, github-issues, npm-pypi, stackoverflow |
| Academic | arxiv, semantic-scholar, google-scholar, citation-graph |
| Community | reddit, hackernews, twitter/x, devto |
| Chinese | zhihu, bilibili, csdn, juejin, 36kr, wechat, weibo, xiaohongshu, douyin, xiaoyuzhou, xueqiu, infoq-cn |
| Video | youtube, bilibili, conference-talks |
| Business | producthunt, crunchbase, g2, linkedin |
| General | web-ddgs, rss |

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
  .claude-plugin/     Plugin manifest
  commands/           /autosearch:setup (auto-runs on first use)
  agents/             Researcher agent definition
  skills/             70+ skills (pipeline, synthesis, evaluation, evolution)
  channels/           32 channel plugins (SKILL.md + search.py each)
    _engines/         Shared backends (baidu, ddgs)
  lib/                search_runner.py, judge.py (fixed evaluator)
  state/              Append-only learning data (query outcomes, patterns, evolution log)
  scripts/            Setup and utility scripts
```

## License

MIT
