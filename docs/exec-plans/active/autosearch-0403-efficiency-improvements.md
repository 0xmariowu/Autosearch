# AutoSearch 效率优化 — 砍浪费不加功能

## Goal

基于 native WebSearch vs AutoSearch 对比实测（2026-04-03），修复三个确认的浪费点：无效渠道、模型过重、中间无反馈。目标：同等质量，token 降 5x，体验从"15 分钟黑洞"变成有进度反馈。

## 背景数据（实测）

- 主题：MCP Protocol Ecosystem 2025-2026
- Native WebSearch：3 秒，~2K tokens，10 个链接，概括性摘要
- AutoSearch：903 秒，~105K tokens，56 次工具调用，50+ cited sources，深度报告
- 结论：质量差距大（AutoSearch 远胜），但 50x token 和 300x 时间有大量可砍的浪费

## 已确认不需要改的

- **渠道并行**：search_runner.py 已用 asyncio.gather 并行执行，不是瓶颈
- **去重时机**：search_runner.py 已在 LLM 评估前做 URL 级去重

---

## F001: 语言/领域预过滤 — done

在 select-channels 中加入语言维度思考步骤。不硬编码渠道列表，让 agent 自己判断语言匹配。

**为什么**：英文技术主题搜小红书/抖音/微博 = 必然零产出。但渠道列表会一直变，硬编码会过时。

#### Steps

- [x] S1: Rule 0 added — reads SKILL.md Language section, no hardcoded lists
- [x] S2: Output section updated — requires excluded channels list with reasons

## F002: Agent 模型降级 — done (S3 pending)

researcher agent 从 Opus 降到 Sonnet。搜索执行 + 评估 + 合成不需要 Opus 级推理。

**为什么**：105K tokens 全跑 Opus，费用是 Sonnet 的 ~5x。pipeline-flow.md 自己设计的模型路由表就写了大部分 phase 用 Haiku/Sonnet。但实际 spawn 时继承了主对话的 Opus。

#### Steps

- [x] S1: Found: command file ran pipeline in Opus context. agents/researcher.md had model: sonnet but was never spawned.
- [x] S2: Command file restructured into Phase A (config, Opus) + Phase B (spawn autosearch:researcher, Sonnet). Pipeline work now runs in Sonnet.
- [ ] S3: 跑一次实测对比 — 同主题 Sonnet vs Opus researcher，对比报告质量和 token 消耗 ← verify: 两份报告 + token 数据

## F003: 渐进式输出 — done

解决"15 分钟黑洞"体验。用户在搜索过程中能看到进度。

**为什么**：MindSearch 的核心卖点就是过程可见。AutoSearch 跑 15 分钟无反馈，用户以为卡死了。

#### Steps

- [x] S1: Researcher runs as foreground Agent — user sees all its text output. No SendMessage needed.
- [x] S2a: Added progress output format to pipeline-flow/SKILL.md: `[Phase N/6] ✓ {name} — {metric}` after each phase. Agent output is directly visible to user.

## Decision Log

- 2026-04-03: F001 选择"agent 自己判断语言"而不是"硬编码排除列表"。原因：渠道 skills 会一直新增，硬编码列表过时风险高。
- 2026-04-03: F002 降到 Sonnet 而非 Haiku。原因：synthesis 阶段需要较强写作能力，Haiku 可能不够。pipeline-flow 的路由表也把 synthesis 标为 Sonnet。
- 2026-04-03: F003 优先尝试 SendMessage 方案（S2a），拆 agent 是 fallback（S2b）。原因：拆 agent 会丢失跨 phase 的上下文连续性。

## Open Questions

- Early stopping 是否要和搜索深度选择绑定？已讨论方向（ceiling + floor），待后续细化。
- F002 降级后如果 synthesis 质量下降明显，是否只对 Phase 2-3 用 Sonnet，Phase 4 回 Opus？需要 S3 实测数据决定。
