# 报告质量提升 + 精准进化

## Goal

1. 解决已知的报告质量问题（r005 商业公司、r013 会议信息、r023 URL 缺失）
2. 从 Armory/Search 深度研究项目学来的合成模式应用到 AutoSearch
3. 让 AVO 进化聚焦在最有效的 3 个靶标上：渠道选择、query 策略、合成引用

## 背景

- pipeline 上次跑分 0.880（22/25 rubrics），3 个失败：r005（商业公司不够）、r013（会议信息缺）、r023（URL 缺失）
- channel plugin 系统已完成（PR #22 merged），30/32 渠道正常工作
- Armory/Search 5 个深度研究项目的合成方案已分析完毕
- `auto-evolve.md` 已有完整的诊断→修改→commit→验证循环，但进化靶标可以更精准

## Features

### F001: 合成引用强制规则 — todo

解决 r023（每个项目/论文必须带 URL）。从 gpt-researcher 和 open_deep_research 学习引用强制模式。

#### Steps
- [ ] S1: 读 `autosearch/v2/skills/synthesize-knowledge.md` 现有 Citation Rules 部分（line 117-126），分析当前规则为什么不够强 ← verify: 写出具体差距分析
- [ ] S2: 在 Citation Rules 部分加入强制规则：（1）每个具体事实/数据/项目描述必须带 `[来源](url)` 格式的内联引用（2）URL 必须来自搜索结果，禁止使用训练数据中记忆的 URL（3）使用训练知识补充的内容必须标记 `[background knowledge]`，不带 URL（4）报告末尾加 `## Sources` 带编号引用列表（学 open_deep_research 的两阶段模式）← verify: `grep -c "MUST\|must\|禁止\|required" autosearch/v2/skills/synthesize-knowledge.md` 至少增加 4 条规则
- [ ] S3: 在 `pipeline-flow.md` 的 Phase 5（合成前）加一个"引用锁定"步骤：先把所有搜索结果整理成编号引用列表 `[1] Title: URL`，合成时只能引用这个列表里的编号 ← verify: `grep "引用锁定\|citation lock\|numbered reference" autosearch/v2/skills/pipeline-flow.md` 有结果
- [ ] S4: 写测试用例文档 `tests/quality/test-citation-rules.md` — 列出 5 个必须通过的引用场景（有 URL 的事实、无 URL 的 background knowledge、混合引用等）← verify: 文件存在

### F002: Query 策略增强 — todo

解决 r013（会议/workshop 信息缺失）和提升整体 query 覆盖率。

#### Steps
- [ ] S1: 在 `gene-query.md` 的 content_type 维度中加入缺失的类型：`conference-workshop`（会议/研讨会）、`company-product`（商业公司/产品）、`comparison`（工具对比）、`tutorial`（教程）← verify: `grep "conference-workshop\|company-product" autosearch/v2/skills/gene-query.md` 有结果
- [ ] S2: 在 Gap-Driven Query Generation 部分加入"必选 query 规则"：（1）学术话题必须生成至少 1 条 `content_type=conference-workshop` 的 query（2）工具/产品话题必须生成至少 1 条 `content_type=company-product` 的 query（3）如果 knowledge map 里 commercial players 是 GAP，必须生成 crunchbase/producthunt query ← verify: `grep "必须生成\|must generate\|mandatory" autosearch/v2/skills/gene-query.md` 有结果
- [ ] S3: 在 gene-query.md 加入"语言适配规则"：中文渠道（zhihu/bilibili/csdn/juejin 等）的 query 必须翻译成中文，不能用英文搜。当前 skill 已有类似规则（line 122-123），强化为明确的渠道→语言映射表 ← verify: `grep "渠道\|channel.*中文\|Chinese channels" autosearch/v2/skills/gene-query.md` 有结果

### F003: 渠道选择进化靶标 — todo

让 `select-channels.md` 成为 AVO 进化的主要靶标。现有 skill 已经有 topic→channel 映射表（Rule 2）和 channel-scores 机制（Rule 4），但需要完善。

#### Steps
- [ ] S1: 更新 `select-channels.md` Rule 2 的 topic→channel 映射表，加入新渠道（twitter）和调整渠道名称对齐 `channels/` 目录名（去掉 `search-` 前缀，因为现在渠道名就是目录名）← verify: `grep "twitter" autosearch/v2/skills/select-channels.md` 有结果，且所有渠道名与 `channels/` 目录名一致
- [ ] S2: 在 Rule 4 (channel effectiveness scores) 部分加入"进化反馈循环"说明：每次 pipeline 跑完后，`auto-evolve.md` 诊断时如果发现 information-recall 失败，优先检查 channel-scores.jsonl 并更新，而不是改 skill 文本。明确写出 `channel-scores.jsonl` 的更新规则 ← verify: `grep "进化\|evolution\|auto-evolve" autosearch/v2/skills/select-channels.md` 有结果
- [ ] S3: 初始化 `state/channel-scores.jsonl` — 基于冒烟测试数据，为每个渠道写入初始分数。30/32 正常工作的渠道 `incremental_rate` 设为 0.5（待验证），2 个 rate-limited 的设为 0.3 ← verify: `wc -l autosearch/v2/state/channel-scores.jsonl` 至少 30 行

### F004: AVO 进化靶标精准化 — todo

修改 `auto-evolve.md`，让进化聚焦在三个高杠杆靶标上，而不是漫无目的地改 skill 文本。

#### Steps
- [ ] S1: 在 Step 4 Diagnosis Map 中更新 "Where to look" 列，加入新的进化路径：

| 失败类型 | 优先进化靶标 | 机制 |
|---|---|---|
| information-recall（渠道没覆盖） | `state/channel-scores.jsonl` | 更新渠道分数，下次自动选对渠道 |
| information-recall（query 没命中） | `skills/gene-query.md` 的必选 query 规则 | 为特定 topic 类型加 mandatory query |
| information-recall（结果找到但没合成） | `skills/synthesize-knowledge.md` 的引用规则 | 加强引用强制 |
| presentation（URL 缺失） | `skills/synthesize-knowledge.md` 的引用规则 | 已由 F001 解决 |
| analysis（分析不够深） | `skills/synthesize-knowledge.md` 的 Analysis Requirements | 加具体分析模板 |

← verify: `grep "channel-scores.jsonl" autosearch/v2/skills/auto-evolve.md` 在 diagnosis map 中出现
- [ ] S2: 在 Step 5 加入"进化优先级"：修改 `channel-scores.jsonl` > 修改 `gene-query.md` > 修改 `select-channels.md` > 修改 `synthesize-knowledge.md`。数据文件的修改比 skill 文本修改更精准、更可验证 ← verify: `grep "优先级\|priority\|prefer.*channel-scores" autosearch/v2/skills/auto-evolve.md` 有结果
- [ ] S3: 在 Step 0（验证先前进化）加入 channel-scores 验证逻辑：如果先前进化修改了 channel-scores.jsonl，验证方式是看相关渠道在本次搜索中的 incremental_rate 是否提升 ← verify: `grep "channel-scores.*验证\|channel-scores.*verif" autosearch/v2/skills/auto-evolve.md` 有结果

### F005: Pipeline 验证（新基线）— todo

用新渠道 + 改进的 skills 跑完整 pipeline，建立新基线。

#### Steps
- [ ] S1: 用 "self-evolving AI agent frameworks" 跑完整 7-phase pipeline ← verify: `tail -1 autosearch/v2/state/rubric-history.jsonl` 有新条目
- [ ] S2: 对比旧基线（0.880）— 重点看 r005/r013/r023 是否翻转 ← verify: 至少 2/3 翻转（r005 应该翻因为渠道修好了，r023 应该翻因为引用规则加强了）
- [ ] S3: 如果 pass_rate < 0.880，分析回退原因，不盲目接受 ← verify: 有分析记录
- [ ] S4: 记录新基线到 `rubric-history.jsonl` 和 `patterns-v2.jsonl` ← verify: 文件有新条目

### F006: AVO 进化验证（3-run）— todo

不做完整的 5 topics × 2 runs（太大），先做 3 次单 topic 进化循环验证 AVO 能不能在新架构上工作。

#### Steps
- [ ] S1: 第 1 次搜索 — 用一个新 topic（不是 self-evolving agents），跑完整 pipeline + check-rubrics + auto-evolve ← verify: `evolution-log.jsonl` 有新条目，且有 diagnosis 和 expected_flips
- [ ] S2: 第 2 次搜索 — 用同一个 topic 再跑一次，验证 AVO 的修改是否让 expected_flips 翻转 ← verify: `evolution-log.jsonl` 新条目有 `verification` 字段
- [ ] S3: 第 3 次搜索 — 用不同 topic，测试 AVO 修改的泛化性（对另一个 topic 是否也有帮助或至少无害）← verify: pass_rate 不低于 F005 的基线
- [ ] S4: 评估：AVO 3 次循环中，是否有至少 1 个 rubric 被成功翻转？如果是，进化机制有效。如果不是，分析阻塞原因 ← verify: 有结论性评估记录

## 依赖关系

```
F001 (引用规则)  ──┐
F002 (query 策略)  ├── F005 (pipeline 验证，depends F001+F002+F003)
F003 (渠道选择)  ──┘         │
F004 (AVO 靶标)  ────────── F006 (AVO 验证，depends F004+F005)
```

F001/F002/F003/F004 可以并行。F005 等 F001-F003 完成。F006 等 F004+F005 完成。

## 进化靶标优先级总览

```
AVO 检测到 rubric 失败
  │
  ├── information-recall 失败？
  │     ├── 渠道没选对 → 更新 channel-scores.jsonl（数据进化，最精准）
  │     ├── query 没命中 → 改 gene-query.md 的必选 query 规则
  │     └── 结果找到但没写进报告 → 改 synthesize-knowledge.md 的引用规则
  │
  ├── analysis 失败？
  │     └── 改 synthesize-knowledge.md 的 Analysis Requirements
  │
  └── presentation 失败？
        └── 改 synthesize-knowledge.md 的 Citation Rules / Delivery Structure
```

核心思路：**优先改数据（channel-scores.jsonl），其次改规则（skill 里的具体 heuristic），最后才改结构（skill 的整体架构）。** 数据改动最精准、最可验证、最容易 revert。

### F007: 模型路由 — 分层用模型降成本 — todo

Pipeline 里所有 LLM 调用都用当前 session 模型（通常是 Opus/Sonnet），浪费。批量评分任务用 Haiku 就够了。

模型分配策略：
- **Haiku**：query 生成（gene-query）、结果评分（llm-evaluate）、rubric 检查（check-rubrics）— 结构化批量任务
- **Sonnet**：知识合成（synthesize-knowledge）、AVO 进化诊断（auto-evolve）— 需要推理质量
- 搜索本身（search_runner.py）不用 LLM，零 token 消耗

#### Steps
- [ ] S1: 在 `pipeline-flow.md` 中为每个 phase 标注推荐模型（Haiku/Sonnet），让 Claude 知道哪些步骤可以降级 ← verify: `grep -c "haiku\|Haiku" autosearch/v2/skills/pipeline-flow.md` >= 3
- [ ] S2: 在 `llm-evaluate.md` 中加入"模型推荐"说明：评分任务推荐用 Haiku，如果当前 session 是 Opus/Sonnet，评分时应该 spawn Haiku agent ← verify: `grep "Haiku\|haiku" autosearch/v2/skills/llm-evaluate.md` 有结果
- [ ] S3: 在 `check-rubrics.md` 中加入同样的模型推荐 ← verify: `grep "Haiku\|haiku" autosearch/v2/skills/check-rubrics.md` 有结果
- [ ] S4: 在 `gene-query.md` 中加入模型推荐：query 生成推荐 Haiku ← verify: `grep "Haiku\|haiku" autosearch/v2/skills/gene-query.md` 有结果

## 依赖关系（更新）

```
F001 (引用规则)  ──┐
F002 (query 策略)  ├── F005 (pipeline 验证，depends F001+F002+F003+F007)
F003 (渠道选择)  ──┤
F007 (模型路由)  ──┘         │
F004 (AVO 靶标)  ────────── F006 (AVO 验证，depends F004+F005)
```

## Decision Log
- 2026-04-03: 引用模式选型 — 采用 gpt-researcher 的 prompt 硬规则 + open_deep_research 的两阶段引用锁定。不采用 node-deepresearch 的 embedding 注入方案（太重，AutoSearch 是 skill-based 不是代码 pipeline）。
- 2026-04-03: 进化靶标精准化 — AVO 进化从"改任意 skill 文本"聚焦到 3 个靶标：channel-scores.jsonl（数据）、gene-query.md（query 规则）、synthesize-knowledge.md（合成规则）。数据进化 > 规则进化 > 结构进化。
- 2026-04-03: 验证规模缩小 — F008 从 5×2=10 runs 缩减到 3 runs（同 topic 2 次 + 跨 topic 1 次），先验证机制是否工作，再考虑大规模验证。
- 2026-04-03: 模型路由 — Haiku 做批量任务（评分/rubric/query 生成），Sonnet 做质量任务（合成/AVO 诊断）。不用 Qwen（本地模型，不适合给用户）。不用 Opus（成本太高，Sonnet 质量够用）。

## Open Questions
- channel-scores.jsonl 的 incremental_rate 怎么自动计算？需要在 pipeline 里加一步对比搜索结果和 Claude 训练知识的重叠度。
- AVO 修改 gene-query.md 加 mandatory query 规则后，会不会导致 query 总数膨胀？需要设上限。
- 两阶段引用锁定（先压缩编号 → 再合成）会增加一次 LLM 调用。Token 成本是否可接受？
