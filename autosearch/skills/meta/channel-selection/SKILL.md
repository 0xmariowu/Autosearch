---
name: autosearch:channel-selection
description: Group-first channel selection algorithm for v2 tool-supplier architecture. Given a research query + clarify rubrics + channel_priority hints, picks 1-3 relevant groups from the router index, then 3-8 leaf channels from within those groups. Replaces flat-rank selection across 41 channels with a two-stage pick so runtime AI never has to read all 41 SKILL.md bodies.
version: 0.1.0
layer: meta
domains: [meta, routing]
scenarios: [channel-routing, query-planning, progressive-disclosure]
trigger_keywords: [select channels, channel picker, which channels, route query, group-first]
model_tier: Standard
auth_required: false
cost: free
experience_digest: experience.md
---

# Channel Selection — Group-First Algorithm

Runtime AI calls this **after** `run_clarify` and **before** `run_channel`. Produces a ranked list of leaf channels to invoke, using the progressive-disclosure structure from `autosearch:router` + 14 group index files.

## Why Group-First

Flat ranking across 41 channels means reading 41 SKILL.md bodies and scoring each. Group-first reduces the decision to:

1. Pick 1-3 groups (from the 14 group index descriptions — short, already cached).
2. Within picked groups, pick 3-8 leaf channels (leaf metadata is short and already in each group index).

Token savings: ~80% over flat-rank. Latency savings: sub-second at Standard tier vs. ~5s at Best tier for 41-way scoring.

## Input

```yaml
input:
  query: str                          # user's research question
  clarify_result:                     # from run_clarify
    mode: "fast" | "deep" | "comprehensive"
    query_type: str
    rubrics: list[str]
    channel_priority: list[str]        # clarifier's hint
    channel_skip: list[str]            # clarifier's anti-hint
  scope:                               # optional
    languages: "all" | "en_only" | "zh_only" | "mixed"
    recency: "any" | "7d" | "30d" | "90d"
    budget:
      max_channels: int                # hard cap, default 8
      max_groups: int                  # hard cap, default 3
      max_cost_usd: float | null
```

## Algorithm

### Stage 1 — Group Selection (≤ 3 groups)

Score each of the 14 groups against the query + rubrics:

| Factor | Weight | How to score |
|---|---|---|
| Domain match | 0.35 | query entities / rubric keywords intersect group `domains` + keyword-hint map in `autosearch:router` |
| Scenario match | 0.25 | `clarify.query_type` matches any group `scenarios` |
| Language match | 0.15 | query language alignment with group's typical surface (chinese-ugc / cn-tech groups boost zh queries; community-en boosts en) |
| Clarifier priority overlap | 0.15 | proportion of `channel_priority` entries that belong to this group |
| Recency compatibility | 0.10 | recency-sensitive groups (chinese-ugc / channels-community-en / channels-video-audio) boost when `scope.recency <= 30d` |

Pick top 3 groups with score ≥ 0.4. If fewer than 3 meet threshold, pick just those; if zero, fall back to `channels-generic-web`.

Apply hard filters:

- Skip any group containing only channels in `clarify.channel_skip`.
- Skip `channels-social-career`, `channels-market-product`, etc. if they don't match domain.
- Skip `channels-chinese-ugc` + `channels-cn-tech` if `scope.languages == "en_only"`.
- Skip `channels-community-en` if `scope.languages == "zh_only"`.

### Stage 2 — Leaf Selection (≤ 8 channels across picked groups)

Within each picked group, score each leaf skill:

| Factor | Weight | How to score |
|---|---|---|
| Clarifier explicit priority | 0.40 | +1.0 if leaf name in `channel_priority`; 0 otherwise |
| Leaf-specific scenario match | 0.25 | intersect leaf `scenarios` with query_type / rubrics |
| Trigger keyword hit | 0.15 | any leaf `trigger_keywords` appear in query text |
| Auth availability | 0.10 | +1.0 if `auth_required=false` OR the required env var is set (e.g. `TIKHUB_API_KEY`); -0.5 if required but missing |
| Experience digest boost | 0.10 | if leaf has `experience.md` with recent `Active Rules` matching this query shape, +0.5 |

Pick top 3-8 leaves total across all picked groups. Hard caps from `scope.budget` apply.

### Boss-Rule Enforcements

- **Chinese-native guard**: if query is Chinese (detected by any Unicode CJK char in `query`), the output MUST include at least 2 channels from `channels-chinese-ugc` or `channels-cn-tech` regardless of historical yield. Boss rule in `feedback_autosearch-chinese-channels`.
- **Channel-quality-not-reduction**: never dropout a full group just because historical yield was zero on one past session. Skill requires ≥ 3 consecutive session-level empty yields before demoting.

## Output

```yaml
output:
  groups:                              # stage-1 result
    - name: "channels-chinese-ugc"
      score: 0.82
      rationale: "query mentions 小红书 + clarifier priority includes xiaohongshu"
    - name: "channels-video-audio"
      score: 0.61
      rationale: "xiaoyuzhou podcast mentioned"
  channels:                            # stage-2 result, ranked
    - name: "search-xiaohongshu"
      group: "channels-chinese-ugc"
      score: 0.88
      model_tier: "Fast"
      auth: "paid (TIKHUB_API_KEY set)"
      rationale: "clarifier priority + query-match + auth available"
    - name: "search-xiaoyuzhou"
      group: "channels-video-audio"
      score: 0.74
      model_tier: "Fast"
      auth: "free"
      rationale: "query mentions podcast + scenario match"
    # ... 1-6 more
  chinese_native_quota_met: true
  skipped_groups: ["channels-social-career"]       # why-skipped log
  skipped_channels: ["search-linkedin"]
  elapsed_ms: 140
```

## Invocation Pattern (runtime AI)

```python
# Call order in a research session
clarify = run_clarify(query, mode_hint="fast")
selection = channel_selection(
    query=query,
    clarify_result=clarify,
    scope={"languages": "mixed", "recency": "30d", "budget": {"max_channels": 6}},
)

# Fan out to picked channels
evidence = []
for leaf in selection.channels[:6]:
    resp = run_channel(leaf.name, query, k=10)
    if resp.ok:
        evidence.extend(resp.evidence)

# Runtime AI synthesizes from evidence
```

## When This Skill Is Used

- Any research task that would otherwise require reading 10+ channel SKILL.md files.
- Fan-out planning before parallel `run_channel` calls.
- Teaching the runtime AI when `channel_priority` from `run_clarify` should / shouldn't override the group-first algorithm.

## When NOT

- Single-channel queries ("give me the top B站 video on X") — call `run_channel("bilibili", query)` directly.
- User explicitly names the channels — respect the user's choice; don't re-rank.

## Cost

Standard-tier LLM call (one pass, ~5s, ~1K tokens in + ~500 out) or can be degraded to Fast-tier with 90% accuracy on simple queries.

## MCP Tool Usage

Use the `select_channels_tool` MCP tool directly instead of executing this algorithm manually:

```
select_channels_tool(
  query="小红书有没有人用 Cursor 做编程",
  channel_priority=["xiaohongshu", "zhihu"],   # from run_clarify output
  channel_skip=[],
  mode="fast"
)
```

Returns `{groups: ["channels-chinese-ugc"], channels: ["xiaohongshu", "zhihu", "bilibili"], rationale: "..."}`.
Pass `channels` directly to `run_channel` or `delegate_subtask`.

## Relationship to Other Skills

- Reads → `autosearch:router` + 14 group index SKILL.md files (L1 progressive disclosure).
- Reads → per-leaf `experience.md` digests for boost scoring.
- Fed by → `run_clarify` output.
- Feeds → `run_channel` fan-out.
- Does NOT replace `run_clarify` — they're sequential, not alternatives.
