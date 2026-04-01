# AutoSearch v3.1 — Python 搜索执行器 + AVO 进化架构

## Goal

搜索执行从 Claude tool calls 迁移到 Python 并行执行器。速度 9min → 3min，token 省 70-80%，搜索成本 $0。AVO 全部能力保留，增加用户反馈驱动进化。

## 架构

```
┌─────────────────────────────────────────────────────────────────┐
│  Claude（大脑）                                                  │
│  ┌───────────────────────────────────────────────────────────┐  │
│  │ Phase 1: 决策                                             │  │
│  │   systematic-recall → select-channels → gene-query        │  │
│  │   输出: queries.json（搜什么 + 去哪搜）                    │  │
│  └───────────────────────────────────────────────────────────┘  │
│                          │                                      │
│                          ▼                                      │
│  ┌───────────────────────────────────────────────────────────┐  │
│  │ Bash: python search_runner.py queries.json                │  │
│  │   → 并行搜索所有渠道（3-5 秒）                             │  │
│  │   → 返回 results.jsonl（干净、去重、带日期）               │  │
│  └───────────────────────────────────────────────────────────┘  │
│                          │                                      │
│  ┌───────────────────────────────────────────────────────────┐  │
│  │ Phase 2: 评估 + 综合                                      │  │
│  │   Claude 读 results.jsonl → 判断 + 综合 → 交付            │  │
│  └───────────────────────────────────────────────────────────┘  │
│                          │                                      │
│  ┌───────────────────────────────────────────────────────────┐  │
│  │ Phase 3: AVO 自动进化（每次搜索后）                        │  │
│  │   打分 → 记 patterns → 更新 channel-scores → 改 skill     │  │
│  └───────────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────────┘
```

## AVO 修改权限

```
AVO 能修改：
├── 所有 mutable skill 文件（60+）
├── channels.json — 启用/禁用/新增渠道
├── patterns-v2.jsonl — 搜索经验
├── channel-scores.jsonl — 渠道效能
├── knowledge-maps/ — 知识积累
├── config.json — 参数
└── 可以创建新 skill 文件 + 新渠道

AVO 不能碰：
├── search_runner.py — 执行引擎
├── judge.py — 评分
├── PROTOCOL.md
└── 5 个 meta-skills
```

---

## F001: search_runner.py — 并行搜索执行器 — todo

Python 脚本，Claude 调一次 Bash，返回所有结果。

### 设计

```
输入: queries.json
[
  {"channel": "zhihu", "query": "自进化 AI agent 框架", "max_results": 10},
  {"channel": "github", "query": "self-evolving agent", "sort": "stars", "max_results": 20},
  {"channel": "producthunt", "query": "AI agent 2026", "max_results": 10},
  ...
]

输出: stdout，每行一条 JSONL（canonical schema）
{"url":"...","title":"...","snippet":"...","source":"zhihu","query":"...","metadata":{...}}

退出码: 0 成功，1 部分失败（stderr 报错），2 全部失败
```

### 搜索方法（per channel）

| 方法 | 渠道 | 实现 |
|------|------|------|
| `site_search` | zhihu, csdn, juejin, 36kr, infoq-cn, stackoverflow, devto, producthunt, crunchbase, g2, papers-with-code, google-scholar, linkedin, weibo, xueqiu, bilibili, xiaohongshu, wechat, conference-talks, xiaoyuzhou | ddgs.text(f"site:{site} {query}") |
| `ddgs_web` | ddgs 通用搜索 | ddgs.text(query) |
| `gh_cli` | github-repos, github-issues, github-code | subprocess: gh search repos/issues/code |
| `semantic_scholar` | citation-graph, author-track | HTTP GET to api.semanticscholar.org |
| `hn_api` | hackernews | HTTP GET to hn.algolia.com/api |

### 关键特性

- **asyncio 真并行**: 所有渠道同时搜索
- **超时保护**: 每个渠道 15 秒超时，超时的跳过不阻塞
- **结果标准化**: 在 Python 内完成 URL 标准化 + 去重
- **日期提取**: 从 snippet/URL/API 字段提取日期，写入 metadata
- **错误隔离**: 一个渠道挂了不影响其他渠道
- **读 channels.json**: 从配置读渠道信息，AVO 可动态修改

#### Steps

- [ ] S1: 写 search_runner.py 核心框架 — asyncio 并行 + CLI 入口 + JSONL 输出 ← verify: `python search_runner.py '[]'` 返回空，退出码 0

- [ ] S2: 实现 site_search 方法 — 用 ddgs 包搜 site:xxx.com ← verify: `python search_runner.py '[{"channel":"zhihu","query":"AI agent"}]'` 返回 JSONL

- [ ] S3: 实现 gh_cli 方法 — subprocess 调 gh search ← verify: github 渠道返回 repos with stars

- [ ] S4: 实现 semantic_scholar 方法 — HTTP GET ← verify: citation-graph 渠道返回论文

- [ ] S5: 实现 hn_api 方法 — HTTP GET ← verify: hackernews 渠道返回帖子

- [ ] S6: 结果标准化 + URL 去重 + 日期提取 — 内置在每个方法的返回处理中 ← verify: 输出符合 canonical schema，有 published_at 字段

- [ ] S7: 错误处理 + 超时 — 每渠道 15s timeout，失败写 stderr 不阻断 ← verify: 一个渠道挂了其他正常返回

## F002: channels.json — 渠道配置 — todo

AVO 可读写的渠道注册表。search_runner.py 从这里读渠道列表。

#### Steps

- [ ] S1: 写 channels.json，包含所有 42 个渠道 ← verify: 每个渠道有 name, method, enabled, site(如适用), lang(如适用), description

- [ ] S2: search_runner.py 启动时读 channels.json，只搜 enabled=true 且在 queries.json 里的渠道 ← verify: 禁用一个渠道后不会搜它

- [ ] S3: 写文档：AVO 如何修改 channels.json（在 consult-reference.md 或新 skill 里说明）← verify: 有明确指导

## F003: pipeline-flow.md 更新 — todo

改 Phase 2 从"Claude 调 WebSearch"变成"Claude 调 search_runner.py"。

#### Steps

- [ ] S1: 更新 pipeline-flow.md Phase 2 — Claude 生成 queries.json → Bash 调 search_runner.py → 读结果 ← verify: 流程清晰，5 步不变

- [ ] S2: 更新 gene-query.md — 输出格式改为 queries.json 兼容格式 ← verify: gene-query 输出可直接传给 search_runner.py

- [ ] S3: 简化 Phase 3 — normalize 和 extract-dates 在 Python 已做完，Claude 只需做 llm-evaluate ← verify: 不重复做已完成的工作

## F004: AVO 自动进化 — todo

每次 /autosearch 结束后自动跑一步进化。用户无感知。

#### Steps

- [ ] S1: 新建 auto-evolve.md skill — 定义自动进化流程：打分 → 找弱点 → 决定改什么 → 改 → 验证 ← verify: 流程完整，包含 commit/revert 逻辑

- [ ] S2: 更新 pipeline-flow.md Phase 5 — 加"自动调用 auto-evolve.md" ← verify: Phase 5 包含进化步骤

- [ ] S3: 进化目标定义 — 增量发现率为主指标，judge.py 为辅 ← verify: auto-evolve.md 有明确的指标定义

- [ ] S4: AVO 可操作范围文档 — 明确列出 AVO 能改什么不能改什么 ← verify: 在 CLAUDE.md 或 auto-evolve.md 中有完整列表

## F005: 用户反馈循环 — todo

用户反馈直接驱动 AVO 进化方向。

#### Steps

- [ ] S1: 交付后追加一句："如果结果有缺失或不满意，告诉我哪里不够好，AutoSearch 会学习改进。" ← verify: 在 synthesize-knowledge.md 或 pipeline-flow.md 交付段

- [ ] S2: 收到用户反馈时写 pattern — type: "user-feedback", content: 用户原话, dimension: 推断的弱项 ← verify: feedback 被记录到 patterns-v2.jsonl

- [ ] S3: auto-evolve.md 优先处理 user-feedback 类型的 pattern（比 judge 数据优先级更高）← verify: 逻辑明确

## F006: 端到端验证 — todo

用 search_runner.py 重跑 3 个 topic 的对比测试。

#### Steps

- [ ] S1: Topic 1 v3.1 (search_runner) vs v3.0 (WebSearch) vs Native Claude ← verify: 速度、URLs、quality 三维对比

- [ ] S2: Topic 2 同上 ← verify: 数据一致性

- [ ] S3: Topic 3 同上 ← verify: 数据一致性

- [ ] S4: 汇总报告 — 速度提升？token 消耗减少？结果质量变化？← verify: 有量化数据

## F007: AVO 连续进化测试 — todo

让 AVO 自动跑 10 次进化迭代，观察轨迹。

#### Steps

- [ ] S1: 跑 10 次 /autosearch 不同 topic，每次结束后 auto-evolve 自动进化一步 ← verify: 10 次迭代数据记录

- [ ] S2: 画进化轨迹 — patterns 数量增长、channel-scores 变化、skill 修改历史 ← verify: 数据可视化或表格

- [ ] S3: 对比第 1 次和第 10 次的搜索质量 — 增量发现率是否提升？← verify: 有量化对比

## F008: 文档收尾 — todo

#### Steps
- [ ] S1: CHANGELOG.md — v3.1 entry
- [ ] S2: HANDOFF.md — search_runner.py 使用说明
- [ ] S3: CLAUDE.md — AVO 修改权限更新
- [ ] S4: AIMD 经验笔记

---

## Decision Log

- 2026-03-31: 搜索执行从 Claude WebSearch 迁移到 Python search_runner.py。原因：速度（200s→5s）、成本（8 次 tool call→1 次）、搜索免费（ddgs）。
- 2026-03-31: AVO 全部修改能力保留。Python 脚本是"快递员"，AVO 是"决策者"。AVO 可改 skill、channels.json、patterns、config。不能改 Python 代码。
- 2026-03-31: channels.json 是 AVO 安装/卸载渠道的接口。AVO 写 channels.json + 创建 skill 文件 = 安装新渠道。
- 2026-03-31: 用户反馈驱动 > judge.py 分数驱动。user-feedback 类 pattern 优先级最高。
- 2026-03-31: 每次 /autosearch 结束后自动进化一步，不需要手动触发。
- 2026-03-31: 参考 NVIDIA AVO 论文：关键差距是迭代量不够（500+ vs 5），不是设计问题。自动进化解决这个 gap。

## 预期成果

| 指标 | v3.0 (当前) | v3.1 (预期) |
|------|-----------|------------|
| 搜索速度 | ~200s | **~5s** |
| 总时间 | 9 min | **2-3 min** |
| Token 消耗 | ~100K | **~30K** |
| 搜索成本 | WebSearch 内部成本 | **$0 (ddgs 免费)** |
| AVO 迭代 | 手动触发，3-5 次 | **自动触发，每次 /autosearch 一步** |
| 用户反馈 | 无 | **记录 → 驱动进化** |
| 渠道管理 | 固定 42 个 skill | **AVO 可动态启用/禁用/新增** |

## 执行顺序

```
F001 (search_runner.py) → F002 (channels.json) → F003 (pipeline 更新)
                                                       ↓
F004 (AVO 自动进化) + F005 (用户反馈) → F006 (端到端验证) → F007 (连续进化) → F008 (文档)
```

关键路径：F001 → F003 → F006。search_runner.py 写好、pipeline 接上、跑一轮验证就能看到效果。

## 依赖

- Python 3.11+（已有，judge.py 要求）
- ddgs 包（AutoSearch V1 已用过）
- httpx 或 aiohttp（异步 HTTP）
- gh CLI（已有）

零新的外部服务依赖。全部本地执行。
