# Skill Attribution
> Source: self-written, plan `autosearch-0418-channels-and-skills.md` § F002c.

---
name: bilibili
description: Chinese tech video platform with tutorials, conference recordings, and uploader-authored articles, via TikHub.
version: 1
languages: [zh, mixed]
methods:
  - id: via_tikhub
    impl: methods/via_tikhub.py
    requires: [env:TIKHUB_API_KEY]
    rate_limit: {per_min: 60, per_hour: 1000}
  - id: api_search
    impl: methods/api_search.py
    requires: []
    rate_limit: {per_min: 30, per_hour: 500}
fallback_chain: [api_search, via_tikhub]
when_to_use:
  query_languages: [zh, mixed]
  query_types: [tutorial-video, comparison, breakdown, tech-opinion]
  avoid_for: [text-only-query, academic-papers]
quality_hint:
  typical_yield: medium
  chinese_native: true
layer: leaf
domains: [chinese-ugc]
scenarios: [chinese-native, video-content, tutorial, tech-opinion]
model_tier: Fast
experience_digest: experience.md
---

## Overview

Bilibili is a Chinese video platform with strong coverage in tutorials, hardware comparisons, software explainers, gaming, and creator-led technical commentary. It is useful when the user wants Chinese-language visual content rather than text-first references.

For autosearch coverage, this channel fills a gap between global video search and Chinese-native creator ecosystems. It matters because many Chinese tutorials, teardown videos, and side-by-side product breakdowns are published on Bilibili long before they appear elsewhere.

## When to Choose It

- Choose it for Chinese tutorial-video and breakdown queries.
- Choose it for device comparisons, creator explainers, and tech-opinion in video form.
- Choose it when visual demonstration matters more than short text description.
- Prefer it over YouTube when the target audience, terminology, or creator ecosystem is Chinese-native.
- Avoid it for pure text lookup or formal academic paper search.

## How To Search (Planned)

- `via_tikhub` - Use TikHub's paid Bilibili general search API to retrieve mixed result groups, then map only video and article results into normalized evidence.
- `via_tikhub` - Strip Bilibili search-hit HTML markers, normalize uploader identity, and derive canonical video or article URLs from `bvid` / article ids when needed.
- `api_search` - Call Bilibili search endpoints for videos and creators using Chinese or mixed query text, then rank by topical relevance and engagement.
- `api_video_detail` - Fetch richer metadata for shortlisted videos with authenticated detail access when `cookie:bilibili` is available.
- `api_video_detail` - Normalize title, uploader, publish time, duration, play stats, and canonical video URL.

## Known Quirks

- TikHub billing applies per request, so this route should avoid wasteful exploratory fan-out.
- Search titles and descriptions can include `<em class="keyword">` hit markers that must be stripped before ranking or display.
- Only `video` and `article` result types are mapped today; user, live, and topic-style results are intentionally ignored.
- Basic search works without auth, but video detail and richer metadata are more stable with a valid cookie.
- Many results are entertainment-adjacent, so ranking must distinguish tech and tutorial intent carefully.
- Some high-signal tutorials use slang or fandom terminology that generic keyword matching may miss.
- Video popularity can dominate search ordering even when a smaller creator has the better explanation.

# Quality Bar

- Evidence items have non-empty title and url.
- No crash on empty or malformed API response.
- Source channel field matches the channel name.
