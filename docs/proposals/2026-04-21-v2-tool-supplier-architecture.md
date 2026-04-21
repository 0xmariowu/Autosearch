# AutoSearch v2 — Tool Supplier 架构方案

> 日期：2026-04-21
> 状态：Proposal（待审批）
> 主作者：小卡拉米（基于老板口述方向）
>
> 背景文档：
> - 诊断：`experience/2026-04-21-gate-12-substance-investigation.md`
> - 工具调研：`docs/research/2026-04-21-tool-layer-strengthening.md`
> - Prior art：Agent-Reach（github.com/Panniantong/agent-reach）
> - 被评估且排除：MediaCrawlerPro（licensing 禁商 + 重依赖）

---

## 1. 定位

autosearch 从 **end-to-end pipeline**（自己做 clarify → query → channel 搜 → compact → synthesize → 交付）转成 **runtime AI 的 tool supplier**——把所有能力（渠道 / 抓取 / 转录 / 工作流）作为独立 skill 暴露，runtime AI（Claude Code / Cursor 等）自己调。autosearch 不再做 LLM 决策、不维护降级链、不做 synthesis。

等式：

```
autosearch =
    3-层暴露（L0 router / L1 14 group index / L2 80+ leaf skill）
  + 41 渠道 skill
  + 多后端工具 skill（转录 × 3 / 抓取 × 4 / mcporter 路由 / yt-dlp）
  + ~15 工作流 skill + 8 新 workflow 候选（delegate-subtask / reflective-search-loop / perspective-questioning / ...）
  + 1 clarify skill（按需）
  + Experience Layer（每 skill 挂 patterns.jsonl + experience.md，自适应成长）
  + 模型路由 metadata（frontmatter model_tier，advisory）
  + SKILL.md 路由决策清单

runtime AI = 决策主体（看 env + 偏好 + 任务 自主选 skill 组合 + 合成报告）
```

**核心理念**（老板口述）：
- **能力建设**：围绕 runtime AI 够不到的能力（中文 UGC / 学术深搜 / 转录 / 动态页）
- **恰当暴露**：分层 + progressive disclosure，runtime 一次只加载必要的
- **经验记录**：每 skill 当一个项目，session 后写 experience.md，凝练给下次用——skill 会成长
- **模型协同**：大部分 Fast 档，关键 1-2 步 Best 档

---

## 2. 为什么要改

### 2.1 Gate 12 的结构性失败

Pairwise 判官对战 native Claude：**post-W1-W6 v3 (m7 patch) vs native = 0/62 losses**。判官反复写同一句话：autosearch 输出"generic / lacks concrete identifiers / highly repetitive"。

样本直接证据（同一 E2B query）：
- native 报告有 `port 49999` / `allowInternetAccess=False` / `timeout=300_000` / `issue #786` / Python+JS SDK 代码块 / 表格
- autosearch 报告七次自述"the snippets do not contain specific information about X"

### 2.2 诊断：不是 prompt 问题，是架构问题

m3 compaction prompt 改成 verbatim（PR #207）、m7 synthesizer prompt 加硬约束（PR #205）都是必要但不充分的补丁。真正的病根是：**autosearch pipeline 把 runtime AI（Claude）当哑终端，runtime 自己的 WebSearch + judgment + synthesis 被旁路**。原料层（M5 channel 只用 ddgs 10 条）够不到 specifics，下游 prompt 再好也是 preserve 空气。

### 2.3 Prior art 验证

Agent-Reach 走的正是"给 runtime AI 装互联网能力"路线——装机完成后自己退出数据流，只留 SKILL.md 路由表 + 上游工具（yt-dlp / gh / mcporter / Jina Reader）。它**明确拒绝做** query decomposition / compaction / synthesis / end-to-end runner——正好是 autosearch 现在做得最差的层。

路线对比结论：
- A. Agent-Reach 式 tool supplier → **推荐**
- B. open_deep_research 式独立 pipeline → 当前模式，Gate 12 架构性输
- C. OpenManus 式 agent framework → 自造 runtime，对抗 Claude 更难

---

## 3. 完整能力全景

### 3.0 Skill 分层结构（progressive disclosure）

runtime AI 每 session 不加载 80 份 SKILL.md 全文（会吃 token）。**三层 + 混合 trigger**：

| 层 | session 初始可见 | 内容 | token 预算 |
|---|---|---|---|
| **L0 router/meta** | 3-5 个短 SKILL.md 常驻 | `autosearch:router` / `model-routing` / `experience-policy` / `clarify` | 极短 |
| **L1 group index** | 14 个 group skill 按需 | 中文 UGC / 中文技术媒体 / 学术 / 代码包 / 产品市场 / 英文社区 / 社交职业 / 通用搜索 / 视频音频 / fetch 工具 / workflow-planning / workflow-quality / workflow-synthesis / workflow-growth | router 命中后读 |
| **L2 leaf skill** | 80+ 个具体 skill | 41 渠道 + 工具后端 + workflow + 8 新候选 | 执行前读 |

**Trigger 6 条规则**（Codex 第二轮调研 §1.2 落地）：
1. keyword trigger 先行（平台名 / 域名 / 明显意图直接命中）
2. domain tag 兜底（`chinese-ugc` / `academic` / `code` / `web-fetch` / `workflow-*`）
3. scenario tag 处理跨域（`recency` / `verification` / `coding` / `deep-research`）
4. LLM lazy load 只在歧义时用
5. `description` 保持 Anthropic-compatible（第一句自然语言触发）
6. 质量/成本 metadata（`model_tier` / `auth_required` / `chinese_native`）单独放，不进正文加载

### 3.1 渠道层（41 个 skill，7 类）

| 类别 | Skill |
|---|---|
| **中文 UGC（10）** | search-bilibili / search-weibo / search-xiaohongshu / search-douyin / search-zhihu / search-xiaoyuzhou（小宇宙播客）/ search-wechat / search-kuaishou / search-v2ex / search-xueqiu |
| **中文技术媒体（5）** | search-36kr / search-csdn / search-juejin / search-infoq-cn / search-sogou-weixin |
| **学术（11）** | search-arxiv / search-google-scholar / search-semantic-scholar / search-papers-with-code / search-openreview / search-conference-talks / search-citation-graph / search-author-track / search-openalex / search-crossref / search-paper-list |
| **代码 / 包（5）** | search-github-repos / search-github-code / search-github-issues / search-npm-pypi / search-huggingface |
| **市场 / 产品（3）** | search-crunchbase / search-producthunt / search-g2-reviews |
| **英文开发者社区（5）** | search-stackoverflow / search-hackernews / search-devto / search-reddit / search-reddit-exa |
| **社交 / 职业（3）** | search-twitter-exa / search-twitter-xreach（付费）/ search-linkedin |
| **通用搜索引擎（5）** | search-ddgs / search-exa / search-tavily / search-searxng（第三波）/ search-hn-exa |
| **视频 / 源（2）** | search-youtube / search-rss |

**硬核中文反爬**：bilibili / weibo / xiaohongshu / douyin / zhihu 5 平台有 **TikHub 付费兜底**（$0.0036/请求，BYOK）。

### 3.2 工具层（backend-per-skill 模式）

每个后端独立 skill 暴露，runtime AI 看 env + 偏好自选。autosearch 不做降级链。

**转录（3 档）**

| Skill | 成本 | 依赖 | 来源 |
|---|---|---|---|
| video-to-text-local | 免费 | Apple Silicon + LM Studio + MLX Whisper | 搬自本地 video2text skill 的三段 pipeline |
| **video-to-text-groq** | **免费** API | `GROQ_API_KEY`（注册即得） | 新增（推荐默认） |
| video-to-text-openai | $0.006/min | `OPENAI_API_KEY` | 新增（付费兜底） |

转录 tool 只返回 `raw.txt + subtitle.srt + meta.json + audio.mp3`，**不做 summary**——长转录由 runtime AI 自己处理（分段 / 调 Groq 免费 `llama-3.3-70b`/ 任意策略）。

**网页抓取（4 档）**

| Skill | 成本 | 能力 |
|---|---|---|
| **fetch-jina** | 免费 | Jina Reader `r.jina.ai/<URL>`，任意 URL → markdown。第一层 fast path |
| **fetch-crawl4ai** | 免费 | Python lib，JS 渲染 / Playwright / anti-bot / deep crawl |
| **fetch-playwright** | 免费 | Playwright MCP，交互式（点击 / 输入 / 截图）动态页兜底 |
| fetch-firecrawl | 付费 | Firecrawl hosted，最强兜底（第三波可选） |

**视频音频下载**

- **yt-dlp**（CLI 依赖）—— bilibili / youtube / douyin / 播客 通用音视频抽取，转录前置步骤

**MCP 路由**

- **mcporter + 免费 MCP** —— 路由 Exa 全网语义 / 微博 / 抖音 / LinkedIn 等免费 MCP server，零 key

**已有保留**

- fetch-webpage（后端改用 fetch-jina / fetch-crawl4ai）
- follow-links / extract-knowledge / knowledge-map

### 3.3 澄清层（1 个）

**M1 Clarifier**：4 问把模糊 query 变 enriched intent。

- 旧：always-on pipeline stage，导致 zh 技术 query "最佳指南" 直接 exit 2
- 新：**按需 skill**，runtime AI 判定 query 模糊时主动调

```
autosearch:clarify(query)
  → { needs_clarify: bool, questions: [..], enriched_query: str }
```

### 3.4 工作流层（~15 个，给 runtime AI 自取）

**决策辅助**：discover-environment / observe-user / research-mode / provider-health / select-channels

**查询生成**：systematic-recall / use-own-knowledge / decompose-task / gene-query / consult-reference

**证据处理**：normalize-results / rerank-evidence / anti-cheat / extract-dates / llm-evaluate / assemble-context

**知识产出**：extract-knowledge / knowledge-map / synthesize-knowledge / evaluate-delivery

**元 skill**：create-skill / auto-evolve / outcome-tracker / goal-loop / pipeline-flow / interact-user

### 3.5 Experience Layer（每 skill 当项目，自适应成长）

**核心理念**：**每个 skill 当一个项目**。session 结束后，参与的 skill 记录"本次使用的经验"到 `experience.md`，凝练成下次可用规则。skill 本身在成长。

**每 skill 下挂两个文件**：

```
skills/search-xiaohongshu/
  SKILL.md              # 定义：名字 / 描述 / trigger / tier
  experience/
    patterns.jsonl      # append-only 原始事件，runtime 不读
  experience.md         # ≤ 120 行凝练摘要，runtime 执行前按需读
```

**patterns.jsonl schema**（每次 skill 执行后追加）：

```json
{
  "ts": "2026-04-21T22:40:00+08:00",
  "session_id": "2026-04-21-round2",
  "skill": "search-xiaohongshu",
  "group": "channels-chinese-ugc",
  "task_domain": "product-research",
  "query_type": "recent-user-opinion",
  "input_shape": "brand + feature + 近30天",
  "method": "tikhub:xhs_search",
  "outcome": "success",
  "metrics": {"yield": 18, "relevant": 9, "latency_ms": 4200, "cost_usd": 0.02, "user_feedback": "accepted"},
  "winning_pattern": "品牌词 + 痛点词 + 近30天 比 '评测' 召回更准",
  "failure_mode": null,
  "good_query": "某品牌 某功能 翻车 2026",
  "bad_query": "某品牌 评测",
  "promote_candidate": true
}
```

**experience.md 格式**：

```markdown
# search-xiaohongshu experience

## Active Rules          # ≤ 20 条
- For product complaint discovery, combine brand + pain word + recent date window.
- Use TikHub first when browser search returns marketing pages.

## Failure Modes          # ≤ 15 条
- Generic `评测` queries over-return influencer content.

## Good Query Patterns    # ≤ 20 条
- `{brand} {feature} 翻车 2026`
- `{category} 避雷 小红书 最近`

## Last Compacted
- 2026-04-21, from 37 events, promoted 3 rules, archived raw events before 2026-04-01.
```

**凝练 pipeline**：

1. **执行后写事件** — 由新 workflow skill `experience-capture`（Fast tier，无 LLM 也可）自动追加 patterns.jsonl
2. **触发凝练** — 任一条件满足即运行 `experience-compact`（Standard tier）：
   - 该 skill 新增事件 ≥ 10 条
   - patterns.jsonl > 64 KB
   - 用户显式反馈 accepted / rejected
   - session 结束且该 skill 本次被用过
3. **AVO 只 promote 到 experience.md**，**不直接改 SKILL.md**
4. **runtime 只读 digest**（experience.md），raw JSONL 供离线分析
5. **提升阈值**：同一规则 `seen ≥ 3` 且 `success ≥ 2` 且 `last_verified ≤ 30d` 才能进 Active Rules

**膨胀防御**：
- experience.md 硬上限 120 行
- Active Rules / Failure Modes / Good Query Patterns 各有条数上限（20/15/20）
- raw patterns.jsonl 按月归档到 `experience/archive/YYYY-MM.jsonl`

**反污染**：
- 单次成功不能进 Active Rules，必须重复证据
- 用户纠错 / rubric failure / 低 relevance 事件只能进 Failure Modes
- 每条规则必须带来源计数：`seen=5, success=4, last_verified=2026-04-21`

### 3.6 模型路由 metadata（advisory，不绑供应商）

autosearch 作为 tool supplier 不能控制 runtime AI 用哪个模型，但可以**打 tier 建议**。runtime AI 读 tag 自行路由。

**frontmatter 最小改动**：

```yaml
model_tier: Fast | Standard | Best
model_routing:
  fast_ok_for: [retrieval, schema normalization]
  upgrade_to_standard_when: [conflicting evidence needs semantic ranking]
  upgrade_to_best_when: [final synthesis or skill evolution depends on this output]
```

**分档原则**（90+ skill 完整表见 Codex 第二轮 §3.3）：

| Tier | 定位 | 典型 skill | 数量 |
|---|---|---|---|
| **Best**（关键 1-2 步） | 错了后续全错 | clarify / decompose-task / systematic-recall / synthesize-knowledge / evaluate-delivery / check-rubrics / create-skill / auto-evolve / goal-loop / knowledge-map / graph-search-plan / perspective-questioning / reflective-search-loop | ~13 |
| **Standard** | 语义判断但可结构化 | select-channels / gene-query / rerank-evidence / llm-evaluate / anti-cheat / extract-knowledge / fetch-crawl4ai / fetch-playwright / experience-compact / trace-harvest | ~20 |
| **Fast**（大多数执行步骤） | 检索 / 清洗 / 执行 | 全部 41 个 search-* / fetch-jina / yt-dlp / video-to-text × 3 / mcporter / normalize / extract-dates / router / experience-capture | ~60 |

**新增 meta skill**：`autosearch:model-routing` — 给 runtime AI 一张三档解释表和升级条件。

### 3.7 新增 8 个 workflow skill 候选（prior art 第二轮提取）

来源：MiroThinker / WebThinker / STORM / node-deepresearch / MindSearch / deepagents / DeepResearchAgent / last30days-skill（详见第二轮调研笔记）

| 新 skill | tier | why autosearch 需要 | 来源 prior art |
|---|---|---|---|
| **delegate-subtask** | Standard | 子任务隔离执行契约：输入 + 预算 + 返回摘要 + 证据 + 失败状态。`decompose-task` 只拆不定义执行契约 | MiroThinker + deepagents + deer-flow + DeepResearchAgent |
| **trace-harvest** | Standard | 从成功 session trace 提炼经验。`outcome-tracker` 只记 downstream，不解析 tool trace 成功路径 | MiroThinker + DeepResearchAgent |
| **reflective-search-loop** | Best | 显式维护 gaps / visited URLs / bad URLs / evaluator 失败反馈。现有步骤 skill 不拥有循环状态 | WebThinker + node-deepresearch + Scira |
| **perspective-questioning** | Best | 多 persona / 利益相关方 / 专家视角生成问题，提升覆盖面。`decompose-task` 偏任务结构不模拟视角 | STORM |
| **citation-index** | Standard | URL 去重 / 统一编号 / 跨 section / subagent citation merge。`synthesize-knowledge` 会写引用但无独立状态 | STORM + deepagents |
| **graph-search-plan** | Best | 研究计划表示为 graph（节点 / 边 / 并发无关节点）。现有 planning 是 list/tree | MindSearch |
| **recent-signal-fusion** | Standard | 跨源近期信号统一成 SourceItem/Candidate/Cluster，专注最近 7/30 天 | last30days-skill + Scira |
| **context-retention-policy** | Fast | session 级 keep-last-k / offload / compact 策略。`assemble-context` 是证据组装不是上下文保留 | MiroThinker + deepagents + deer-flow |

### 3.8 外部依赖（BYOK，optional）

所有 key 统一放 `~/.config/ai-secrets.env`。autosearch 用 `requires: [env:XXX]` 声明，用户未配时 skill 报错引导配置。

| Key | 用途 | 成本 |
|---|---|---|
| `TIKHUB_API_KEY` | 小红书 / 微博 / 知乎 / Twitter / 抖音 5 硬核平台深度 | $0.0036/请求 |
| `GROQ_API_KEY` | Whisper 转录免费 + llama-3.3-70b 免费 LLM | **免费** |
| `OPENAI_API_KEY` | Whisper 付费兜底 + 其他 | $0.006/min |
| `EXA_API_KEY` | 全网语义搜索 | 付费 |
| `TAVILY_API_KEY` | 研究级搜索 | 付费 |
| `FIRECRAWL_API_KEY` | 最强 JS 页抓取（第三波） | 付费 |

---

## 4. 被砍除

- `lib/search_runner.py` —— end-to-end orchestrator
- `autosearch/skills/prompts/m3_evidence_compaction.md` —— specifics 黑洞
- `autosearch/skills/prompts/m7_section_write*.md` —— LLM synthesis 交还 runtime
- 自创 N-dim × 0/3/5 rubric —— feedback memory 已记"AI judge 留，自创 rubric 丢"
- Always-on clarify pipeline stage —— 改按需 skill

---

## 5. 入口与路由

**主入口**：Claude Code plugin + `SKILL.md` 路由决策清单（不是 MCP server 主导）
- plugin 已有（`.claude-plugin/plugin.json`）
- 70+ skill 已注册为 `autosearch:*` 加载到系统
- SKILL.md 重写成"给 runtime AI 的决策清单"—— 不写"该用哪个"，写"按 env + 场景选哪个"

**次入口**：MCP server 仅暴露 3 个运维 tool
```
autosearch.doctor()        → 各 skill 健康检查
autosearch.configure(k, v) → BYOK 配置辅助
autosearch.list_channels() → 能力目录
```

**第三方 MCP**：通过 mcporter 路由 Exa / 微博 / 抖音 / LinkedIn 等免费 MCP

---

## 6. 落地路线（三波）

### 第一波 — 工具层补强 + metadata 框架（无依赖，可立即开工）

**工具层**：
1. **验前提**（10 分钟）：`claude -p --dangerously-skip-permissions` 加载 plugin skills 验证
2. **fetch-jina** skill 新建 + 替换 `fetch-webpage` 后端（S）
3. **fetch-crawl4ai** skill 新建（M）
4. **fetch-playwright** skill 新建 + MCP config（S）
5. **yt-dlp** 装为 autosearch 依赖（S）
6. **video-to-text-groq** / **video-to-text-openai** / **video-to-text-local** 三 skill 从现有本地 video2text pipeline 拆分搬迁（M）
7. **mcporter + 免费 MCP** 路由层（S）

**分层 + metadata 基础**（低成本，不改 loader）：

8. 新增 `autosearch:router` + 14 个 group index 文件（文档入口，`docs/skill-format.md` 未知字段先放着不破坏现有 loader）（S）
9. 给现有 leaf skill frontmatter 加 `layer / domains / scenarios / model_tier / experience_digest` 字段（M，批量改 80+ 文件）
10. 新增 `autosearch:model-routing` meta skill（S）

### 第二波 — 架构主体（依赖第一波）

11. **砍 m3 / m7 / search_runner.py**（破坏性改动，M）
12. **M1 Clarifier** 从 pipeline stage 改为按需 skill（S）
13. **SKILL.md 路由表重写** —— 70+ skill 按 3.0 三层分组 + 运行时决策清单（M）
14. **TikHub SKILL.md 路由化** —— 5 硬核平台明确"先免费 native → TikHub 兜底"决策树（S）
15. **select-channels** 改成先读 group index 再挑 leaf（避免 runtime 看 80 平铺）（S）
16. **Gate 12 新 bench framing** —— `claude -p + skills` vs `claude -p 裸` bench 脚本（S）
17. **CHANGELOG + 3-commit + Closes-#N** workflow 遵守（每 PR 自带）

### 第三波 — Experience Layer kick-off + 新 workflow skill

**经验沉淀实验**（先 2 个高频 skill 试）：

18. 新增 `experience-capture` workflow skill（Fast tier，自动追加 patterns.jsonl）（S）
19. 新增 `experience-compact` workflow skill（Standard tier，凝练到 experience.md）（M）
20. **kick-off 实验**：`search-xiaohongshu` + `select-channels` 两个高频 skill 先挂 experience layer（M）
21. 观察 2 周，验证膨胀防御 + 反污染规则有效，再推广全 skill

**8 个新 workflow skill**（按 §3.7 候选清单，按优先级分批）：

22. **delegate-subtask**（必备，给深研任务用）
23. **reflective-search-loop**（Best，替代旧 pipeline 的循环价值）
24. **citation-index**（Standard，合成必备）
25. 其余 5 个按需（trace-harvest / perspective-questioning / graph-search-plan / recent-signal-fusion / context-retention-policy）

### 第四波 — 可选扩展

26. **SearXNG** 自托管 SERP 聚合（替代 web-ddgs 单点风险）
27. **fetch-firecrawl** 付费兜底
28. **渠道扩展候选**：百度贴吧 / Instagram / Threads / Polymarket / GitLab / Bitbucket / Mastodon / NVD / PubMed / Docker Hub / Crates / Packagist / RubyGems / Pub.dev（通过 SearXNG 聚合）

---

## 7. Gate 12 评估新 framing

### 旧（必输）
- A：autosearch CLI end-to-end
- B：`claude -p` 裸
- 结果：0/62 losses（autosearch 是 runtime 对手）

### 新（可赢）
- A：`claude -p --dangerously-skip-permissions` + autosearch skill bundle 已加载
- B：`claude -p --dangerously-skip-permissions` 裸
- 判官：`scripts/bench/judge.py pairwise`（不变）
- 成功标准：**A 组 win rate ≥ 50%**（A 组是纯增益，理论下限 = 平局）

前提验证：`claude -p --dangerously-skip-permissions` 能否加载 plugin skills？若不加载，需改用 `--allowedTools autosearch:*` 或在 bench 脚本注入 skill context。

---

## 8. v1.0 Positioning 重写

不再 claim "beats native Claude"。改 claim：

> **AutoSearch augments native Claude with 41 curated channels (especially Chinese UGC, academic, developer community) and multi-backend web tools (Jina / crawl4ai / Playwright / Whisper), exposed as skill library. Runtime AI stays in control — autosearch is the toolbox, not another pipeline.**

Gate 12 new framing win rate ≥ 50% → v1.0 tag。

---

## 9. 风险与开放问题

### 9.1 一般风险

| 风险 | 应对 |
|---|---|
| headless plugin 加载未验 | 第一波先 10 分钟前置验证；失败则改 `--allowedTools` 或 skill 注入 |
| TikHub 覆盖外硬核反爬（微博 flaky / Instagram / LinkedIn）仍弱 | 接受 trade-off（C 路线选择）；第四波用 SearXNG + last30days pattern 补 |
| runtime AI 不触发 skill 的概率 | SKILL.md 路由清单要明确"何时调哪个"；触发率作为 Gate 12 new bench 监控指标 |
| frontmatter 膨胀 | trigger keyword 表太长抵消分层收益；group index 保持短表，长规则放 references / experience digest |
| CHANGELOG / 3-commit / Closes-#N / no-issue-link 要求 | 每 PR 开单前备齐；否则 CI 直接挡 |
| pre-push 强制 rebase on main | PR 并发多时 iterative rebase loop，老板授权 `--force-with-lease` |
| MediaCrawlerPro / Firecrawl AGPL / 商用限制 | 方案已主动排除；未来如引入必须另评 |
| Loader 未知 frontmatter 字段 | 先把新字段放 router/group 文档，避免破坏现有 loader；稳定后再并入 `docs/skill-format.md` |
| runtime 不遵守 model_tier | autosearch 只能 advisory；报告和 SKILL.md 明确这是建议不是强制 |

### 9.2 AVO 自进化——7 条硬约束（老板重点提醒）

老板 2026-04-21："AVO 进化本身有空要注意"。AVO 是自改 skill 的机器，失控会把系统带歪。边界如下：

1. **AVO 永不改 `judge.py` 和 `PROTOCOL.md`**（项目 CLAUDE.md §14）——判官和契约是固定的
2. **AVO 永不改 meta skill**（`create-skill` / `observe-user` / `extract-knowledge` / `interact-user` / `discover-environment`）——这是 DNA 复制机器不是基因
3. **AVO 修改 SKILL.md 必须走 git commit，可 revert**（CLAUDE.md §17）——失败自动 revert
4. **分层保护**：AVO 默认只 promote rule 到 `experience.md`，**不直接改 SKILL.md 正文**。只有规则连续命中阈值（`seen ≥ 3 + success ≥ 2 + last_verified ≤ 30d`）才触发 `auto-evolve` 提议改 SKILL.md
5. **Append-only 状态永不删**：`patterns.jsonl` / `evolution-v1.jsonl` / `outcomes.jsonl`（CLAUDE.md §16）
6. **失速保护**：stagnation detected（连续 N 轮 rubric 不涨 / 失败 repeat 3+ 次相同 diagnosis）→ 暂停 `auto-evolve`，不猛踩油门等老板 check
7. **反污染 + 膨胀防御**：
   - 单次成功不足以提 Active Rule（必须 `seen ≥ 3`）
   - 用户纠错 / rubric failure 只能进 Failure Modes，永远不能进 Active Rules
   - experience.md ≤ 120 行硬上限，Active Rules ≤ 20 条，超了必须归档旧规则
   - patterns.jsonl 按月归档到 `experience/archive/YYYY-MM.jsonl`，保留 raw 但 runtime 不读

### 9.3 隐私 / 安全

- `patterns.jsonl` 可能记录用户 query 和证据 URL；对 private URL / 账号 / cookie 相关字段做脱敏或 hash
- 全局 secret 只走 `~/.config/ai-secrets.env`，skill frontmatter 和 experience.md 永不写明文 key

---

## 10. 下一步

- [ ] 老板审批本方案
- [ ] 验前提：headless plugin 加载（10 分钟）
- [ ] `/plan-to-issues` 将本方案 §6 三波拆成 GitHub issue
- [ ] 按 issue 派 Codex 开工第一波 PR（Jina / crawl4ai / Playwright / yt-dlp / Groq / mcporter）
- [ ] 第二波开工需等第一波第一批工具可用后
- [ ] Gate 12 new bench 在第二波 §12 落地后跑第一轮基线
