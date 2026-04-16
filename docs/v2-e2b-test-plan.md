# autosearch v2 · e2b.dev 渠道验证测试计划

> 目标：在 e2b sandbox 一次性跑完 13 个中文平台 × 每平台 3-7 个开源方案的可用性矩阵，产出每条路径的 **success_rate / latency / content_quality**，作为 v2 架构决策依据。

## 核心原则

1. **严格抄作业，禁止自写 scraper** —— 每个 adapter 必须 `git clone` 源 repo，调用 repo 暴露的 API/函数。**不允许重写签名算法、反爬逻辑、HTTP 封装**。repo 跑不了就 RED 淘汰换 Secondary。Adapter 代码只能是 "import + 调用 + 映射到 ScrapeResult" 这 20-30 行映射层
2. **统一测试 query 集**，每方案跑相同 query，横向可比
3. **统一评分 metric**：Wilson 95% CI 下界 / 中位延迟 / 内容长度 / 反爬命中
4. **每 adapter 独立 sandbox**，避免依赖冲突 / state 污染
5. **按梯队推进**：第一梯队不跑通，不动第二第三梯队
6. **Day 2 批量开发并行**：48 个 adapter 启 5 路 Codex 并行写，每路 10 个

## 0. 前置

### API key（已存 gitignored `.env`）

```bash
# 项目根 .env（不入 git）
E2B_API_KEY=<存在本地 .env>
```

所有脚本通过 `os.environ["E2B_API_KEY"]` 读取。**永远不写进 repo 文件**。

### 依赖安装（e2b SDK）

```bash
pip install e2b e2b-code-interpreter
# or
npm install @e2b/code-interpreter
```

### 统一测试 query 集（20 个，4 类 × 5）

每个方案跑 20 个 query × 每 query 3 次 × 2 时段 = **120 次**，才做判定。避免样本不足误判。

| 类别 | queries |
|---|---|
| 消费决策 | iPhone 16 值得买吗 / SU7 真实体验 / 扫地机器人推荐 / 儿童牛奶选哪个 / 小红书好物 |
| 技术 | RAG 架构教程 / LangGraph 怎么用 / Rust vs Go / Playwright 反爬 / PostgreSQL 索引 |
| 金融 | A股 AI 概念股 / 英伟达财报 / 黄金 2026 走势 / 万科会不会爆雷 / 美元指数 |
| 热点人物 | 张雪峰 最新 / 雷军 小米汽车 / DeepSeek 最新发布 / 上海天气极端 / 2026 两会 |

### 评分指标

每条路径 × 每个 query 产出一行 JSON：

```json
{
  "platform": "xiaohongshu",
  "path": "primary_A_xhshow",
  "repo": "Cloxl/xhshow",
  "query": "iPhone 16 值得买吗",
  "status": "ok | anti_bot | timeout | error",
  "http_code": 200,
  "items_returned": 15,
  "avg_content_len": 340,
  "first_byte_ms": 480,
  "total_ms": 2100,
  "error": null,
  "sample": "第一条结果原文片段"
}
```

### pass/fail 标准（Wilson 95% CI）

每方案总样本 120。成功率用 **Wilson score interval 95% 下界** 判定，不用裸比例：

```python
def wilson_lower(successes, total, z=1.96):
    if total == 0: return 0
    p = successes / total
    denom = 1 + z*z/total
    center = p + z*z/(2*total)
    margin = z * math.sqrt(p*(1-p)/total + z*z/(4*total*total))
    return max(0, (center - margin) / denom)
```

| 等级 | 条件 |
|---|---|
| **GREEN** | CI 下界 ≥0.75 + 平均内容 ≥200 字 + 中位延迟 <5s |
| **YELLOW** | CI 下界 0.4-0.75，或内容薄，或延迟 5-15s |
| **RED** | CI 下界 <0.4，或频繁反爬，或需要人工介入 |
| **INSUFFICIENT** | 有效样本 <60 直接跳过（不强行定级） |

### 分场景细粒度打分

同一 adapter 在不同 query 类别可能差异巨大。评分存为矩阵，不全局定级：

```json
{
  "path_id": "cloxl_xhshow",
  "overall": "YELLOW",
  "by_category": {
    "consumer": "GREEN",
    "tech": "RED",
    "finance": "RED",
    "celebrity": "GREEN"
  },
  "recommended_scope": ["consumer", "celebrity"]
}
```

**意义**：v2 SourceRouter 按 query 分类动态挑 adapter，不"一刀切"。

### 平台异常隔离

若某时刻**所有 adapter 对同一 query 都失败** = 平台暂时挂（不是 adapter 坏）。该组样本标记"platform_outage"，从评分池排除。

---

## 1. 第一梯队 · 6 平台（重点投入）

每平台 Primary/Secondary/Tertiary 全测，至少 3 个候选方案。**这 6 个平台的 matrix 不测完，不开工 v2**。

### 1.1 小红书

| path | repo | 类型 | 零登录 | 优先测 |
|---|---|---|---|---|
| P-A | Cloxl/xhshow (835★) | x-s 纯算 | ✅ | 🥇 |
| P-B | Cialle/RedCrack (126★) | 全加密纯算 | ✅ | 🥈 |
| P-C | xhs996/xhs_spider (377★) | 签名逆向 | ✅ | 🥉 |
| S-A | submato/xhscrawl (1.3k★) | xs 逆向（含部分浏览器逻辑） | 🟡 | |
| S-B | cv-cat/Spider_XHS (5.2k★) | JS 全域 | 🟡 需 cookie | |
| S-C | ReaJason/xhs (2.1k★) | Python SDK | 🟡 需 cookie | |
| S-D | xpzouying/xiaohongshu-mcp (12.9k★) | Go MCP | 🟡 需 cookie | 对照组 |
| T | Bing site:xiaohongshu.com | SEO 兜底 | ✅ | 永不 fail |

### 1.2 抖音

| path | repo | 类型 | 零登录 | 优先测 |
|---|---|---|---|---|
| P-A | NearHuiwen/TiktokDouyinCrawler (476★) | a-bogus 纯算 | ✅ | 🥇 |
| P-B | cv-cat/DouYin_Spider (1.4k★) | 逆向 + 全 API | ✅ | 🥈 |
| P-C | NearHuiwen/TiktokCrawler (51★) | 独立 x-bogus | ✅ | 🥉 |
| S-A | erma0/douyin (1.4k★) | TS 综合 | 🟡 | |
| S-B | ShilongLee/Crawler (1.3k★) | Docker 一键 | 🟡 | |
| S-C | loadchange/amemv-crawler (2.6k★) | 下载向 | 🟡 | |
| S-D | freeloop4032/douyin-live (98★) | 直播弹幕 | ✅ 但场景特殊 | |
| T | Bing site:douyin.com | SEO 兜底 | ✅ | 永不 fail |

### 1.3 B站

| path | repo | 类型 | 零登录 | 优先测 |
|---|---|---|---|---|
| P-A | 自写 WBI 签名（算法来自 SocialSisterYi 20.3k） | 纯 HTTP + 签名 | ✅ | 🥇 |
| P-B | Nemo2011/bilibili-api (3.8k★) | Python SDK | ✅ | 🥈 |
| P-C | cv-cat/BilibiliApis (27★) | 算法逆向 | ✅ | 🥉 |
| S-A | Vespa314/bilibili-api (1.4k★) | 停维护对照 | ✅ | |
| S-B | czp3009/bilibili-api (521★) | Kotlin | ✅（调用成本高） | |
| T | Bing site:bilibili.com | SEO 兜底 | ✅ | 永不 fail |

### 1.4 微信公众号

| path | repo | 类型 | 零登录 | 优先测 |
|---|---|---|---|---|
| P-A | cooderl/wewe-rss (9.2k★) | 微信读书 → RSS | 🟡 需一次性读书 cookie | 🥇 |
| P-B | rachelos/we-mp-rss (2.9k★) | RSS + API | 🟡 | 🥈 |
| P-C | ttttmr/Wechat2RSS (1.4k★) | Shell 实现 | 🟡 | 🥉 |
| S-A | chyroc/WechatSogou (6.2k★) | Sogou 搜索 | ✅ 但 captcha | |
| S-B | wnma3mz/wechat_articles_spider (3.4k★) | 需登录 token | 🟡 | |
| S-C | bowenpay/wechat-spider (3.3k★) | 文章抓 | 🟡 | |
| T | Bing site:mp.weixin.qq.com + 百度 | SEO 兜底 | ✅ | 永不 fail |

### 1.5 微博

| path | repo | 类型 | 零登录 | 优先测 |
|---|---|---|---|---|
| P-A | m.weibo.cn `/api/container/getIndex` | 公开 HTTP | ✅ | 🥇 |
| P-B | dataabc/weiboSpider (9.5k★) | 用户 timeline | ✅ 部分需 cookie | 🥈 |
| P-C | dataabc/weibo-crawler (4.5k★) | 含图片视频 | ✅ 部分 | 🥉 |
| S-A | LiuXingMing/SinaSpider (3.3k★) | Scrapy + Redis | 🟡 | |
| S-B | stay-leave/weibo-public-opinion-analysis (1k★) | 舆情分析链路 | 🟡 | |
| S-C | CharesFang/WeiboSpider (139★) | — | 🟡 | |
| T | Bing site:weibo.com | SEO 兜底 | ✅ | 永不 fail |

### 1.6 知乎

| path | repo | 类型 | 零登录 | 优先测 |
|---|---|---|---|---|
| P-A | Bing site:zhihu.com | SEO（收录极好） | ✅ | 🥇 |
| P-B | zhuanlan.zhihu.com HTTP | 专栏反爬松 | ✅ | 🥈 |
| P-C | cv-cat/ZhihuApis (22★) | x-zse-96 逆向 | ✅ 存疑 | 🥉 |
| S-A | lzjun567/zhihu-api (991★) | Python for Humans | 🟡 | |
| S-B | moxiegushi/zhihu (528★) | 验证码识别 | 🟡 | |
| S-C | LiuRoy/zhihu_spider (1.3k★) | 老牌 | 🟡 | |
| S-D | littlepai/Unofficial-Zhihu-API (77★) | 深度学习识别验证码 | 🟡 | |
| S-E | syaning/zhihu-api (265★) | JS | 🟡 | |
| T | 百度 site:zhihu.com | SEO 兜底 | ✅ | 永不 fail |

---

## 2. 第二梯队 · 4 平台

### 2.1 快手

| path | repo | 类型 | 零登录 | 优先测 |
|---|---|---|---|---|
| P-A | NanmiCoder/MediaCrawler (47.9k★) 快手 module | 浏览器 + stealth | ❌ 需 cookie + 浏览器 | 🥇（接受 e2b 跑 Playwright） |
| P-B | ShilongLee/Crawler (1.3k★) | Docker 一键含快手 | 🟡 | 🥈 |
| P-C | yuncaiji/API (367★) | 多 app 逆向含快手 | ✅ 若 API 纯 HTTP | 🥉 |
| S-A | oGsLP/kuaishou-crawler (186★) | 单平台（已停更） | 🟡 | |
| S-B | sh-moranliunian/CobWeb (19★) | — | 🟡 | |
| T | Bing site:kuaishou.com | SEO 兜底 | ✅ | |

### 2.2 即刻

| path | repo | 类型 | 零登录 | 优先测 |
|---|---|---|---|---|
| P-A | MidnightDarling/jike-skill (15★) | Claude Code Skill（扫码登录）| ❌ | 🥇（工程可行性测） |
| P-B | RSSHub public `/jike/*` | RSS | ✅ | 🥈 |
| S-A | cypggs/jike-cli (0★) | CLI | 🟡 | |
| T | Bing site:okjike.com | SEO 兜底 | ✅ | 永不 fail |

### 2.3 小宇宙

| path | repo | 类型 | 零登录 | 优先测 |
|---|---|---|---|---|
| P-A | RSSHub public `/xiaoyuzhoufm/*` | RSS（shownotes） | ✅ | 🥇 |
| P-B | slarkio/xyz-dl (16★) | 音频 + 文字 | ✅ | 🥈 |
| P-C | anfushuang/xiaoyuzhoufmdownload (33★) | Python 音频下载 | ✅ | 🥉 |
| S-A | donlon/xyz-fetcher (4★) | Python 爬虫 | ✅ | |
| S-B | ychenjk-sudo/xiaoyuzhou-transcription-skill (8★) | 转录 + 总结 skill | ✅ 贵 | |
| S-C | fueny/PTT-Cpu- (8★) | 小宇宙转文字稿 | ✅ 贵 | |
| T | Bing site:xiaoyuzhou.fm | SEO 兜底 | ✅ | 永不 fail |

### 2.4 36氪

| path | repo | 类型 | 零登录 | 优先测 |
|---|---|---|---|---|
| P-A | 36kr.com/feed 官方 RSS | RSS | ✅ | 🥇 |
| P-B | cxyfreedom/website-hot-hub (339★) | 热榜聚合（含 36氪）| ✅ | 🥈 |
| S-A | jiangqqlmj/36Kr_Data_Crawler (6★) | Jsoup 抓首页 | ✅ | |
| S-B | ldh2068vip/36krCrawler (4★) | Java 采集 | ✅ | |
| T | Bing site:36kr.com | SEO 兜底 | ✅ | 永不 fail |

---

## 3. 第三梯队 · 3 平台

### 3.1 CSDN

| path | repo | 类型 | 零登录 | 优先测 |
|---|---|---|---|---|
| P-A | blog.csdn.net/{user}/rss 原生 RSS | RSS | ✅ | 🥇 |
| P-B | ds19991999/csdn-spider (62★) | 用户博文 MD | ✅ | 🥈 |
| S-A | SchrodingersBug/CSDN_SearchEngine (30★) | 爬虫 + 倒排索引 | ✅ | |
| S-B | kaixindelele/CSDN_pageviews_spider (15★) | — | ✅ | |
| T | Bing site:csdn.net | SEO 兜底 | ✅ | 永不 fail |

### 3.2 掘金

| path | repo | 类型 | 零登录 | 优先测 |
|---|---|---|---|---|
| P-A | api.juejin.cn 公开 endpoint（F12 扒）| HTTP | ✅ | 🥇 |
| P-B | 掘金官方 RSS | RSS | ✅ | 🥈 |
| S-A | iDerekLi/juejin-helper (277★) | 签到工具（含 API）| 🟡 | |
| S-B | sanfengliao/vue-juejin (289★) | Vue 客户端（含 API 调用参考）| ✅ | |
| S-C | lm-rebooter/NuggetsBooklet (955★) | 小册 | ✅ | |
| T | Bing site:juejin.cn | SEO 兜底 | ✅ | 永不 fail |

### 3.3 雪球

| path | repo | 类型 | 零登录 | 优先测 |
|---|---|---|---|---|
| P-A | xueqiu.com/hq.json 公开端点 | HTTP | ✅ | 🥇 |
| P-B | liqiongyu/xueqiu_mcp (106★) | MCP server | ✅ | 🥈 |
| P-C | decaywood/XueQiuSuperSpider (2.4k★) | Java 超级爬虫 | ✅ | 🥉 |
| S-A | Rockyzsu/xueqiu (99★) | Python 登录 + 全文章 | 🟡 | |
| S-B | 1dot75cm/xueqiu (46★) | humanize API | ✅ | |
| S-C | newer027/Xueqiu_data (29★) | 组合分析 | ✅ | |
| T | Bing site:xueqiu.com | SEO 兜底 | ✅ | 永不 fail |

---

## 4. 测试 harness 架构

### 目录结构

```
autosearch/tests/e2b-channel-matrix/
├── runner.py              # 主入口：读方案表 → 启 e2b sandbox → 跑 → 收结果
├── harness/
│   ├── base.py            # ScrapeResult schema, 统一 timing/error 捕获
│   ├── sandbox.py         # e2b SDK 封装
│   └── registry.py        # 所有方案的 metadata
├── adapters/              # 每个方案一个 adapter，clone repo + 写 entry
│   ├── xiaohongshu/
│   │   ├── cloxl_xhshow/
│   │   │   ├── setup.sh   # git clone + pip install
│   │   │   └── run.py     # 调用 repo API，输出统一 JSON
│   │   ├── cialle_redcrack/
│   │   ├── ...
│   ├── douyin/
│   ├── bilibili/
│   ...
├── queries/
│   └── standard.json      # 5 个测试 query
└── reports/
    └── {YYYY-MM-DD}/
        ├── raw.jsonl      # 每条路径 × 每 query 一行
        ├── summary.json   # 汇总 matrix
        └── report.md      # 人看的 rollup
```

### ScrapeResult schema

```python
from pydantic import BaseModel
from typing import Literal, Optional

class ScrapeResult(BaseModel):
    platform: str
    path_id: str            # e.g. "xiaohongshu.primary.cloxl_xhshow"
    repo: str               # github url
    query: str
    status: Literal["ok", "anti_bot", "timeout", "error", "needs_login"]
    http_code: Optional[int] = None
    items_returned: int = 0
    avg_content_len: int = 0
    first_byte_ms: Optional[int] = None
    total_ms: Optional[int] = None
    error: Optional[str] = None
    sample: Optional[str] = None  # 第一条 200 字截取
    anti_bot_signals: list[str] = []  # ["captcha_url", "403", "empty_20x"]
```

### e2b sandbox 生命周期（template + batch + CI）

每个 adapter 一个 sandbox，跑完全部 query × 重试次数：

```python
from e2b_code_interpreter import Sandbox
import asyncio, json, shlex

async def run_adapter_full(adapter, queries, reps=3) -> list[ScrapeResult]:
    """一个 sandbox 跑完一个 adapter 的全部测试，共享 setup"""
    sbx = await Sandbox.create(template=adapter.template, timeout=600)
    try:
        # 一次 setup（template 已含依赖，只 clone repo）
        await sbx.commands.run(f"bash {adapter.setup_sh}", timeout=120)
        # warmup 两次确认能跑，不行直接 short-circuit
        warmup = await run_single(sbx, adapter, queries[0])
        if warmup.status == "error":
            return [warmup.copy(update={"query": q}) for q in queries for _ in range(reps)]
        # 批量跑
        results = []
        consecutive_fail = 0
        for q in queries:
            for i in range(reps):
                r = await run_single(sbx, adapter, q)
                results.append(r)
                if r.status in ("error", "timeout"):
                    consecutive_fail += 1
                    if consecutive_fail >= 5:  # 健康断路
                        return results + short_circuit_rest(queries, q, reps, i)
                else:
                    consecutive_fail = 0
        return results
    finally:
        await sbx.kill()

# 全局并发 20
semaphore = asyncio.Semaphore(20)
async def run_bounded(adapter, queries):
    async with semaphore:
        return await run_adapter_full(adapter, queries)

all_results = await asyncio.gather(*[run_bounded(a, QUERIES) for a in adapters])
```

### 方案 adapter 骨架

每个第三方 repo 都遵循同样的 adapter 协议：

```bash
# adapters/xiaohongshu/cloxl_xhshow/setup.sh
set -euo pipefail
git clone --depth=1 https://github.com/Cloxl/xhshow.git /workspace/xhshow
cd /workspace/xhshow
pip install -r requirements.txt
```

```python
# adapters/xiaohongshu/cloxl_xhshow/run.py
# 职责：吃 --query，吐统一 JSON
import argparse, json, sys, time, traceback
sys.path.insert(0, "/workspace/xhshow")

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--query", required=True)
    args = ap.parse_args()
    t0 = time.time()
    try:
        from xhshow import search  # 改成对应 repo 的 API
        items = search(keyword=args.query, page=1, page_size=20)
        result = {
            "platform": "xiaohongshu",
            "path_id": "xiaohongshu.primary.cloxl_xhshow",
            "repo": "https://github.com/Cloxl/xhshow",
            "query": args.query,
            "status": "ok" if items else "empty",
            "items_returned": len(items),
            "avg_content_len": int(sum(len(i.get("content","")) for i in items)/max(len(items),1)),
            "total_ms": int((time.time()-t0)*1000),
            "sample": (items[0].get("content","")[:200]) if items else None,
        }
    except Exception as e:
        result = {
            "platform": "xiaohongshu",
            "path_id": "xiaohongshu.primary.cloxl_xhshow",
            "repo": "https://github.com/Cloxl/xhshow",
            "query": args.query,
            "status": "error",
            "error": f"{type(e).__name__}: {e}",
            "total_ms": int((time.time()-t0)*1000),
        }
    print(json.dumps(result, ensure_ascii=False))

if __name__ == "__main__":
    main()
```

每个 adapter **只要写 20-30 行 `run.py`**，把 repo 的 API 映射到统一输出。写不出来（repo 接口太封闭）= 该 repo 不可复用，直接 RED 淘汰。

---

## 5. 并发最大化（15-20 分钟跑完全矩阵）

e2b free tier **20 并发 sandbox**。核心优化三层：

### Layer 1 · 预构建 Sandbox Template

`git clone + pip install` 占 setup 80% 时间。不重复做：

| Template | 包含 | 用于 |
|---|---|---|
| `as-python-http` | Python 3.11 + requests/httpx/feedparser/bs4/trafilatura/ddgs | 60% 纯 HTTP adapter |
| `as-python-browser` | 上面 + Playwright + Chromium | MediaCrawler 等浏览器 adapter |
| `as-node-browser` | Node 20 + puppeteer/playwright-node | JS 系 MCP（xpzouying 小红书）|

**启动时间**：60-120s → **<2s**。成本直接降一个数量级。

### Layer 2 · Sandbox 级并发 20

```python
semaphore = asyncio.Semaphore(20)
async def run_one(adapter):
    async with semaphore:
        sbx = await Sandbox.create(template=adapter.template)
        try:
            return await adapter.run_all_queries(sbx)
        finally:
            await sbx.kill()

await asyncio.gather(*[run_one(a) for a in adapters])
```

### Layer 3 · Sandbox 内 Query 批处理

一个 sandbox 跑完**同一 adapter** 的全部 20 query × 3 次，共享 setup：

```
❌ 每 query 起新 sandbox：50 × 60 = 3000 sandbox
✅ 每 adapter 共享 sandbox：50 sandbox
```

**setup 摊薄**：2s / 60 请求 = 0.03s per query，可忽略。

### 时间实算

| 阶段 | 数字 |
|---|---|
| 总测试 | 50 adapter × 20 query × 3 次 = 3000 |
| 单 sandbox 耗时 | setup 2s + 60 请求 × 3s = ~180s |
| 并发 20 → 轮数 | ceil(50/20) = 3 轮 |
| 单时段总耗时 | 3 × 180s = **~9 分钟** |
| 2 时段总 | **~20 分钟** |

### 成本实算

3000 × 3s × $0.0001 × 2 时段 ≈ **$1.8**。重跑 5 次 <$10。免费 tier 够。

### 附加优化

- **健康断路**：adapter 连续 5 次 timeout 直接终止剩余 query，标 RED，省 sandbox 时间
- **错峰启动**：20 并发拆 2 批 × 10，间隔 30s，避免同 IP 段集中风控
- **Warmup**：先跑小热身（1 adapter × 2 query）确认环境，再全速压测。防止 bug 让 3000 次白跑

## 6. 排期

### 批次 0 · Harness + Template（Day 1）
- 搭 harness（runner + sandbox SDK 封装 + schema + CI 报告）
- 推 3 个 e2b template 到 registry
- B站 WBI 和 Bing SEO 两个 adapter 跑通 pipeline
- 产出：pipeline green

### 批次 1 · 全量铺 adapter（Day 2-3）
- 按"抄作业"原则批量写 50 个 adapter
- 每个 adapter = setup.sh + run.py（~30 行）
- Codex 批量产出，Claude Code review

### 批次 2 · 第一梯队测试（Day 3 晚）
- 6 平台 × 5-8 adapter × 60 请求 × 2 时段 = ~500 次有效样本（每 adapter）
- 跑完出第一梯队 health matrix

### 批次 3 · 第二梯队测试（Day 4）
- 4 平台 × 3-4 adapter × 全量样本

### 批次 4 · 第三梯队测试（Day 4）
- 3 平台 × 3 adapter × 全量样本

### 批次 5 · 汇总 + v2 routing table（Day 5）
- 按 Wilson CI 打分 + 分场景矩阵
- 每平台推荐 Primary + Secondary + Tertiary + 按 category 的 scope
- 提交老板 review

---

## 6. 失败处理

### 方案不能跑的情况分类

1. **repo 依赖冲突 / 没有 entry**：直接 RED，写入 `disqualified.md` 记录原因
2. **repo 要 cookie / 登录**：尝试生成一次 cookie（手动登录导出）测一次，之后按"需登录"标记
3. **反爬触发**：记录 http_code + response_text 片段，尝试 Tertiary 路径
4. **e2b sandbox 网络被平台屏蔽**：换地区 / 或跳过该方案
5. **需要 JS 执行但 repo 是纯 HTTP**：尝试配浏览器（e2b 支持 Playwright），如果 repo 设计就不支持则 RED

### 重试策略
- 同一 query 同一路径失败 → **不重试**（捕获真实 signal）
- 整批测试失败 → 换 sandbox template 重跑
- **不要** 把 retry logic 藏进 adapter 里 —— 会掩盖"这个方案真实稳定性差"的信号

---

## 7. 产出交付

测试完成后生成三份文件：

### 7.1 `reports/{date}/health-matrix.json`
```json
{
  "generated_at": "2026-04-16T15:00:00Z",
  "platforms": {
    "xiaohongshu": {
      "primary_candidates": [
        {"path_id": "cloxl_xhshow", "success_rate": 0.8, "avg_latency_ms": 2100, "grade": "GREEN"},
        {"path_id": "cialle_redcrack", "success_rate": 0.4, "avg_latency_ms": 3200, "grade": "YELLOW"},
        {"path_id": "xhs996_xhs_spider", "success_rate": 0.0, "avg_latency_ms": null, "grade": "RED"}
      ],
      "recommended": {
        "primary": "cloxl_xhshow",
        "secondary": "cialle_redcrack",
        "tertiary": "bing_seo"
      }
    }
  }
}
```

### 7.2 `reports/{date}/v2-routing-table.md`
人读版本，每平台一节，写明：
- 推荐 Primary 是哪个 repo，为什么
- 预计维护成本（churn rate、签名稳定性）
- 何时触发切 Secondary
- Tertiary 保底是什么

### 7.3 `reports/{date}/disqualified.md`
列出被踢掉的方案（要 cookie/不能复用/依赖地狱/死 repo），理由 + 证据。

---

## 8. 风险 · 必须在测试前明确

1. **e2b ToS**：大规模中国平台爬虫是否允许？测试阶段 ~270 次请求应该安全，生产阶段如果用 e2b 当执行层要重新评估
2. **纯算法签名 churn**：测试完通过的 Primary，过 1-3 个月可能失效。必须建 `scripts/daily-health-check.sh` 每天重跑核心 20 个 query，失败告警
3. **微信公众号 wewe-rss 依赖微信读书 cookie**：测试时用测试账号一次性，生产策略老板后续再定
4. **知乎 / 微博 / B站 e2b 出口 IP 可能被风控**：测试时准备 IP 多样性备案（e2b sandbox 地区可选）

---

## 9. 下一步

**立刻可做**：
1. 创建 `tests/e2b-channel-matrix/` 目录结构
2. 写 `harness/sandbox.py` + `harness/base.py`（200 行）
3. 先写 **B站 Primary A（WBI 签名自实现）** 和 **Bing SEO Tertiary** 两个 adapter 跑通 pipeline
4. 跑通后批量铺开其他 adapter

**谁写**：建议 Codex 做。因为这 45+ 个 adapter 大部分是 "clone repo + 写 20 行映射"，重复性高，Codex 批量产出效率远高于 Claude Code。

**我主导的部分**：harness 设计、报告模板、测试结果判读（GREEN/YELLOW/RED 决策不能让 Codex 拍板）。
