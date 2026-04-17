# Self-written, plan v2.3 § 6

## Spike 2: trafilatura Chinese Extraction Harness

### Goal

Per plan v2.3 § 6, Spike 2 validates whether `trafilatura` can clear the M4 baseline for Chinese article extraction before broader pipeline work starts.

Success bar: `> 90%` extraction pass rate per site for four source groups, each sampled with 30 public URLs:

- 知乎
- CSDN
- 掘金
- 微信公众号

### Approach

The harness uses `httpx` for raw HTML fetches and `trafilatura.extract(..., include_tables=False, include_comments=False, output_format="txt")` for plain-text extraction, matching the plan's M4 source reference to `storm/knowledge_storm/utils.py:L685-L711`.

Playwright is explicitly deferred. Per plan § 8 TBD-C, the default chain stays `plain httpx -> Playwright (specific channels only) -> abort with structured error`, so this spike measures the plain-HTTP baseline first and leaves browser fallback for M4.

### URL Selection Method

| Site | Method |
|---|---|
| 知乎 | Public search-surfaced `question/<id>` and `zhuanlan/p/<id>` URLs from stable AI, Python, and history topics; mix of Q&A pages and long-form columns. |
| CSDN | Public `blog.csdn.net/<user>/article/details/<id>` posts from Python, AI, backend, architecture, and algorithm queries; skewed toward tutorial-style articles likely to produce long body text. |
| 掘金 | Public `juejin.cn/post/<id>` posts from frontend, backend, Python, AI, and computing-history searches; mixed explainers, notes, and hands-on walkthroughs. |
| 微信公众号 | Canonical `mp.weixin.qq.com` article URLs copied from public reshare/archive pages for tech accounts such as 腾讯技术工程, 阿里技术, AI前线 / InfoQ, and 阮一峰 related reposts. |

### Result Table (run 2026-04-17, local)

| site | pass_rate | top fail pattern | avg html size | verdict |
|---|---|---|---|---|
| zhihu | 0/30 (0.0%) | 26× `403/http_error`, 4× `200/antibot` | 25.8 KB | **FAIL** — needs cookie + UA spoof + Playwright fallback |
| csdn | 0/30 (0.0%) | 30× `521/http_error` (Cloudflare JS challenge) | 2.1 KB | **FAIL** — Cloudflare wall, Playwright/Camoufox required |
| juejin | 0/30 (0.0%) | 27× `200/antibot`, 3× `404/http_error` | 139.3 KB | **FAIL** — SPA, needs Playwright for JS rendering |
| wechat | 22/30 (73.3%) | 7× `200/antibot`, 1× `200/short_extract` | 2.2 MB | **MARGINAL** — below 90% bar, mostly works with httpx |

### Verdict

Plan § 6 bar (`> 90%` per site) is **not met** on any site. `httpx + trafilatura` alone is insufficient for Chinese extraction.

### Implications for plan v2.3

1. **§ 8 TBD-C needs revision**: "Playwright 非主力" is wrong for Chinese sites. For zhihu / csdn / juejin, Playwright (or Camoufox) must be the primary fetch path, not a fallback.
2. **§ 13.5 M4 per-source cleaner framework**: still needed for wechat's 7 antibot cases and for cleaning Playwright-rendered HTML per site.
3. **M3 channel strategy (plan § 12)**: the v1 legacy tags confirmed Agent-Reach uses `xhs-cli` subprocess, `rdt-cli`, `gh`, `douyin-mcp-server` — these wrap native SDKs/CLIs rather than scraping HTML. Spike 2 confirms: for any Chinese platform without such a wrapper (e.g. direct blog scraping on CSDN / juejin), browser automation is mandatory.
4. **Cost**: plan § 4 "non-Playwright primary" budget optimistic. Realistic: every Chinese site needs Playwright/Camoufox unless a native SDK/CLI exists.

### Per-site remediation

| site | recommended chain |
|---|---|
| zhihu | cookie (`z_c0`) + `UA: Mozilla/5.0 (Windows NT 10.0...) zh-CN` + `Referer: https://www.zhihu.com/` via httpx; fallback Playwright+cookie for 403 retries. Status: plan § 12 already budgets 2-3 weeks for from-scratch zhihu channel — spike confirms scope. |
| csdn | Playwright/Camoufox required (Cloudflare 521 is JS challenge, no headers bypass). Add per-source cleaner to strip navigation + CSDN-specific SPA wrappers. Plan § 12 budgets ~2 days via searxng sogou_wechat reference — **needs revision to include Playwright cost** (~2-3 days). |
| juejin | Playwright required for SPA hydration. `juejin.cn/post/<id>` serves shell HTML only; article body rendered client-side. Plan (no 1:1 source for juejin) — self-written channel, ~2-3 days including Playwright wrapper. |
| wechat | Keep httpx primary; reserve Playwright for 23% antibot cases. Per-source cleaner for wechat-specific `__biz` / `mid` / `idx` URL validation + redirect handling. Aligned with plan § 12 (~2 days + maintenance). |

### Remediation Map (unchanged)

| fail_reason | next action |
|---|---|
| `http_error` | HTTP retry layer + cookie/UA injection |
| `antibot` | Playwright/Camoufox fallback plan § 8 TBD-C |
| `empty_extract` | per-source cleaner plan § 13.5 M4 |
| `short_extract` | per-source cleaner plan § 13.5 M4 |
| `js_only` | Playwright fallback |

Raw data: `tests/eval/spike_2_results.json` (120 entries, one per URL).
