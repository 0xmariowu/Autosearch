---
name: wechat_channels
description: WeChat Channels (视频号) short video search via TikHub. Returns videos matching a keyword — creator name, title, duration, CDN video URL. Best for Chinese-language video content on WeChat ecosystem. Requires TIKHUB_API_KEY.
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
  query_types: [video, tutorial, knowledge, opinion, trending]
  avoid_for: [academic-papers, text-only-query, overseas-content]
quality_hint:
  typical_yield: medium
  content_type: short-video
layer: leaf
domains: [social, video, chinese-ugc]
scenarios: [Chinese video discovery, WeChat ecosystem research]
model_tier: Fast
experience_digest: experience/experience.md
---

Search WeChat Channels (视频号) for Chinese-language short videos.
Returns title, creator, duration, and video CDN URL.

Note: Video CDN URLs (`findermp.video.qq.com`) require WeChat session for download.
For transcription, use `video-to-text` skills on videos from supported platforms (bilibili/douyin/youtube).

## MCP tool example

```
run_channel("wechat_channels", "Python机器学习教程", k=10)
```

# Quality Bar

- ≥3 results with valid `wechat_channels:{creator}` source
- Title extracted, HTML tags cleaned
- Video URL returned for reference
