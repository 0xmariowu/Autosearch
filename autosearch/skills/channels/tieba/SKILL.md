---
name: tieba
description: Use for Chinese community forum discussions on Baidu Tieba when query involves Chinese tech topics, product feedback, or hobby communities not covered by xiaohongshu/zhihu.
version: 1
languages: [zh]
methods:
  - id: api_search
    impl: methods/api_search.py
    requires: []
    rate_limit: {per_min: 10, per_hour: 200}
fallback_chain: [api_search]
when_to_use:
  query_languages: [zh]
  query_types: [community, product-feedback, hobby, chinese-ugc]
  avoid_for: [academic, english, real-time-news]
quality_hint:
  typical_yield: medium
  chinese_native: true
layer: leaf
domains: [chinese-ugc]
scenarios: [chinese-community, product-discussion, hobby-forum, tech-q-and-a]
model_tier: Fast
---

## Overview

百度贴吧（Baidu Tieba）是中国最大的中文社区论坛，按话题分吧。适合找技术讨论、产品评价、爱好者社区等内容。无需 API key，免费。

## When to Choose It

- 查中文用户对特定产品/工具的讨论
- 找特定兴趣圈（游戏吧、数码吧、编程吧）的社区帖子
- 当 zhihu/xiaohongshu 没有足够覆盖时的补充

## How To Search

Uses `tieba.baidu.com/f/search/res` search endpoint with HTML parsing via trafilatura.


# Quality Bar

- Evidence items have non-empty title and url.
- No crash on empty or malformed HTML response.
- Source channel field matches "tieba".
