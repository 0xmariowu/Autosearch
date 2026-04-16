# Adapter Contract · 8 路 Codex 必读

> 每个 adapter 是一个**独立的 e2b sandbox 测试单元**。严格遵守本 spec，否则会被 8 路 review 打回。

## 铁律（违反立即 RED 重写）

1. **严禁自写爬虫 / 签名算法 / 反爬绕过**。必须 `git clone` 第三方 repo 或 `pip install` 第三方包，调用它暴露的 API
2. **严禁写死本地 Mac 路径**（`/Users/`、`/home/`）。sandbox 里只能用 `/tmp/as-matrix/`
3. **严禁硬编码 cookie / API key / 账号**。需要登录的方案直接标 `status="needs_login"` 返回
4. **严禁吞掉 exception**。异常必须反映到 `status="error" + error` 字段
5. **严禁超出 30 秒**。30s 内必须给结果，超时交出权（sandbox.py 会 kill）

## 目录结构（严格遵守）

```
tests/e2b-channel-matrix/adapters/
└── {platform}__{scheme}/         # 目录名规范：{platform 小写}__{方案名 snake_case}
    ├── setup.sh                  # bash 脚本，clone + pip install
    └── run.py                    # Python 入口，吃 --query，吐一行 JSON
```

**目录名示例**（参考）：
- `xiaohongshu__cloxl_xhshow`
- `douyin__nearhuiwen_a_bogus`
- `bilibili__nemo2011`
- `bilibili__cv_cat_bilibiliapis`
- `weibo__dataabc_weibospider`
- `weibo__m_weibo_cn_api`
- `wechat__wewe_rss`
- `seo__bing_via_ddgs`

## setup.sh 规范

```bash
#!/usr/bin/env bash
set -euo pipefail

# 1. clone 第三方 repo（如果是 pip install 的库直接第 2 步）
git clone --depth=1 https://github.com/OWNER/REPO /tmp/as-matrix/REPO

# 2. 安装依赖
pip install /tmp/as-matrix/REPO

# 3. 补装第三方 repo 可能遗漏的依赖（比如 bilibili-api 需要 httpx）
pip install httpx  # 如需

# 不允许：apt-get install / docker / 任何交互式操作
# 不允许：clone 后再 cd 进去改源码
```

**硬限制**：setup.sh 执行时间 ≤ 180s，超时 = RED

## run.py 规范

```python
from __future__ import annotations
import argparse, json, sys, time
from pathlib import Path

# 如果是 git clone 进来的 repo，把它加到 sys.path
REPO_PATH = Path("/tmp/as-matrix/REPO")
if str(REPO_PATH) not in sys.path:
    sys.path.insert(0, str(REPO_PATH))

REPO_URL = "https://github.com/OWNER/REPO"
PLATFORM = "xiaohongshu"  # 小写平台名
PATH_ID = "xiaohongshu__cloxl_xhshow"  # 必须与目录名一致


def _extract_item_text(item) -> str:
    """从 API 返回的单条 item 提取文本内容（标题+正文优先）。"""
    if isinstance(item, str):
        return item
    if not isinstance(item, dict):
        return str(item)
    for k in ("content", "desc", "body", "text", "title", "snippet", "summary"):
        v = item.get(k)
        if v:
            return str(v)
    return json.dumps(item, ensure_ascii=False)[:300]


def run(query: str, query_category: str) -> dict:
    started = time.perf_counter()
    try:
        # ⬇️ 调用第三方 repo 的 API，不要自己写 HTTP 请求
        from some_library import search
        resp = search(keyword=query, limit=20)

        # ⬇️ 提取有意义的内容项（过滤掉 tips/empty_groups/meta 等）
        items = resp.get("data") or []
        items = [x for x in items if _has_real_content(x)]

        # ⬇️ 计算 summary
        max_items = items[:20]
        texts = [_extract_item_text(i) for i in max_items]
        avg_len = int(sum(len(t) for t in texts) / len(texts)) if texts else 0
        sample = (texts[0][:200] if texts else None)

        elapsed_ms = int((time.perf_counter() - started) * 1000)
        return {
            "platform": PLATFORM,
            "path_id": PATH_ID,
            "repo": REPO_URL,
            "query": query,
            "query_category": query_category,
            "status": "ok" if items else "empty",
            "items_returned": len(max_items),
            "avg_content_len": avg_len,
            "total_ms": elapsed_ms,
            "sample": sample,
            "anti_bot_signals": [],
        }
    except Exception as exc:
        elapsed_ms = int((time.perf_counter() - started) * 1000)
        msg = f"{type(exc).__name__}: {exc}"
        # 反爬 / 登录 / 超时要标记到 status
        status = "error"
        if any(s in msg.lower() for s in ["captcha", "验证码", "403", "401", "access denied"]):
            status = "anti_bot"
        elif any(s in msg.lower() for s in ["login", "unauthorized", "cookie", "token"]):
            status = "needs_login"
        elif "timeout" in msg.lower():
            status = "timeout"
        return {
            "platform": PLATFORM,
            "path_id": PATH_ID,
            "repo": REPO_URL,
            "query": query,
            "query_category": query_category,
            "status": status,
            "error": msg,
            "total_ms": elapsed_ms,
            "anti_bot_signals": [],
        }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--query", required=True)
    ap.add_argument("--query-category", required=True)
    args = ap.parse_args()
    result = run(args.query, args.query_category)
    print(json.dumps(result, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
```

## 输出 JSON 必填字段

| 字段 | 类型 | 必填 | 说明 |
|---|---|---|---|
| `platform` | str | ✅ | 小写平台名，如 `xiaohongshu` |
| `path_id` | str | ✅ | 与目录名一致，如 `xiaohongshu__cloxl_xhshow` |
| `repo` | str | ✅ | GitHub URL |
| `query` | str | ✅ | 原样回显 |
| `query_category` | str | ✅ | consumer/tech/finance/celebrity/general |
| `status` | enum | ✅ | ok / empty / anti_bot / needs_login / timeout / error |
| `items_returned` | int | - | 过滤后有意义 item 数 |
| `avg_content_len` | int | - | 平均内容长度（字符数，不含标签） |
| `total_ms` | int | - | 从进入 run 到返回的毫秒数 |
| `sample` | str\|null | - | 第一条 item 的 200 字摘要（脱 HTML） |
| `error` | str\|null | - | 异常类型 + 原文 |
| `anti_bot_signals` | list[str] | - | 比如 `["captcha_url", "403", "empty_20x"]` |

## Mapping 原则（防 items_returned 虚高）

**反例**：B站 API 返回 `{"result": [{"result_type": "tips", "data": []}, {"result_type": "video", "data": [...]}]}`，如果直接 `response["result"]` 当 items，就会把 `tips/live_user/empty` 这些元数据组也算成 item，**items_returned 虚高**。

**正解**（B站为例，已在 `bilibili__nemo2011/run.py` 实现）：
```python
CONTENT_TYPES = {"video", "article", "bili_user", "media_bangumi", "media_ft"}
for group in response["result"]:
    if group.get("result_type") in CONTENT_TYPES:
        items.extend(group.get("data", []))
```

**适用于所有平台**：
- 小红书：过滤 `model_type != note` 的卡片
- 抖音：过滤广告位、推荐位
- 微博：过滤转发卡片中的广告
- 知乎：过滤「相关搜索」，只保留 `object.type == "answer" / "article"`

## 禁止项汇总

| ❌ 禁止 | ✅ 替代 |
|---|---|
| 自己写签名算法 | `import` 第三方 repo 的签名函数 |
| 硬编码 cookie | 返回 `status="needs_login"` |
| `try: ... except: pass` | 必须 re-raise 或 status=error |
| 在 run.py 里 `subprocess.run(["pip", "install", ...])` | 放到 setup.sh |
| `/Users/` `/home/` 开头的路径 | `/tmp/as-matrix/` |
| 不 filter tips / empty group | 必须 filter 真实内容类型 |
| 写死 `max_items=100` 后 OOM | 遵守 20-50 上限 |
| 调用外网 API 前不设 timeout | `timeout=10` 是默认 |

## 自测流程（Codex 写完每个 adapter 必须跑）

```bash
# 本地 dry-run 验证 JSON 结构
python tests/e2b-channel-matrix/adapters/{path_id}/run.py \
    --query "AI 创业" --query-category consumer

# 期望：stdout 输出一行 JSON，platform/path_id/status 必填齐全
```

**Codex 写完 N 个 adapter 就用 `runner.py --smoke --only {path_id1,path_id2,...}` 跑真 e2b**：
```bash
set -a && source .env && set +a
.venv/bin/python tests/e2b-channel-matrix/runner.py --smoke --only xiaohongshu__cloxl_xhshow
```

每个 adapter 必须在真 e2b 上至少跑 1 次 `status in ("ok","empty")`，才能 commit。status="error" 或 "needs_login" 必须在 PR 描述里说明原因。

## Registry 注册

adapter 写完后在 `tests/e2b-channel-matrix/harness/registry.py` 里加一条：

```python
AdapterConfig(
    platform="xiaohongshu",
    path_id="xiaohongshu__cloxl_xhshow",
    repo="https://github.com/Cloxl/xhshow",
    template="as-python-http",  # 或 as-python-browser
    setup_script=ROOT / "adapters/xiaohongshu__cloxl_xhshow/setup.sh",
    run_script=ROOT / "adapters/xiaohongshu__cloxl_xhshow/run.py",
    setup_timeout_s=120,
    run_timeout_s=30,
    circuit_breaker_failures=5,
),
```

## Commit 规范

- 使用 `scripts/committer`（不要直接 `git commit`）
- 每路 Codex 一批 adapter = 一个 commit：`feat(adapters): {platform group} × N adapters`
- 不允许 `git add .`；只 stage 自己这批 adapter + registry.py 改动
