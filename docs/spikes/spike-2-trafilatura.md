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

### Result Table

| site | pass_rate | top_fail_reason | verdict (pass/fail/needs-cleaner) |
|---|---|---|---|
| zhihu |  |  |  |
| csdn |  |  |  |
| juejin |  |  |  |
| wechat |  |  |  |

### Remediation Map

| fail_reason | next action |
|---|---|
| `http_error` | HTTP retry layer |
| `antibot` | Playwright fallback plan § 8 TBD-C |
| `empty_extract` | per-source cleaner plan § 13.5 M4 |
| `short_extract` | per-source cleaner plan § 13.5 M4 |
| `js_only` | Playwright fallback |

Claude runs locally via `python tests/eval/spike_2_trafilatura.py` and fills result table.
