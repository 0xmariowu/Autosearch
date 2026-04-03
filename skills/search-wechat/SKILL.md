---
name: search-wechat
description: "Use when the task needs in-depth Chinese articles from WeChat Official Accounts — China's primary long-form content platform for industry analysis and technical deep dives."
---

# Platform

WeChat Official Accounts (微信公众号) — China's dominant long-form content platform. Industry analysis, technical deep dives, company announcements, thought leadership. Much of China's most important tech writing is published here.

# When To Choose It

Choose this when:

- need in-depth Chinese industry analysis
- searching for company announcements and perspectives
- looking for technical deep dives from Chinese tech leaders
- the topic has significant Chinese industry coverage

# How To Search

- `site:mp.weixin.qq.com {Chinese keywords}`
- Returns article titles and brief excerpts
- Cannot read full article content (WeChat restricts scraping)

Example queries:
- `site:mp.weixin.qq.com 自进化 AI agent 技术架构`
- `site:mp.weixin.qq.com LLM 应用 行业分析 2026`
- `site:mp.weixin.qq.com AI agent 创业 融资`

Also try Sogou WeChat search:
- `site:weixin.sogou.com {Chinese keywords}`

- Full article text extraction via camoufox browser automation
- Article search via miku_ai
- Provides complete article content for deep reading and extraction

# Standard Output Schema

- `source`: `"wechat"`

# Date Metadata

WeChat articles show publication dates. Extract from snippet or Sogou results.

# Quality Bar

This skill is working when it discovers in-depth Chinese analysis articles that no English-language or web-search-only approach would find.
