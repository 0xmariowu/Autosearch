<h1 align="center">AutoSearch</h1>

<p align="center">
  <strong>Claude Code can't search the real internet. AutoSearch gives it 32 channels, self-improving queries, and cited reports. Zero API keys.</strong>
</p>

<p align="center">
  <a href="https://github.com/0xmariowu/Autosearch/releases"><img src="https://img.shields.io/github/v/release/0xmariowu/Autosearch?style=flat-square" alt="Release"></a>
  <a href="LICENSE"><img src="https://img.shields.io/github/license/0xmariowu/Autosearch?style=flat-square" alt="License"></a>
  <a href="https://github.com/0xmariowu/Autosearch/actions/workflows/ci.yml"><img src="https://img.shields.io/github/actions/workflow/status/0xmariowu/Autosearch/ci.yml?style=flat-square&label=CI" alt="CI"></a>
  <img src="https://img.shields.io/badge/python-3.10%2B-blue?style=flat-square" alt="Python">
  <img src="https://img.shields.io/badge/channels-32-green?style=flat-square" alt="Channels">
</p>

<p align="center">
  <a href="#install">Install</a> &bull;
  <a href="#benchmark">Benchmark</a> &bull;
  <a href="#how-it-works">How It Works</a> &bull;
  <a href="#channels">Channels</a> &bull;
  <a href="#self-evolution">Self-Evolution</a> &bull;
  <a href="#contributing">Contributing</a>
</p>

---

<!-- TODO: Replace with terminal recording (asciinema/vhs) showing /autosearch in action -->
<!-- ![AutoSearch Demo](assets/demo.gif) -->

## Quick Start

```bash
# Install (one command)
curl -fsSL https://raw.githubusercontent.com/0xmariowu/autosearch/main/scripts/install.sh | bash

# Use
/autosearch "compare vector databases for RAG applications"
```

AutoSearch asks depth (Quick / Standard / Deep), focus, and delivery format — then searches, evaluates, and delivers a cited report with real-time progress:

```
[Phase 1/6] ✓ Prepare — 25 rubrics, 47 items recalled, 15 queries planned
[Phase 2/6] ✓ Search — 62 results from 12 channels
[Phase 3/6] ✓ Evaluate — 54 relevant, 3 gap queries
[Phase 4/6] ✓ Deliver — report ready (38 citations, judge score 0.82)
[Phase 5/6] ✓ Quality — 23/25 rubrics passed
[Phase 6/6] ✓ Evolve — 4 patterns saved
```

## Benchmark

Tested on 5 topics across academic, tools, business, Chinese, and how-to categories:

| Topic | AutoSearch | Native Claude | Delta |
|---|---|---|---|
| Self-evolving AI agents | 88% | 76% | **+12%** |
| Vector databases for RAG | 100% | 70% | **+30%** |
| AI coding market 2026 | 87% | 67% | **+20%** |
| Chinese LLM ecosystem | 92% | 83% | **+8%** |
| Production RAG systems | 93% | 67% | **+27%** |
| **Overall** | **92%** | **72%** | **+20%** |

Scored with auto-generated rubrics measuring information recall, analysis depth, and citation quality.

## How It Works

```
You: /autosearch "topic"
 │
 ▼
[1] Claude recalls what it knows → identifies knowledge gaps
 │
[2] Generates targeted queries (only for gaps, not what Claude already knows)
 │
[3] Searches 32 channels in parallel via search_runner.py
 │
[4] Evaluates relevance with LLM scoring, filters noise
 │
[5] Synthesizes report with two-stage citation lock (every URL from search results)
 │
[6] Checks quality rubrics → evolves search strategy for next time
```

**Key insight**: Claude already knows 60-70% of most topics. AutoSearch only searches for the gaps — fresh data, community voice, Chinese sources, niche repos. This makes it faster and more focused than "search everything" tools.

## Channels

32 channels. No API keys required. Every channel has a dedicated connector.

| Category | Channels |
|---|---|
| Code | github-repos, github-issues, github-code, npm-pypi, stackoverflow |
| Academic | arxiv, semantic-scholar, google-scholar, citation-graph, papers-with-code, openreview |
| Community | reddit, hackernews, twitter/x, devto |
| Chinese | zhihu, bilibili, csdn, juejin, 36kr, wechat, weibo, xiaohongshu, douyin, xiaoyuzhou, xueqiu, infoq-cn |
| Video | youtube, bilibili, conference-talks |
| Business | producthunt, crunchbase, g2, linkedin |
| General | web-ddgs, rss |

Optional paid channels (Exa, Tavily) unlock semantic search — see `env.example` for keys.

## Self-Evolution

After every session, AutoSearch:

1. **Tracks per-query performance** — which queries found relevant results, which returned nothing
2. **Detects and fills gaps** — if a dimension has zero coverage, runs targeted follow-up searches
3. **Checks quality against rubrics** — auto-generated pass/fail criteria
4. **Evolves its own skills** — diagnoses the weakest point, modifies search rules, commits the improvement

The evaluator (`judge.py`) is fixed and cannot be modified by evolution — only search strategy evolves. This prevents gaming the metric.

```
Session 1: "vector database" → finds 30 results, misses pricing info
Session 2: same topic → auto-includes pricing queries (learned from Session 1)
Session 3: new topic → applies winning query patterns across topics
```

## Why AutoSearch

| | AutoSearch | Native Claude | Perplexity |
|---|---|---|---|
| Sources | 32 dedicated channels | Claude's training data only | Web search + 1 engine |
| Chinese sources | 12 native channels (zhihu, bilibili, etc.) | None | Limited |
| Self-improvement | Learns from every session | Static | Static |
| Academic coverage | arXiv, Semantic Scholar, OpenReview | Training cutoff | Surface-level |
| Citation quality | Two-stage lock, every URL verified | No citations | URL-level |
| Cost | Free (included in Claude Code) | Free | $20/mo |
| Integration | Native Claude Code plugin | Built-in | Separate tool |

## Why I Built This

I kept doing the same research workflow manually: search Google, then Reddit, then GitHub, then arXiv, then Chinese platforms — 30 minutes per topic, and I'd always miss something. AutoSearch automates the multi-platform search I was already doing, but it also learns what works. After 10 sessions on AI topics, it knew that arXiv + GitHub + zhihu was the winning combination and stopped wasting queries on channels that never returned relevant results for that domain.

## Update

```bash
claude plugin update autosearch@autosearch
```

Or re-run the install script. To enable auto-updates: `/plugin` → Marketplaces → autosearch → Enable auto-update.

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md) for dev setup, PR rules, and how to add a channel.

## Architecture

<details>
<summary>Directory structure</summary>

```
autosearch/
  .claude-plugin/     Plugin manifest (version, metadata)
  commands/           /autosearch entry point + setup
  agents/             Researcher agent definition
  skills/             40+ skills (pipeline, synthesis, evaluation, evolution)
  channels/           32 channel plugins (SKILL.md + search.py each)
    _engines/         Shared backends (baidu, ddgs)
  lib/                search_runner.py, judge.py (fixed evaluator)
  state/              Append-only learning data
  scripts/            Setup, install, version management
```

</details>

## License

MIT
