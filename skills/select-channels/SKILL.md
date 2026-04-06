---
name: select-channels
description: "Use after systematic-recall to choose 5-10 most relevant search channels from the 30+ available, based on topic type, knowledge gaps, and platform-topic match patterns."
---

# Purpose

AutoSearch has 30+ search channels. Searching all of them for every query wastes time and produces noise. This skill selects the 5-10 channels most likely to produce incremental discoveries for the current topic.

# When To Use

Use after systematic-recall.md has produced a knowledge map with gaps identified.
Use before gene-query.md generates queries.
The selected channels determine WHERE queries are sent.

# Selection Rules

## Rule 0: Language relevance filter

Before applying any other rule, exclude channels whose language does not match the topic.

Read each channel's `## Language` section in its SKILL.md. If the channel's language coverage has no overlap with the topic's language, exclude it and log the reason.

Examples:
- English technical topic → exclude zhihu, csdn, juejin, bilibili, 36kr, weibo, xiaohongshu, douyin, xiaoyuzhou, xueqiu, infoq-cn, wechat (Chinese-only channels)
- Chinese topic → exclude devto, stackoverflow, reddit, hn (English-only channels with negligible Chinese content)
- Mixed/multilingual topic → keep both, prioritize by relevance

Do not hardcode channel lists. Read the SKILL.md Language section for each candidate channel. Channels evolve — the Language section is the source of truth.

Log every exclusion: `excluded: {channel} — language mismatch ({channel_language} vs {topic_language})`

## Rule 0.5: Language-mandatory channels

After the language filter, ALWAYS include a minimum set of channels based on topic language. This is not optional — the LLM must not override this.

**Chinese topic** — include AT LEAST 5 from this list:
`csdn`, `juejin`, `bilibili`, `zhihu`, `36kr`, `wechat`, `weibo`, `xiaohongshu`, `douyin`, `infoq-cn`, `xueqiu`, `xiaoyuzhou`

Pick the 5-8 most relevant to the topic type. For example:
- Technical Chinese → csdn, juejin, zhihu, bilibili, infoq-cn
- Business Chinese → 36kr, xueqiu, weibo, wechat, zhihu
- Consumer/social Chinese → xiaohongshu, douyin, weibo, bilibili, zhihu

**English topic** — include AT LEAST:
- `web-ddgs` (general web)
- 2+ community channels (reddit, hn, devto, stackoverflow — pick by topic type)
- 1+ discovery channel (producthunt, github-repos, arxiv — pick by topic type)

Why mandatory: Without this rule, the LLM agent tends to select only 2-4 "safe" channels (web-ddgs + arxiv). The whole point of AutoSearch is multi-platform coverage — selecting 3 channels makes it no better than a web search.

## Rule 1: Always include these (2-3 channels)

- GitHub repos (`github-repos`) — for any topic involving code or tools
- A general web search (`web-ddgs`) — for broad coverage
- Own knowledge via `systematic-recall` — already done in Phase 1

## Rule 2: Match topic type to channels

| Topic type | Add these channels |
|-----------|-------------------|
| Academic/research | google-scholar, semantic-scholar, citation-graph, arxiv |
| Open-source tools | github-repos, github-issues, npm-pypi, stackoverflow |
| Commercial products | producthunt, crunchbase, g2, twitter |
| Chinese market/tech | zhihu, csdn, juejin, bilibili, 36kr, wechat, weibo, xiaohongshu, douyin, infoq-cn, xueqiu |
| Community sentiment | reddit, hn, twitter, stackoverflow |
| Video/tutorial | youtube, bilibili, conference-talks |
| Business intelligence | crunchbase, 36kr, linkedin, xueqiu, twitter |
| Emerging/recent | producthunt, github-repos, twitter, hn |

## Rule 2b: Query type adjustment

`lib/query_type.py` classifies the topic into one of 7 types. Use the query type to boost or deprioritize channels:

| Query type | Boost these | Deprioritize |
|-----------|------------|-------------|
| how_to | youtube, stackoverflow, reddit | arxiv, crunchbase |
| comparison | reddit, hn, youtube | producthunt |
| opinion | reddit, twitter, hn | arxiv, google-scholar |
| prediction | twitter, reddit | stackoverflow, arxiv |
| product | reddit, twitter, producthunt | arxiv |
| concept | hn, reddit, arxiv, web-ddgs | producthunt |
| breaking_news | twitter, reddit, web-ddgs, hn | arxiv |

This is a soft signal — don't exclude deprioritized channels entirely, just rank them lower in the selection.

## Rule 3: Fill gaps from knowledge map

For each GAP dimension in the knowledge map, add the channel most likely to fill it:

| GAP in dimension | Best channel |
|-----------------|-------------|
| Recent developments | github-repos, producthunt, twitter, hn |
| Commercial players | crunchbase, producthunt, 36kr, twitter |
| Community feedback | reddit, hn, zhihu, xiaohongshu, twitter |
| Academic papers | google-scholar, semantic-scholar, citation-graph, arxiv |
| Implementation details | stackoverflow, github-repos, github-issues, csdn |
| Design patterns | devto, zhihu, infoq-cn, twitter |

## Rule 4: Use channel effectiveness scores

Read `state/channel-scores.jsonl` for proven channel performance data. Each entry records:

```json
{
  "channel": "github-repos",
  "topic_type": "general",
  "lang": "en",
  "incremental_rate": 0.45,
  "relevance_rate": 0.85,
  "avg_results": 20,
  "sessions_tested": 3
}
```

- `lang` = language context in which this score was measured ("en", "zh", etc.)
- `incremental_rate` = fraction of results that were genuinely new (not in Claude's knowledge)
- `relevance_rate` = fraction of results marked relevant by llm-evaluate

### Language-aware scoring

**First determine the topic language** (from Phase A auto-detection). Then filter scores:

1. Only use scores where `lang` matches the topic language
2. If a channel has no score for the current language, treat it as **untested** — include with medium priority to gather data. Untested ≠ zero yield. A channel that was never tested in Chinese might be excellent for Chinese topics.
3. Never use English-session scores to judge a channel's Chinese performance, or vice versa

Example: topic is Chinese → zhihu has no `lang: "zh"` score → zhihu is untested → include with medium priority. Do NOT look at zhihu's `lang: "en"` score (which would be zero and misleading).

Prefer channels with higher `incremental_rate` for the matching `topic_type` AND `lang`.
A channel with `incremental_rate: 0.05` for a topic type should be deprioritized.
A channel with `incremental_rate: 0.50` should be strongly prioritized.

Also read `state/patterns-v2.jsonl` for entries with type "platform". If a pattern says "zhihu is best for Chinese dev experience" and the topic matches, include zhihu.

### Evolution feedback loop

After each pipeline run, `auto-evolve.md` should update `channel-scores.jsonl` based on actual results:
- Channels that returned high-relevance results → increase `incremental_rate`
- Channels that returned 0 results or all irrelevant → decrease `incremental_rate`
- New channel+topic_type combos get baseline scores from the first run
- **Always include `lang` field** when writing new scores — inherit from the session's detected language

This data-driven evolution is more precise than modifying skill text. The `auto-evolve.md` diagnosis should prefer updating `channel-scores.jsonl` over rewriting this skill when information-recall rubrics fail due to channel selection.

## Rule 4b: Exclude broken channels (API/auth issues only)

Before applying Rule 5, exclude channels that cannot work due to missing API keys or auth — NOT channels that returned zero results for a different language.

Known broken channels (require API key or auth not currently configured):
- `crunchbase` — requires API key. Use `web-ddgs` with `site:crunchbase.com` as fallback.
- `twitter` — requires API access. Use `web-ddgs` with `site:twitter.com` as fallback.

Do NOT exclude Chinese channels (zhihu, csdn, 36kr, etc.) based on zero-yield from English sessions. Those channels have no data in English — but they work for Chinese topics. Check `channel-scores.jsonl` with the correct `lang` filter instead.

## Rule 5: Cap channels by depth

| Depth | Cap | Rationale |
|-------|-----|-----------|
| Quick | 10 | Fast scan, focused channels |
| Standard | 15 | Balanced breadth and depth |
| Deep | all 34 | Exhaustive coverage |

If the rules above suggest more than the cap, prioritize:
1. Channels with highest expected incremental value (content Claude can't know)
2. Channels with proven win patterns
3. Channels matching the most GAP dimensions

# Output

List both selected and excluded channels:

```
Excluded channels:
- xiaohongshu — language mismatch (Chinese-only vs English topic)
- douyin — language mismatch (Chinese-only vs English topic)
- xueqiu — language mismatch (Chinese-only vs English topic)

Selected channels:
1. github-repos — core tool discovery
2. web-ddgs — broad web coverage
3. google-scholar — academic coverage (GAP: dimension 4)
4. producthunt — recent product launches (GAP: dimension 7)
5. reddit — community sentiment
6. arxiv — academic papers (GAP: dimension 3)
```

Pass the selected list to gene-query.md for platform-targeted query generation.

# Quality Bar

A good channel selection produces 5-10 channels where each one is expected to find something the others cannot. If two selected channels would return substantially the same results, drop one.
