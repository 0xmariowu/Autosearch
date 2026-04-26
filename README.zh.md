<h1 align="center">
  <img src="docs/assets/logo.png" alt="" height="60" align="absmiddle">&nbsp;AutoSearch
</h1>

<p align="center">
  <strong>面向 AI Agent 的开源深度搜索 (Open-source Deep Research)</strong>
</p>

<p align="center">
  <em>40 个渠道，含 10+ 中文信息源。</em><br>
  <em>MCP-native，LLM 解耦。直接接入你已经在用的 Agent 主机。</em>
</p>

<p align="center">
  <a href="https://github.com/0xmariowu/Autosearch/releases"><img src="https://img.shields.io/github/v/release/0xmariowu/Autosearch?style=flat-square" alt="Release"></a>
  <a href="LICENSE"><img src="https://img.shields.io/github/license/0xmariowu/Autosearch?style=flat-square" alt="License"></a>
  <a href="https://github.com/0xmariowu/Autosearch/actions/workflows/ci.yml"><img src="https://img.shields.io/github/actions/workflow/status/0xmariowu/Autosearch/ci.yml?style=flat-square&label=CI" alt="CI"></a>
  <img src="https://img.shields.io/badge/python-3.12%2B-blue?style=flat-square" alt="Python">
  <a href="https://www.npmjs.com/package/autosearch-ai"><img src="https://img.shields.io/npm/v/autosearch-ai?style=flat-square" alt="npm"></a>
</p>

<p align="center">
  <a href="https://docs.autosearch.dev">文档</a> &bull;
  <a href="https://docs.autosearch.dev/install">安装</a> &bull;
  <a href="https://docs.autosearch.dev/channels">渠道</a> &bull;
  <a href="README.md">English</a>
</p>

---

你让 AI 去研究一个问题，它给你的是截止训练数据的知识——

- "帮我看看 arxiv 上这周的 LLM 论文" → **搜不了**，没有学术数据库访问
- "小红书上大家怎么评价这个产品" → **打不开**，必须登录才能搜
- "GitHub 上有没有类似的开源项目" → **结果很水**，只能用通用搜索
- "帮我整理一下推特上对这个技术的讨论" → **看不到**，Twitter 没有公开 API
- "这个话题在知乎和 Reddit 上分别是什么观点" → 要跑两个平台，结果还得手动汇总

**AutoSearch 把这件事变成一句话。** 挑一条适合你的：

**机器有 Node？**（最常见——macOS / Linux / Windows 都行）

```bash
npx autosearch-ai
```

**在用 Claude Code / Cursor / Zed？** 把这一行粘给你的 AI Agent：

```
Help me install AutoSearch: https://raw.githubusercontent.com/0xmariowu/Autosearch/main/docs/install.md
```

**macOS / Linux shell 老用户？**

```bash
curl -fsSL https://raw.githubusercontent.com/0xmariowu/Autosearch/main/scripts/install.sh | bash
```

安装后你的 Agent 能同时搜 40 个渠道——学术论文、开发者社区、中文社媒、Linux DO 论坛帖子，结果去重排序，每条结果都有来源链接。

---

## 支持的渠道

| 渠道 | 装好即用 | 配置后解锁 | 怎么配 |
|------|---------|-----------|-------|
| 📄 **arxiv** | 学术预印本 CS/ML/物理 | — | 无需配置 |
| 🔬 **PubMed / OpenAlex / DBLP** | 生物医学 + 跨学科论文 | — | 无需配置 |
| 🐙 **GitHub** | 代码、Issue、仓库搜索 | — | 无需配置 |
| 🔍 **DuckDuckGo** | 通用网页搜索 | — | 无需配置 |
| 🟠 **Hacker News** | 开发者讨论 + 早期产品信号 | — | 无需配置 |
| 📖 **Reddit** | 社区讨论 + 用户真实体验 | — | 无需配置 |
| 🤗 **Hugging Face** | 开源 ML 模型搜索 | — | 无需配置 |
| 📦 **Stack Overflow** | 编程 Q&A | — | 无需配置 |
| 📰 **Google News** | 实时新闻聚合 | — | 无需配置 |
| 💻 **dev.to** | 开发者博客 | — | 无需配置 |
| 📊 **SEC EDGAR** | 美股公司财报 | — | 无需配置 |
| 🌐 **Wikipedia / Wikidata** | 百科 + 结构化知识 | — | 无需配置 |
| 💬 **微信公众号** | 公众号文章全文搜索 | — | 无需配置 |
| 📱 **36kr / InfoQ** | 中文科技商业资讯 | — | 无需配置 |
| 🧵 **Linux DO / Discourse 论坛** | Linux DO 话题和基于 Discourse 的公开论坛讨论 | — | 无需配置 |
| 🎬 **YouTube** | 视频搜索 + 字幕 | — | 设置 `YOUTUBE_API_KEY` |
| 📺 **Bilibili** | 中文技术视频 | — | 设置 `TIKHUB_API_KEY` |
| 📹 **微信视频号** | 中文短视频 | — | `TIKHUB_API_KEY` |
| 🌸 **小红书** | 生活方式 + 产品口碑 | 更稳定 | `autosearch login xhs` 或 `TIKHUB_API_KEY` |
| 🐦 **Twitter / X** | 实时讨论 + 技术动态 | — | `TIKHUB_API_KEY` |
| 📣 **微博 / 抖音 / 知乎** | 中文舆论 + 深度讨论 | — | `TIKHUB_API_KEY` |
| 📈 **雪球** | A股/港股讨论 | — | `autosearch login xueqiu` |
| 💼 **LinkedIn** | 公开页面 via Jina Reader | — | 无需配置 |

> 不知道怎么配？直接告诉 Agent「帮我配 XXX」，它会引导你一步步完成。

---

## 安装完之后

运行 `autosearch doctor` 查看每个渠道的状态：

```
AutoSearch 渠道状态
==========================================
开箱即用 (27/27)    ✅ arxiv  ✅ github  ✅ hackernews ...
API key   (0/11)   ○  youtube      →  set YOUTUBE_API_KEY
                   ○  bilibili     →  set TIKHUB_API_KEY
需登录    (0/2)    ○  xiaohongshu  →  autosearch login xhs
                   ○  xueqiu       →  autosearch login xueqiu
```

---

## License

[MIT](LICENSE).
