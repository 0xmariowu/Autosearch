<h1 align="center">
  <img src="docs/assets/logo.png" alt="" height="60" align="absmiddle">&nbsp;AutoSearch
</h1>

<p align="center">
  <strong>Open-source deep research tool for AI coding developers.</strong><br>
  Structured coverage across English and Chinese sources, cited markdown reports.
</p>

<p align="center">
  <a href="https://github.com/0xmariowu/Autosearch/releases"><img src="https://img.shields.io/github/v/release/0xmariowu/Autosearch?style=flat-square" alt="Release"></a>
  <a href="LICENSE"><img src="https://img.shields.io/github/license/0xmariowu/Autosearch?style=flat-square" alt="License"></a>
  <a href="https://github.com/0xmariowu/Autosearch/actions/workflows/ci.yml"><img src="https://img.shields.io/github/actions/workflow/status/0xmariowu/Autosearch/ci.yml?style=flat-square&label=CI" alt="CI"></a>
  <img src="https://img.shields.io/badge/python-3.12%2B-blue?style=flat-square" alt="Python">
  <img src="https://img.shields.io/badge/status-v2%20alpha-orange?style=flat-square" alt="Status">
</p>

<p align="center">
  <a href="#status">Status</a> &bull;
  <a href="#quick-start">Quick Start</a> &bull;
  <a href="#architecture">Architecture</a> &bull;
  <a href="#interfaces">Interfaces</a> &bull;
  <a href="docs/delivery-status.md">Delivery Status</a>
</p>

---

## Status

AutoSearch is undergoing a full **v2 rewrite** (`legacy-v1` tag preserves the v1 state). v2 replaces the monolithic v1 with a modular pipeline (M0–M8) behind strict source-mapped reuse of proven deep-research projects. Channel adapters (the real data sources) are on the roadmap — the current release ships a `DemoChannel` placeholder so the end-to-end pipeline is exercisable.

See [`docs/delivery-status.md`](docs/delivery-status.md) for a module-by-module checklist.

## Quick Start

**Dev install (current — no PyPI release yet):**

```bash
git clone https://github.com/0xmariowu/Autosearch
cd Autosearch
uv venv --python 3.12
uv pip install -e . --python .venv/bin/python
.venv/bin/autosearch query "your topic"
```

**After the first tagged v2 release:**

```bash
pipx install autosearch
autosearch query "your topic"
```

Requirements: Python 3.12+. Set one of `ANTHROPIC_API_KEY`, `OPENAI_API_KEY`, `GOOGLE_API_KEY`, or have the `claude` CLI on `PATH` — the LLM layer auto-detects the first available provider.

Streaming progress to stderr is default (`--stream`); suppress with `--no-stream` or use `--json` for a machine-readable envelope:

```bash
autosearch query "retrieval-augmented generation survey" --json
```

## Architecture

```
query
  ↓
M0 Knowledge Recall (known facts + gaps)
M1 Goal Crystallization + Clarify (rubrics + mode)
M2 Search Strategy (subqueries)
M3 Iteration Controller (reflect-on-gaps loop across channels)
M4 Material Cleaner (trafilatura)
M5 Evidence Processor (URL dedup + SimHash + BM25)
M7 Report Synthesizer (outline + per-section + citation remap)
M8 Quality Gate (rubric evaluation, one retry on fail)
  ↓
markdown + References + Sources breakdown
```

Observability (`CostTracker`) and persistence (`SessionStore`, three-table SQLite schema) are available as Pipeline constructor args.

Each module traces to a 1:1 source in a well-known deep-research project — see `docs/delivery-status.md` for the mapping.

## Interfaces

AutoSearch runs as:

- **CLI**: `autosearch query "..."`
- **HTTP + SSE**: `autosearch serve` — `POST /search` streams typed events (`phase` / `iteration` / `gap` / `quality` / `finished`)
- **MCP server**: `autosearch mcp` (or `autosearch-mcp` console script) — exposes a `research` tool to Claude Code, Cursor, and other MCP clients
- **Claude Code slash command**: `/autosearch` (ships in `commands/autosearch.md`)

## Supported Channels

Generated from `autosearch/skills/channels/*/SKILL.md`. Run `.venv/bin/python scripts/generate_channels_table.py` after adding or changing a channel.

<!-- channels-table-start -->
### Tier 0 - always-on (16)
| Channel | Languages | Description | Typical yield |
|---|---|---|---|
| arxiv | en | Use for academic preprint searches in CS/ML/physics when query is English or mixed and expects peer-reviewed or preprint papers. | medium-high |
| ddgs | en, mixed | DuckDuckGo Search — free general web search with no auth, use as broad default for any English or mixed query. | medium |
| devto | en, mixed | Developer blog articles tagged by technology topic, via the public dev.to API. | medium |
| github | en | Use for code-level, issue-level, and repository discovery when query involves a library, framework, or implementation detail. | high |
| google_news | en, mixed | Current news headlines aggregated across publishers via Google News RSS (English US feed). | high |
| hackernews | en | Use for real-time developer discussion, tooling opinions, and early-stage product signals from the HN community. | medium-high |
| infoq_cn | zh, mixed | Chinese engineering articles covering architecture, AI, and enterprise tech from InfoQ 中文, via public RSS feed. | medium |
| kr36 | zh, mixed | Chinese tech business news, startup funding, and industry analysis from 36kr. | medium |
| package_search | en, mixed | Discover packages across PyPI (exact-name lookup) and npm (full-text search) registries. | medium |
| papers | en, mixed | Multi-source academic paper search (arxiv, pubmed, biorxiv, medrxiv, google_scholar) via paper-search-mcp. | high |
| podcast_cn | zh, mixed | Chinese-language podcasts searchable via the Apple iTunes store public API. | low |
| reddit | en, mixed | Reddit community discussions, user experience reports, and topic debates via the public search.json endpoint. | medium |
| sogou_weixin | zh, mixed | Chinese WeChat Official Account articles via the public Sogou WeChat search SERP. | high |
| stackoverflow | en, mixed | Programming Q&A with community-voted answers across 200+ technical tags via api.stackexchange.com. | high |
| wikidata | en, mixed | Structured entity data (people, places, concepts) from Wikidata knowledge graph. | medium |
| wikipedia | en, mixed | Authoritative encyclopedia articles via the Wikipedia Action API (English edition). | high |

### Tier 1 - env-gated (1)
| Channel | Languages | Required env | Description | Typical yield |
|---|---|---|---|---|
| youtube | en, zh, mixed | env:YOUTUBE_API_KEY | Use for video tutorial discovery, conference talks, technical walkthroughs, and product demos. | medium |

### Tier 2 - BYOK paid (6)
| Channel | Languages | Required env | Description | Typical yield |
|---|---|---|---|---|
| bilibili | zh, mixed | env:TIKHUB_API_KEY | Chinese tech video platform with tutorials, conference recordings, and uploader-authored articles, via TikHub. | medium |
| douyin | zh | env:TIKHUB_API_KEY | Chinese short-video content with product demos, tech reviews, and viral trends, via TikHub. | medium |
| twitter | en, mixed | env:TIKHUB_API_KEY | Real-time public discourse including product launches, tech announcements, and breaking news, via TikHub. | medium |
| weibo | zh, mixed | env:TIKHUB_API_KEY | Chinese microblog platform for real-time opinion, trending topics, and event-level commentary in Chinese discourse, via TikHub. | medium |
| xiaohongshu | zh, mixed | env:TIKHUB_API_KEY | Chinese lifestyle + experience-sharing notes with strong product/beauty/travel/food coverage, via TikHub. | high |
| zhihu | zh, mixed | env:TIKHUB_API_KEY | Chinese Q&A platform with deep technical discussions and user experience reports — use when query is Chinese or mixed and targets developer opinions, comparisons, or tutorials. | medium-high |
<!-- channels-table-end -->

## Contributing

The v1 architecture (`skills/`, `channels/*/SKILL.md`, AVO self-evolution loop) was retired in v2. Contributions targeting the v2 architecture are welcome — the module map in `docs/delivery-status.md` is the starting point.

## License

[MIT](LICENSE).
