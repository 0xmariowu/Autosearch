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

## Rule 1: Always include these (2-3 channels)

- GitHub repos (`search-github-repos`) — for any topic involving code or tools
- A general web search (`search-ddgs` or `search-tavily`) — for broad coverage
- Own knowledge via `systematic-recall` — already done in Phase 1

## Rule 2: Match topic type to channels

| Topic type | Add these channels |
|-----------|-------------------|
| Academic/research | search-google-scholar, search-citation-graph, search-papers-with-code, search-openreview |
| Open-source tools | search-github-repos, search-github-code, search-npm-pypi, search-stackoverflow |
| Commercial products | search-producthunt, search-crunchbase, search-g2-reviews |
| Chinese market/tech | search-zhihu, search-csdn, search-juejin, search-36kr |
| Community sentiment | search-reddit, search-hackernews, search-twitter |
| Video/tutorial | search-conference-talks, search-youtube, search-bilibili |
| Business intelligence | search-crunchbase, search-36kr, search-linkedin |
| Emerging/recent | search-producthunt, search-github-repos (sort:stars,created:recent), search-twitter |

## Rule 3: Fill gaps from knowledge map

For each GAP dimension in the knowledge map, add the channel most likely to fill it:

| GAP in dimension | Best channel |
|-----------------|-------------|
| Recent developments | GitHub (created:recent), ProductHunt, Twitter |
| Commercial players | Crunchbase, ProductHunt, 36Kr |
| Community feedback | Reddit, HN, Zhihu, Xiaohongshu |
| Academic papers | Google Scholar, Semantic Scholar, OpenReview |
| Implementation details | StackOverflow, GitHub Code, CSDN |
| Design patterns | Dev.to, Zhihu, InfoQ |

## Rule 4: Check patterns for proven matches

Read `state/patterns-v2.jsonl` for entries with type "platform". If a pattern says "zhihu is best for Chinese dev experience" and the topic matches, include zhihu.

## Rule 5: Cap at 10 channels

More than 10 channels produces diminishing returns. If the rules above suggest more than 10, prioritize:
1. Channels with highest expected incremental value (content Claude can't know)
2. Channels with proven win patterns
3. Channels matching the most GAP dimensions

# Output

List the selected channels with one-line justification each:

```
Selected channels:
1. search-github-repos — core tool discovery
2. search-ddgs — broad web coverage
3. search-zhihu — Chinese developer perspective (GAP: dimension 8)
4. search-google-scholar — academic coverage (GAP: dimension 4)
5. search-producthunt — recent product launches (GAP: dimension 7)
6. search-reddit — community sentiment
```

Pass this list to gene-query.md for platform-targeted query generation.

# Quality Bar

A good channel selection produces 5-10 channels where each one is expected to find something the others cannot. If two selected channels would return substantially the same results, drop one.
