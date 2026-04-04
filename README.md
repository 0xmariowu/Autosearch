<h1 align="center">AutoSearch</h1>

<p align="center">
  <strong>Research that gets smarter every time you use it.</strong><br>
  32 search channels. Self-evolving queries. Cited reports. Zero API keys.
</p>

<p align="center">
  <a href="https://github.com/0xmariowu/Autosearch/releases"><img src="https://img.shields.io/github/v/release/0xmariowu/Autosearch?style=flat-square" alt="Release"></a>
  <a href="LICENSE"><img src="https://img.shields.io/github/license/0xmariowu/Autosearch?style=flat-square" alt="License"></a>
  <a href="https://github.com/0xmariowu/Autosearch/actions/workflows/ci.yml"><img src="https://img.shields.io/github/actions/workflow/status/0xmariowu/Autosearch/ci.yml?style=flat-square&label=CI" alt="CI"></a>
  <img src="https://img.shields.io/badge/python-3.10%2B-blue?style=flat-square" alt="Python">
  <img src="https://img.shields.io/badge/channels-32-green?style=flat-square" alt="Channels">
</p>

<p align="center">
  <a href="#quick-start">Quick Start</a> &bull;
  <a href="#what-makes-it-different">What Makes It Different</a> &bull;
  <a href="#self-evolution">Self-Evolution</a> &bull;
  <a href="#how-it-works">How It Works</a> &bull;
  <a href="#channels">Channels</a> &bull;
  <a href="#contributing">Contributing</a>
</p>

---

## Quick Start

```bash
# Install (one command)
curl -fsSL https://raw.githubusercontent.com/0xmariowu/autosearch/main/scripts/install.sh | bash

# Use
/autosearch "compare vector databases for RAG applications"
```

AutoSearch asks two questions — how deep and what format — then searches, evaluates, and delivers a cited report with real-time progress:

```
[Phase 1/6] Prepare  — 25 rubrics, 47 items recalled, 15 queries planned
[Phase 2/6] Search   — 62 results from 12 channels
[Phase 3/6] Evaluate — 54 relevant, 3 gap queries
[Phase 4/6] Deliver  — report ready (38 citations)
[Phase 5/6] Quality  — 23/25 rubrics passed
[Phase 6/6] Evolve   — 4 patterns saved
```

## What Makes It Different

| | AutoSearch | Perplexity | Native Claude |
|---|---|---|---|
| **Search channels** | 32 dedicated connectors | ~3 web engines | 1 (WebSearch) |
| **Chinese sources** | 12 native (zhihu, bilibili, 36kr, csdn...) | 0 | 0 |
| **Academic sources** | 6 (arXiv, Semantic Scholar, OpenReview, Papers with Code...) | 1 | 0 |
| **Gets smarter over time** | Yes — learns which queries and channels work | No | No |
| **Every result cited** | Yes (two-stage citation lock) | Yes (URL-level) | No |
| **Reports** | Markdown / Rich HTML / Slides | Web page | Plain text |
| **Cost** | Free (Claude Code plugin) | $20/month | Free |
| **Integration** | Native inside Claude Code | Separate tool | Built-in but limited |

## Self-Evolution

This is the core idea. Most search tools run the same strategy every time. AutoSearch learns from every session and gets measurably better.

**How it works**: after each search, AutoSearch records which queries found relevant results and which returned nothing. Next time, it skips what failed and doubles down on what worked. Over sessions, it builds a profile of which channels are useful for which types of topics.

**What it looks like in practice**:

```
Session 1: "vector databases for RAG"
  → Searched 15 channels, 8 had results
  → Learned: arxiv + github-repos are high-yield for this topic
  → Learned: producthunt and crunchbase returned nothing useful
  → Saved 3 winning query patterns

Session 2: same topic, 2 weeks later
  → Auto-skipped channels that failed last time
  → Reused winning query patterns, added freshness filter
  → Found 12 new results the first session missed
  → Score improved: 0.65 → 0.78

Session 3: different topic ("AI agent frameworks")
  → Applied cross-topic patterns (arxiv query structure, github star filter)
  → Reached 0.71 on first attempt (vs 0.58 baseline)
```

**The safety mechanism**: the evaluator (`judge.py`) is fixed and cannot be modified by evolution. Only search strategy evolves — not the scoring. This prevents the system from gaming its own metrics.

## How It Works

```
You: /autosearch "topic"
 │
 ▼
[1] Claude recalls what it already knows → maps 9 knowledge dimensions
 │
[2] Identifies gaps → generates queries ONLY for what Claude doesn't know
 │
[3] Searches 32 channels in parallel (10-30 seconds)
 │
[4] LLM evaluates each result for relevance, filters noise
 │
[5] Synthesizes report with two-stage citation lock
 │
[6] Checks quality rubrics → evolves strategy → commits improvements
```

**The key insight**: Claude already knows 60-70% of most research topics from training data. AutoSearch doesn't waste time re-searching what Claude already knows. It maps gaps first, then searches specifically for fresh data, community voice, Chinese sources, and niche repositories that Claude's training missed.

## Channels

32 channels. No API keys required. Every channel has a dedicated search connector — not just web search with `site:` filters.

| Category | Channels | Why it matters |
|---|---|---|
| **Code** | github-repos, github-issues, github-code, npm-pypi, stackoverflow | Find actual implementations, not just articles about them |
| **Academic** | arxiv, semantic-scholar, google-scholar, citation-graph, papers-with-code, openreview | Latest papers + code, conference proceedings, citation networks |
| **Community** | reddit, hackernews, twitter/x, devto | Real user experiences, not marketing |
| **Chinese** | zhihu, bilibili, csdn, juejin, 36kr, wechat, weibo, xiaohongshu, douyin, xiaoyuzhou, xueqiu, infoq-cn | 12 platforms. No other research tool covers the Chinese internet like this |
| **Video** | youtube, bilibili, conference-talks | Tutorials, demos, conference keynotes with transcript extraction |
| **Business** | producthunt, crunchbase, g2, linkedin | Startup discovery, funding data, real user reviews |
| **General** | web-ddgs, rss | Broad web coverage as a baseline |

Optional: add Exa or Tavily API keys for semantic search capabilities.

## Why I Built This

I kept doing the same research workflow manually: search Google, then Reddit, then GitHub, then arXiv, then three Chinese platforms — 30 minutes per topic, and I'd always miss something. The worst part: every session started from zero. I'd forget which queries worked last time.

AutoSearch automates the multi-platform search I was already doing. But the part that actually matters is that it learns. After 10 sessions on AI topics, it stopped wasting queries on channels that never returned relevant results for that domain and started using query patterns that consistently found what I needed.

## Update

```bash
claude plugin update autosearch@autosearch
```

Or re-run the install script. To enable auto-updates: `/plugin` > Marketplaces > autosearch > Enable auto-update.

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
