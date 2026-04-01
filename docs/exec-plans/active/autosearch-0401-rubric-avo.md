# AutoSearch v4.0 — Rubric-Based AVO + 完整进化系统

## Goal

让 AVO 像 NVIDIA AVO 一样有硬指标驱动进化。核心变化：从模糊的 judge.py 分数进化，变成 binary rubric pass rate 进化。每次 /autosearch 后自动进化一步，50 次后显著超越初始版本。

## 核心公式

```
Vary(P_t) = Agent(P_t, K, f)

P_t = state/ (patterns, channel-scores, knowledge-maps, rubric-history)
K   = skill-reference.jsonl (1,063 entries, 2,858 heuristics) + 69 skills
f   = Rubric Pass Rate (binary, 不可模糊)
```

## 架构

```
/autosearch "query"
│
├── Phase 0: 生成 Rubrics（Claude 定义"完整答案长什么样"）
│   generate-rubrics.md → 30-60 条 binary rubrics
│
├── Phase 1: 回忆 + 规划（30s）
│   systematic-recall → select-channels → gene-query → queries.json
│
├── Phase 2: 搜索（15-30s）
│   search_runner.py 并行执行
│
├── Phase 3: 评估（30s）
│   llm-evaluate 判断搜索结果相关性
│
├── Phase 4: 综合交付（60-90s）
│   synthesize-knowledge → delivery
│
├── Phase 5: Rubric 检查（30s）
│   check-rubrics.md → 逐条检查 → pass/fail 列表
│   rubric_pass_rate = passed / total
│
└── Phase 6: AVO 自动进化（30s）
    auto-evolve.md:
    1. 找 score 最低的 rubric category
    2. 诊断：为什么没满足？
    3. 改一个 skill（或 channel-scores/patterns）
    4. 记录：哪个 rubric 失败 → 改了什么 → 预期什么翻转
    5. 下次 /autosearch 验证是否翻转 → commit/revert

总时间：3-5 分钟
```

---

## Feature 清单

### F001: generate-rubrics.md — todo

在搜索前，Claude 生成 topic-specific 的 binary rubrics。

#### 设计

Rubric 格式：
```json
{
  "id": "r001",
  "category": "information-recall",
  "rubric": "Lists at least 5 foundational methods (e.g., STaR, Reflexion, Voyager)",
  "priority": "high"
}
```

三个 category（对标 DeepResearch Bench II）：
- `information-recall`：该找到的信息找到了吗？
- `analysis`：产出了有价值的洞察吗？
- `presentation`：结构清晰、引用完整吗？

#### Steps

- [ ] S1: 写 generate-rubrics.md skill — 输入 topic，输出 30-60 条 binary rubrics，按 3 个 category 分类 ← verify: 对同一个 topic 生成 rubrics 覆盖 information-recall (60%), analysis (30%), presentation (10%) 的比例

- [ ] S2: Rubric 生成规则 — 每条 rubric 必须是 binary（可以回答 yes/no），必须具体（不能是"报告很全面"），必须可验证（不需要外部知识就能判断）← verify: 示例 rubrics 全部符合 binary + 具体 + 可验证

- [ ] S3: Rubric 存储 — 每次搜索的 rubrics 存到 evidence/rubrics-{topic-slug}.jsonl ← verify: 文件格式正确

### F002: check-rubrics.md — todo

交付后，逐条检查 rubrics。

#### Steps

- [ ] S1: 写 check-rubrics.md skill — 读 delivery + rubrics → 逐条判断 pass(1)/fail(0) → 输出 checked-rubrics.jsonl ← verify: 每条 rubric 有 pass/fail + evidence（从 delivery 中引用的段落）

- [ ] S2: 输出格式：
```json
{
  "id": "r001",
  "category": "information-recall",
  "rubric": "Lists at least 5 foundational methods",
  "passed": true,
  "evidence": "Report mentions STaR, Reflexion, Voyager, DSPy, ADAS, FunSearch"
}
```
← verify: passed 是 boolean，evidence 引用 delivery 原文

- [ ] S3: 汇总分数 — total pass rate + per-category pass rate ← verify: 输出示例：`{"total": 0.72, "information-recall": 0.65, "analysis": 0.80, "presentation": 0.90}`

### F003: auto-evolve.md — todo

每次 /autosearch 结束后自动运行。AVO 的核心进化 skill。

#### Steps

- [ ] S1: 写 auto-evolve.md skill — 完整进化循环：
```
1. 读 checked-rubrics.jsonl → 找所有 failed rubrics
2. 按 category 聚合 → 哪个 category 最弱？
3. 选最弱 category 的 top-3 failed rubrics
4. 诊断：为什么失败？
   - information-recall 失败 → 渠道问题？query 问题？
   - analysis 失败 → synthesize skill 不够？缺分析指令？
   - presentation 失败 → 格式问题？引用问题？
5. 决定改什么：
   - 渠道问题 → 改 select-channels.md 或 channel-scores.jsonl
   - Query 问题 → 改 gene-query.md 或 patterns
   - 综合问题 → 改 synthesize-knowledge.md
   - 分析问题 → 改 synthesize-knowledge.md 的分析指令
6. 执行修改 → git commit
7. 记录到 state/evolution-log.jsonl:
   {"session":"...","failed_rubrics":["r003","r015","r042"],
    "weakest_category":"information-recall",
    "diagnosis":"producthunt channel not selected for this topic type",
    "action":"modified select-channels.md to include producthunt for product-related topics",
    "commit":"abc123",
    "expected_rubric_flips":["r003","r015"]}
```
← verify: 流程完整，包含诊断+修改+记录

- [ ] S2: 进化验证规则 — 下次同 topic 搜索时，检查 expected_rubric_flips 是否真的翻转了。翻转了 → 保留 commit。没翻转 → 分析原因，可能 revert ← verify: 验证逻辑在 auto-evolve.md 中明确

- [ ] S3: 停滞检测 — 连续 3 次进化没有 rubric 翻转 → 换方向（参考 NVIDIA AVO 的 supervisor 机制）← verify: 停滞检测逻辑明确

### F004: pipeline-flow.md 更新 — todo

加 Phase 0 (rubrics 生成) 和 Phase 5-6 (检查 + 进化)。

#### Steps

- [ ] S1: 更新 pipeline-flow.md — 6 个 Phase（0-5 改为 0-6）← verify: 流程清晰

- [ ] S2: 更新时间预算 — Phase 0: 15s, Phase 5: 30s, Phase 6: 30s, 总计 3-5 min ← verify: 时间合理

### F005: state/evolution-log.jsonl — todo

AVO 进化历史。每次进化一条记录。

#### Steps

- [ ] S1: 定义 schema — session, timestamp, rubric_pass_rate, failed_rubrics, weakest_category, diagnosis, action, commit_hash, expected_flips ← verify: schema 完整

- [ ] S2: 初始化空文件 ← verify: 文件存在

### F006: synthesize-knowledge.md 加分析指令 — todo

当前 synthesize 偏"整理信息"，缺"分析洞察"。对标 DeepResearch Bench 的 Analysis 维度。

#### Steps

- [ ] S1: 加"分析洞察"section — 明确要求产出：
  - 比较（A vs B，优劣权衡）
  - 趋势（从 X 到 Y 的演变方向）
  - 因果（为什么 X 会导致 Y）
  - 判断（基于证据的推荐）
  - 争议（不同观点的对立和未解决问题）
← verify: 5 种分析类型都有指令 + 示例

### F007: 验证 — todo

#### Steps

- [ ] S1: Topic 1 完整 pipeline（含 rubrics + check + auto-evolve）← verify: rubrics 生成 → 搜索 → 交付 → rubric 检查 → 进化 全流程跑通

- [ ] S2: 对比 rubric pass rate vs judge.py score — 两者是否相关？rubric 是否更精确？← verify: 有量化对比

- [ ] S3: AVO 进化一步后，重跑同 topic — 至少 1 条 rubric 从 fail 变 pass ← verify: 有翻转证据

### F008: 10 次连续进化 — todo

证明 AVO 随迭代变好。

#### Steps

- [ ] S1: 5 个不同 topic，每个跑 2 次（第 1 次 + AVO 进化后第 2 次）← verify: 10 次运行数据

- [ ] S2: 每个 topic 对比：第 1 次 vs 第 2 次 rubric pass rate ← verify: 5 个 topic 都有对比数据

- [ ] S3: 整体轨迹 — patterns 增长、channel-scores 变化、evolution-log 条目 ← verify: 累积数据可视化

- [ ] S4: 和 DeepResearch Bench 的 GPT-o3 (45%) 对标 — AutoSearch 的 rubric pass rate 是多少？← verify: 有可比较的数字

### F009: 文档收尾 — todo

#### Steps
- [ ] S1: CHANGELOG.md — v4.0: rubric-based AVO
- [ ] S2: HANDOFF.md — 完整进化系统说明
- [ ] S3: CLAUDE.md — 加 rubric 相关规则
- [ ] S4: AIMD 经验笔记

---

## Decision Log

- 2026-04-01: AVO 核心指标从 judge.py 8 维分数改为 **rubric pass rate**。原因：binary rubrics 不可模糊，AVO 能精确知道缺什么、改什么。对标 NVIDIA AVO 的 TFLOPS 和 DeepResearch Bench II 的 9,430 rubrics。
- 2026-04-01: Rubrics 由 Claude 在每次搜索前自动生成（不需要人工写）。原因：Claude 对大多数 topic 知道"完整答案应该包含什么"。
- 2026-04-01: 三个 rubric category 对标 DeepResearch Bench II：information-recall (60%), analysis (30%), presentation (10%)。原因：Information Recall 是行业最大瓶颈（~40%），也是 AutoSearch 42 渠道的优势所在。
- 2026-04-01: AVO 进化闭环 = 找 failed rubric → 诊断 → 改 skill → 验证 rubric 翻转 → commit/revert。这和 NVIDIA AVO 的 edit-evaluate-diagnose 循环完全对齐。
- 2026-04-01: evolution-log.jsonl 记录每次进化的完整上下文（failed rubrics, diagnosis, action, expected flips）。这是 AVO 的"血统" P_t。
- 2026-04-01: judge.py 保留作为辅助信号，不删除。rubric pass rate 作为主指标，judge.py 作为维度级别的补充。

## 和前几版的演进

| 版本 | AVO 指标 | 问题 |
|------|---------|------|
| v2.3 | judge.py 7 维 | 模糊，AVO 不知道改什么 |
| v2.4 | judge.py 8 维 (加 knowledge_growth) | 略好，但仍然模糊 |
| v3.0 | judge.py + incremental_discovery_rate | 两个指标但不够细 |
| **v4.0** | **rubric pass rate (binary, per-item)** | **不可模糊，精确到每条缺失** |

## 预期成果

| 指标 | 当前 | v4.0 目标 |
|------|------|----------|
| AVO 进化精度 | +0.025 模糊提升 | **每次翻转 1-3 条 rubric** |
| AVO 迭代量 | 5 次（手动触发） | **50+ 次（自动触发）** |
| 评估和行业对标 | 不可比 | **直接对标 DeepResearch Bench** |
| Information Recall | ~40%（行业平均） | **60%+（42 渠道优势）** |

## 执行顺序

```
F001 (generate-rubrics) + F002 (check-rubrics) → F003 (auto-evolve) → F004 (pipeline 更新)
                                                                              ↓
F005 (evolution-log) + F006 (synthesize 分析指令) → F007 (验证) → F008 (10 次进化) → F009 (文档)
```

关键路径：F001 → F002 → F003 → F007。写 rubric 生成/检查 → 写自动进化 → 验证跑通。
