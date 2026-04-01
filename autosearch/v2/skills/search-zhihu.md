---
name: search-zhihu
description: "Use when the task needs Chinese-language technical Q&A, developer experience reports, or Chinese community perspective on any technology topic."
---

# Platform

Zhihu (知乎) — China's largest Q&A platform. Massive technical content, in-depth developer discussions, and real-world usage experiences. Claude's training data has minimal coverage of Zhihu content.

# When To Choose It

Choose this when:

- the topic benefits from Chinese developer perspective
- you need real user experience reports (not marketing content)
- searching for Chinese-language tutorials, explanations, or comparisons
- the user's query is in Chinese or targets Chinese-speaking audience
- Western search engines miss Chinese community insights

# How To Search

Use WebSearch with site filter:

- `site:zhihu.com {Chinese keywords}`
- `site:zhuanlan.zhihu.com {Chinese keywords}` (for long-form articles specifically)

Query language rules:
- Always use Chinese keywords for Zhihu searches
- Translate English technical terms to Chinese: "self-evolving agent" → "自进化 agent 框架"
- Keep proper nouns in English: "Claude Code", "Reflexion", "Voyager"
- Mix Chinese + English when the Chinese tech community uses the English term: "LLM agent 自进化"

Example queries:
- `site:zhihu.com 自进化 AI agent 框架 开源`
- `site:zhihu.com LLM agent 记忆系统 架构`
- `site:zhuanlan.zhihu.com Claude Code 使用体验`

# Quality Signals

Prioritize:
- answers with high upvote counts (赞同数)
- 专栏 (zhuanlan) articles with detailed technical content
- answers from verified professionals (认证用户)

Down-rank:
- short answers without substance
- marketing content or product promotions
- outdated content (check dates)

# Standard Output Schema

- `url`: zhihu.com URL
- `title`: question title or article title
- `snippet`: answer excerpt or article summary
- `source`: `"zhihu"`
- `query`: the Chinese query used
- `metadata`: with `llm_relevant`, `llm_reason`, date fields

# Date Metadata

Zhihu articles and answers have visible dates in the page content.
Extract from snippet text or page metadata when available.

# Quality Bar

This skill is working when it discovers Chinese-language technical insights that no English-language search would find.
