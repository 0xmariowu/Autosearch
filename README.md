<h1 align="center">
  <img src="docs/assets/logo.png" alt="" height="60" align="absmiddle">&nbsp;AutoSearch
</h1>

<p align="center">
  <strong>Deep research MCP server for AI developers.</strong><br>
  39 search channels across academic, developer, and Chinese platforms — cited results, no hallucination.
</p>

<p align="center">
  <a href="https://github.com/0xmariowu/Autosearch/releases"><img src="https://img.shields.io/github/v/release/0xmariowu/Autosearch?style=flat-square" alt="Release"></a>
  <a href="LICENSE"><img src="https://img.shields.io/github/license/0xmariowu/Autosearch?style=flat-square" alt="License"></a>
  <a href="https://github.com/0xmariowu/Autosearch/actions/workflows/ci.yml"><img src="https://img.shields.io/github/actions/workflow/status/0xmariowu/Autosearch/ci.yml?style=flat-square&label=CI" alt="CI"></a>
  <img src="https://img.shields.io/badge/python-3.12%2B-blue?style=flat-square" alt="Python">
  <a href="https://www.npmjs.com/package/autosearch-ai"><img src="https://img.shields.io/npm/v/autosearch-ai?style=flat-square" alt="npm"></a>
</p>

<p align="center">
  <a href="https://docs.autosearch.dev">Docs</a> &bull;
  <a href="https://docs.autosearch.dev/install">Install</a> &bull;
  <a href="https://docs.autosearch.dev/channels">Channels</a> &bull;
  <a href="#mcp-tools">MCP Tools</a>
</p>

---

## Install

```bash
# Option 1 — npm (recommended, no Python setup required)
npm install -g autosearch-ai
autosearch-ai init

# Option 2 — pip
pip install autosearch
autosearch init
```

`init` auto-detects your LLM providers and writes the MCP config to `~/.claude/mcp.json` and `~/.cursor/mcp.json`.

---

## What it does

AutoSearch runs as an **MCP server** inside Claude Code, Cursor, or any MCP-compatible client. Your AI agent calls tools like `run_channel`, `delegate_subtask`, and `consolidate_research` — AutoSearch searches real sources and returns structured, cited results.

- **39 channels**: arxiv, PubMed, GitHub, Hacker News, Reddit, Xiaohongshu, Weibo, Twitter, Douyin, and more
- **22 MCP tools**: search, delegation, loop management, citation export
- **5 search modes**: academic / news / chinese_ugc / developer / product — auto-detected from query
- **No hallucination**: every result cites the source URL

---

## MCP Tools

| Tool | Description |
|---|---|
| `run_clarify` | Detect query intent, pick mode and channels |
| `run_channel` | Search one channel with dedup + BM25 ranking |
| `delegate_subtask` | Run multiple channels in parallel |
| `consolidate_research` | Compress evidence to prevent context overflow |
| `loop_init` / `loop_update` / `loop_gaps` | Deep research loop |
| `citation_create` / `citation_add` / `citation_export` | Citation management |
| `list_skills` / `list_channels` / `list_modes` | Discover available resources |
| `doctor` | Full channel health report with fix hints |

---

## Supported Channels

Run `autosearch doctor` to see live status. Generated from `autosearch/skills/channels/*/SKILL.md`.

<!-- channels-table-start -->
### Tier 0 - always-on (21)
| Channel | Languages | Description | Typical yield |
|---|---|---|---|
| arxiv | en | Use for academic preprint searches in CS/ML/physics when query is English or mixed and expects peer-reviewed or preprint papers. | medium-high |
| crossref | en | Cross-publisher scholarly search via the Crossref DOI registry, useful for journal articles, book chapters, and citation-linked research metadata. | medium |
| dblp | en | Computer science bibliography search — technical papers, proceedings, and journal articles indexed by venue, author, and year. | medium |
| ddgs | en, mixed | DuckDuckGo Search — free general web search with no auth, use as broad default for any English or mixed query. | medium |
| devto | en, mixed | Developer blog articles tagged by technology topic, via the public dev.to API. | medium |
| github | en | Use for code-level, issue-level, and repository discovery when query involves a library, framework, or implementation detail. | high |
| google_news | en, mixed | Current news headlines aggregated across publishers via Google News RSS (English US feed). | high |
| hackernews | en | Use for real-time developer discussion, tooling opinions, and early-stage product signals from the HN community. | medium-high |
| huggingface_hub | en, mixed | Discover open machine learning models on Hugging Face Hub via the public model search API. | high |
| infoq_cn | zh, mixed | Chinese engineering articles covering architecture, AI, and enterprise tech from InfoQ 中文, via public RSS feed. | medium |
| kr36 | zh, mixed | Chinese tech business news, startup funding, and industry analysis from 36kr. | medium |
| openalex | en, mixed | Search scholarly works through OpenAlex's public works search API with open-access URL fallback. | high |
| package_search | en, mixed | Discover packages across PyPI (exact-name lookup) and npm (full-text search) registries. | medium |
| papers | en, mixed | Multi-source academic paper search (arxiv, pubmed, biorxiv, medrxiv, google_scholar) via paper-search-mcp. | high |
| podcast_cn | zh, mixed | Chinese-language podcasts searchable via the Apple iTunes store public API. | low |
| reddit | en, mixed | Reddit community discussions, user experience reports, and topic debates via the public search.json endpoint. | medium |
| sec_edgar | en | US public company filings (10-K, 10-Q, 8-K) via SEC EDGAR full-text search — financial and regulatory disclosures for research. | medium |
| sogou_weixin | zh, mixed | Chinese WeChat Official Account articles via the public Sogou WeChat search SERP. | high |
| stackoverflow | en, mixed | Programming Q&A with community-voted answers across 200+ technical tags via api.stackexchange.com. | high |
| wikidata | en, mixed | Structured entity data (people, places, concepts) from Wikidata knowledge graph. | medium |
| wikipedia | en, mixed | Authoritative encyclopedia articles via the Wikipedia Action API (English edition). | high |

### Tier 1 - env-gated (1)
| Channel | Languages | Required env | Description | Typical yield |
|---|---|---|---|---|
| youtube | en, zh, mixed | env:YOUTUBE_API_KEY | Use for video tutorial discovery, conference talks, technical walkthroughs, and product demos. | medium |

### Tier 2 - BYOK paid (8)
| Channel | Languages | Required env | Description | Typical yield |
|---|---|---|---|---|
| bilibili | zh, mixed | env:TIKHUB_API_KEY | Chinese tech video platform with tutorials, conference recordings, and uploader-authored articles, via TikHub. | medium |
| douyin | zh | env:TIKHUB_API_KEY | Chinese short-video content with product demos, tech reviews, and viral trends, via TikHub. | medium |
| kuaishou | zh, mixed | env:TIKHUB_API_KEY | Chinese short-video platform with lifestyle, humor, regional culture, and product demos, via TikHub. | medium |
| tiktok | en, mixed | env:TIKHUB_API_KEY | Global short-video platform with creator content, product demos, viral trends, and topical reactions, via TikHub. | medium |
| twitter | en, mixed | env:TIKHUB_API_KEY | Real-time public discourse including product launches, tech announcements, and breaking news, via TikHub. | medium |
| weibo | zh, mixed | env:TIKHUB_API_KEY | Chinese microblog platform for real-time opinion, trending topics, and event-level commentary in Chinese discourse, via TikHub. | medium |
| xiaohongshu | zh, mixed | env:TIKHUB_API_KEY | Chinese lifestyle + experience-sharing notes with strong product/beauty/travel/food coverage, via TikHub. | high |
| zhihu | zh, mixed | env:TIKHUB_API_KEY | Chinese Q&A platform with deep technical discussions and user experience reports — use when query is Chinese or mixed and targets developer opinions, comparisons, or tutorials. | medium-high |
<!-- channels-table-end -->

---

## License

[MIT](LICENSE).
