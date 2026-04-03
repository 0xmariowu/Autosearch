---
name: search-weibo
description: "Use when the task needs real-time Chinese social media reactions, trending discussions, or public opinion on technology topics."
---

# Platform

Weibo (微博) — China's Twitter equivalent. Real-time discussions, hot searches, tech announcements, public reactions.

# When To Choose It

Choose this when:

- need real-time Chinese public reaction to a tech event
- searching for trending tech discussions in China
- looking for official announcements from Chinese tech companies
- want to gauge Chinese market sentiment

# How To Search

- `site:weibo.com {Chinese keywords}`

- Hot search trending topics
- User feed content
- Comment threads

# Standard Output Schema

- `source`: `"weibo"`

# Date Metadata

Weibo posts have timestamps. Extract from snippet.

# Quality Bar

This skill is working when it discovers real-time Chinese social reactions and trending discussions that delayed web indexing misses.
