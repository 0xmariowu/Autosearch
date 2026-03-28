# AutoSearch AVO Genome Architecture

## Goal

把 AutoSearch 从"人设计搜索策略、AI 执行"重构为"AI 自己进化搜索策略"。核心变化：所有策略决定从硬编码 Python 搬到可进化的 Genome JSON，由 AVO Controller 自主进化。人只定义评分函数 f（Goal Judge）。

## 架构总览

```
AVO Controller  →  vary genome  →  Runtime 执行  →  Judge 评分  →  commit/discard
     ↑                                                    │
     └────────── lineage (evolution.jsonl) ←────────���─────┘
```

三层分离：
- **Genome**: 可进化的策略 JSON（AVO 进化的对象）
- **Runtime**: 读 genome 执行搜索（~200 行解释器，不含策略决定）
- **Primitives**: 最小原子操作（~15 个，纯机制）

## Constraints & Assumptions

- 现有测试必须继续 pass（行为向后兼容）
- Genome 文件是 JSON（不是 Python，AVO 能直接改）
- Engagement formulas 用安全表达式字符串（白名单函数 + 变量）
- Goal Judge 接口不变（是 f，唯一的固定合同）
- evidence record schema 不变（Layer 0 数据合同）
- evolution.jsonl 格式扩展但向后兼容

---

## F001: Genome Schema 定义 — todo

定义 Genome 的完整 JSON Schema。这是所有后续工作的地基——没有 schema 就没有 genome，没有 genome 就没有 AVO 进化。

### 背景

目前硬编码分布在 19 个文件、87 个策略决定��。需要一个统一的 schema 把它们全部收纳。Schema 要覆盖六大块：phases（搜索阶段）、query_generation（查询生成）、scoring（打分）、platform_routing（平台选择）、thresholds（阈值）、synthesis（合成）。

### Steps

- [ ] S1: 创建 `genome/schema.py` — 定义 GenomeSchema dataclass + JSON Schema 导出 ← verify: `python3 -c "from genome.schema import GenomeSchema; g = GenomeSchema.default(); print(g.to_json())"` 输出合法 JSON
- [ ] S2: 创建 `genome/defaults/engine.json` — 从 engine.py 当前值提取，包含 EngineConfig 所有字段（max_stale=5, max_rounds=15, queries_per_round=15, llm_ratio=0.20, pattern_ratio=0.20, gene_ratio=0.60, harvest_since, llm_model）← verify: JSON 值和 engine.py:99-110 当前值一致
- [ ] S3: 创建 `genome/defaults/orchestrator.json` — 从 orchestrator.py 各处内联常量提取：max_steps（run_task() 参数默认值）、temperature（_call_llm() 内联）、max_tokens（_call_llm() 内联）、stuck_detect_interval（主循环的 `% 3` 检查）、search_timeout（ThreadPoolExecutor 超时）。SYSTEM_PROMPT 存为**外部文件引用** `"system_prompt_file": "genome/defaults/orchestrator-system-prompt.txt"` 而非内联 JSON 字符串（51 行 prompt 内联会导致 JSON 难以编辑和 diff）。同时创建 orchestrator-system-prompt.txt。 ← verify: JSON 字段值和 orchestrator.py 当前行为一致；system_prompt_file 文件存在且内容和 orchestrator_prompts.py SYSTEM_PROMPT 一致
- [ ] S4: 创建 `genome/defaults/modes.json` — 从 research/modes.py MODE_POLICIES 提取全部三个 mode 定义（speed/balanced/deep 的 16 个参数 × 3 = 48 个值）← verify: JSON 值和 modes.py:36-111 一致
- [ ] S5: 创建 `genome/defaults/scoring.json` — **设计新的结构化 scoring config**，默认值从 lexical.py 的硬编码字面量提取：`term_weights: {"title": 4, "snippet": 2, "url": 1, "source": 1}`（对应 lexical.py:103-111 的 `+4/+2/+1/+1`）、`content_type_bonus: 2`（lexical.py:119）、`harmonic_divisor: 10`（lexical.py:125）、`stop_words` 集合（lexical.py:37-57）、`tracking_params` 集合（lexical.py:11-35）。从 consensus_score.py 提取 boost formula。新增 `generic_tokens` list 和 `generic_cap` 字段。注意：这些是**新定义的 config 字段**，当前代码中是裸字面量不是命名常量。 ← verify: JSON 中 term_weights.title=4, term_weights.snippet=2 等值和 lexical.py 行为一致
- [ ] S6: 创建 `genome/defaults/platform_routing.json` — 从 source_capability.py 提取（STATUS_PRIORITY, TIER_PRIORITY）+ 从 capabilities/search_all.py 提取（默认 provider 列表）+ 新增 intent-based routing ← verify: JSON 值和 source_capability.py:28-39 + search_all.py:35-42 一致
- [ ] S7: 创建 `genome/defaults/thresholds.json` — 从多个文件收集全部阈值：project_experience.py (RECENT_RUN_WINDOW=12, PREFERRED_MIN_ATTEMPTS=8, COOLDOWN_ERROR_RATE=0.70 等), evaluation_harness.py (per_query_cap=5, per_source_cap=18, per_domain_cap=18 — 注意：这些在 evaluation_harness.py 定义，goal_bundle_loop.py 只是传递), goal_runtime.py (max_source_concentration=0.82, max_query_concentration=0.70 — 注意：selector.py 从传入 dict 读取，goal_runtime.py 是 defaults 的来源), avo.py (stagnation_window=3, stagnation_threshold=1.01) ← verify: JSON 值和 project_experience.py, evaluation_harness.py, goal_runtime.py, avo.py 源文件一致
- [ ] S8: 创建 `genome/defaults/synthesis.json` — 从 research/synthesizer.py 提取（POSITIVE_CLAIM_TERMS, NEGATIVE_CLAIM_TERMS, CLAIM_STOP_WORDS, query_cluster_limit=8, domain_cluster_limit=8, multi_source_threshold=2）+ 新增 intent_templates 和 report_sections ← verify: JSON 值和 synthesizer.py:19-66 一致
- [ ] S9: 创建 `genome/defaults/query_generation.json` — 从 research/planner.py 提取（GENERIC_ANCHOR_TOKENS, strong_evidence_types, anchor_token_limit=4, recursive_depth_limit=4, branch_budget defaults）+ 新增 intent_patterns 和 mutation_kinds with weights + 新增 entity_extraction 配置 ← verify: JSON 值和 planner.py:11-28 一致
- [ ] S10: 创建 `genome/safe_eval.py` — 安全表达式求值器，白名单函数（log1p, min, max, abs, sqrt, log, pow）+ 白名单变量（来自 evidence 字段名）。用 ast.parse + whitelist visitor，不用 eval()。 ← verify: `safe_eval("0.50*log1p(score) + 0.35*log1p(comments)", {"score": 100, "comments": 50})` 返回正确数值；`safe_eval("__import__('os').system('rm -rf /')", {})` 抛异常
- [ ] S11: 创建 `genome/__init__.py` — load_genome(path) 读 JSON 返回 GenomeSchema，merge_genome(base, overrides) 合并，validate_genome(genome) 验证 schema ← verify: load 默认 genome → validate → 无错误

---

## F002: Seed Genomes 创建 — todo

把现有的三种运行模式（engine 3-phase、orchestrator ReAct、daily 发现）转化为三个种子 Genome。这些是 AVO evolution population 的初始成员。

### 背景

目前 engine.py、orchestrator.py、daily.py 各自是独立的搜索流程，逻辑硬编码在 Python 里。转化为 genome 后，它们变成 AVO 可以进化的策略候选人。

### Steps

- [ ] S1: 创建 `genome/seeds/engine-3phase.json` — 完整描述 engine.py 的三阶段策略：Phase 1 EXPLORE（基因/模式/LLM 三源查询、stale detection）、Phase 2 HARVEST（top query re-search、engagement filter）、Phase 3 POST-MORTEM（pattern extraction）。每个 phase 映射到 primitives 调用链。 ← verify: genome JSON 能被 GenomeSchema.validate() 通过
- [ ] S2: 创建 `genome/seeds/orchestrator-react.json` — 完整描述 orchestrator.py 的 ReAct 策略：health check → think → search_all → process（consensus + merge + dedup）→ learnings → diversify → terminate。包含 system_prompt、tool selection rules、message compression 参数。 ← verify: genome JSON 能被 GenomeSchema.validate() 通过
- [ ] S3: 创建 `genome/seeds/daily-discovery.json` — 完整描述 daily.py 的发现策略：固定平台列表、种子基因从 queries.json 读取、max_rounds=3、queries_per_round=20。 ← verify: genome JSON 能被 GenomeSchema.validate() 通过
- [ ] S4: 创建 `genome/seeds/README.md` — 说明每个种子 genome 的来源、适用场景、和原始 Python 代码的映射关系 ← verify: 文件存在且包含三个 seed 的描述

---

## F003: Primitives 提取 — todo

把 capabilities/ 里 38 个 capability 拆成 ~15 个 primitive（纯机制）+ 组合逻辑上升到 genome。Primitive 只做一件事，不含策略决定。

### 背景

当前 capabilities/ 混合了两种东西：纯原子操作（search_web → 发 HTTP 请求返回 hits）和策略组合（search_and_process → search + score + dedup，组合逻辑写死在 Python 里）。AVO 需要进化组合方式，所以组合逻辑必须在 genome 里，不在 primitive 里。

### Steps

- [ ] S1: 创建 `genome/primitives.py` — primitive 注册表，定义 PrimitiveSpec(name, input_schema, output_type, fn)。提供 register_primitive() 和 call_primitive(name, input) ← verify: 注册一个 mock primitive → call → 返回正确结果
- [ ] S2: 提取 search primitives — 把 capabilities/search_web.py, search_web_broad.py, search_github.py, search_arxiv.py, search_semantic.py, search_social.py, search_v2ex.py, search_reddit_sub.py, search_datasets.py 统一为 primitive `search(query, platform, limit)` 接口。注意 search_web_broad.py 在 orchestrator 的 tool 列表里，必须包含。具体 backend dispatch 通过 search_mesh/router.py（保持不变）。 ← verify: `call_primitive("search", {"query": "test", "platform": "ddgs", "limit": 10})` 返回 SearchHitBatch
- [ ] S3: 提取 fetch primitive — 从 capabilities/crawl_page.py + capabilities/follow_links.py 提取为 `fetch(url)` → 返回 markdown + references ← verify: `call_primitive("fetch", {"url": "https://example.com"})` 返回 dict with clean_markdown
- [ ] S4: 提取 score primitive — 从 rerank/lexical.py 提取为 `score(hits, rules)` → rules 来自 genome.scoring ← verify: score 结果和当前 lexical_score() 一致（给相同 input 返回相同 output）
- [ ] S5: 提取 dedup primitive — 从 capabilities/dedup_results.py + rerank/lexical.py dedup_hits 提取为 `dedup(hits, threshold)` → threshold 来自 genome ← verify: dedup 结果和当前一致
- [ ] S6: 提取 extract_entities primitive — 新建，从 evidence titles/bodies 提取 @handles, org names, product names, subreddit names。用正则 + 简单 NER。 ← verify: 给定 "Check out @cursor_ai for AI coding" → 提取出 ["@cursor_ai"]
- [ ] S7: 提取 cross_ref primitive — 从 capabilities/cross_verify.py + consensus_score.py 提取为 `cross_ref(hits, jaccard_threshold)` → 检测跨源内容重叠 ← verify: 两个不同 URL 但 title 相似的 hits → cross_refs 字段被填充
- [ ] S8: 提取 classify_intent primitive — 新建，用正则分类 query intent（how_to/comparison/opinion/debug/breaking/research/prediction）← verify: "how to deploy Next.js" → "how_to"；"Cursor vs Windsurf" → "comparison"
- [ ] S9: 提取 synthesize primitive — 从 research/synthesizer.py 提取 claim extraction + stance detection 为 `synthesize(evidence, rules)` → rules 来自 genome.synthesis ← verify: 输出 claim alignment 结果和当前一致
- [ ] S10: 提取 report primitive — 从 capabilities/generate_report.py 提取为 `report(evidence, template)` → template 来自 genome.synthesis.intent_templates ← verify: 给定 evidence + "comparison" template → 输出包含 side_by_side_table section
- [ ] S11: 提取 store primitive — evidence store 的 add/query 接口，从 evidence_index/query.py 提取 ← verify: add 一条 evidence → query 能找回
- [ ] S12: 提取 generate_queries primitive — 从 engine.py 的 query generation 逻辑 + research/planner.py 的 mutation 逻辑提取为 `generate_queries(task, config)` → config 来自 genome.query_generation ← verify: 给定 genes + config → 输出 query list
- [ ] S13: 提取 evaluate_engagement primitive — 新建，用 genome.scoring.engagement_formulas 的安全表达式计算 engagement score ← verify: `evaluate_engagement({"score": 100, "comments": 50}, "reddit", genome)` 返回正确值
- [ ] S14: 保留现有 capabilities/ 为兼容层 — 每个 capability 的 run() 内部改为调 primitive + 读 genome defaults。保证旧的 dispatch("search_web", ...) 接口继续工作。 ← verify: 全部现有 test 通过

---

## F004: Runtime — Genome 解释器 — todo

创建 Runtime 模块，读取 Genome JSON 并按 phases 执行搜索。Runtime 不含任何策略决定——它是一个通用的 genome 执行器。

### 背景

当前搜索逻辑分散在 engine.py（1646 行）、orchestrator.py（525 行）、daily.py（400+ 行）里，各自有独立的循环、调度、收集逻辑。Runtime 统一为一个 ~200 行的解释器，从 genome 读策略，调 primitives 执行。

### Steps

- [ ] S1: 创建 `genome/runtime.py` — 核心循环：读 genome → classify intent → for phase in genome.phases → generate_queries → resolve_platforms → call primitives → score → collect evidence → return bundle。~200 行。 ← verify: `runtime.execute(load_genome("genome/seeds/engine-3phase.json"), "find AI agent repos")` 返回 EvidenceBundle
- [ ] S2: 实现 phase 执行器 — 每个 phase 是 capabilities 列表 + 输入输出绑定。支持：`parallel: true`（并行调 primitive）、`input_from: "top_k:20"`（从上个 phase 取 top K 结果）、`query_source: "extract_entities_from_phase:broad"`（实体提取反向搜索）← verify: 串行 phase 和并行 phase 都能正确执行
- [ ] S3: 实现 genome scoring 应用 — Runtime 读 genome.scoring 的 term_weights, generic_tokens, generic_cap, engagement_formulas, cross_source_bonus 来打分。用 safe_eval 计算 engagement formulas。 ← verify: scoring 结果和当前 lexical_score() 等价（给相�� genome defaults）
- [ ] S4: 实现 platform routing 应用 — Runtime 读 genome.platform_routing + intent 来决定搜哪些平台。合并 source_capability 的 health 状态（不健康的平台即使 genome 指定了也跳过）← verify: intent="how_to" 时优先 github/stackoverflow
- [ ] S5: 实现 thresholds 应用 — Runtime 读 genome.thresholds 控制 dedup_jaccard, relevance_min, stale detection, max_results, per_domain_cap 等 ← verify: threshold 值从 genome 读取而非硬编码
- [ ] S6: 兼容性桥接 — engine.py、orchestrator.py、daily.py 各加一个 `run_with_genome(genome_path, task)` 入口，内部调 runtime.execute()。原有入口不变，继续工作。 ← verify: `python3 cli.py search "test query"` 行为不变
- [ ] S7: 集成测试（fixture-based）— 先用旧代码对固定输入录制一份 reference output（query + mock API responses → evidence bundle），保存为 `tests/fixtures/runtime_reference.json`。然后用新 runtime + seed genome 对相同 fixture 输入跑一次，diff 输出。差异只应来自字段顺序等无关因素，不应来自策略逻辑。live API 测试另做（不作为 pass/fail 条件）。 ← verify: `python3 -m pytest tests/test_runtime_equivalence.py -x` 通过

---

## F005: AVO Controller 升级 — todo

把 avo.py 从"只进化 orchestrator prompt"升级为"进化整个 genome"。这是 AVO 成为主架构的核心。

### 背景

当前 avo.py（400 行）的进化对象是 orchestrator 的 system_prompt 字符串。升级后，进化对象是完整的 genome JSON。AVO 论文的 `Vary(P_t) = Agent(P_t, K, f)` 直接映射：P_t = genome lineage, K = Armory + patterns, f = goal_judge。

### Steps

- [ ] S1: 扩展 evolution.jsonl 格式 — 新增 `genome_id`, `genome_path`, `parent_id`, `mutation_type` 字段。旧格式（只有 prompt + scores）继续可读。 ← verify: `load_population()` 能读旧格式 + 新格式
- [ ] S2: 实现 genome variation — 新建 `genome/vary.py`，提供 vary_genome(parent, population, knowledge, diagnosis) → 新 genome。支持 5 种变异：micro_mutation（改一个数值）、structural_mutation（增删/重排 phase）、crossover（从两个 parent 各取一部分）、supervisor_redirect（LLM 分析 lineage 给全新方向）、knowledge_injection（从 patterns.jsonl 注入成功模式）← verify: 每种变异都能产出合法 genome（通过 validate）
- [ ] S3: 实现 AVO 主循环 — 重构 `avo.py`：当前 main loop 在 `if __name__` + argparse 里，没有独立的 run_avo() 函数。需要新建 `run_avo(task_spec, max_generations, ...)` 封装完整循环：select parent → vary genome → runtime.execute(genome, task) → goal_judge.evaluate(evidence) → commit/discard → check stagnation。旧的 argparse 入口调新函数。 ← verify: `python3 avo.py "test task" --generations 3` 跑完，evolution.jsonl 有 3 条新记录，每条有 genome_id + scores
- [ ] S4: 升级 stagnation diagnosis — check_stagnation() 不再只看 total score，还分析哪个 genome section 是瓶颈（phases? scoring? query_generation?）。给 supervisor_redirect 提供具体修改建议。 ← verify: 人工构造 3 代 flat-score population → diagnosis 输出指向具体 genome section
- [ ] S5: 实现 genome lineage persistence — 每个 committed genome 保存为 `genome/evolved/{genome_id}.json`，evolution.jsonl 记录 genome_id → genome_path 映射。支持 load_best_genome(task_spec) 读取当前最优 genome。 ← verify: commit 3 代后，`load_best_genome()` 返回得分最高的 genome
- [ ] S6: 集成 MCP — `autosearch-mcp/tools.py` 的 `autosearch_evolve` tool 改为调新的 avo.py ← verify: MCP tool 调用成功

---

## F006: 代码回接 — todo

让现有代码模块从 genome 读取配置而非硬编码，同时保持向后兼容。

### 背景

F001-F005 建立了 genome 系统，但现有模块（engine.py、planner.py、lexical.py 等）还在用硬编码值。这一步让它们"知道"genome 的存在——优先从 genome 读，fallback 到旧默认值。

### Steps

- [ ] S1:（depends: F003.S14）research/modes.py — MODE_POLICIES 的默认值从 genome/defaults/modes.json 读取。get_mode_policy() 增加可选 genome 参数。 ← verify: 不传 genome 时行为不变；传 genome 时用 genome 的值
- [ ] S2: rerank/lexical.py — lexical_score() 增加可选 scoring_config 参数。不传时用现有硬编码；传时用 genome.scoring 的 term_weights、generic_tokens、generic_cap。 ← verify: 不传时行为不变（现有 test 通过）
- [ ] S3: research/planner.py — GENERIC_ANCHOR_TOKENS、branch budget defaults、anchor_token_limit、recursive_depth_limit 从 genome 读取（通过 program/search_decision 传入）。 ← verify: 现有 planner test 通过
- [ ] S4: research/synthesizer.py — POSITIVE_CLAIM_TERMS、NEGATIVE_CLAIM_TERMS、CLAIM_STOP_WORDS、cluster limits 从 genome.synthesis 读取。 ← verify: 现有 synthesizer test 通过
- [ ] S5: project_experience.py — RECENT_RUN_WINDOW、COOLDOWN_ERROR_RATE 等阈值��� genome.thresholds 读取。 ← verify: 现有 test 通过
- [ ] S6: engine.py — EngineConfig 的默认值从 genome/defaults/engine.json 读取。run_engine() 接受可选 genome_path 参数。 ← verify: `run_engine()` 不传 genome 时行为不变
- [ ] S7: orchestrator.py — max_steps、temperature、timeout、system_prompt 从 genome 读取。run_task() 接受可选 genome_path 参数。 ← verify: `run_task()` 不传 genome 时行为不变
- [ ] S8: daily.py — DAILY_PLATFORMS、DAILY_MAX_ROUNDS 等从 genome/defaults/daily-discovery.json 读取 ← verify: daily 模式行为不变
- [ ] S9: evaluation_harness.py — per_query_cap、per_source_cap、per_domain_cap 从 genome.thresholds 读取（注意：这些 defaults 在 evaluation_harness.py 定义，不是 goal_bundle_loop.py）← verify: 现有 goal_bundle_loop test + evaluation_harness test 通过
- [ ] S10:（gate step — requires F003.S14 + F006.S1-S9 all complete）全量测试回归 — `python3 -m pytest tests/ -x` 全部通过 ← verify: 0 failures

---

## F007: last30days 模式融合 — todo

把��� last30days 借鉴的六个模式作为 genome 的初始进化素材（seed genome 的增强版），而不是硬编码。

### 背景

之前分析的六个模式（entity extraction、query intent、cross-source convergence、informative token filter、engagement formulas、structured report synthesis）不应该硬编码为 Python 逻辑，而应该是 genome 值，让 AVO 未来可以进化它们。

### Steps

- [ ] S1: entity extraction phase — 在 engine-3phase seed genome 里加 phase "entity_followup"，query_source 设为 "extract_entities_from_phase:broad"。在 runtime 里实现 extract_entities_from_phase 的 phase 引用解析。 ← verify: genome 有 entity_followup phase → runtime 执行时调 extract_entities primitive → 产生反向 query
- [ ] S2: query intent classification — intent_patterns 写入 genome/defaults/query_generation.json（7 种 intent + 正则）。classify_intent primitive 读取 genome 的 patterns。 ← verify: intent_patterns 从 genome 读取；换一套正则就能改变分类行为
- [ ] S3: cross-source convergence — genome.thresholds 加 convergence_jaccard 字段（默认 0.42）。cross_ref primitive 读取此阈值。在 scoring 阶段，cross-source hit 得到 genome.scoring.cross_source_bonus 倍的加成。 ← verify: 两个不同源但相似的 hit → bonus 应用
- [ ] S4: informative token filter — genome.scoring 加 generic_tokens list + generic_cap 值。score primitive 区分 informative 和 generic match。 ← verify: 全 generic match 的 hit 分数不超过 generic_cap
- [ ] S5: engagement formulas — genome.scoring.engagement_formulas 为每个平台定义表达式字符串。evaluate_engagement primitive 用 safe_eval 计算。 ← verify: `evaluate_engagement({"score": 100, "comments": 50}, "reddit", genome)` 用 genome 的 reddit formula 计算
- [ ] S6: intent-driven synthesis templates — genome.synthesis.intent_templates 定义不同 intent 的报告结构。report primitive 按 intent 选 template。 ← verify: intent="comparison" → report 输出包含 side_by_side 结构

---

## F008: Capability 自进化基础 — todo

让 AVO 能创建新的 capability 组合（primitives 的新排列），并在进化过程中发现有效组合。

### 背景

当前 capabilities/ 的组合方式写死在 Python 里。AVO 应该能在 genome.phases 里创造新的 primitive 组合，测试效果，保留好的、淘汰差的。

### Steps

- [ ] S1: genome phase validation — validate_genome() 检查每个 phase 的 capabilities 列表是否全部是已注册 primitive。非法 primitive 名 → 验证失败。 ← verify: phase 包含 "nonexistent_primitive" → validation error
- [ ] S2: AVO vary structural_mutation — vary_genome() 的 structural_mutation 模式能：(a) 在现有 phases 之间插入新 phase，(b) 删除一个 phase，(c) 改变 phase 内 primitives 的顺序，(d) 把一个 phase 拆成两个。每次只做一个结构变异。 ← verify: 给定 3-phase genome → structural_mutation → 产出 2/3/4 phase genome
- [ ] S3: AVO vary crossover — 从两个不同的 seed genome 各取部分组成新 genome。规则：phases 取自 parent A，scoring 取自 parent B（或反过来）。 ← verify: crossover(engine-3phase, orchestrator-react) → 产出混合 genome
- [ ] S4: 组合发现日志 — AVO 每代记录 `mutation_type` + `mutation_detail`（具体改了什么）。方便分析哪种变异类型最有效。 ← verify: evolution.jsonl 每条新记录都有 mutation_type 和 mutation_detail
- [ ] S5: 集成测试 — 跑 5 代 AVO evolution，验证至少出现 2 种不同的 mutation_type ← verify: evolution.jsonl 包含 micro_mutation + structural_mutation（或其他组合）

---

## F009: 文档与迁移指南 — todo

更新所有相关文档，让未来的 session 和贡献者理解新架构。

### Steps

- [ ] S1: 更新 `docs/2026-03-22-system-architecture.md` — 加入 Genome-Runtime-Primitives 三层架构说明 ← verify: 文档包含三层架构图
- [ ] S2: 创建 `genome/README.md` — Genome schema 说明、字段含义、如何创建新 seed genome、如何手动修改 genome 进行实验 ← verify: 文件存在且覆盖所有 genome sections
- [ ] S3: 更新 `CLAUDE.md` — 加入 Genome 规则：(a) 不直接编辑 genome/evolved/ 里的文件（那些是 AVO 产出），(b) 新的策略决定加到 genome/defaults/ 而非 Python 代码，(c) evolution.jsonl 是 append-only ← verify: CLAUDE.md 包含 genome 相关规则
- [ ] S4: 更新 `CHANGELOG.md` — 记录架构变化 ← verify: CHANGELOG 有条目

---

## Dependency Graph

```
F001 (Schema) ──→ F002 (Seeds) ──→ F004 (Runtime) ──→ F005 (AVO Controller)
     │                                    ↑                      │
     └──→ F003 (Primitives) ─────────────┘                      │
                                                                 ↓
F006 (Code Rewire) ←── depends on F001 + F003 + F004      F008 (Self-Evolution)
     │
     ↓
F007 (last30days Patterns) ←── depends on F003 + F004 + F006

F009 (Docs) ←── after all others
```

**推荐执行顺序**：
1. F001 → F002（genome 定义，纯数据，风险最低）
2. F003（primitives 提取，重构但不改行为）
3. F004（runtime，新代码，核心模块）
4. F006（回接，逐文件改，每步可验证）
5. F005（AVO 升级，依赖 F001+F003+F004）
6. F007（last30days 融合，依赖 F003+F004+F006）
7. F008（自进化，依赖 F005）
8. F009（文档，最后）

## Decision Log

- 2026-03-28: Genome 格式选择 JSON 而非 YAML/TOML — JSON 可以被 LLM 直接生成和解析，AVO vary 时最方便
- 2026-03-28: Engagement formulas 用安全表达式字符串 — 需要 AVO 能进化公式，但不能执行任意代码。白名单 ast visitor 是最安全的方案
- 2026-03-28: 保留 capabilities/ 兼容层而非删除 — 渐进迁移，现有 orchestrator 的 tool dispatch 继续工作
- 2026-03-28: Primitives ~15 个而非更多 — 遵循"最小原子操作"原则。组合逻辑在 genome 里，不在 primitive 里
- 2026-03-28: Runtime ~200 行目标 — 解释器越小越好，策略全在 genome。如果 runtime 超过 400 行说明有策略泄漏进来了。注意：engine.py 是 1646 行，runtime 需要验证是否覆盖了所有 edge case（stale detection、harvest filtering、post-mortem pattern writing、LLM eval fallback）
- 2026-03-28: SYSTEM_PROMPT 存为外部文件引用而非内联 JSON — 51 行 prompt 内联会导致 JSON 难以编辑和 diff
- 2026-03-28: safe_eval 的 runtime formula 错误应当作 fitness penalty 而非 crash — AVO 进化可能产出语法合法但语义错误的公式（除零、缺变量），需要 graceful handling
- 2026-03-28: genome/evolved/ 需要 retention policy — 长期进化会积累数百个文件。保留 top N 个 + 最近 M 代，其余归档或删除

### Reviewer Findings (2026-03-28)

code-reviewer 审查发现 4 个 Critical + 3 个 Important 问题，已全部修复：
- C1: lexical.py 的 scoring 值是裸字面量不是命名常量 → S5 改为"设计新 config 字段"
- C2: per_query_cap 的 defaults 在 evaluation_harness.py 不是 goal_bundle_loop.py → S7/S9 修正归属
- C3: orchestrator.py 的 config 分散在各处不在特定行块 → S3 去掉错误行号引用 + SYSTEM_PROMPT 改为外部文件
- C4: search_web_broad.py 遗漏 → S2 补上
- I1: F004.S7 verify 不可执行 → 改为 fixture-based 等价测试
- I2: F006 对 F003.S14 有隐式依赖 → 补上显式 depends 标注
- I3: run_avo() 在当前代码不存在 → S3 说明是新建函数

## Open Questions

- Q1: Goal Judge (f) 的 dimension 定义本身是否也应该可进化？当前设计中 judge 是唯一固定合同，但 AVO 论文里 f 也是固定的（TFLOPS + correctness）。倾向保持固定。
- Q2: 是否需要 population-level branching（island model）？AVO 论文只做了 single-lineage。autosearch 的 3 个 seed genome 天然形成初始 population，但是否需要 MAP-Elites 式的多样性维护？
- Q3: Budget-aware variation — API 调用有成本，不能像 CUDA kernel 那样无限试。是否需要在 AVO loop 里加 cost tracking + cost-based variation selection？
- Q4: genome/evolved/ retention policy — 保留 top N + 最近 M 代？还是全部保留？population 上限多少？
- Q5: Runtime 200 行目标是否现实？engine.py 1646 行里有多少是 edge case handling（stale detection, harvest filtering, LLM eval fallback）必须在 runtime 里，不能纯靠 genome 声明式表达？需要 F004 执行时验证。
