---
title: AutoSearch — Unified Perception System Architecture
date: 2026-03-22
project: autosearch
type: design
tags: [autosearch, architecture, perception-system, four-pillars]
---

# AutoSearch — 统一感知系统架构

## 定位

四大金刚之一 — **感知**（Perception）。

```
AutoSearch（感知）→ Armory（知识）→ Harness（行为）→ AIMD（记忆）→ AutoSearch...
```

AutoSearch 负责从外部世界持续发现新的高质量 AI 知识资源，自动评估、入库到 Armory，并通过 outcome feedback 不断优化自己的搜索策略。

## 系统架构

```
┌─ AutoSearch Engine ────────────────────────────────────────────┐
│                                                                 │
│  QueryGenerator                                                 │
│    ├── seed_queries (from queries.json, never capped)           │
│    ├── llm_suggestions (from LLM eval, recency cap 30)         │
│    ├── pattern boost (from patterns.jsonl winning words)        │
│    └── gene pool (entity × object × context random combos)     │
│         20% seed/llm + 20% pattern + 60% gene                  │
│                                                                 │
│  PlatformConnector (11 methods)                                 │
│    ├── reddit_api / reddit_exa                                  │
│    ├── hn_algolia / hn_exa                                      │
│    ├── exa (mcporter)                                           │
│    ├── github_issues / github_repos                             │
│    └── twitter_exa / twitter_xreach                             │
│                                                                 │
│  LLMEvaluator (Sonnet 4.6 daily / Haiku manual)                │
│    └── relevance scoring: 0.4 × engagement + 0.6 × relevance   │
│                                                                 │
│  3-Phase Execution                                              │
│    Phase 1: EXPLORE (N rounds, early stop at 5 stale)           │
│    Phase 2: HARVEST (top 15 queries, collect findings)          │
│    Phase 3: POST-MORTEM (winning/losing words → patterns.jsonl) │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
                    ↓ findings.jsonl
┌─ Pipeline (pipeline.py) ───────────────────────────────────────┐
│                                                                 │
│  1. Engine (daily.py)                                           │
│     └── 3 rounds × 20 queries × 6 platforms                    │
│                                                                 │
│  2. Format Adapter                                              │
│     └── engine JSONL → per-platform JSONL (score-and-stage 格式)│
│     └── topic inference: exact query match > word-level vote    │
│                                                                 │
│  3. score-and-stage.js (Scout 遗产，暂不改写)                    │
│     ├── Armory dedup (armory-index.json)                        │
│     ├── Seen dedup (state.json)                                 │
│     ├── Quality scoring (freshness × reliability × depth)       │
│     ├── Diversity filter (title similarity > 0.6 去重)          │
│     ├── Distribution selection (GH≥10, Articles≥15, Disc≥5)    │
│     ├── Chinese translation (Google Translate API)              │
│     ├── Trend detection + auto-evolution (queries.json)         │
│     └── Daily report → AIMD/ai-recommendations/YYYY-MM-DD.md   │
│                                                                 │
│  4. auto-intake.sh                                              │
│     └── score ≥ 90 repos → clone → deep-research → Armory      │
│                                                                 │
│  4b. outcomes.py record_intakes()                               │
│     └── query → repo 追溯链 → outcomes.jsonl                    │
│                                                                 │
│  5. send-email.sh                                               │
│     └── daily report → Resend API → email                       │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
                    ↓ weekly
┌─ Outcome Tracker (outcomes.py track) ──────────────────────────┐
│                                                                 │
│  For each intaked repo in outcomes.jsonl:                       │
│    1. Check when-blocks.jsonl → count WHEN/USE blocks produced  │
│    2. outcome_score = min(100, when_use_count × 5)              │
│    3. Write outcome_boost pattern → patterns.jsonl              │
│       └── high-outcome queries get boosted in future sessions   │
│                                                                 │
│  This is the REAL feedback loop:                                │
│    搜到 → 入库 → 产出 WHEN/USE → 被实际使用 → boost 搜索策略    │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

## 文件清单

### AutoSearch repository root (感知系统主目录)

| 文件 | 行数 | 功能 |
|------|------|------|
| `engine.py` | ~1080 | 搜索引擎核心 — 7 个 class，11 个 platform connector |
| `cli.py` | ~155 | 手动搜索入口 (`python cli.py --config task.json`) |
| `daily.py` | ~320 | 每日发现模式 (`python daily.py --dry-run`) |
| `pipeline.py` | ~427 | 统一管道 (`python pipeline.py`) |
| `outcomes.py` | ~275 | Outcome feedback (`python outcomes.py` / `python outcomes.py track`) |
| `patterns.jsonl` | 增长中 | 累积搜索智慧（winning words, losing words, outcome boosts）|
| `evolution.jsonl` | 增长中 | 跨 session 实验日志 |
| `outcomes.jsonl` | 增长中 | query → repo → WHEN/USE 追溯链 |
| `CLAUDE.md` | ~250 | AutoSearch 方法论文档 |
| `platforms.md` | ~100 | 平台 API 细节 |
| `standard.json` | ~20 | 搜索标准配置 |

### Armory/scripts/scout/ (Armory 侧工具)

| 文件 | 功能 | 状态 |
|------|------|------|
| `score-and-stage.js` | 评分 + 去重 + 翻译 + 报告生成 | 活跃，暂不改写 |
| `auto-intake.sh` | 高分 repo 克隆 + deep-research | 活跃 |
| `generate-deep-research.js` | 分析 repo 生成 WHEN/USE blocks | 活跃 |
| `send-email.sh` | Resend API 发邮件 | 活跃 |
| `queries.json` | 15 topic groups (seed genes 来源) | 活跃，auto-evolution |
| `state.json` | 持久状态 (seen URLs, trends, runs) | 活跃 |
| `search-*.sh` (5 个) | 旧搜索脚本 | 被 engine.py PlatformConnector 替代 |
| `scout.sh` | 旧管道入口 | 被 pipeline.py 替代 |

## 调度

```
launchd (com.vimala.armory-scout)
  → ~/.local/bin/armory-scout.sh
    → rsync iCloud → local (autosearch/ + scout/)
    → export SCOUT_DIR=local, ARMORY_ROOT=iCloud
    → python3 pipeline.py
    → reverse rsync: patterns.jsonl, evolution.jsonl, outcomes.jsonl → iCloud
```

- 时间：每天 6:00 AM
- 日志：`~/.local/log/armory-scout/scout.log`
- TCC 限制：通过 rsync + env var override 绕过

## 自我进化机制

### 搜索策略进化 (patterns.jsonl)

每次 daily run 都是一次 AutoSearch session：
1. **Post-mortem** 分析 winning/losing words → 写回 patterns.jsonl
2. 下次 run 读 patterns.jsonl → 生成更好的 queries
3. **Outcome boost** — 高 outcome 的 query 被加权（搜到的东西真的有用）

```
Session 1: 14 patterns → run → +4 patterns
Session 2: 18 patterns → run → +4 patterns (reads Session 1 winners)
Session N: 14 + 4N patterns → each session starts smarter
```

### 话题进化 (queries.json auto-evolution)

score-and-stage.js 的 trend detection：
1. 从 raw candidates 提取高频词
2. 检测 "新兴话题"（高频但不在现有 topic groups 里）
3. 持续 3+ 天的趋势自动加到 queries.json
4. 长期零产出的 auto-added topics 自动移除

### Outcome 进化 (outcomes.jsonl)

搜索 → intake → WHEN/USE blocks → 反馈回搜索策略：
- **Proxy metric**: query 返回了高 engagement 结果（patterns.jsonl 已有）
- **Outcome metric**: intake 的 repo 产出了多少 WHEN/USE blocks（outcomes.jsonl 新增）
- outcome_score 写回 patterns.jsonl 的 outcome_boost → engine 优先使用有实际产出的 query patterns

## 运维

### 日常检查

```bash
# 今天的 daily report 是否生成
ls delivery/

# 最近的 scout 日志
tail -30 ~/.local/log/armory-scout/scout.log

# pattern 积累趋势
wc -l patterns.jsonl

# outcome 状态
python3 outcomes.py         # record new intakes
python3 outcomes.py track   # update WHEN/USE counts
```

### 手动运行

```bash
# Dry-run（不实际搜索，只看配置）
python3 daily.py --dry-run

# 只跑引擎，不跑下游管道
python3 pipeline.py --engine-only

# 完整管道但跳过邮件
python3 pipeline.py --skip-email

# 手动搜索（AI 填参数）
python3 cli.py --config task.json
```

### 故障排查

| 症状 | 检查 | 可能原因 |
|------|------|---------|
| 日报没生成 | `tail scout.log` | engine 失败 or score-and-stage 失败 |
| patterns.jsonl 不增长 | `diff` local vs iCloud | reverse rsync 没跑 |
| outcome_score 全是 0 | `python outcomes.py track` | intaked repos 还没产出 WHEN/USE |
| Twitter 结果全空 | `xreach auth check` | cookies 过期 |
| Exa/Reddit/HN 全空 | `mcporter --version` | mcporter config 或 cwd 问题 |

---

## Genome-Runtime-Primitives Architecture (AVO v2)

Added 2026-03-28. Replaces hardcoded strategy with evolvable JSON genomes.

```
AVO Controller  →  vary genome  →  Runtime executes  →  Judge scores  →  commit/discard
     ↑                                                      │
     └────────── lineage (evolution.jsonl) ←────────────────┘
```

Three-layer separation:

| Layer | File | Purpose |
|-------|------|---------|
| Genome | `genome/defaults/*.json`, `genome/seeds/*.json`, `genome/evolved/*.json` | Evolvable strategy JSON |
| Runtime | `genome/runtime.py` (~400 lines) | Generic interpreter, no strategy |
| Primitives | `genome/primitives.py` (13 ops) | Minimal atomic operations |

AVO genome evolution (`avo.py --genome`): select parent → vary (5 mutation types) → execute → evaluate → commit/discard. Mutations: micro, structural, crossover, supervisor_redirect, knowledge_injection.

All original entry points unchanged. Each module accepts optional `genome=` param with fallback to hardcoded defaults.
