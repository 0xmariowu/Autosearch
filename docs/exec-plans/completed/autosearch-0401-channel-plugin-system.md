# Channel Plugin System — 把每个搜索渠道变成独立 plugin

## Goal

把 search_runner.py 里的 32 个渠道从"一个大文件里的 lambda 字典"重构成独立的 channel plugin（每个渠道一个目录，SKILL.md + search.py）。同时从 SearXNG / swirl-search / OpenManus 提取更好的搜索实现替换 ddgs site:X。

## 背景

- 当前：32 个渠道全部塞在 `search_runner.py`（735 行），26 个用 `ddgs site:X`（不可靠）
- 问题：ddgs 不索引中文网站，很多渠道返回 0 结果或垃圾结果
- 方案来源：Armory/Search 有 16 个项目，SearXNG 有 100+ engine 可直接提取
- 架构参考：Claude Code plugin 模式（约定式目录发现）

## Features

### F001: Channel loader 基础设施 — todo

搭建 channel plugin 的加载机制。loader 扫描 `channels/*/` 目录，读 SKILL.md frontmatter，导入 search.py，自动注册到 CHANNEL_METHODS。下划线开头的目录（如 `_engines/`）跳过（共享引擎，不是独立渠道）。

#### Steps
- [ ] S1: 创建 `autosearch/v2/channels/__init__.py`，实现 `load_channels()` — 扫描同级目录（跳过 `_` 前缀和 `__pycache__`），每个子目录必须有 `search.py`，导入其 `search()` 函数，返回 `dict[str, Callable]`。支持 SKILL.md frontmatter 里的 `aliases` 字段（如 papers-with-code → arxiv）← verify: `cd ~/Projects/autosearch && python -c "from autosearch.v2.channels import load_channels; ch = load_channels(); print(len(ch), list(ch.keys()))"` 返回空字典
- [ ] S2: 定义 SKILL.md frontmatter 标准（name, description, categories, platform, api_key_required, aliases）和 search.py 接口标准（`async def search(query: str, max_results: int = 10) -> list[dict]`），写成 `channels/STANDARD.md` ← verify: 文件存在，内容完整
- [ ] S3: 修改 `search_runner.py`，将现有 `load_channels()` 函数（读 channels.json 的）重命名为 `load_channel_config()`，新增 `from autosearch.v2.channels import load_channels as load_channel_plugins`，在 CHANNEL_METHODS 构建时合并 plugin 渠道（plugin 优先于内联 lambda）← verify: `cd ~/Projects/autosearch && pytest -x -q` 全过（现有行为不变）
- [ ] S4: 写 `tests/test_channel_loader.py` — 测试：loader 发现机制、缺失 search.py 跳过、`_` 前缀目录跳过、aliases 注册、接口校验、总渠道数断言 ← verify: `pytest tests/test_channel_loader.py -v` 全过

### F002: 搬家 — 现有 API 渠道拆成 plugin（7 个）— todo

把 search_runner.py 里已有真实 API 的 7 个渠道搬到独立目录。代码逻辑不变，只是拆文件 + 写 SKILL.md。

渠道列表：ddgs, github-repos, github-issues, hn, semantic-scholar, citation-graph, arxiv

#### Steps
- [ ] S1: 创建 7 个渠道目录，每个包含 `search.py`（从 search_runner.py 提取）和 `SKILL.md`（按 STANDARD.md 格式）。arxiv 的 SKILL.md 加 `aliases: [papers-with-code]` ← verify: `cd ~/Projects/autosearch && python -c "from autosearch.v2.channels import load_channels; ch = load_channels(); print(len(ch)); assert 'papers-with-code' in ch"` 返回 8（7 渠道 + 1 别名）
- [ ] S2: 从 search_runner.py 删除已搬走的函数和对应 CHANNEL_METHODS 条目（depends: F001 S3 完成）← verify: `pytest -x -q` 全过 + `python search_runner.py '[{"channel":"hn","query":"test"}]'` 返回结果 + `python search_runner.py '[{"channel":"papers-with-code","query":"test"}]'` 返回结果（验证别名）
- [ ] S3: 写 `tests/test_channels_existing.py` — 对每个搬家渠道做 smoke test（mock HTTP，验证返回格式）← verify: `pytest tests/test_channels_existing.py -v` 全过

### F003: 抄 SearXNG — 7 个渠道（bilibili, stackoverflow, reddit, google-scholar, youtube, wechat, npm-pypi）— todo

从 SearXNG engine 代码提取搜索逻辑，适配成 AutoSearch channel plugin。

来源映射：
- bilibili ← `searxng/searx/engines/bilibili.py`（Bilibili API，JSON）
- stackoverflow ← `searxng/searx/engines/stackexchange.py`（StackExchange API，JSON）
- reddit ← `searxng/searx/engines/reddit.py`（Reddit JSON API，`search.json`）
- google-scholar ← `searxng/searx/engines/google_scholar.py`（HTML 解析）
- youtube ← `searxng/searx/engines/youtube_noapi.py`（HTML 解析）
- wechat ← `searxng/searx/engines/sogou_wechat.py`（搜狗微信搜索）
- npm-pypi ← `searxng/searx/engines/npm.py` + `pypi.py`（官方 API）

#### Steps
- [ ] S1: 逐个提取 SearXNG engine 代码，适配成 `async def search(query, max_results) -> list[dict]`。去掉 SearXNG 框架依赖（`searx.utils`、`searx.exceptions`），改用 httpx。每个渠道一个目录 ← verify: `cd ~/Projects/autosearch && for d in channels/bilibili channels/stackoverflow channels/reddit channels/google-scholar channels/youtube channels/wechat channels/npm-pypi; do python -c "import importlib.util; s=importlib.util.spec_from_file_location('m','autosearch/v2/$d/search.py'); m=importlib.util.module_from_spec(s); s.loader.exec_module(m); print(f'OK: $d')" || echo "FAIL: $d"; done` 全部 OK
- [ ] S2: 为每个渠道写 SKILL.md — 描述适用场景、质量信号、已知限制 ← verify: 7 个 SKILL.md 都有完整 frontmatter（name, description, categories, platform）
- [ ] S3: 从 search_runner.py 删除对应的 ddgs site:X lambda（depends: F001 S3 完成）← verify: `pytest -x -q` 全过
- [ ] S4: 写 `tests/test_channels_searxng.py` — 每个渠道 mock HTTP 测返回格式 ← verify: `pytest tests/test_channels_searxng.py -v` 全过
- [ ] S5: 实际网络调用冒烟测试（可选，CI 不跑）— 每个渠道用一个简单 query 验证能拿到结果 ← verify: `pytest tests/test_channels_searxng.py -v -k live --run-live` 至少 5/7 返回结果

### F004: 百度引擎 — 9 个中文渠道升级 — todo

从 SearXNG 提取 `baidu.py`，改造成支持 `site:` 参数的通用中文站内搜索。9 个中文渠道从 ddgs 切换到百度。

渠道列表：zhihu, csdn, juejin, 36kr, infoq-cn, weibo, xueqiu, xiaoyuzhou, xiaohongshu

#### Steps
- [ ] S1: 提取 SearXNG `baidu.py`，适配成 `channels/_engines/baidu.py` — 通用百度搜索函数 `async def search_baidu(query, site=None, max_results=10) -> list[dict]` ← verify: `cd ~/Projects/autosearch && python -c "import importlib.util; s=importlib.util.spec_from_file_location('m','autosearch/v2/channels/_engines/baidu.py'); m=importlib.util.module_from_spec(s); s.loader.exec_module(m); print('OK: search_baidu imported')"` 无报错
- [ ] S2: 创建 9 个渠道目录，每个 search.py 调用 `search_baidu(query, site="zhihu.com")` ← verify: `cd ~/Projects/autosearch && python -c "from autosearch.v2.channels import load_channels; ch = load_channels(); missing = [c for c in ['zhihu','csdn','juejin','36kr','infoq-cn','weibo','xueqiu','xiaoyuzhou','xiaohongshu'] if c not in ch]; print(f'OK: all 9' if not missing else f'MISSING: {missing}')"` 返回 OK
- [ ] S3: 为每个渠道写 SKILL.md ← verify: 9 个 SKILL.md 都有完整 frontmatter
- [ ] S4: 从 search_runner.py 删除对应 ddgs site:X lambda（depends: F001 S3 完成）← verify: `pytest -x -q` 全过
- [ ] S5: 写 `tests/test_channels_baidu.py` — mock 百度 HTTP 响应，验证 site: 参数拼接和结果解析 ← verify: `pytest tests/test_channels_baidu.py -v` 全过
- [ ] S6: 实际冒烟测试（可选，CI 不跑）— `search_baidu("AI agent框架", site="zhihu.com")` vs 旧 `search_ddgs_site("AI agent框架", "zhihu.com")` 对比结果数量和质量 ← verify: 百度 >= ddgs 的结果数量

### F005: 其他渠道 — crunchbase, devto, douyin, 保留 ddgs 的 3 个 — todo

#### Steps
- [ ] S1: crunchbase — 参考 swirl-search `SearchProviders/crunchbase.json`，写 `channels/crunchbase/search.py` + SKILL.md ← verify: import 无报错
- [ ] S2: devto — 用 dev.to Forem API（`https://dev.to/api/articles?tag=&query=`，免费无 key），写 `channels/devto/search.py` + SKILL.md ← verify: import 无报错
- [ ] S3: douyin — 用百度 site:douyin.com（同 F004 模式），写 `channels/douyin/search.py` + SKILL.md ← verify: import 无报错
- [ ] S4: producthunt, g2, linkedin — 暂无更好方案，创建 plugin 目录但 search.py 内部仍用 ddgs site:X ← verify: `load_channels()` 包含这 3 个
- [ ] S5: conference-talks — 复用 youtube 的搜索逻辑（import 或共享），SKILL.md 写不同的 query 策略（加 "conference talk" "keynote" 前缀）← verify: import 无报错
- [ ] S6: rss — 创建 plugin 目录，search.py 内部用 ddgs web + "RSS feed" ← verify: import 无报错
- [ ] S7: 写 `tests/test_channels_misc.py` ← verify: `pytest tests/test_channels_misc.py -v` 全过

### F006: 清理 search_runner.py — todo

F002-F005 完成后，search_runner.py 只剩 loader + dispatcher，不再有任何渠道实现代码。

#### Steps
- [ ] S1: 删除 search_runner.py 中所有渠道函数（search_ddgs_site, search_ddgs_web, search_gh_repos 等）和内联 CHANNEL_METHODS 字典。替换为 `from autosearch.v2.channels import load_channels as load_channel_plugins; CHANNEL_METHODS = load_channel_plugins()` ← verify: `pytest -x -q` 全过 + `cd ~/Projects/autosearch && python -c "from autosearch.v2.search_runner import CHANNEL_METHODS; print(f'{len(CHANNEL_METHODS)} channels'); assert len(CHANNEL_METHODS) >= 31, f'Expected >= 31, got {len(CHANNEL_METHODS)}'"` 渠道数 >= 31
- [ ] S2: search_runner.py 应该从 735 行缩减到 <150 行（只保留 CLI 入口 + run_single_query + normalize + dedup）← verify: `wc -l autosearch/v2/search_runner.py` < 150
- [ ] S3: 全量冒烟测试 — 用 `/autosearch "self-evolving AI agent frameworks"` 跑完整 7-phase pipeline ← verify: `tail -1 autosearch/v2/state/rubric-history.jsonl | python -c "import json,sys; d=json.load(sys.stdin); assert d['pass_rate'] >= 0.880, f'pass_rate {d[\"pass_rate\"]} < 0.880'"` pass rate >= 0.880

### F007: pipeline 验证 — todo

跑完整 pipeline，对比 channel plugin 前后质量。

#### Steps
- [ ] S1: 用 "self-evolving AI agent frameworks"（有基线数据，当前 0.880）跑完整 7-phase pipeline ← verify: `tail -1 autosearch/v2/state/rubric-history.jsonl | python3 -c "import json,sys; d=json.load(sys.stdin); print(f'pass_rate={d[\"pass_rate\"]}, failed={d.get(\"channels_failed\",[])}'); assert d['pass_rate'] >= 0.880"` pass rate >= 0.880
- [ ] S2: 重点对比中文渠道（zhihu, csdn 等）— 百度 vs ddgs 的结果数量和质量差异 ← verify: `channels_failed` 列表中中文渠道数 < 4（之前 reddit/zhihu/producthunt/papers-with-code 共 4 个失败）
- [ ] S3: 记录结果到 `rubric-history.jsonl` 和 `patterns-v2.jsonl` ← verify: `wc -l` 比之前各多至少 1 行

## 依赖关系

```
F001 (loader 基础设施)
  ├── F002 (搬家，depends F001)
  ├── F003 (抄 SearXNG，depends F001)
  ├── F004 (百度引擎，depends F001)
  └── F005 (其他渠道，depends F001)
        └── F006 (清理，depends F002+F003+F004+F005)
              └── F007 (验证，depends F006)
```

## 渠道完整映射表

| # | 渠道 | 分组 | 来源 | 需要 API key |
|---|------|------|------|-------------|
| 1 | web-ddgs | F002 搬家 | 现有代码 | 否 |
| 2 | github-repos | F002 搬家 | 现有代码（gh CLI） | 否 |
| 3 | github-issues | F002 搬家 | 现有代码（gh CLI） | 否 |
| 4 | hn | F002 搬家 | 现有代码（Algolia） | 否 |
| 5 | semantic-scholar | F002 搬家 | 现有代码 | 否 |
| 6 | citation-graph | F002 搬家 | 现有代码 | 否 |
| 7 | arxiv | F002 搬家 | 现有代码 + papers-with-code 合并 | 否 |
| 8 | bilibili | F003 SearXNG | `searx/engines/bilibili.py` | 否 |
| 9 | stackoverflow | F003 SearXNG | `searx/engines/stackexchange.py` | 否 |
| 10 | reddit | F003 SearXNG | `searx/engines/reddit.py` | 否 |
| 11 | google-scholar | F003 SearXNG | `searx/engines/google_scholar.py` | 否 |
| 12 | youtube | F003 SearXNG | `searx/engines/youtube_noapi.py` | 否 |
| 13 | wechat | F003 SearXNG | `searx/engines/sogou_wechat.py` | 否 |
| 14 | npm-pypi | F003 SearXNG | `searx/engines/npm.py` + `pypi.py` | 否 |
| 15 | zhihu | F004 百度 | SearXNG `baidu.py` + site:zhihu.com | 否 |
| 16 | csdn | F004 百度 | SearXNG `baidu.py` + site:csdn.net | 否 |
| 17 | juejin | F004 百度 | SearXNG `baidu.py` + site:juejin.cn | 否 |
| 18 | 36kr | F004 百度 | SearXNG `baidu.py` + site:36kr.com | 否 |
| 19 | infoq-cn | F004 百度 | SearXNG `baidu.py` + site:infoq.cn | 否 |
| 20 | weibo | F004 百度 | SearXNG `baidu.py` + site:weibo.com | 否 |
| 21 | xueqiu | F004 百度 | SearXNG `baidu.py` + site:xueqiu.com | 否 |
| 22 | xiaoyuzhou | F004 百度 | SearXNG `baidu.py` + site:xiaoyuzhoufm.com | 否 |
| 23 | xiaohongshu | F004 百度 | SearXNG `baidu.py` + site:xiaohongshu.com | 否 |
| 24 | crunchbase | F005 其他 | swirl-search | 否 |
| 25 | devto | F005 其他 | dev.to Forem API | 否 |
| 26 | producthunt | F005 保留 ddgs | ddgs site:producthunt.com | 否 |
| 27 | g2 | F005 保留 ddgs | ddgs site:g2.com | 否 |
| 28 | linkedin | F005 保留 ddgs | ddgs site:linkedin.com | 否 |
| 29 | douyin | F005 其他 | SearXNG `baidu.py` + site:douyin.com | 否 |
| 30 | conference-talks | F005 特殊 | 复用 youtube search.py | 否 |
| 31 | rss | F005 特殊 | ddgs web + "RSS feed" | 否 |

总计 31 个渠道目录（papers-with-code 合并到 arxiv 作为别名）。

## Decision Log
- 2026-04-01: 渠道架构选型 — 采用 Claude Code plugin 模式（目录约定发现），每个渠道 = SKILL.md（策略）+ search.py（执行）。拒绝纯 markdown skill 方案（搜索是确定性 HTTP 请求，不适合 LLM 判断）。
- 2026-04-01: 中文渠道策略 — ddgs 不索引中文网站导致失败，换百度 site:X。SearXNG 有现成 baidu.py 可提取。
- 2026-04-01: 保留 ddgs 的 3 个渠道（producthunt, g2, linkedin）— 无免费 API 替代方案，先保持现状，后续发现更好方案再替换。
- 2026-04-01: 通用百度搜索函数放 `channels/_engines/baidu.py`（下划线前缀 = 共享引擎，不是独立渠道）。

## Review Fixes (2026-04-01, code-architect review)
- 修复：F001 S1 loader 跳过 `_` 前缀目录（`_engines/` 是共享引擎不是渠道）
- 修复：F001 S3 重命名现有 `load_channels()` 为 `load_channel_config()` 避免命名冲突
- 修复：F002 S1 arxiv 加 aliases 字段，S2 验证 papers-with-code 别名生效
- 修复：F002-F005 所有删除步骤标注 depends F001 S3
- 修复：F003 S1 verify 改为具体的 import 命令
- 修复：F004 S1 verify 改为 import 检查（不依赖网络），实际网络测试移到 S6
- 修复：F005 补上遗漏的 douyin 渠道
- 修复：F006 S1 加渠道数量断言（>= 31）
- 修复：F006 S3 / F007 S1 加具体的 pipeline 调用命令和 pass_rate 校验命令
- 渠道总数从 30 修正为 31

## Open Questions
- 百度搜索是否有反爬限制（验证码、频率限制）？F004 S6 实际调用时验证。
- conference-talks 是否该和 youtube 合并成一个渠道？还是保持独立更好？（当前方案：独立目录，共享 search 逻辑）
