---
name: channels-chinese-ugc
description: Chinese UGC / social platforms — Bilibili, Weibo, Xiaohongshu, Douyin, Zhihu, Xiaoyuzhou podcasts, WeChat, Kuaishou, V2EX, Xueqiu.
layer: group
domains: [chinese-ugc]
scenarios: [chinese-native, opinion-mining, recency, verification, product-review]
model_tier: Fast
experience_digest: experience.md
---

# Chinese UGC Channels

Opinions, experiences, product reviews, and discussions from Chinese social platforms. Strongest differentiator of autosearch — native Claude WebSearch rarely reaches these surfaces.

## Leaf skills

| Leaf | When to use | Tier | Auth |
|---|---|---|---|
| `search-bilibili` | 视频 / 教程讨论 / tech videos | Fast | free + TikHub fallback |
| `search-weibo` | 热搜 / 话题 / 公众意见 | Fast | free + TikHub fallback |
| `search-xiaohongshu` | 产品口碑 / 生活方式 / 真实使用 | Fast | TikHub required |
| `search-douyin` | 短视频 / 抖音观点 | Fast | TikHub paid or free mcporter MCP |
| `search-zhihu` | 中文问答 / 深度讨论 | Fast | TikHub required |
| `search-xiaoyuzhou` | 中文播客 / 访谈 | Fast | free |
| `search-wechat` | 公众号文章 / 微信长文 | Fast | free (Sogou + Exa) |
| `search-kuaishou` | 短视频下沉市场 | Fast | free native |
| `search-v2ex` | 中文开发者社区 / 技术讨论 | Fast | free (direct API) |
| `search-xueqiu` | 股票 / 投资讨论 / 热帖 | Fast | free native |

## Routing notes

- Chinese-language tasks should keep **at least 2 channels from this group**, regardless of historical yield. Native-language coverage is a non-negotiable contract for Chinese tasks; routing must not shrink it on win-rate alone.
- For hard anti-bot platforms (Xiaohongshu / Douyin / Zhihu), TikHub is the paid fallback; `mcporter` gives the free alternative if user has no TikHub key.
- Podcast-style queries should also check `channels-video-audio` for `search-xiaoyuzhou` + transcription skills.
