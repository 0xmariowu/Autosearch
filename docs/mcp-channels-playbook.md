# AutoSearch 渠道调研最终手册

> 时间：2026-04-19
> 覆盖：mcpmarket.com 调研 + 实测 + TikHub 付费 API 打通
> 定位：这份是**最终总纲**，之前分散文档（`mcp-channel-research.md` / `mcp-test-plan.md` / `mcp-test-results.md` / `mcp-no-cookie-inventory.md` / `mcp-final-summary.md` / `tikhub-smoke-test.md`）都汇总到这里。未来所有渠道决策从这份开始。

---

## TL;DR

**三档结论**：

1. **无 cookie 免费可用**：搜狗微信、open-websearch（4 引擎）、Paper Search MCP（21 学术源）、PullPush（Reddit 历史）、RSS 直读、Jina Reader（部分站）、以及 13 个官方 API。
2. **硬骨头 8 个中付费打通 5 个**（TikHub）：小红书、微博、知乎、Twitter/X、抖音。剩 3 个（微博上游 flaky、Instagram/LinkedIn 参数未调通）本轮未完全解决。
3. **最终架构**：AutoSearch 走 BYOK（用户自配 TikHub key），`requires: [env:TIKHUB_API_KEY]` 声明依赖，未来可无缝切换到 hosted proxy 做商业化。

**成本锚点**：TikHub 实测平均 **$0.0036/请求**。1000 次研究级调用 ≈ $3.6/月。

---

## 第一部分：无 cookie 可用清单（41 个）

### A. 本次亲手实测 PASS（9 个）

| 方案 | 平台/能力 | 认证 | 备注 |
|---|---|---|---|
| **搜狗微信 SERP** | 微信公众号 | 🟢 无 | `weixin.sogou.com/weixin?type=2&query=<q>` |
| **open-websearch fetch-web + readability** | 任意页 → 干净 markdown | 🟢 无 | Mozilla Readability 算法清洗 |
| **open-websearch csdn** | CSDN 技术博客 | 🟢 无 | 原生中文 |
| **open-websearch duckduckgo** | DuckDuckGo | 🟢 无 | 备用通用搜 |
| **open-websearch startpage** | Startpage（Google 代理） | 🟢 无 | 备用通用搜 |
| **Paper Search MCP** | arXiv + PubMed + Semantic Scholar + OpenAlex + 其他 17 源 | 🟢 无 | 一键 21 学术源，MIT |
| **PullPush** | Reddit 历史数据 2005-至今 | 🟢 无 | `q=` 全文搜挂，按 subreddit/时间过滤正常 |
| **Substack RSS** | Substack / Medium / 独立博客 | 🟢 无 | 所有站暴露 `/feed` |
| **Jina Reader** | B站 / 反爬弱的站 | 🟢 无 | 知乎小红书微博会被封 |

### B. 官方 API 已知可用（13 个，AutoSearch 已集成或一行接入）

| 平台 | 接入方式 | 限额 |
|---|---|---|
| HackerNews Algolia | 官方 API | 无限 |
| Reddit 公开 JSON | `/r/<sub>.json` | 无登录 |
| Stack Exchange API | 官方 | 300/day 无 key |
| GitHub Public Search | 官方 API | 10/min 无 token |
| Dev.to | 公开 API | 无 key |
| npm / PyPI registry | 官方 | 无 key |
| OpenReview API | 官方 | 无 key |
| arXiv API | 官方 | 无 key |
| 雪球 / 36kr / InfoQ 中文 | 各自 web/API | 无 key |
| 小宇宙 | RSS / 公开页 | 无 key |
| B站公开搜索 API | 官方 | 无登录 |
| YouTube transcript | yt-dlp + whisper（本地） | 无 key |
| Crunchbase 公开页 | 公开搜索 | 有限 |

### C. mcpmarket 发现的新品类（AutoSearch 空白）（11 个）

| 方案 | 能力 | 优先级 |
|---|---|---|
| [Wikipedia MCP](https://mcpmarket.com/server/wikipedia-1) | 百科全站 + 摘要 | 🔴 最高 |
| [Wikidata](https://mcpmarket.com/server/wikidata) | SPARQL + 实体 | 🔴 最高 |
| [Google Trends Explorer](https://mcpmarket.com/server/google-trends-explorer) | 趋势信号 | 🔴 最高 |
| [Google News Trends](https://mcpmarket.com/es/server/google-news-trends) | 新闻 + 趋势词 | 🔴 高 |
| [USPTO](https://mcpmarket.com/server/uspto) | 美国专利 + 商标 | 🟡 按需 |
| [Google Patents](https://mcpmarket.com/server/google-patents) | 全球专利 | 🟡 按需 |
| [EPSS](https://mcpmarket.com/server/epss) | CVE + 漏洞评分 | 🟡 按需 |
| [Cybersecurity CVE](https://mcpmarket.com/es/server/cybersecurity-2) | NVD 数据库 | 🟡 按需 |
| [OpenStreetMap](https://mcpmarket.com/server/openstreetmap) | 地图 + POI | 🟢 按需 |
| [CoinGecko](https://mcpmarket.com/server/coingecko) | 加密货币 | 🟢 按需 |
| [Open Meteo](https://mcpmarket.com/tools/skills/open-meteo-weather) | 全球天气 | 🟢 按需 |

### D. 现有 channel 补强（8 个）

| 方案 | 补哪个 | 备注 |
|---|---|---|
| [Package Version](https://mcpmarket.com/ja/server/package-version) | npm/PyPI/Maven/Go/Swift/Docker Hub 等 9 注册表 | 一个 MCP 顶 9 个 |
| [GitLab MCP](https://mcpmarket.com/server/gitlab) | 补 GitHub 之外 | 公开 repo 无 token |
| [Newsfeed](https://mcpmarket.com/server/newsfeed) | `search-rss` 预置分类 | 免费 |
| [Trend Radar](https://mcpmarket.com/tools/skills/trend-radar) | HN + GitHub 信号聚合 | 免费 |
| [Steam Context](https://mcpmarket.com/server/steam-context) | 游戏品类 | Steam API key 免费 |
| [Zillow](https://mcpmarket.com/server/zillow) | 房产品类 | 大部分无 key |
| [AI Job Hunting Agent](https://mcpmarket.com/es/server/ai-job-hunting-agent) | Indeed + Remotive 岗位 | 免费 |
| 搜狗微信 MCP 包装（[ptbsare](https://github.com/ptbsare/sogou-weixin-mcp-server) / [fancyboi999](https://github.com/fancyboi999/weixin_search_mcp)） | 公众号 | 底层同搜狗 SERP |

---

## 第二部分：硬骨头攻克矩阵

### 🔴 已打通（TikHub 付费，5/8）

| 平台 | TikHub endpoint | 实测数据 |
|---|---|---|
| 小红书 | `GET /api/v1/xiaohongshu/web/search_notes?keyword=<q>` | Claude 4.7 搜到 20 条笔记，含 title/author/likes |
| 知乎 | `GET /api/v1/zhihu/web/fetch_article_search_v3?keyword=<q>` | LLM agent 搜到 20 条高质量问答 |
| 抖音 | `GET /api/v1/douyin/web/fetch_video_search_result_v2?keyword=<q>` | DeepSeek 搜到 12 条，最高 54 万赞 |
| Twitter/X | `GET /api/v1/twitter/web/fetch_search_timeline?keyword=<q>&search_type=Top` | 19 条，全字段（favorites/views/retweets） |
| B站 | `GET /api/v1/bilibili/web/fetch_general_search?keyword=<q>&order=totalrank&page=1&page_size=10` | 8 条视频 + 播放量 |

### ⚠️ 本轮未完全解决（3/8）

| 平台 | 状态 | 排查方向 |
|---|---|---|
| **微博** | TikHub 上游 flaky——`web/fetch_search` 返回 ok=1 但 cards 时空时不空，重试波动；`web_v2/fetch_realtime_search` 400；`app/fetch_search_all` 422 | 去 TikHub Discord 问客服；尝试 `web_v2/fetch_ai_smart_search` |
| **Instagram** | `v2/general_search` 返回 200 OK 但全 0 | 换 `v2/search_hashtags` 或针对性关键词（#hashtag / @username） |
| **LinkedIn** | `web/search_jobs` 400，加 geocode 也 400 | 去 TikHub docs 查 demo 参数，可能需要特殊 geocode 格式 |

### 🟢 真·完全无法无 cookie 搞定

**Facebook / Instagram 公开个人页 / 小红书私人号内容 / Twitter 私人账号**——即使 TikHub 也要账号支持。这些不在研究场景核心，暂不投入。

---

## 第三部分：TikHub 实战经验

### 基础信息

- **官网**：https://tikhub.io · **API base**：`https://api.tikhub.io/api/v1/`
- **认证**：`Authorization: Bearer $TIKHUB_API_KEY`
- **OpenAPI 规格**：`GET https://api.tikhub.io/openapi.json`（1058 个 endpoint）
- **计费**：pay-per-request，平均 **$0.0036/次**（官方宣传 $0.001 起步，实测贵 3-4 倍）
- **免费额度**：每日签到可领少量 free credit

### 覆盖平台（确认跑通）

16 平台共 1000+ tools：
```
TikTok (204) · Douyin (247) · Instagram (82) · Xiaohongshu (71)
Weibo (64)  · Bilibili (41) · YouTube (37)   · Kuaishou (33)
Zhihu (32)  · LinkedIn (25) · Reddit (24)    · WeChat · Twitter
Threads · TikHub Utilities · 其他
```

### 关键坑（按踩坑顺序）

1. **注册要验证邮箱**。不验证一切 endpoint 都 403 "邮箱未验证"。
2. **免费 tier 只覆盖部分 endpoint**。小红书/微博/Twitter/抖音都是 402（Payment Required）直到付费余额 > 0。知乎 / B站属于免费 tier 覆盖。
3. **小红书别用 `web_v3`**。`/xiaohongshu/web_v3/fetch_search_notes` 返回 400。用老版 `/xiaohongshu/web/search_notes`。
4. **抖音别用 `app/v3`**。`/douyin/app/v3/fetch_video_search_result` 返回 400。用 `/douyin/web/fetch_video_search_result_v2`，数据在 `data.business_data[i].data`（嵌套两层）。
5. **微博 endpoint 多版本都不稳**。`web_v2/fetch_realtime_search` 400；`app/fetch_search_all` 422；`web/fetch_search` 200 但 cards 波动。
6. **400 = 上游爬取失败，不是参数错**。TikHub 的 400 body 是"请查看文档核对参数"，但实际上是 TikHub 自己爬目标站失败。这种 400 **不计费**（Only pay for successful requests）。
7. **Twitter 结构已扁平化**。`data.timeline` 是 list（不是 GraphQL 原格式的 instructions 嵌套），直接遍历即可。字段：`screen_name / text / favorites / views / retweets / replies / created_at / tweet_id / lang`。

### 🚨 安全注意：Key 会在错误响应里被回显

**TikHub 的 400 / 403 / 422 响应体会原样回显完整 `Authorization` header（含 Bearer token）**。接入必须：

```python
# BAD — 直接打印 response body 会泄露 key
except httpx.HTTPStatusError as e:
    log.error("TikHub failed", body=e.response.text)  # ❌

# GOOD — 先脱敏再 log
def sanitize(data: dict) -> dict:
    detail = data.get("detail", {})
    if isinstance(detail, dict):
        detail.pop("headers", None)
        for k in list(detail.keys()):
            if "auth" in k.lower() or "token" in k.lower():
                detail[k] = "<redacted>"
    return data

except httpx.HTTPStatusError as e:
    log.error("TikHub failed", body=sanitize(e.response.json()))  # ✅
```

测试里必须有一条：**assert exception string 不包含 "Bearer"**。

### MCP vs API 选择

TikHub 官方提供 4 种 transport：Stdio / SSE / Streamable HTTP / Curl(API)。

**对 AutoSearch 而言**：**选 Curl/API 直连**，不要走 MCP。

理由：
- AutoSearch 是 Python plugin，用户 `pip install` 安装。走 MCP 要求用户额外装 Node.js + `mcp-remote` + TikHub MCP server（3 个依赖）
- AutoSearch 的 channel 是"工具"本身，再走一层 MCP 是工具里调工具，JSON-RPC over stdio 多一层序列化毫无意义
- TikHub MCP 全勾是 1000+ tool schema，注入 Claude context ~400k token，直接炸
- 即使只勾 6 个硬骨头平台也 ~470 tools（~190k token），依然不理想

**Stdio MCP 适用场景**：用户在 Claude Code 会话里想直接 "搜一下小红书" 的即兴调用。这是用户自己装 TikHub MCP 的事，和 AutoSearch 无关。

---

## 第四部分：AutoSearch 最终接入架构

### BYOK（Bring Your Own Key）是唯一合理方案

**不要做的**：
- ❌ 把 TikHub key 硬编码到发布版里（pip 包明文可提取）
- ❌ 一个 key 共享给所有用户（违反 ToS + 余额被烧光）

**要做的**：
- ✅ 用户自己去 `tikhub.io` 注册 + 充值
- ✅ `export TIKHUB_API_KEY=xxx`，AutoSearch 读 env var
- ✅ SKILL.md 声明 `requires: [env:TIKHUB_API_KEY]`，没 key 时 channel 自动标记不可用，其他 channel 照跑

### Channel 结构（已通过 pilot 验证）

```
autosearch/lib/
└── tikhub_client.py              # 通用客户端 + 错误脱敏 + 5xx 重试

skills/channels/zhihu/
├── SKILL.md                      # frontmatter 声明 via_tikhub method
└── methods/
    └── via_tikhub.py             # 调 /zhihu/web/fetch_article_search_v3 映射到 Evidence

tests/lib/test_tikhub_client.py   # 客户端单测（含脱敏断言）
tests/channels/zhihu/test_via_tikhub.py  # method 单测
```

**fallback_chain 顺序**：`[via_tikhub, api_search, api_answer_detail]` — TikHub 有 key 时优先用，没 key 时 fallback 到原方案。

### 为未来 proxy 留口子

`tikhub_client.py` 的 base URL 从 env var 读：

```python
base_url = os.getenv("TIKHUB_BASE_URL", "https://api.tikhub.io")
```

未来老板上 hosted proxy 做商业化时，用户只需改两个 env var，零代码改动：

```bash
export TIKHUB_BASE_URL=https://api.autosearch.com/tikhub
export TIKHUB_API_KEY=<AutoSearch 平台发的 token>
```

### 待接入的 5 个 channel（按优先级）

| 优先级 | Channel | Endpoint | 状态 |
|---|---|---|---|
| 1 | **zhihu** | `zhihu/web/fetch_article_search_v3` | ✅ pilot 写完（branch `feat/tikhub-channels`） |
| 2 | **xiaohongshu** | `xiaohongshu/web/search_notes` | 待扩展 |
| 3 | **twitter** | `twitter/web/fetch_search_timeline` | 待扩展 |
| 4 | **douyin** | `douyin/web/fetch_video_search_result_v2` | 待扩展 |
| 5 | **bilibili** | `bilibili/web/fetch_general_search` | 待扩展 |

Pilot 验证通过后，让 Codex 按同一模板并行写剩下 4 个 adapter。改造量每个 < 50 行。

---

## 附录

### A. 测试命令速查（可复制即跑）

```bash
# 搜狗微信 + readability 清洗 = 公众号全文搜索
cd /tmp/mcp-smoke/ows
node build/index.js fetch-web \
  "https://weixin.sogou.com/weixin?type=2&query=<KEYWORD>" \
  --readability --spawn --json

# open-websearch 多引擎
node build/index.js search "<query>" --engine duckduckgo --limit 5 --spawn --json
node build/index.js search "<query>" --engine csdn --limit 5 --spawn --json

# Paper Search MCP 学术
cd /tmp/mcp-smoke/paper-search-mcp
python3 -c "
import sys; sys.path.insert(0,'.')
from paper_search_mcp.academic_platforms.arxiv import ArxivSearcher
s = ArxivSearcher()
for p in s.search('<query>', max_results=5):
    print(p.title, p.url)
"

# PullPush Reddit 历史
curl -s "https://api.pullpush.io/reddit/search/submission/?subreddit=<NAME>&after=<TS>&before=<TS>&size=10"

# Jina Reader 任意 URL
curl -sL "https://r.jina.ai/<URL>"

# TikHub 任意 endpoint（脱敏地看结果）
curl -sS -H "Authorization: Bearer $TIKHUB_API_KEY" \
  "https://api.tikhub.io/api/v1/zhihu/web/fetch_article_search_v3?keyword=<q>" \
  -o /tmp/t.json
python3 -c "
import json
d = json.load(open('/tmp/t.json'))
detail = d.get('detail', {})
if isinstance(detail, dict): detail.pop('headers', None)
print(json.dumps(d, indent=2, ensure_ascii=False)[:1000])
"
rm -f /tmp/t.json  # 关键：清理可能含 key 回显的临时文件
```

### B. 外部链接

- mcpmarket.com — 本次调研来源
- tikhub.io — 付费平台 API
- github.com/Aas-ee/open-webSearch — 8 引擎免费 SERP
- github.com/openags/paper-search-mcp — 21 学术源
- github.com/jacklenzotti/pullpush-mcp — Reddit 历史
- r.jina.ai — Jina Reader 免费 URL → markdown

### C. 相关文档（本次之前）

已被本手册汇总、**可以不用再翻**：
- `mcp-channel-research.md` — 初期调研
- `mcp-channel-test-plan.md` — 测试计划
- `mcp-test-results.md` — 第一轮实测
- `mcp-no-cookie-inventory.md` — 无 cookie 清单
- `mcp-final-summary.md` — 阶段总结
- `tikhub-smoke-test.md` — TikHub 详细实测

保留归档供溯源，但日常看**本手册 + `tikhub-smoke-test.md`** 即可。

### D. 开销总账（截至 2026-04-19）

- TikHub：**$0.053**（19 次 smoke request）
- 其他：$0（全部免费方案）

---

**维护规则**：接入一个新 channel 或打通一个新硬骨头 → 更新本手册对应表格，保持单一事实来源。

---

## 附 E. 2026-04-19 补充扫描（免 key + 免 cookie 新增）

本轮深挖 mcpmarket.com 发现了之前漏掉的 **12 个完全免 key 免 cookie 的品类**。按研究价值分档：

### 🔴 高价值（强烈建议接入）

| MCP | 能力 | 认证 | 实测 | 为什么值得 |
|---|---|---|---|---|
| [FRED](https://mcpmarket.com/server/fred) · [Fredapi](https://mcpmarket.com/server/fredapi) · [FRED Macro Data](https://mcpmarket.com/server/fred-macroeconomic-data) | 美联储经济数据 80w+ 时间序列 | 🟢 无 key | 未测 | AI/创业研究的宏观信号必备 |
| [World Bank Data](https://mcpmarket.com/server/world-bank-data) | 全球经济指标 | 🟢 无 key | 未测 | 国别对比研究刚需 |
| [Public APIs Directory](https://mcpmarket.com/es/server/public-apis) ([repo](https://github.com/zazencodes/public-apis-mcp)) | 免费 API 目录 semantic search | 🟢 无 key | **✅ 04-19** | **元工具** — AutoSearch 未来发现新 channel 的引擎 |
| [Open Library / Books](https://mcpmarket.com/server/books) · [OpenLibrary](https://mcpmarket.com/server/openlibrary) | ISBN 书籍查询，全量书目 | 🟢 无 auth | 未测 | 学术/出版研究基础 |
| [Word of the Day](https://mcpmarket.com/server/word-of-the-day) | Free Dictionary API，定义+发音+例句 | 🟢 无 key | 未测 | 事实核查基础工具 |
| [Dash Docset](https://mcpmarket.com/server/dash) · [Enhanced Dash](https://mcpmarket.com/server/enhanced-dash) | 本地 Dash docset 查询 | 🟢 本地 | 未测 | 技术文档即时查询 |
| [Hugging Face MCP](https://mcpmarket.com/tools/skills/hugging-face-mcp) | Hub model/dataset 搜索 | 🟢 公开搜索无 key | **✅ 04-19** | AI 研究基础 |
| Wikipedia API（官方） | 百科搜索 + 摘要 | 🟢 无 key | **✅ 04-19** | 事实核查/百科补全基础 |
| Wikidata SPARQL（官方） | 结构化实体 + 图谱查询 | 🟢 无 key | **✅ 04-19** | 实体关系查询 |
| Google Trends via `pytrends` | 关键词趋势时间序列 | 🟢 无 key | **✅ 04-19** | 话题热度/品牌对比信号 |

### 🟡 按需接入

| MCP | 能力 | 认证 | 场景 |
|---|---|---|---|
| [Flightradar24](https://mcpmarket.com/server/flightradar24-1) · [Flight (ADS-B)](https://mcpmarket.com/server/flight) | 实时航班追踪 | 🟢 部分无 key | 出行 / 供应链研究 |
| [Etherscan MCP](https://mcpmarket.com/server/etherscan-2) · [Dune Analytics](https://mcpmarket.com/tools/skills/dune-analytics-on-chain-data) | 以太坊链上数据 | 🟢 Etherscan 免费 key / 🟡 Dune 付费 | Web3 研究 |
| [Ethereum JSON-RPC](https://mcpmarket.com/server/eth-1) | 原生 JSON-RPC 查链 | 🟢 公开节点 | DeFi 深度研究 |
| [TMDB](https://mcpmarket.com/server/tmdb) · [IMDb](https://mcpmarket.com/es/server/imdb-1) · [OMDB](https://mcpmarket.com/es/server/omdb) | 电影/电视数据 | 🟢 TMDB/OMDB 免费 key | 内容/娱乐研究 |
| [Last.fm (ScrobblerContext)](https://mcpmarket.com/es/server/scrobblercontext) | 音乐数据 | 🟢 免费 key | 内容分析 |
| [OpenFoodFacts](https://mcpmarket.com/server/openfoodfacts) | 全球食品数据库 | 🟢 无 key | 消费品/健康研究 |

### 🟢 基础工具（偶尔用）

| MCP | 能力 | 认证 |
|---|---|---|
| [Whois Lookup](https://mcpmarket.com/server/whois) · [Domain Lookup](https://mcpmarket.com/server/domain-lookup) | WHOIS / RDAP 查询 | 🟢 无 key |
| [DeepL MCP](https://mcpmarket.com/server/deepl) | 翻译 | 🟡 免费 tier 需 key |
| [Pexels MCP](https://mcpmarket.com/es/server/pexels) | 免费 stock 图片 | 🟡 免费 key |

### mcpmarket 完全空白（这些品类以后别找 mcpmarket）

- **今日头条 / 百家号 / 网易号**（中文新闻聚合）
- **Reuters / TechCrunch / Bloomberg**（专业新闻，只有 RSS）
- **Coursera / edX / Khan Academy / MOOC**
- **中国政府开放数据**（统计局、海关）
- **ESPN / 体育数据**
- **空气质量 / 环境数据 / 实时碳排放**

这些只能靠 RSS + Exa `site:` 覆盖，或者等 mcpmarket 以后上新。

### 2026-04-19 实测验证（5 个核心 MCP）

对"基础事实 / 趋势 / AI Hub / 元工具"这 5 个最关键 MCP 做了底层 API smoke test。结果全 PASS：

| MCP | 底层 API | Smoke test | 样本 |
|---|---|---|---|
| **Wikipedia** | `en.wikipedia.org/w/api.php?action=query&list=search&srsearch=<q>` | 搜 `Claude AI` → 5 条 | Claude (language model) · Anthropic · OpenAI Codex · Artificial intelligence · Project Maven |
| **Wikidata** | `query.wikidata.org/sparql` (SPARQL) | `P31 wd:Q11660` 查 AI 实体 → 5 条 | AlphaFold · Lee Luda · Intelligent Autonomous Systems |
| **Google Trends** | `pytrends` Python 库（非官方，模拟请求） | 7 天每小时 `Claude AI` vs `ChatGPT` → **169 行** | 最新一小时 Claude AI=3, ChatGPT=45（品牌认知度差距直观） |
| **Hugging Face Hub** | `huggingface.co/api/models?search=<q>` | 搜 `llama` → 5 条 | meta-llama/Llama-3.1-8B-Instruct ⬇936万 · Llama-3.3-70B-Instruct ⬇49万 |
| **Public APIs Directory** | 本地 `datastore/index.json`（1426 API 全量） | 全量加载 + 筛 auth=No → **668 个免 key** | 1426 个 API 涵盖 Animals/Crypto/Finance/Transport/Security 等几十类 |

**关键澄清**：Public APIs Directory MCP（[zazencodes/public-apis-mcp](https://github.com/zazencodes/public-apis-mcp)）**完全不依赖已挂掉的 `api.publicapis.org`**。它的数据是内置 JSON（1426 条），embedding 索引本地构建（.npz 文件）。所以即使那个老 API 域名已 DNS 解析失败，MCP 功能完好。

**踩坑预警 — Google Trends**：pytrends 是非官方模拟请求，Google 偶尔会改 cookie/token 机制导致失效。接入时**必加重试 + 错误容忍**，不能作为硬依赖。比其他 4 个官方 API 脆弱得多。

**接入建议（最轻方案）**：前 4 个都可以**直接 Python httpx 调 HTTP API**，不必启动 MCP 进程。Public APIs Directory 可以把它的 `index.json` 拷贝到 AutoSearch 里自己解析——1426 条 JSON 没什么分量，embedding 也可以本地现算。这样 AutoSearch 对外零新依赖进程。

---

### 扫描后更新 AutoSearch 优先级

原 playbook 第一部分 C 节的"强烈建议接入"6 个基础上，**追加 3 个最高优先级**：

1. **FRED + World Bank**（宏观经济信号，免 key 免 cookie 一步到位）
2. **Public APIs Directory**（元工具，加了它 AutoSearch 自动发现新 channel）
3. **Open Library**（学术/出版研究基础）

合计现在 AutoSearch 应该新增 **9 个 channel** 就能达到"业内唯一全覆盖研究系统"：

```
Wikipedia + Wikidata          # 百科       ✅ 已验证
Google Trends                 # 趋势       ✅ 已验证（有 flaky 风险）
Hugging Face Hub              # AI 模型    ✅ 已验证
Public APIs Directory         # 元工具     ✅ 已验证
Google Patents                # 专利       未验证
CVE/NVD                       # 安全       未验证
FRED + World Bank             # 宏观经济   未验证
Open Library                  # 书籍       未验证
```

全部 🟢 零 key 零 cookie。改造量小，收益最大。

**第一批接入（已实测可用的 4 个）**：Wikipedia、Wikidata、Hugging Face、Public APIs Directory — 这 4 个可以立刻让 Codex 写 channel adapter，每个 < 30 行 Python + httpx 代码。

**第二批接入（未实测 5 个）**：Google Trends、Google Patents、CVE/NVD、FRED、Open Library — 按研究场景优先级推进，每个接入前先 smoke test 底层 API。
