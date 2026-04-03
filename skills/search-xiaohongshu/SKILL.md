---
name: search-xiaohongshu
description: "Use when the task needs real user experience reports, product reviews, or lifestyle-oriented tech content from China's leading experience-sharing platform."
---

# Platform

Xiaohongshu (小红书/RED) — China's experience-sharing platform. Users share real product experiences, reviews, and tutorials. Strong for honest user feedback that marketing content doesn't show.

# When To Choose It

Choose this when:

- need real user experience with a product or tool
- searching for honest reviews and comparisons
- looking for visual tutorials and step-by-step guides
- the topic has a consumer/user experience dimension

# How To Search

- `site:xiaohongshu.com {Chinese keywords}`
- Note: xiaohongshu has strong anti-scraping, lite mode may return limited results

Example queries:
- `site:xiaohongshu.com AI agent 使用体验`
- `site:xiaohongshu.com Claude 使用心得 2026`
- `site:xiaohongshu.com AI 编程工具 推荐`

Requires Docker + mcporter + xiaohongshu-mcp.
- Search notes by keyword
- Read full note content
- Get comments and engagement data

# Standard Output Schema

- `source`: `"xiaohongshu"`

# Date Metadata

Xiaohongshu notes show dates. Extract from snippet.

# Quality Bar

This skill is working when it discovers real user experiences and honest reviews that no other platform provides.
