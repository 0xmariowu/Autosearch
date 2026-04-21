---
name: channels-cn-tech
description: Chinese tech media — 36kr, CSDN, Juejin, InfoQ CN, Sogou Weixin. Industry analysis, developer articles, and company coverage aimed at the Chinese market.
layer: group
domains: [chinese-tech, media]
scenarios: [chinese-tech-news, startup-coverage, developer-articles]
model_tier: Fast
experience_digest: experience.md
---

# Chinese Tech Media Channels

Tech-focused Chinese publishers. Different register and audience than `channels-chinese-ugc` — editorial content, not user-generated.

## Leaf skills

| Leaf | When to use | Tier | Auth |
|---|---|---|---|
| `search-36kr` | Startup / VC / Chinese tech business news | Fast | free |
| `search-csdn` | 中文技术文章 / 教程 / troubleshooting | Fast | free |
| `search-juejin` | 中文前端 / 后端 / 工程文章 | Fast | free |
| `search-infoq-cn` | 企业技术实践 / 架构案例 | Fast | free |
| `search-sogou-weixin` | 微信公众号全文（配合 search-wechat） | Fast | free |

## Routing notes

- For broad Chinese tech sector coverage, combine with `channels-chinese-ugc` (`search-wechat` + `search-zhihu`).
- CSDN and Juejin are developer-facing; 36kr and InfoQ CN are business / architecture-facing. Pick by audience.
