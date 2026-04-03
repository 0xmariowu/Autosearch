# AutoSearch v2.3 — Skills 大升级 + AVO 进化基建

## Goal

让 AutoSearch 通过 AVO 自我进化**大幅超越 native Claude 搜索能力**。两手抓：(1) 建参考库给 AVO 学习材料，(2) 写 solid 起始 skills 给 AVO 一个高起跑线。目标：10 个 session 后在所有维度超越 native Claude。

## 定位

AutoSearch 的价值不在单次搜索，在**累积进化**。native Claude 每次从零开始，AutoSearch 每次从上次终点开始。
- 单次搜索的差距靠 skills 质量弥补
- 多次搜索的领先靠 AVO 进化 + 数据累积实现
- 1,009 skills 参考库是 AVO 的教科书，不是我们手动抄的答案

## 验证数据

| 测试 | 结果 | 日期 |
|------|------|------|
| F006 搜索 pipeline | PASS_WITH_ISSUES (0.676) | 2026-03-31 |
| F007 AVO 进化 | PASS (6/6 checkpoints, 0.716→0.751) | 2026-03-31 |
| Skill decomposition | 16 projects, 1,009 skills | 2026-03-31 |
| Gap analysis | 25 clusters, 4 critical gaps | 2026-03-31 |

---

## Feature 清单

### F001: 建 skill 参考库 — todo

把 1,009 个 skills 结构化为 AVO 可查询的参考库。AVO 进化时查参考库找"别人怎么做的"，而不是从零猜。

**为什么是 P0**：没有参考库，AVO 只能 trial-and-error。有了参考库，AVO 变成 reference-guided evolution。学习效率天壤之别。

#### Steps

- [ ] S1: 定义参考库 schema ← verify: schema 覆盖 skill name, project, category, description, heuristics(list), failure_modes(list), unique_pattern, source_files

- [ ] S2: 用 Codex 批量把 16 个项目的 decomposition 结果转化为 structured JSONL。每个 skill 一行，带完整 heuristics。源数据在 /tmp/codex-skill-decomp/*.md + experience note ← verify: ≥900 条目（去除纯 UI/deployment 无关项后），每条都有 ≥2 heuristics

- [ ] S3: 建索引 — 按 capability cluster 分类标记（和 gap-analysis 的 25 个 cluster 对齐），方便 AVO grep ← verify: 每条有 cluster 字段，25 个 cluster 都有条目

- [ ] S4: 写入 autosearch/v2/state/skill-reference.jsonl ← verify: 文件存在，jq 可解析

- [ ] S5: 更新 create-skill.md（meta-skill 不能改内容，但可以在旁边放一个 mutable 的 consult-reference.md）— 新建 consult-reference.md skill，指导 AVO 在修改或创建 skill 时先查参考库 ← verify: skill 描述了查询流程（grep cluster → 读 entries → 提取 applicable heuristics → 融入修改）

### F002: 结构化 patterns.jsonl 格式 — todo

当前 patterns.jsonl 是自由文本，AVO 很难机器化利用。需要结构化让累积数据真正可用。

**为什么是 P0**：patterns 是 AVO 跨 session 学习的核心载体。格式不好 = 学不动。

#### Steps

- [ ] S1: 定义新 pattern schema ← verify: 字段包含 pattern_type(query/platform/skill/strategy), query_pattern(optional), platform(optional), dimension_affected, outcome(win/loss), delta(float), why(string), session_id, timestamp

- [ ] S2: 迁移现有 35 条 patterns 到新格式（保留原始内容在 old_text 字段，新字段从内容提取）← verify: 35 条全部迁移，原始文本保留

- [ ] S3: 更新 PROTOCOL.md §6 的 pattern 格式说明 —— 等等，PROTOCOL.md 不可改。改 extract-knowledge.md（mutable）来指导 pattern 写入格式 ← verify: extract-knowledge.md 有明确的 pattern 写入格式说明

### F003: 7 个新 skills — todo

新建 7 个 skill，每个从参考库提取最佳实践作为起始内容。AVO 以后可以进化它们。

**原则**：写 solid 但不 over-optimize。给 AVO 一个好起跑线，不是终点线。

#### Steps

- [ ] S1: normalize-results.md ← verify: 定义了 canonical evidence schema（url, title, snippet, source, query, metadata.{llm_relevant, llm_reason, published_at, updated_at, created_utc, stars, citations}），有跨平台去重规则（URL canonicalization + title similarity），有格式标准化示例

- [ ] S2: extract-dates.md ← verify: 覆盖 5 种日期来源（GitHub updatedAt, arXiv ID, URL path, snippet text, HTTP header），有优先级规则（structured > URL > text），输出 ISO 8601

- [ ] S3: assemble-context.md ← verify: 有 token budget 策略（按 relevance 排序截断），有去重规则（同一 URL 的多条结果合并），有来源归属保留规则

- [ ] S4: decompose-task.md ← verify: 有何时分解/何时不分解的判断规则，有子问题独立性检查，有结果合并策略，上限 5 个子问题

- [ ] S5: follow-links.md ← verify: 有 URL 评分规则（awesome-list/survey 高分），有深度限制（默认 1 跳），有 hostname 多样性规则

- [ ] S6: rerank-evidence.md ← verify: LLM-based ranking 为主（Claude 自己读结果排序），有明确排序标准（task relevance > evidence quality > source authority），有 top-K 选择指导

- [ ] S7: evaluate-delivery.md ← verify: 有 4 维自检（覆盖度、深度、可操作性、引用完整度），有 pass/fail 阈值，不合格时的修正策略

### F004: 扩展 4 个已有 skills — todo

#### Steps

- [ ] S1: fetch-webpage.md 重写 — 加 markdown 转换、blocked 检测、PDF 处理、fallback 策略 ← verify: 从参考库 crawl4ai + gpt-researcher + node-deepresearch 的 heuristics 体现在内容里

- [ ] S2: synthesize-knowledge.md 扩展 — 加引用管理（每个 claim 链接 source）、block-based delivery 结构（框架 → 证据 → 分析 → gaps）、gap 声明 ← verify: 引用规则明确，delivery 有结构模板

- [ ] S3: research-mode.md 扩展 — 加 scope 定义（in/out/done）、和 decompose-task 的协作规则 ← verify: 三个问题模板（what's in scope / what's out / what does done look like）

- [ ] S4: llm-evaluate.md 扩展 — 加结构化 gap detection（evidence vs rubric diff）、gap-based follow-up query 生成 ← verify: gap detection 有具体步骤（列 rubric dimensions → 检查 coverage → 输出 missing list）

### F005: 14 platform skills 统一升级 — todo

#### Steps

- [ ] S1: 定义 platform skill 标准化模板 — 3 个统一段落：Output Schema（和 normalize-results.md 对齐）、Date Extraction（和 extract-dates.md 对齐）、Source Tagging（judge.py diversity 用的 source 字段规范）← verify: 模板内容明确，可机械应用

- [ ] S2: Codex 批量应用模板到 14 个 platform skills（5 并行 × 3 批）。保留每个 skill 的独特内容（quality signals, known patterns, rate limits），只追加统一段落 ← verify: 14 个 skill 都有新段落，原有内容完整

### F006: 验证——F006-bis 搜索质量测试 — todo

用升级后的全套 skills 重跑同一个 query，三方对比。

#### Steps

- [ ] S1: 跑 AutoSearch v2.3（新 skills），query = "find open-source self-evolving AI agent frameworks and research" ← verify: evidence JSONL + delivery.md 生成

- [ ] S2: 跑 native Claude 同 query 作为 baseline ← verify: 输出保存到 evidence/f006bis-native-claude.md

- [ ] S3: judge.py 打分 + 三方对比表 ← verify: v2.2(0.676) vs v2.3(目标 0.85+) vs native Claude，7 维全列

- [ ] S4: 如果 v2.3 < 0.85，分析哪个维度拖后腿，记录到 patterns.jsonl ← verify: 有具体 action item

### F007: 验证——多 session 进化轨迹 — todo

**这是证明 AutoSearch 能超越 native Claude 的核心测试。**

不同 topic 跑 5 个 session，每个 session 让 AVO 进化 1-2 代。观察 patterns 累积后搜索质量的变化曲线。

#### Steps

- [ ] S1: 定义 5 个不同 topic 的搜索任务（覆盖不同领域，防止 overfitting）← verify: 5 个 topic 列表

- [ ] S2: 每个 topic 跑 native Claude baseline ← verify: 5 份 baseline 保存

- [ ] S3: 跑 session 1-5，每个 session 用不同 topic，AVO 在每个 session 内进化 1-2 代 ← verify: 5 份 evidence + 5 份 judge score

- [ ] S4: 画轨迹图（x=session#, y=judge score vs native Claude score）← verify: 能看出累积优势趋势

- [ ] S5: 分析 patterns.jsonl 增长（从 ~35 条到多少？新 patterns 的 win rate？）← verify: 有量化数据

### F008: 文档收尾 — todo

#### Steps

- [ ] S1: CHANGELOG.md — v2.3 entry（用户能做什么：参考库、新 skills、结构化 patterns）← verify: lead with what user can DO
- [ ] S2: HANDOFF.md — 更新 fix/f006-issues branch section ← verify: 新 skill 列表 + 验证数据
- [ ] S3: AIMD 经验笔记 ← verify: INDEX.jsonl 更新
- [ ] S4: 更新 CLAUDE.md v2.3 rules（如有新规则）← verify: 和新 skills 一致

---

---

## Phase 2: Claude-First 架构升级

### 架构转变

从"替代 Claude 搜索"变成"增强 Claude"。核心变化：Claude 的训练知识从被动补充变为主动先导。

```
旧流程：搜索 → 评估 → 综合（Claude 是后处理器）
新流程：Claude 系统回忆 → 识别缺口 → 只搜缺口 → Claude 综合
```

### F009: Claude-first 核心 skills — todo

#### Steps

- [ ] S1: 新建 systematic-recall.md — 替代 use-own-knowledge.md 的被动模式。8 维度系统回忆 + 确信度标注（高/中/低/不知道）。维度：方法论、人物机构、标志项目、顶会论文、设计模式、风险局限、商业玩家、争议观点 ← verify: 有维度清单、有确信度标注规则、有输出格式（知识地图 JSONL）

- [ ] S2: 新建 knowledge-map.md — 存储和加载跨 session 的知识地图。格式：per-topic JSONL in state/knowledge-maps/。每条记录 entity+confidence+source+last_verified ← verify: 有 CRUD 操作定义、有 session 间加载规则、有 freshness decay（confidence 随时间衰减）

- [ ] S3: 改 decompose-task.md — 加 Claude-first 流程："先回忆 → 画知识地图 → 识别缺口 → 只为缺口生成 sub-questions" ← verify: 现有内容保留，新增 "Knowledge-First Decomposition" section

- [ ] S4: 改 gene-query.md — 加 gap-driven 模式：从知识地图的空白区/低确信区生成 query，不从 task 文本生成 ← verify: 新增 "Gap-Driven Queries" section，和现有 gene combination 并存

### F010: 新渠道 skills — todo

#### Steps

- [ ] S1: 新建 search-citation-graph.md — 用 Semantic Scholar API 查引用关系。输入：paper title 或 arXiv ID → 输出：citing papers + referenced papers ← verify: 有 API 调用示例、有 rate limit 说明、符合 platform skill 标准（output schema + date + source tag "semantic-scholar"）

- [ ] S2: 新建 search-author-track.md — 查特定作者的其他工作。输入：author name → 输出：该作者所有论文按时间排序 ← verify: 同上

- [ ] S3: 新建 search-openreview.md — 查顶会 accepted papers。输入：conference + year → 输出：accepted paper list ← verify: 有 OpenReview API 格式、source tag "openreview"

### F011: 三路对比验证 — todo

**核心验证**：同一个 query，三个版本，全方位对比。

Query: "find open-source self-evolving AI agent frameworks and research"

| Version | 说明 |
|---------|------|
| **A: v2.3 Search-First** | 当前版本，搜索优先，use-own-knowledge 被动补充 |
| **B: v2.4 Claude-First** | 新版本，系统回忆先导，只搜缺口 |
| **C: Native Claude** | 无 AutoSearch，纯 Claude 回答 |

#### Steps

- [ ] S1: 跑 Version A（v2.3 search-first）← verify: evidence JSONL + judge score + delivery.md

- [ ] S2: 跑 Version B（v2.4 claude-first）← verify: evidence JSONL + judge score + delivery.md + knowledge-map output

- [ ] S3: 跑 Version C（native Claude baseline）← verify: 输出保存

- [ ] S4: 三路对比报告 ← verify: 表格覆盖以下维度

**对比维度**：

| 维度 | 怎么测 |
|------|--------|
| 速度 | wall clock time（秒） |
| 结果数量 | unique URLs |
| 内容类型覆盖 | repos / papers / products / blogs / videos 分别计数 |
| 概念框架深度 | 有几个维度、几个 design patterns、有无 risk analysis |
| 引用完整度 | claims with source / total claims |
| judge.py 7 维 | quantity, diversity, relevance, freshness, efficiency, latency, adoption |
| 知识利用率 | own-knowledge entries / total entries |
| 搜索效率 | unique relevant URLs / total queries |

- [ ] S5: 写结论 — 哪个版本在哪些维度赢，综合评判 ← verify: 有明确推荐

### F012: 多 session 进化轨迹（用胜出版本）— todo

用 F011 胜出的版本，跑 5 个不同 topic，验证累积优势。

#### Steps

- [ ] S1: 定义 5 个 topic ← verify: 列表确认
- [ ] S2: 每个 topic 先跑 native Claude baseline ← verify: 5 份保存
- [ ] S3: 跑 5 个 session，每个 AVO 进化 1-2 代 ← verify: patterns 累积数据
- [ ] S4: 轨迹分析 — score 曲线 + patterns 增长 ← verify: 可视化或表格

### F013: 文档收尾 — todo

#### Steps
- [ ] S1: CHANGELOG.md — v2.4 entry
- [ ] S2: HANDOFF.md — 更新
- [ ] S3: AIMD 经验笔记
- [ ] S4: CLAUDE.md 更新

---

## Decision Log

- 2026-03-31: **重心转移** — 从"我们手动优化 skills"变为"给 AVO 最好的学习环境"。1,009 skills 做参考库而不是手动提取。
- 2026-03-31: **Claude-first 架构** — 从"替代 Claude"变为"增强 Claude"。系统回忆先导，搜索只补缺口。三路对比验证。
- 2026-03-31: rerank-evidence 用 LLM（Claude 自己）做 ranking，不需要外部 embedding API。本地模型是未来优化路径，不是现在的依赖。
- 2026-03-31: PROTOCOL.md 不可改，patterns 格式变更通过 extract-knowledge.md（mutable skill）引导。
- 2026-03-31: 参考库放 state/skill-reference.jsonl，和 patterns.jsonl 同级，AVO 在 startup 时可以发现它。
- 2026-03-31: consult-reference.md 是新 mutable skill（不是 meta-skill），AVO 修改 skill 时 PROTOCOL.md §2 会让 agent 读它。
- 2026-03-31: F007 多 session 测试是证明核心价值（累积超越 native Claude）的关键，不能跳过。

## Open Questions

1. **5 个测试 topic** 选什么？建议覆盖：技术调研（当前）、学术综述、商业竞品分析、开源生态扫描、新兴趋势追踪。用户确认？
2. **参考库更新机制** — 发现新的好项目后，怎么追加到参考库？手动还是 AVO 通过 extract-knowledge.md 自动？
3. **v2.3 release** — 是 skills 升级完验证后发，还是参考库 + 新 skills 分两次发？

## 执行策略

| Feature | Codex tasks | 依赖 |
|---------|-------------|------|
| F001 (参考库) | 16 (每个项目 1 个转化 task) | 无 |
| F002 (patterns 格式) | 0 (Claude 直接做) | 无 |
| F003 (7 新 skills) | 7 (每个 skill 1 个提取 task) | F001 完成（参考库作为输入） |
| F004 (4 扩展 skills) | 4 | F001 |
| F005 (14 platform) | 14 | F003 S1 (normalize-results 定义 schema) |
| F006 (F006-bis 验证) | 1 agent | F003 + F004 + F005 |
| F007 (多 session 轨迹) | 5 agents | F006 通过 |
| F008 (文档) | 0 | F007 |

**总计 ~47 Codex tasks + 6 agent runs**
**可并行**：F001 和 F002 同时跑。F003/F004/F005 三个 Feature 部分可并行。
**关键路径**：F001 → F003 → F006 → F007

预估 4-5 个 session 完成全部 Feature。
