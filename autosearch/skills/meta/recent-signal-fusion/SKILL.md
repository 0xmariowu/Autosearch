---
name: autosearch:recent-signal-fusion
description: Unify signals from multiple recency-sensitive channels (Reddit, X, Hacker News, Weibo, YouTube, GitHub activity, Polymarket, etc.) into a single time-weighted candidate list. Clusters semantic near-duplicates across sources, weights by recency + platform reliability, and produces a ranked "what's happening recently" bundle for the runtime AI to synthesize.
version: 0.1.0
layer: meta
domains: [workflow, synthesis]
scenarios: [recency-focus, trending-topics, 24h-watch, weekly-digest]
trigger_keywords: [recent, trending, latest, 最近, 24 hours, weekly, signal fusion]
model_tier: Standard
auth_required: false
cost: free
experience_digest: experience.md
---

# Recent Signal Fusion — Cross-Platform Recency Bundle

Adapted from `last30days-skill`'s SourceItem / Candidate / Cluster / Report pipeline + Scira's group-mode aggregation. Turns N channels' recent outputs into a single time-weighted cluster list.

## Input

```yaml
input:
  topic: str                                 # research topic
  time_window: "24h" | "7d" | "30d"          # how far back to care
  channels: list[str]                        # which channel skills to call
  min_recency_ratio: float                   # reject items older than (now - time_window)
  max_items_per_channel: int                 # e.g. 30
```

## Pipeline Stages

1. **Parallel fetch** — call each channel with a time-window filter in the query. Collect raw evidence lists.

2. **Normalize to SourceItems**:
   ```yaml
   source_item:
     id: str                        # hash(url + title)
     url: str
     title: str
     content_snippet: str
     platform: str                  # source_channel
     posted_at: datetime
     engagement: {likes, comments, shares} | null
     language: str
     raw_evidence_ref: dict         # original Evidence slim-dict
   ```

3. **Recency filter** — drop items older than `time_window`. Use `extract-dates` skill for items without explicit `posted_at`.

4. **Semantic clustering** — group near-duplicate SourceItems across platforms:
   ```yaml
   cluster:
     id: str
     canonical_title: str           # best representative title
     topic_keywords: list[str]      # extracted from the cluster
     sources: list[source_item_id]
     platform_spread: int           # how many distinct platforms
     earliest_posted_at: datetime
     latest_posted_at: datetime
   ```

5. **Rank by weighted score**:
   ```
   score = (
     0.4 * recency_score(latest_posted_at, time_window)
     + 0.3 * platform_spread_score(platform_spread)   # cross-platform = stronger signal
     + 0.2 * engagement_score(sum(engagement))         # aggregated across sources
     + 0.1 * platform_reliability_score(platforms)     # quality weighting
   )
   ```

6. **Emit bundle**:
   ```yaml
   bundle:
     topic: str
     time_window: str
     total_source_items: int
     total_clusters: int
     top_clusters: list[Cluster]     # top 20 by score
     platforms_hit: list[str]
     platforms_empty: list[str]
     earliest_signal: datetime
     latest_signal: datetime
   ```

## Platform Reliability Default Weights

- `github-*` / `arxiv` / `hackernews` → 1.0 (deterministic, low spam).
- `stackoverflow` / `reddit` / `devto` → 0.8 (moderated, some spam).
- `twitter-exa` / `xiaohongshu` / `weibo` / `douyin` → 0.6 (high spam, high recency value).
- `search-rss` (user-curated) → 1.0.

Runtime AI can override per-session for specific platform-topic fits.

## Anti-Collapse Guard

If after ranking, the top 5 clusters are all from the same platform → flag as "platform-collapse", re-rank with platform_spread weighted 2×. Ensures the bundle isn't just "top 5 trending X posts" when other platforms had relevant signal.

## When to Use

- User asks "what's happening with X recently?" / "what's the latest on X?" / "近期 X 讨论怎么样?"
- Weekly / daily brief generation.
- Trend tracking across platforms.

## When NOT to Use

- Historical / reference research (use `channels-academic`, not this).
- Single-platform watch (call that channel directly).
- Highly technical API questions (recency not the primary filter).

## Cost

Standard-tier LLM for clustering + canonical-title extraction. Typical run: 5-10 seconds + sum of channel call costs. Cheaper than decompose-task because channels fan out in parallel.

## Interactions

- Calls → `run_channel` (parallel) for each selected channel.
- Uses → `extract-dates` (normalize posted_at fields).
- Uses → `rerank-evidence` (as fallback when semantic clustering is inconclusive).
- Feeds → `synthesize-knowledge` (the bundle is the input context).
