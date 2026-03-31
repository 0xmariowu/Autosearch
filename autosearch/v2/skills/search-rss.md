---
name: search-rss
description: "Use when the task can benefit from structured feeds — blog aggregators, news feeds, release notifications, or any source publishing RSS/Atom."
---

# Platform

RSS/Atom feeds — structured content syndication. Many tech blogs, news sites, and project release pages publish RSS feeds.

# When To Choose It

Choose this when:

- tracking specific blog or news sources for updates
- need structured feed data with reliable dates
- monitoring project release announcements
- aggregating content from known feed URLs

# How To Search

## Lite Mode (always available)

Cannot search RSS feeds via WebSearch. Use WebSearch to find RSS feed URLs first:
- `{blog name} RSS feed URL`
- Then use `curl {feed_url}` to read the XML directly

## Full Mode (when feedparser installed)

- Parse any RSS/Atom feed into structured entries
- Extract: title, link, summary, published date, author
- feedparser is already installed with agent-reach

# Standard Output Schema

- `source`: `"rss"`

# Date Metadata

RSS feeds have publication dates as standard fields.

# Quality Bar

This skill is working when it provides structured, dated content from specific sources that broad web search doesn't target.
