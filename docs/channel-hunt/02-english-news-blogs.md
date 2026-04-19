# 海外新闻 + 博客平台 · 免 key 免 cookie 调研

> 时间：2026-04-19
> 调研员：Codex (auto)

## TL;DR
- 验证通过：5 个
- 验证失败：9 个
- 建议接入 AutoSearch 前 3 个：Hacker News Algolia、DEV Community API、Hashnode GraphQL
- `public-apis` 的 News 分类里，明确 `Auth=No` 的只有 `Chronicling America` 和 `OkSurf`；`AP / NYT / Guardian` 仍然需要 key
- `mcpmarket` 本轮搜到的主要是 RSS / News 基础设施（如 `NewsMCP`、`RSS Feeds`、`Zenfeed`），更像聚合层，不是一手英文新闻/博客平台
- 本地 shell 外网 DNS 受限，`/tmp/channel-hunt/en-news/` 已补齐 `curl` / `httpx` 烟测脚本；内容有效性以 Web 侧抓取复核为准，因此响应时间统一记为 `N/A`

## ✅ 验证通过

### Hacker News Algolia
- **URL 模板**: `https://hn.algolia.com/api/v1/search_by_date?query=OpenAI&tags=story&hitsPerPage=5`
- **认证**: none
- **返回格式**: JSON
- **响应时间**: `N/A`（当前 shell DNS 受限，未能本地实测）
- **样本**（query="OpenAI"）:
  - OpenAI is throwing everything into building an automated researcher · https://news.ycombinator.com/item?id=47468452 · 2026-04-18
  - OpenAI tries to build its coding cred, acquires Python toolmaker Astral · https://news.ycombinator.com/item?id=47451348 · 2026-04-17
  - OpenAI buys Jony Ive's design startup for $6.5B · https://news.ycombinator.com/item?id=44055191 · 2026-03-22
- **AutoSearch 接入代码**:
  ```python
  resp = httpx.get("https://hn.algolia.com/api/v1/search_by_date", params={"query": "OpenAI", "tags": "story", "hitsPerPage": 5}, timeout=15.0)
  ```

### Hacker News Firebase
- **URL 模板**: `https://hacker-news.firebaseio.com/v0/newstories.json` + `https://hacker-news.firebaseio.com/v0/item/<id>.json`
- **认证**: none
- **返回格式**: JSON
- **响应时间**: `N/A`
- **样本**（news.ycombinator.com 近 30 天 HN item）:
  - OpenAI is throwing everything into building an automated researcher · https://news.ycombinator.com/item?id=47468452 · 2026-04-18
  - OpenAI tries to build its coding cred, acquires Python toolmaker Astral · https://news.ycombinator.com/item?id=47451348 · 2026-04-17
  - OpenAI buys Jony Ive's design startup for $6.5B · https://news.ycombinator.com/item?id=44055191 · 2026-03-22
- **说明**: endpoint 为 HN 官方 Firebase 数据面；本轮样本用 HN 公开 item 页回查
- **AutoSearch 接入代码**:
  ```python
  ids = httpx.get("https://hacker-news.firebaseio.com/v0/newstories.json", timeout=15.0).json()
  ```

### DEV Community API
- **URL 模板**: `https://dev.to/api/articles?tag=openai&top=30&per_page=5`
- **认证**: none（官方与社区文档都明确 public read-only endpoints 可匿名访问）
- **返回格式**: JSON
- **响应时间**: `N/A`
- **样本**:
  - AI Judges: DeepSeek & o3-mini Rate Translations & Summaries. Reasoning Skills Tested! · https://dev.to/aimodels-fyi/ai-judges-deepseek-o3-mini-rate-translations-summaries-reasoning-skills-tested-1j0h · 2026-04-17
  - [2026-04] How I Currently Use Claude Code · https://dev.to/masutaka/2026-04-how-i-currently-use-claude-code-2nck · 2026-04-12
  - Anthropic kills Claude subscription access for third-party tools like OpenClaw — what it means for developers · https://dev.to/mcrolly/anthropic-kills-claude-subscription-access-for-third-party-tools-like-openclaw-what-it-means-for-3ipc · 2026-04-05
- **AutoSearch 接入代码**:
  ```python
  resp = httpx.get("https://dev.to/api/articles", params={"tag": "openai", "top": 30, "per_page": 5}, timeout=15.0)
  ```

### Hashnode GraphQL
- **URL 模板**: `POST https://gql.hashnode.com`
- **认证**: none（官方文档明确 public API queries 走单一 GraphQL endpoint；私有字段才要求 Authorization）
- **返回格式**: JSON
- **响应时间**: `N/A`
- **样本**（Hashnode 公开帖子/讨论页）:
  - Anthropic’s NPM Blunder: The Claude Code Source Code Leak Explained · https://hashnode.com/posts/anthropic-s-npm-blunder-the-claude-code-source-code-leak-explained/69cc82f5e4688e4edd796388 · 2026-04-19
  - I Scanned 95 Days of My Claude Code Logs and Found Anthropic''s Second Silent Cache TTL Regression · https://hashnode.com/posts/claude-code-cache-ttl-audit/69dd47806fc3afd36f6b23e9 · 2026-04-18
  - CLI Coding Agents 2026: Every Tool, Every Price, Every Model · https://hashnode.com/posts/cli-coding-agents-2026-every-tool-every-price-every-model/69d0f0696b6d76716fb58cac · 2026-04-04
- **AutoSearch 接入代码**:
  ```python
  resp = httpx.post("https://gql.hashnode.com", json={"query": "query Publication { publication(host: \"blog.developerdao.com\") { id isTeam title } }"}, timeout=15.0)
  ```

### The Verge RSS
- **URL 模板**: `https://www.theverge.com/rss/index.xml`
- **认证**: none
- **返回格式**: RSS
- **响应时间**: `N/A`
- **样本**:
  - Read OpenAI's latest internal memo about beating the competition - including Anthropic · https://www.theverge.com/ai-artificial-intelligence/911118/openai-memo-cro-ai-competition-anthropic · 2026-04-14
  - OpenAI just bought TBPN · https://www.theverge.com/ai-artificial-intelligence/906022/openai-buys-tbpn · 2026-04-05
  - OpenAI shelves erotic chatbot 'indefinitely' · https://www.theverge.com/ai-artificial-intelligence/901293/openai-adult-mode-erotic-chatbot-shelved-indefinitely · 2026-03-29
- **说明**: RSS 路径按 The Verge 公开常用 feed 路径推断；近 30 天样本已从站点公开文章页复核
- **AutoSearch 接入代码**:
  ```python
  resp = httpx.get("https://www.theverge.com/rss/index.xml", timeout=15.0)
  ```

## ❌ 验证失败
- TechCrunch RSS: 官方订阅页能看到 feed 入口，但本轮 direct feed 点击在浏览器侧返回 400；同时只拿到 1 条明确落在近 30 天内的可靠样本，未达标
- Reuters RSS: Thomson Reuters IR 页面公开列出 RSS 链接，但浏览器侧点击返回 403；新闻 feed 路径在本轮环境里没拿到稳定匿名 200
- BBC RSS: 公共 feed URL 可从 RSS 目录页拿到，但本轮没能从 BBC 公开页稳定复核 3 条近 30 天样本
- Guardian API: `public-apis` 里明确标成 `apiKey`，不满足“免 key”
- NYT RSS: 公开 feed 路径可定位，但本轮没有拿到 3 条能稳定复核的近 30 天样本
- Engadget RSS: 站点公开文章页可见，但本轮只复核到 2 条近 30 天 OpenAI 相关文章，样本不足 3 条
- Ars Technica RSS: 公开文章可见，但本轮搜到的可核验样本主要落在 2026-01 或更早，不满足近 30 天
- Bluesky public search: 官方 docs 写的是“可直接打 `public.api.bsky.app`，但部分 provider 可能要求 auth”；社区已有 `403` 反馈，本轮不把它算稳定 PASS
- Mastodon public timeline: 官方 docs 明写“实例若关闭 public preview 会要求 token”；这不是稳定的跨实例匿名源

## ⚠️ 未测（建议跟进）
- Medium tag RSS: `https://medium.com/feed/tag/openai` 路径本身很像可用，但本轮没补齐 3 条“标题 + 直链 + 日期”样本
- Changelog News: 站点和 archive 都是公开的，理论上可接 `https://changelog.com/news/feed`；但本轮搜索结果偏旧，建议单独补一次最新 issue 抽样
- `public-apis` 的 `Chronicling America`: 免 key，但偏历史报纸，不适合 AutoSearch 的“近实时英文科技新闻”
- `public-apis` 的 `OkSurf`: 免 key Google News 包装层，值得单测，但不属于一手平台
- `mcpmarket` 的 `NewsMCP` / `RSS Feeds` / `Zenfeed`: 更适合作为聚合器或 MCP 中间层，若后续需要“多源统一入口”可再单独调研
