---
name: autosearch:router
description: Route an autosearch task to the smallest relevant group of skills, then load only the matching leaf skills. First line of defense against loading all 80+ skill SKILL.md files at session start.
version: 0.1.0
layer: router
domains: [meta]
scenarios: [task-routing, skill-discovery]
trigger_keywords: [autosearch, 研究, research, 查资料, find information, 搜索, search]
model_tier: Fast
auth_required: false
cost: free
loads:
  - references/groups/channels-chinese-ugc.md
  - references/groups/channels-cn-tech.md
  - references/groups/channels-academic.md
  - references/groups/channels-code-package.md
  - references/groups/channels-market-product.md
  - references/groups/channels-community-en.md
  - references/groups/channels-social-career.md
  - references/groups/channels-generic-web.md
  - references/groups/channels-video-audio.md
  - references/groups/tools-fetch-render.md
  - references/groups/workflow-planning.md
  - references/groups/workflow-quality.md
  - references/groups/workflow-synthesis.md
  - references/groups/workflow-growth.md
---

# Routing Policy

When the runtime AI picks up an autosearch research task, do **not** try to read every leaf `SKILL.md`. Follow this three-step routing:

1. **Identify 1–3 groups** from the query intent. Use the keyword hints below as a first pass; use the domain + scenario tags on each group index for ambiguity.
2. **Read only those group indexes** (`references/groups/<group>.md`). Each group index lists its leaf skills with one-line triggers and suggested model tier.
3. **Pick 3–8 leaf skills** from the matched groups. Read their `SKILL.md` only when you're about to call them.

Do **not** enumerate every leaf skill to the main model. That defeats the entire progressive-disclosure design and burns tokens.

## Group Selection Hints

### Content surface

| If the query mentions… | Pick group |
|---|---|
| 小红书 / 抖音 / B站 / 微博 / 知乎 / 播客 / 快手 / 雪球 / V2EX | `channels-chinese-ugc` |
| 36kr / CSDN / 掘金 / InfoQ 中文 / 微信公众号 | `channels-cn-tech` |
| paper / arxiv / citation / benchmark / 论文 / survey / openreview | `channels-academic` |
| github / repo / code / issue / npm / pypi / huggingface | `channels-code-package` |
| crunchbase / 融资 / producthunt / G2 review | `channels-market-product` |
| stack overflow / hacker news / dev.to / reddit | `channels-community-en` |
| twitter / X / linkedin / 职业 / career | `channels-social-career` |
| 一般网页 / 搜索引擎 / tavily / exa / ddgs / searxng / rss | `channels-generic-web` |
| 视频 / 字幕 / 转录 / podcast / youtube | `channels-video-audio` |

### Tool surface

| If the task is… | Pick group |
|---|---|
| Fetch a URL, render JS, run interactive browser, download media | `tools-fetch-render` |
| Clarify user intent, decompose a task, recall known info, gene queries | `workflow-planning` |
| Normalize, rerank, anti-cheat, extract dates, score with LLM, apply rubrics | `workflow-quality` |
| Assemble context, extract knowledge, build knowledge map, synthesize report | `workflow-synthesis` |
| Track outcomes, auto-evolve skills, create new skills, capture/compact experience | `workflow-growth` |

## Model Tier Escalation

Every group index and leaf skill carries a `model_tier` field (`Fast` / `Standard` / `Best`). Default router execution is `Fast`. Escalate only when the group index or leaf skill calls for a higher tier on the specific step (for example, `synthesize-knowledge` needs `Best`; `search-bilibili` is `Fast`).

Rule of thumb:

- **Fast**: retrieval, normalization, schema checks, URL reading — the bulk of every session.
- **Standard**: semantic ranking, evidence extraction, source curation, mid-complexity planning.
- **Best**: clarify, decompose, synthesize, evaluate delivery, skill evolution — the 1–2 steps that shape the whole outcome.

See `autosearch:model-routing` (if available in the runtime) for the full advisory catalog.

## What the Router Does Not Do

- Does not call any leaf skill itself — it only points.
- Does not guess: if no group matches, ask the user or degrade to `channels-generic-web`.
- Does not cache across sessions — skill state lives in each skill's `experience.md` (read lazily).

# Quality Bar

- Evidence items have non-empty title and url.
- No crash on empty or malformed API response.
- Source channel field matches the channel name.
