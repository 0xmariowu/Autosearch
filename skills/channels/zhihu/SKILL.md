# Skill Attribution
> Source: self-written, plan `autosearch-0418-channels-and-skills.md` § F002c.

---
name: zhihu
description: Chinese Q&A platform with deep technical discussions and user experience reports — use when query is Chinese or mixed and targets developer opinions, comparisons, or tutorials.
version: 1
languages: [zh, mixed]
methods:
  - id: api_search
    impl: methods/api_search.py
    requires: []
    rate_limit: {per_min: 30, per_hour: 500}
  - id: api_answer_detail
    impl: methods/api_answer.py
    requires: [cookie:zhihu]
    rate_limit: {per_min: 20, per_hour: 300}
fallback_chain: [api_search, api_answer_detail]
when_to_use:
  query_languages: [zh, mixed]
  query_types: [technical, experience-report, product-review, tutorial, comparison]
  avoid_for: [real-time-news, academic-papers]
quality_hint:
  typical_yield: medium-high
  chinese_native: true
---

## Overview

Zhihu is a major Chinese question-and-answer platform with long-form posts, answer threads, and high-signal technical comparisons. It is useful when the user wants Chinese-language reasoning, practical experience reports, or side-by-side discussion of tools and products.

For autosearch coverage, this channel brings native Chinese discourse that is not well represented on English platforms. It matters because many Chinese developer and user communities publish nuanced tutorials, migration notes, and comparative buying advice directly on Zhihu.

## When to Choose It

- Choose it for Chinese or mixed-language queries about technical tradeoffs, tutorials, or product comparisons.
- Choose it when user experience reports and long-form answers are more useful than short posts.
- Choose it for developer opinion in Chinese around frameworks, devices, services, or workflow tools.
- Prefer it over general social feeds when depth and explanation matter.
- Avoid it for breaking news or formal paper lookup.

## How To Search (Planned)

- `api_search` - Use Zhihu search endpoints to discover questions, answers, and articles matching the query, then extract canonical URLs and brief snippets.
- `api_answer_detail` - Fetch fuller answer detail for shortlisted posts using authenticated endpoints when a cookie is available.
- `api_answer_detail` - Normalize answer author, vote count, created time, question title, and answer body excerpt for downstream ranking.

## Known Quirks

- Unauthenticated search can work, but deeper answer detail is more reliable with a valid `cookie:zhihu`.
- Zhihu content quality varies from expert long-form posts to shallow SEO-style reposts.
- Answer pages can change structure, so detail extraction is more brittle than simple search discovery.
- Technical queries in Chinese often benefit from strong entity normalization because product names mix English and Chinese tokens.
