# Skill Attribution
> Source: self-written, plan `autosearch-0418-channels-and-skills.md` § F002c.

---
name: zhihu
description: Chinese Q&A platform with deep technical discussions and user experience reports — use when query is Chinese or mixed and targets developer opinions, comparisons, or tutorials.
version: 1
languages: [zh, mixed]
methods:
  - id: via_tikhub
    impl: methods/via_tikhub.py
    requires: [env:TIKHUB_API_KEY]
    rate_limit: {per_min: 60, per_hour: 1000}
fallback_chain: [via_tikhub]
when_to_use:
  query_languages: [zh, mixed]
  query_types: [technical, experience-report, product-review, tutorial, comparison]
  avoid_for: [real-time-news, academic-papers]
quality_hint:
  typical_yield: medium-high
  chinese_native: true
layer: leaf
domains: [chinese-ugc]
scenarios: [chinese-native, deep-qna, expert-opinion]
model_tier: Fast
experience_digest: experience.md
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

- `via_tikhub` - Use TikHub's paid Zhihu article search API for direct article discovery without relying on local cookies.
- `api_search` - Use Zhihu search endpoints to discover questions, answers, and articles matching the query, then extract canonical URLs and brief snippets.
- `api_answer_detail` - Fetch fuller answer detail for shortlisted posts using authenticated endpoints when a cookie is available.
- `api_answer_detail` - Normalize answer author, vote count, created time, question title, and answer body excerpt for downstream ranking.

## Known Quirks

- TikHub access is paid and currently costs about `$0.0036/request`, so it should stay first in fallback only where the direct API win justifies spend.
- Unauthenticated search can work, but deeper answer detail is more reliable with a valid `cookie:zhihu`.
- Zhihu content quality varies from expert long-form posts to shallow SEO-style reposts.
- Answer pages can change structure, so detail extraction is more brittle than simple search discovery.
- Technical queries in Chinese often benefit from strong entity normalization because product names mix English and Chinese tokens.

# Quality Bar

- Evidence items have non-empty title and url.
- No crash on empty or malformed API response.
- Source channel field matches the channel name.
