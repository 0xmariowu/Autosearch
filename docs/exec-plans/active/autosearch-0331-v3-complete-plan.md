# AutoSearch v3.0 — 完整重构计划

## Goal

AutoSearch = Claude 的知识 × 渠道发现能力。通过 38 个搜索渠道 + 精简 pipeline + AVO 自我进化，在内容广度、深度、速度、成本上全面超越 native Claude。

## 定位

Native Claude = 聪明教授凭记忆回答
AutoSearch = 同一个教授 + 38 个研究助手 + 图书馆 + 引用数据库 + 跨 session 记忆

## 架构：5 步 Pipeline

```
Phase 1: 回忆 + 规划 → Phase 2: 增量搜索 → Phase 3: 清洗评估 → Phase 4: 综合交付 → Phase 5: 学习
```

---

## Part A: 渠道 Skills（38 个）

### A1. 通用搜索（3 个，已有）

| # | Skill | 搜索方法 | 需安装 |
|---|-------|---------|--------|
| 1 | search-ddgs | WebSearch / ddgs CLI | 否 |
| 2 | search-searxng | SearXNG 实例 | 需本地实例 |
| 3 | search-tavily | Tavily API | 需 API key |

### A2. 代码/项目平台（5 个，已有 3 个）

| # | Skill | 搜索方法 | 需安装 |
|---|-------|---------|--------|
| 4 | search-github-repos | `gh search repos` | 否（gh 已有） |
| 5 | search-github-issues | `gh search issues` | 否 |
| 6 | search-github-code | `gh search code` | 否 |
| 7 | search-stackoverflow | `WebSearch site:stackoverflow.com` | 否 |
| 8 | search-npm-pypi | `WebSearch site:npmjs.com` 或 `site:pypi.org` | 否 |

### A3. 学术/研究（6 个，已有 3 个）

| # | Skill | 搜索方法 | 需安装 |
|---|-------|---------|--------|
| 9 | search-exa | Exa API (MCP) | 需 MCP |
| 10 | search-citation-graph | Semantic Scholar API | 否（HTTP） |
| 11 | search-author-track | Semantic Scholar API | 否 |
| 12 | search-openreview | OpenReview API / WebSearch | 否 |
| 13 | search-papers-with-code | `WebSearch site:paperswithcode.com` | 否 |
| 14 | search-google-scholar | `WebSearch site:scholar.google.com` | 否 |

### A4. 英文社区/社交（5 个，部分已有）

| # | Skill | 搜索方法 | 需安装 |
|---|-------|---------|--------|
| 15 | search-hackernews | Algolia HN API / WebSearch | 否 |
| 16 | search-reddit | WebSearch / Exa | 否 |
| 17 | search-twitter | bird CLI (Agent-Reach) | 需安装 bird |
| 18 | search-linkedin | MCP browser (Agent-Reach) | 需 Docker |
| 19 | search-devto | `WebSearch site:dev.to` | 否 |

### A5. 中文平台（8 个，全新，核心增量）

| # | Skill | 搜索方法 | 需安装 | Claude 增量 |
|---|-------|---------|--------|-----------|
| 20 | search-zhihu | `WebSearch site:zhihu.com` | 否 | 中文技术 Q&A |
| 21 | search-csdn | `WebSearch site:csdn.net` | 否 | 中文开发教程 |
| 22 | search-juejin | `WebSearch site:juejin.cn` | 否 | 中文前沿分享 |
| 23 | search-bilibili | yt-dlp 提取字幕 | 需 yt-dlp | 技术视频内容 |
| 24 | search-xiaohongshu | Docker MCP (Agent-Reach) | 需 Docker | 使用体验评测 |
| 25 | search-wechat | camoufox (Agent-Reach) | 需安装 | 深度行业文章 |
| 26 | search-36kr | `WebSearch site:36kr.com` | 否 | 中国科技商业 |
| 27 | search-infoq-cn | `WebSearch site:infoq.cn` | 否 | 企业技术实践 |

### A6. 商业/产品（3 个，全新）

| # | Skill | 搜索方法 | 需安装 |
|---|-------|---------|--------|
| 28 | search-producthunt | `WebSearch site:producthunt.com` | 否 |
| 29 | search-crunchbase | `WebSearch site:crunchbase.com` | 否 |
| 30 | search-g2-reviews | `WebSearch site:g2.com` | 否 |

### A7. 视频/音频（3 个，全新）

| # | Skill | 搜索方法 | 需安装 |
|---|-------|---------|--------|
| 31 | search-youtube | yt-dlp 提取字幕/元数据 | 需 yt-dlp |
| 32 | search-podcast | 小宇宙 + Whisper / WebSearch | 可选 |
| 33 | search-conference-talks | `WebSearch "{conference} {year} talks site:youtube.com"` | 否 |

### A8. 其他数据源（5 个）

| # | Skill | 搜索方法 | 需安装 |
|---|-------|---------|--------|
| 34 | search-huggingface | HF API | 否 |
| 35 | search-weibo | API (Agent-Reach) | 可选 |
| 36 | search-v2ex | API (Agent-Reach) | 可选 |
| 37 | search-rss | feedparser (Agent-Reach) | 需安装 |
| 38 | search-paper-list | gh search awesome-lists (AVO 自创) | 否 |

### 渠道汇总

| 类别 | 数量 | 零安装可用 | 需安装 |
|------|------|-----------|--------|
| 通用搜索 | 3 | 1 | 2 |
| 代码/项目 | 5 | 5 | 0 |
| 学术/研究 | 6 | 5 | 1 |
| 英文社区 | 5 | 3 | 2 |
| 中文平台 | 8 | 5 | 3 |
| 商业/产品 | 3 | 3 | 0 |
| 视频/音频 | 3 | 1 | 2 |
| 其他数据源 | 5 | 2 | 3 |
| **合计** | **38** | **25** | **13** |

**25 个渠道零安装立刻可用**（只需 WebSearch site: 或已有的 gh CLI）。

---

## Part B: Pipeline Skills（15 个）

### Phase 1: 回忆 + 规划（5 个）

| # | Skill | 必须/可选 | 作用 |
|---|-------|----------|------|
| 1 | systematic-recall | 必须 | 9 维知识扫描，出知识骨架 |
| 2 | knowledge-map | 必须 | 加载/保存跨 session 知识 |
| 3 | research-mode | 必须 | scope 定义 + 搜索预算 |
| 4 | decompose-task | 可选 | 复杂 topic 拆子问题 |
| 5 | select-channels | 必须 [新] | 从 38 渠道选 5-10 个最相关的 |

### Phase 2: 搜索支持（3 个）

| # | Skill | 必须/可选 | 作用 |
|---|-------|----------|------|
| 6 | gene-query | 必须 | gap-driven query 生成 |
| 7 | fetch-webpage | 可选 | 深度内容抓取 |
| 8 | follow-links | 可选 | 跟 awesome-list 链接 |

### Phase 3: 清洗评估（4 个）

| # | Skill | 必须/可选 | 作用 |
|---|-------|----------|------|
| 9 | normalize-results | 必须 | 统一格式 + 去重 |
| 10 | extract-dates | 必须 | 新鲜度元数据 |
| 11 | llm-evaluate | 必须 | 相关性判断 + gap 检测 |
| 12 | anti-cheat | 可选 | 防刷分（AVO 场景） |

### Phase 4: 综合交付（3 个）

| # | Skill | 必须/可选 | 作用 |
|---|-------|----------|------|
| 13 | synthesize-knowledge | 必须 | 概念框架 + 引用 + 增量标注 |
| 14 | evaluate-delivery | 必须 | 4 维质检 |
| 15 | assemble-context | 可选 | token 预算管理（大结果集时） |

### 新增 Skill: select-channels.md

38 个渠道不可能每次都全搜。需要一个 skill 来智能选择：

**输入**：topic + knowledge map gaps + research mode
**输出**：5-10 个最相关渠道
**逻辑**：
- 中文 topic → 加知乎、CSDN、B站
- 学术 topic → 加 Semantic Scholar、OpenReview、Google Scholar
- 产品调研 → 加 Product Hunt、Crunchbase、G2
- 社区声音 → 加 Reddit、HN、Twitter
- 最新动态 → 加 GitHub (created:recent)、web search + 年份
- 参考 patterns.jsonl 的渠道-topic 匹配记录

AVO 可以进化这个 skill 的选择逻辑。

---

## Part C: AVO 进化基础设施（4 个）

| # | Skill | 作用 |
|---|-------|------|
| 1 | consult-reference | 查 1,063 条 skill 参考库 |
| 2 | create-skill (meta, 不可改) | AVO 创建新 skill |
| 3 | discover-environment (meta, 不可改) | 扫描可用工具 |
| 4 | extract-knowledge (meta, 不可改) | 提取知识写 patterns |

加上 judge.py（8 维评分）和 state 文件（patterns、knowledge-maps、skill-reference）。

---

## 总技能清单

| 类别 | 数量 |
|------|------|
| 渠道 Skills | 38 |
| Pipeline Skills | 15 |
| AVO 基础设施 | 4 (含 3 meta) |
| **总计** | **57** |

当前已有：43 个（含重叠）
需新建：~20 个（主要是渠道 skills）
需安装工具后启用：13 个

---

## 执行计划

### F001: 零安装渠道 Skills 批量创建 — todo

25 个只需 `WebSearch site:` 的渠道，Codex 批量写。

#### Steps
- [ ] S1: 定义统一的 site-search platform skill 模板（description 格式、中英文 query 示例、output schema、date metadata、Quality Bar）← verify: 模板完整
- [ ] S2: Codex 批量创建 25 个 skill 文件（5 并行 × 5 批）← verify: 25 个文件，每个符合 rule 16 标准
- [ ] S3: 新建 select-channels.md ← verify: 有渠道分类逻辑、有 topic-渠道匹配规则

渠道列表（25 个零安装）：
1. search-stackoverflow (site:stackoverflow.com)
2. search-npm-pypi (site:npmjs.com / site:pypi.org)
3. search-papers-with-code (site:paperswithcode.com)
4. search-google-scholar (site:scholar.google.com)
5. search-devto (site:dev.to)
6. search-zhihu (site:zhihu.com)
7. search-csdn (site:csdn.net)
8. search-juejin (site:juejin.cn)
9. search-36kr (site:36kr.com)
10. search-infoq-cn (site:infoq.cn)
11. search-producthunt (site:producthunt.com)
12. search-crunchbase (site:crunchbase.com)
13. search-g2-reviews (site:g2.com)
14. search-conference-talks (site:youtube.com + conference query)
15. search-hackernews (已有，保留)
16. search-reddit (已有，保留)
17. search-huggingface (已有，保留)
18. search-github-repos (已有，保留)
19. search-github-issues (已有，保留)
20. search-github-code (已有，保留)
21. search-exa (已有，保留)
22. search-citation-graph (已有，保留)
23. search-author-track (已有，保留)
24. search-openreview (已有，保留)
25. search-paper-list (AVO 创建，保留)

### F002: Agent-Reach 渠道 Skills — todo

13 个需要安装工具的渠道。

#### Steps
- [ ] S1: `pip install agent-reach && agent-reach install --env=auto` ← verify: agent-reach doctor 全绿
- [ ] S2: 为 Agent-Reach 渠道创建 skill 文件（调用对应 CLI）← verify: 13 个文件
  - search-bilibili (yt-dlp)
  - search-youtube (yt-dlp)
  - search-xiaohongshu (MCP)
  - search-wechat (camoufox)
  - search-twitter (bird CLI)
  - search-linkedin (MCP browser)
  - search-weibo (API)
  - search-douyin (MCP)
  - search-xueqiu (API)
  - search-xiaoyuzhou (Whisper)
  - search-v2ex (API)
  - search-rss (feedparser)
  - search-podcast (Whisper)

### F003: Pipeline Skills 优化 — todo

简化 pipeline，确保 5 步流程顺畅。

#### Steps
- [ ] S1: 新建 select-channels.md — 38 渠道智能选择器 ← verify: 有分类逻辑、有 topic 匹配规则、AVO 可进化
- [ ] S2: 简化 PROTOCOL.md — 等等，不可改。改为写一个新的 mutable skill `pipeline-flow.md` 描述 5 步流程，引导 agent 按正确顺序使用 skills ← verify: 5 步清晰，每步引用对应 skills
- [ ] S3: 确保所有 pipeline skills 一致引用新的渠道 skills ← verify: normalize-results schema 覆盖所有 source tags

### F004: 三路对比验证（v3.0 版）— todo

用完整渠道集重跑对比。

#### Steps
- [ ] S1: v3.0 AutoSearch（38 渠道 + 5 步 pipeline）跑 Topic 1 ← verify: evidence + delivery
- [ ] S2: Native Claude 同 query ← verify: 输出保存
- [ ] S3: 对比表 ← verify: 渠道覆盖、内容类型、速度、深度全维度比较
- [ ] S4: 重点验证：中文平台增量、商业产品增量、视频内容增量 ← verify: 这些 native Claude 必须 = 0，AutoSearch > 0

### F005: AVO 进化验证 — todo

#### Steps
- [ ] S1: AVO 能否学习渠道-topic 匹配 ← verify: patterns 记录渠道增量率
- [ ] S2: AVO 能否发现并创建缺失渠道 ← verify: E3 已验证，确认在 v3.0 仍工作
- [ ] S3: 多 session 累积（3 session 同 topic）← verify: knowledge map 增长 + 搜索效率提升

### F006: 文档收尾 — todo

#### Steps
- [ ] S1: CHANGELOG.md — v3.0 entry
- [ ] S2: HANDOFF.md — 完整渠道列表 + pipeline 说明
- [ ] S3: AIMD 经验笔记
- [ ] S4: CLAUDE.md 更新（渠道 skill 命名规范 + select-channels 规则）

---

## Decision Log

- 2026-03-31: 渠道是 AutoSearch 最大的增量价值。38 个渠道 = 38 个 Claude 搜不到的内容源。
- 2026-03-31: 25 个渠道零安装可用（WebSearch site:），立刻可以创建。
- 2026-03-31: Agent-Reach 的 16 个渠道直接转化为 skill 文件，不是"安装 Agent-Reach 作为依赖"。
- 2026-03-31: Pipeline 简化到 5 步，不做无效中间 I/O。
- 2026-03-31: AVO 进化目标 = 增量发现率（AutoSearch 找到但 Claude 找不到的内容占比）。
- 2026-03-31: select-channels.md 是新的关键 skill — 38 个渠道不能每次都全搜，需要智能选择。
- 2026-03-31: judge.py 保留但定位变化：从"唯一评估标准"变为"其中一个信号"。增量发现率才是核心指标。

## 执行优先级

```
F001（25 零安装渠道）→ F003（pipeline 优化）→ F004（验证）
                ↓
    F002（13 需安装渠道，和 F001 并行或稍后）→ F005（AVO 验证）→ F006（文档）
```

**关键路径**：F001 → F004。只要 25 个零安装渠道上了，就能验证价值。

## 预期成果

| 维度 | Native Claude | AutoSearch v3.0 | 差距 |
|------|-------------|----------------|------|
| 中文平台内容 | 0 | 8 个平台 | **无限大** |
| 视频内容 | 0 | 3 个平台（字幕提取） | **无限大** |
| 商业产品数据 | 有限 | 3 个专门平台 | 显著 |
| 社区真实反馈 | 0 | 5 个社区平台 | **无限大** |
| 学术网络追踪 | 0 | 3 个学术工具 | **无限大** |
| 累积学习 | 0 | knowledge map + patterns | **无限大** |
| 搜索渠道总数 | WebSearch 1 个 | **38 个** | 38x |
