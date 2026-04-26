<div align="center">

# AutoSearch

**Open-source Deep Research for AI Agents**

*40 channels, including 10+ Chinese sources.*<br>
*MCP-native. LLM-decoupled. Plug into the agent host you already use.*

[![CI](https://github.com/0xmariowu/Autosearch/actions/workflows/ci.yml/badge.svg)](https://github.com/0xmariowu/Autosearch/actions/workflows/ci.yml)
[![release](https://img.shields.io/github/v/release/0xmariowu/Autosearch?display_name=tag)](https://github.com/0xmariowu/Autosearch/releases)
[![npm](https://img.shields.io/npm/v/autosearch-ai?label=npm)](https://www.npmjs.com/package/autosearch-ai)
[![License](https://img.shields.io/github/license/0xmariowu/Autosearch)](LICENSE)
[![Claude Code plugin](https://img.shields.io/badge/Claude%20Code-plugin-orange)](https://github.com/0xmariowu/Autosearch)
[![MCP native](https://img.shields.io/badge/MCP-native-blue)](https://modelcontextprotocol.io)

[Install](#install) · [Channels](docs/channels.mdx) · [MCP Setup](docs/mcp-clients.md) · [Examples](docs/) · [Docs](https://docs.autosearch.dev) · [中文](README.zh.md)

</div>

AutoSearch is open-source deep research infrastructure built for AI agents. Plug Claude Code, Cursor, Cline, GPT-Researcher, LangChain, LlamaIndex, AutoGen, and other hosts into MCP-native access across 40 channels, including 10+ Chinese sources.

The engine returns indexed multi-source results and stays uncoupled from LLM calls, so your agent keeps its own model, prompts, and workflow.

---

You ask your AI to research something. It answers from training data cutoff —

- "Show me this week's LLM papers on arxiv" → **can't**, no academic database access
- "What are people saying about this product on Reddit" → **shallow**, only surface-level web results
- "Find similar open-source projects on GitHub" → **weak**, general search misses most repos
- "Summarize the Twitter discussion on this topic" → **blocked**, no public API
- "Compare opinions on Hacker News vs Chinese tech forums" → two platforms, manual aggregation

**AutoSearch fixes this in one line.** Pick the path that matches you:

## Install

**Have Node?** (most common — works on macOS, Linux, Windows)

```bash
npx autosearch-ai
```

**Using Claude Code / Cursor / Zed?** Paste this into your AI agent:

```
Help me install AutoSearch: https://raw.githubusercontent.com/0xmariowu/Autosearch/main/docs/install.md
```

**Shell user on macOS / Linux?**

```bash
curl -fsSL https://raw.githubusercontent.com/0xmariowu/Autosearch/main/scripts/install.sh | bash
```

The npm wrapper runs install/init only when you invoke it explicitly. Plain
`npm install -g autosearch-ai` does not auto-run `init`; avoiding npm
install-time scripts is intentional supply-chain hardening.

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
Always-on (27/27)   ✅ arxiv  ✅ github  ✅ hackernews ...
API-key   (0/11)    ○  youtube  →  set YOUTUBE_API_KEY
                    ○  bilibili →  set TIKHUB_API_KEY
Login     (0/2)     ○  xiaohongshu  →  autosearch login xhs
                    ○  xueqiu       →  autosearch login xueqiu
```

---

## License

[MIT](LICENSE).
