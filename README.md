<h1 align="center">
  <img src="docs/assets/logo.png" alt="" height="60" align="absmiddle">&nbsp;AutoSearch
</h1>

<p align="center">
  <strong>40 search channels for your AI Agent</strong>
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
  <a href="README.zh.md">中文</a>
</p>

---

You ask your AI to research something. It answers from training data cutoff —

- "Show me this week's LLM papers on arxiv" → **can't**, no academic database access
- "What are people saying about this product on Reddit" → **shallow**, only surface-level web results
- "Find similar open-source projects on GitHub" → **weak**, general search misses most repos
- "Summarize the Twitter discussion on this topic" → **blocked**, no public API
- "Compare opinions on Hacker News vs Chinese tech forums" → two platforms, manual aggregation

**AutoSearch fixes this in one line.**

Paste into your AI Agent (Claude Code, Cursor, etc.):

```
Help me install AutoSearch: https://raw.githubusercontent.com/0xmariowu/Autosearch/main/docs/install.md
```

Or install directly:

```bash
npx autosearch-ai
```

```bash
curl -fsSL https://raw.githubusercontent.com/0xmariowu/Autosearch/main/scripts/install.sh | bash
```

After install, your Agent searches 40 channels simultaneously — academic papers, developer communities, Chinese social media, and Linux DO forum threads — results deduplicated and ranked, every result includes a source URL.

---

## Channels

| Channel | Ready out of box | Unlocked after config | How to configure |
|---------|-----------------|----------------------|-----------------|
| 📄 **arxiv** | Academic preprints CS/ML/Physics | — | No config needed |
| 🔬 **PubMed / OpenAlex / DBLP** | Biomedical + cross-discipline papers | — | No config needed |
| 🐙 **GitHub** | Code, Issues, repository search | — | No config needed |
| 🔍 **DuckDuckGo** | General web search | — | No config needed |
| 🟠 **Hacker News** | Developer discussions + early product signals | — | No config needed |
| 📖 **Reddit** | Community discussion + real user experiences | — | No config needed |
| 🤗 **Hugging Face** | Open-source ML model search | — | No config needed |
| 📦 **Stack Overflow** | Programming Q&A | — | No config needed |
| 📰 **Google News** | Real-time news aggregation | — | No config needed |
| 💻 **dev.to** | Developer blogs | — | No config needed |
| 📊 **SEC EDGAR** | US company filings | — | No config needed |
| 🌐 **Wikipedia / Wikidata** | Encyclopedia + structured knowledge | — | No config needed |
| 💬 **WeChat Official Accounts** | Full-text article search | — | No config needed |
| 📱 **36kr / InfoQ** | Chinese tech & business news | — | No config needed |
| 🧵 **Linux DO / Discourse Forums** | Linux DO topics and Discourse-based public forum discussions | — | No config needed |
| 🎬 **YouTube** | Video search + transcripts | — | Set `YOUTUBE_API_KEY` |
| 📺 **Bilibili** | Chinese tech videos | — | Set `TIKHUB_API_KEY` |
| 📹 **WeChat Channels** | Chinese short videos (视频号) | — | `TIKHUB_API_KEY` |
| 🌸 **Xiaohongshu** | Lifestyle + product reviews | More stable | `autosearch login xhs` or `TIKHUB_API_KEY` |
| 🐦 **Twitter / X** | Real-time discussion + tech news | — | `TIKHUB_API_KEY` |
| 📣 **Weibo / Douyin / Zhihu** | Chinese social + in-depth discussion | — | `TIKHUB_API_KEY` |
| 📈 **Xueqiu** | A-share / HK stock discussion | — | `autosearch login xueqiu` |
| 💼 **LinkedIn** | Public pages via Jina Reader | — | No config needed |

> Not sure how to configure? Just tell your Agent "help me configure XXX" — it will guide you step by step.

---

## After install

Run `autosearch doctor` to check the status of every channel:

```
AutoSearch Channel Status
==========================================
Always-on (21/21)   ✅ arxiv  ✅ github  ✅ hackernews ...
Env-gated  (0/1)    ○  youtube  →  set YOUTUBE_API_KEY
Login      (0/15)   ○  xiaohongshu  →  autosearch login xhs
```

---

## License

[MIT](LICENSE).
