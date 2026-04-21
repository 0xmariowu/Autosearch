---
name: autosearch:experience-capture
description: Append a single skill-execution event to the per-skill `experience/patterns.jsonl` file. Runs every time a leaf skill is used. Append-only — runtime AI never reads this file directly; only the compacted `experience.md` digest. Fast tier, no LLM required.
version: 0.1.0
layer: meta
domains: [meta, self-adaptive]
scenarios: [skill-outcome-tracking, experience-capture]
trigger_keywords: [capture experience, log skill run, record outcome]
model_tier: Fast
auth_required: false
cost: free
experience_digest: experience.md
---

# experience-capture — Per-Skill Event Writer

Appends one line of JSON per skill execution to `<skill_dir>/experience/patterns.jsonl`.

## Why This Skill Exists

Each autosearch leaf skill is treated as a small project that grows over time. Every time the runtime AI calls a skill, this capture skill logs **what the call looked like and whether it worked**, so the companion `experience-compact` skill can later promote recurring winning patterns into `experience.md`.

Three independent files per leaf skill:

```
autosearch/skills/channels/<skill>/
  SKILL.md                     # static, versioned via git
  experience.md                # compacted digest (≤120 lines, read by runtime before calling skill)
  experience/
    patterns.jsonl             # append-only raw events, grows, archived monthly
    archive/YYYY-MM.jsonl      # monthly-rotated archives
```

## Event Schema

One JSON object per line:

```json
{
  "ts": "2026-04-22T08:15:00+08:00",
  "session_id": "<session-id or null>",
  "skill": "search-xiaohongshu",
  "group": "channels-chinese-ugc",
  "task_domain": "product-research",
  "query_type": "recent-user-opinion",
  "input_shape": "brand + feature + 近30天",
  "method": "tikhub:xhs_search",
  "environment": {"auth": "paid", "locale": "zh-CN"},
  "outcome": "success",
  "metrics": {
    "yield": 18,
    "relevant": 9,
    "unique_sources": 7,
    "latency_ms": 4200,
    "cost_usd": 0.02,
    "user_feedback": "accepted"
  },
  "winning_pattern": "品牌词 + 痛点词 + 近30天 比 '评测' 召回更准",
  "failure_mode": null,
  "good_query": "某品牌 某功能 翻车 2026",
  "bad_query": null,
  "evidence_refs": [],
  "promote_candidate": true,
  "notes": "适合和 search-douyin 交叉验证"
}
```

## Invocation Pattern

The runtime AI calls this skill after executing any leaf channel / fetch / transcription skill:

```python
capture_event({
  "skill": "search-xiaohongshu",
  "task_domain": "product-research",
  "outcome": "success",  # or "failure" or "partial"
  "metrics": {...},
  "good_query": "...",
  "notes": "..."
})
```

The skill implementation (runtime AI uses Bash or direct file append):

1. Open `autosearch/skills/channels/<skill>/experience/patterns.jsonl` (create dir if missing).
2. Append one JSON line with `ts` set to current ISO-8601 time.
3. Close file. No compaction, no LLM call.

Latency target: < 50 ms, no network.

## When NOT to Capture

- User cancelled the skill mid-execution before results came in — too noisy.
- Skill threw an unhandled exception / segfault — exceptional, not a pattern.
- Runtime AI is running in a "dry run" / exploratory mode.

Captures are cheap; err on the side of capturing. `experience-compact` filters noise.

## Privacy Rules

- **Do not capture PII** (user names, emails, private URLs). `input_shape` should describe the *shape* of the query, not the exact terms the user typed. `good_query` / `bad_query` should be sanitized templates ("品牌 + 痛点 + 近30天") unless the exact string is demonstrably non-sensitive.
- **Do not capture cookies or API keys** in the `environment` field. Only record whether auth was paid / free / cookie-based.
- **Evidence refs** should point to deterministic IDs (URLs, patterns.jsonl offsets), never user-identifiable fields.

## Rotation

When `experience/patterns.jsonl` exceeds 1 MB, rotate:

```
experience/patterns.jsonl         → experience/archive/YYYY-MM.jsonl
experience/patterns.jsonl (fresh) → ready for next session
```

This rotation is the `experience-compact` skill's job, not this capture skill's. Capture always appends to the live file.

## Relationship to Other Skills

- Writes to → `<leaf>/experience/patterns.jsonl`.
- Read by → `experience-compact` skill (promote rules into `experience.md`).
- Does NOT feed → runtime AI directly. Only `experience.md` is runtime-visible.
