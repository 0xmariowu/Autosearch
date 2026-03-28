# AutoSearch v2 — Skills-Native Self-Evolving Search

## Goal

从零重建 AutoSearch。核心理念：一切都是 Skills，AVO 自进化驱动架构本身。用户给模糊输入，系统自主搜索、学习、进化、交付满意结果。不是在老代码上改——是新的架构、新的项目目录。

## 产品定义

**一句话**：一个自我进化的搜索研究 agent，通过开放可插拔的 skills 生态和 AVO 循环，把模糊意图变成满意的交付。

**核心价值**：不是搜索结果（谁都能搜），是架构——开放 skills + 自进化机制。

**三个入口**：
1. 斜杠命令：`/autosearch "找 AI agent 项目"` → 执行 → 交付
2. 对话自然调用：Claude 在编码中判断需要搜索 → 自动调用
3. MCP / API：其他 agent 或 cron 调用

## 设计哲学

五条来自 prior art 的核心原则：

1. **"The harness IS the algorithm"**（Karpathy/autoresearch）— PROTOCOL.md 不是文档，是系统本身。
2. **"Zero-code self-evolution"**（Claude-Diary）— Reflect→Rules 循环，不需要代码变更来改进行为。
3. **"Description-based dispatch"**（Superpowers）— Agent 读 skill 描述自动决定用哪个，不需要路由代码。
4. **"Agent as variation operator"**（NVIDIA AVO 论文 §3）— Agent 不是在 pipeline 里生成候选。Agent 就是 variation operator：自主 plan→implement→test→debug→commit/discard。
5. **"Adapt to your workflows"**（pi-mono）— 用户通过 skills 定制行为，不需要 fork 或改内部代码。Skills 可通过包管理分享。

## AVO 形式化（论文 §3.1 映射到搜索）

```
Vary(P_t) = Agent(P_t, K, f)

P_t = 搜索策略 lineage：(config, patterns, skills) 的版本历史
K   = 知识库：现有 skills + patterns.jsonl + 搜索平台文档
f   = judge.py：固定的多维评分函数（唯一不可改的合同）
```

AVO 论文的关键行为，映射到搜索：

| AVO 论文行为 | 在 AutoSearch 中的对应 |
|-------------|---------------------|
| 咨询 prior implementations | 读 patterns.jsonl + worklog.jsonl 历史 |
| 读 domain knowledge (K) | 读 platform skills + strategy skills |
| 实现修改 | 改 config.json / 改 strategy skill / 创建新 platform skill |
| 测试修改 | 跑一轮搜索，用 judge.py 评分 |
| 诊断失败 | 分析为什么分数没提升（edit-evaluate-diagnose cycle, §3.2） |
| 修复并重试 | 调整修改，再跑一轮 |
| Commit / discard | 好 → git commit；差 → git revert |
| Self-supervision (§3.3) | stuck.md：stagnation → redirect strategy |

## 约束栈

五个不可违反的约束（去掉任何一个系统会变混乱）：

1. **f 不可改** — `judge.py` 是唯一代码文件，确定性评分。AI 不能自评。（AVO 论文：f 是固定合同）
2. **搜索免费** — 所有 platform skill 只用免费资源（gh CLI, ddgs, curl）。不引入付费 API 依赖。
3. **Skill 格式固定** — 遵循 skill-spec.md 规范（参考 pi-mono 的 Agent Skills standard）。AVO 可以创建/修改 skill 内容，不能改格式。
4. **状态 append-only** — worklog.jsonl 和 patterns.jsonl 只追加。Skill/config 变更通过 git commit，失败 git revert（保留失败历史供 AVO 学习）。
5. **模型路由可进化** — 初始全 Haiku，AVO 可升级特定阶段到 Sonnet（或让 AVO 自己实验最优路由）。

## 架构

```
autosearch/v2/
├── PROTOCOL.md                  ← 核心协议（= program.md）
├── skill-spec.md                ← Skill 格式规范（参考 agentskills.io）
│
├── skills/
│   ├── platforms/               ← 搜索能力（AVO 可增删改）
│   │   ├── github.md
│   │   ├── web-ddgs.md
│   │   ├── reddit.md
│   │   ├── hackernews.md
│   │   └── arxiv.md
│   │
│   ├── strategies/              ← 搜索方法（AVO 可进化）
│   │   ├── query-expand.md      ← 模糊输入 → 多 query
│   │   ├── score.md             ← 结果打分规则
│   │   ├── deduplicate.md       ← 去重策略
│   │   └── synthesize.md        ← 合成交付物
│   │
│   └── avo/                     ← 自进化协议
│       ├── loop.md              ← AVO 主循环（plan→search→score→diagnose→evolve）
│       ├── reflect.md           ← 单轮反思
│       ├── evolve.md            ← 跨轮策略进化（三层）
│       ├── create-skill.md      ← 创建新 skill（能力进化）
│       ├── diagnose.md          ← 诊断失败原因（edit-evaluate-diagnose, §3.2）
│       └── stuck.md             ← Self-supervision（stagnation → redirect, §3.3）
│
├── state/
│   ├── config.json              ← 当前策略参数（AVO 进化对象）
│   ├── patterns.jsonl           ← 跨 session 学习（append-only）
│   └── worklog.jsonl            ← 运行记录 + 反思记录（Driveline 设计）
│
├── evidence/                    ← 搜索结果（JSONL per run）
├── delivery/                    ← 最终交付物
│
└── judge.py                     ← 唯一代码：确定性多维评分（~100 行）
```

## 成本模型

```
搜索 API：$0（全免费）
  GitHub    → gh CLI（free, 5000 req/hr authenticated）
  DuckDuckGo → ddgs package（free）
  Reddit    → public JSON API（free, 100 req/min）
  HN        → Algolia API（free, 10000 req/hr）
  Arxiv     → public API（free, 3 req/sec）

Agent 模型（初始 config，AVO 可自主调整）：
  搜索执行 → Haiku     ~$0.001/轮
  反思/进化 → Haiku     ~$0.001/轮（初始保守，AVO 可升到 Sonnet）
  创建 skill → Sonnet    ~$0.01/次（创建新能力需要更强推理）

一次完整搜索任务（5 代 AVO）：~$0.01-0.10
对比：Perplexity Pro $20/月，Tavily API $100/月起
```

---

## F001: 核心协议 + Skill 规范 — todo

PROTOCOL.md 和 skill-spec.md。这两个文件定义整个系统——不是文档，是系统本身。

### 背景

PROTOCOL.md 对应 autoresearch 的 program.md，是 Agent 的操作系统。skill-spec.md 对应 pi-mono 的 Agent Skills standard，定义 skill 格式让 AVO 创建的新 skill 和手写的一样可用。

### Steps

- [ ] S1: 写 `skill-spec.md` — Skill 格式规范。参考 pi-mono 的 SKILL.md 结构 + agentskills.io 标准。定义 frontmatter（name, type, version, requires, triggers, cost）+ 正文结构（When to use, Execute, Parse, Score hints, Known limitations）。AVO 按这个格式创建新 skill。 ← verify: 格式清晰，字段完整，附带示例
- [ ] S2: 写 `PROTOCOL.md` — 核心协议。定义完整循环：

  **AVO 主循环**（论文 §3 映射）：
  ```
  repeat:
    1. PLAN     — 读 config + patterns + skills，决定搜什么、用哪些平台
    2. SEARCH   — 按 platform skills 执行（bash 调 API）
    3. SCORE    — 按 score.md 规则 + judge.py 确定性评分
    4. DIAGNOSE — 如果分数没提升，分析 WHY（论文 §3.2 edit-evaluate-diagnose）
    5. EVOLVE   — 修改 config / strategy / 创建新 skill
    6. RECORD   — 写 worklog.jsonl + patterns.jsonl
  until: judge 分数达到交付标准 or 预算用完 or stuck 触发
  ```

  还包含：角色定义、输入处理（模糊→结构化）、状态恢复（worklog crash recovery，Driveline 设计）、模型路由（初始全 Haiku，AVO 可调）、交付标准。目标 ~300 行。 ← verify: 协议覆盖完整 AVO 循环 + crash 恢复 + 论文 §3.2 diagnose + §3.3 stuck

- [ ] S3: 写 `state/config.json` 初始版 — 策略参数：platform_weights（各平台权重）、query_strategy（展开参数）、scoring（打分阈值）、model_routing（初始全 haiku）、avo_params（反思阈值、stuck 检测窗口、进化预算）。 ← verify: JSON 合法，所有字段有合理默认值

- [ ] S4: 创建目录结构 — `state/worklog.jsonl`（空）、`state/patterns.jsonl`（空）、`evidence/`、`delivery/`、`skills/platforms/`、`skills/strategies/`、`skills/avo/` ← verify: 目录结构完整

---

## F002: 5 个 Platform Skills — todo

每个平台一个 skill。纯 Markdown + bash 命令。零 Python。AVO 未来可修改或创建新的。

### 背景

Platform skills 是系统的"手脚"。每个 skill 按 skill-spec.md 格式，告诉 Agent 怎么搜一个平台：命令、解析方式、质量信号。这些是 AVO 能力进化的起始集。

### Steps

- [ ] S1: 写 `skills/platforms/github.md` — 搜 GitHub repos + issues。`gh search repos` + `gh search issues`。JSON 解析。Score hints: stars, recency, has-description, language match。`requires: [gh]`。 ← verify: 手动执行 skill 命令拿到结果
- [ ] S2: 写 `skills/platforms/web-ddgs.md` — DuckDuckGo 搜通用网页。`python3 -c "from ddgs import DDGS; ..."` 一行命令。Score hints: domain authority, title match。`requires: [ddgs]`。 ← verify: 命令执行返回结果
- [ ] S3: 写 `skills/platforms/reddit.md` — Reddit public JSON API（`curl`）。Score hints: score, num_comments, subreddit relevance。`requires: [curl]`。 ← verify: curl 返回 JSON
- [ ] S4: 写 `skills/platforms/hackernews.md` — HN Algolia API（`curl`）。Score hints: points, num_comments, recency。`requires: [curl]`。 ← verify: curl 返回 JSON
- [ ] S5: 写 `skills/platforms/arxiv.md` — arxiv API（`curl`）。XML/Atom 解析。Score hints: recency, category match。`requires: [curl]`。 ← verify: curl 返回结果

---

## F003: 4 个 Strategy Skills — todo

搜索方法论。Agent 按这些 skill 做决策。AVO 策略进化的主要对象。

### Steps

- [ ] S1: 写 `skills/strategies/query-expand.md` — 模糊输入 → 5-15 个精确 query。方法：同义词展开、角色视角（开发者/研究者/用户各出 query）、否定限定（排除噪音）。含示例。 ← verify: 给 "AI agent 项目" 展开出 ≥5 个不同 query
- [ ] S2: 写 `skills/strategies/score.md` — 多维打分规则。维度：relevance、authority、freshness、engagement、uniqueness。每个维度的计算方法和权重。与 judge.py 的维度对齐。 ← verify: 规则明确可执行，维度和 judge.py 一致
- [ ] S3: 写 `skills/strategies/deduplicate.md` — URL 归一化（去 tracking params、www、trailing slash）、标题 Jaccard > 0.7 = 疑似重复、跨平台同源检测。 ← verify: 规则明确可执行
- [ ] S4: 写 `skills/strategies/synthesize.md` — 按用户意图选模板：比较型（对比表）、教程型（步骤列表）、调研型（分类+证据+结论）、发现型（列表+亮点）。输出到 `delivery/`。 ← verify: 每种模板有具体结构

---

## F004: Judge — 唯一代码 — todo

确定性评分函数。f 是固定合同，AI 不能改。

### 背景

AVO 论文 §3.1：f 评估 candidate 沿多个维度，correctness check 失败 → 零分。搜索版：无结果 → 零分，单源 → diversity 低分。judge.py 提供确定性评分，AVO 靠这个分数决定 commit/discard。

### Steps

- [ ] S1: 写 `judge.py` — 输入：evidence JSONL 文件路径。输出：JSON 分数到 stdout。维度：
  - `quantity`: unique URLs / target count（比例，cap 1.0）
  - `diversity`: 源平台 Simpson diversity index
  - `relevance`: query term 在 title/snippet 中覆盖率
  - `freshness`: 近 6 月内容占比
  - `efficiency`: 结果数 / 查询数
  - `total`: 加权平均

  CLI：`python3 judge.py <evidence-file> [--target N]`。返回码 0=成功 1=错误。约 100 行。 ← verify: `python3 judge.py evidence/test.jsonl` 输出合法 JSON

- [ ] S2: 写 `tests/test_judge.py` — 边界测试：空输入→全零、单条→正确计算、100 条多源→diversity 高、全同源→diversity 低。 ← verify: 测试全过

---

## F005: AVO 自进化 Skills — todo

系统的灵魂。实现 AVO 论文 §3 的完整行为，用 skills 而非代码。

### 背景

AVO 不是"调参数"。它是一个完整的 agent 循环：plan→implement→test→diagnose→commit/discard。参考 AVO 论文 §3.2 的 edit-evaluate-diagnose cycle 和 §3.3 的 self-supervision mechanism。结合 Claude-Diary 的 Reflect→Rules 和 Driveline 的 worklog。

### Steps

- [ ] S1: 写 `skills/avo/loop.md` — AVO 主循环协议。定义一代（generation）的完整执行流程：
  1. **Select**：从 worklog.jsonl 找 best config（或用当前）
  2. **Plan**：读 patterns + 分析 weakest dimension → 决定改什么
  3. **Implement**：改 config.json 或 strategy skill 或创建新 platform skill
  4. **Test**：执行一轮搜索，调 judge.py 评分
  5. **Diagnose**（§3.2）：如果分数没提升 → 读 diagnose.md 分析 WHY → 修复 → 重试（最多 2 次）
  6. **Commit/Discard**：好 → git commit + 追加 worklog.jsonl；差 → git revert
  7. **Supervise**（§3.3）：检查 stagnation → 如果触发 → 读 stuck.md 切策略

  ← verify: 协议完整映射 AVO 论文 §3.1-3.3，每步有明确的输入/输出/判断条件

- [ ] S2: 写 `skills/avo/reflect.md` — 单轮反思。每轮搜索后执行。分析：哪些 query 命中率高、哪个平台质量好、打分是否合理、有没有被遗漏的数据源。输出：反思记录追加到 worklog.jsonl（`type: "reflection"`）。 ← verify: 步骤完整，输出格式明确

- [ ] S3: 写 `skills/avo/evolve.md` — 跨轮策略进化。三层：
  - **参数进化**：改 config.json 权重/阈值（每轮可做）
  - **策略进化**：改 strategies/*.md 规则（连续 3 轮参数进化无效时）
  - **能力进化**：创建新 platforms/*.md（发现新数据源时，读 create-skill.md）

  每次修改用 git commit。失败 git revert（保留历史供学习，uditgoenka 设计）。 ← verify: 三层触发条件和执行步骤明确

- [ ] S4: 写 `skills/avo/diagnose.md` — 诊断失败（论文 §3.2）。当 judge 分数没提升时：
  1. 对比 before/after 的各维度分数
  2. 找到 weakest 或 regression 的维度
  3. 分析可能原因（query 太窄？平台选错？打分规则不合适？）
  4. 提出修复方案
  5. 执行修复，重新测试

  最多重试 2 次（论文 §3.2 的 max_retries）。 ← verify: 诊断流程明确，有退出条件

- [ ] S5: 写 `skills/avo/create-skill.md` — 创建新 skill。触发条件：evidence 中 >20% URL 来自未覆盖域名、或 diagnose 建议需要新数据源。步骤：确认平台有免费 API → 按 skill-spec.md 格式写 → 测试验证 → git commit。 ← verify: 流程明确，含测试步骤

- [ ] S6: 写 `skills/avo/stuck.md` — Self-supervision（论文 §3.3）。触发条件：连续 3 代 judge total 分数 flat（max ≤ min × 1.01）或递减。策略切换选项：
  1. 换平台权重（diversity 维度差时）
  2. 换 query 展开方法（relevance 差时）
  3. 升级模型（Haiku→Sonnet，efficiency 差时）
  4. 创建新 platform skill（quantity 差时）
  5. 请求用户澄清目标（所有维度都差时）

  参考 uditgoenka 的连续 5 次 discard 切策略。 ← verify: 多种脱困策略，有明确触发阈值

---

## F006: 端到端验证 — todo

证明整个系统能跑。从模糊输入到交付，完整走一遍。

### Steps

- [ ] S1: 手动执行一次完整 AVO 循环 — 任务："找 10 个 2025 年后的 AI agent 开源框架"。按 PROTOCOL.md 走完整循环：PLAN → SEARCH → SCORE → DIAGNOSE → EVOLVE → RECORD。记录每步结果。 ← verify: evidence/ 有结果，judge.py 给出分数，worklog.jsonl 有完整记录

- [ ] S2: 验证 AVO 参数进化 — 第一轮后执行 evolve.md。验证 config.json 被修改（比如某平台权重变了）。 ← verify: config.json 有 git diff

- [ ] S3: 跑 3 代 AVO 循环 — 连续 3 轮搜索+反思+进化。验证：
  (a) judge 分数有变化趋势
  (b) config.json 累计变更合理
  (c) patterns.jsonl 有新条目
  ← verify: worklog.jsonl 有 3 轮数据，分数可追溯

- [ ] S4: 验证 diagnose — 人为制造一次"差结果"（比如只搜一个平台）。验证 diagnose.md 被触发，分析出 diversity 维度差，建议加平台。 ← verify: worklog 记录 diagnose event

- [ ] S5: 验证 stuck detection — 把 config 的 platform_weights 全设为低值制造 stagnation。验证 stuck.md 触发策略切换。 ← verify: worklog 记录 stuck + strategy switch

- [ ] S6: 验证交付 — 执行 synthesize.md，从 evidence 生成交付物。 ← verify: delivery/ 有可读报告

---

## F007: 产品化入口 — todo

三个入口，一套 skills。

### Steps

- [ ] S1: 写 Claude Code skill — 注册为 `/autosearch` 斜杠命令。加载 PROTOCOL.md 执行。参数：task（搜索目标）、generations（AVO 轮数，默认 3）。 ← verify: `/autosearch "find AI agent repos"` 触发完整循环

- [ ] S2: 写 dispatch trigger — skill description 定义 trigger 词（search, find, research, discover, 调研, 搜索, 找）。对话中遇到时自动加载。参考 Superpowers 的 1% rule。 ← verify: 对话中"帮我找..."时自动触发

- [ ] S3: 写 MCP server — 薄壳。一个 tool：`autosearch_run(task_spec, generations)`。`asyncio.to_thread` 执行。 ← verify: MCP tool 可调用

- [ ] S4: 写 cron / schedule entry — 定期触发 AVO 进化。用 Claude Code schedule 或 launchd。 ← verify: 定时任务注册

---

## F008: 文档 + 迁移 — todo

### Steps

- [ ] S1: 更新 `CLAUDE.md` — v2 规则：judge.py 不可 AI 修改，skills 遵循 skill-spec.md，config/skill 变更通过 git commit ← verify: 规则写入
- [ ] S2: 更新 `CHANGELOG.md` ← verify: 条目存在
- [ ] S3: 写 `v2/README.md` — 架构图、快速开始、AVO 循环说明、和 v1 的关系 ← verify: 文件存在
- [ ] S4: 标记 v1 genome 计划为 completed ← verify: 文件移到 completed/

---

## Dependency Graph

```
F001 (Protocol + Spec) ──→ F002 (Platforms)  ──→ F006 (验证)
        │                       │                     │
        └──→ F003 (Strategies) ─┘                     │
        │                                             │
        └──→ F004 (Judge) ──→ F006                    │
        │                                             │
        └──→ F005 (AVO Skills) ──→ F006               │
                                                      ↓
                                               F007 (产品化)
                                                      │
                                                      ↓
                                               F008 (文档)
```

**推荐执行顺序**：
1. F001（协议 + 规范）
2. F002 + F003 + F004 并行（平台 / 策略 / 评分）
3. F005（AVO，依赖 F001）
4. F006（端到端验证）
5. F007（产品化入口）
6. F008（文档）

## 和 v1 的关系

| | v1（genome 架构） | v2（skills 架构） |
|---|---|---|
| 核心 | Python runtime 解释 JSON genome | PROTOCOL.md 协议驱动 Claude 执行 |
| 进化 | Python random mutation（vary.py） | Claude reasoning（AVO 论文 §3 完整映射） |
| 平台 | capabilities/*.py（40 Python 文件） | skills/platforms/*.md（5 Markdown 文件） |
| 评分 | lexical.py + 多处分散 | judge.py（100 行，唯一代码） |
| 总量 | ~7000 行 Python | ~100 行 Python + ~2500 行 Markdown |

v1 代码不删。v2/ 是独立目录。v1 的 patterns.jsonl 数据可作为 v2 种子。

## Decision Log

- 2026-03-28: AVO 论文 §3 的 Agent 形式化直接映射到搜索——P_t 是 skills+config 的 git 历史，K 是现有 skills + patterns，f 是 judge.py
- 2026-03-28: edit-evaluate-diagnose cycle（§3.2）加入 AVO skills — 不只是 try/discard，是分析 WHY 然后 repair。这是论文超越 autoresearch 的关键创新
- 2026-03-28: Self-supervision（§3.3）用 stuck.md 实现 — 连续 stagnation 自动 redirect，不需要人介入
- 2026-03-28: 参考 pi-mono 的 Agent Skills standard — skill 格式标准化，未来可通过包管理分享
- 2026-03-28: 模型路由初始全 Haiku，AVO 可自主调整 — 不预判什么阶段需要什么模型，让系统自己发现
- 2026-03-28: git commit/revert 管理 skill 变更（uditgoenka 设计）— revert 保留失败历史，AVO 可从失败学习
- 2026-03-28: v2 独立目录，不在 v1 上改 — clean break，验证后迁移

## Open Questions

- Q1: AVO 创建的新 skill 质量如何保证？create-skill.md 要求测试，但 Agent 可能写出看起来对但不工作的 skill。是否需要一个 skill validator？
- Q2: 多 session 并发写 state/ 文件如何处理？worklog.jsonl append 是原子的，但 config.json 全量覆写。
- Q3: delivery/ 输出格式标准化还是 synthesize.md 自由选择？
- Q4: 是否需要 meta-skill（类似 Superpowers 的 using-superpowers）在 session 开始注入上下文？
- Q5: 无人值守 AVO 进化是否安全？连续改坏了是否需要自动回滚上限？论文 §3.3 只检测 stagnation，不检测 regression。
- Q6: 是否参考 pi-mono 的 `pi install` 做 skill 包管理？让用户能安装第三方 platform skills？
