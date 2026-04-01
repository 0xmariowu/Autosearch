---
name: search-csdn
description: "Use when the task needs Chinese developer tutorials, code examples, troubleshooting guides, or technical blog posts from China's largest developer community."
---

# Platform

CSDN — China's largest developer community platform. Rich in code tutorials, troubleshooting articles, and technical blog posts. Strong coverage of practical implementation details.

# When To Choose It

Choose this when:

- you need step-by-step Chinese-language implementation guides
- searching for solutions to specific technical errors (in Chinese context)
- the topic involves frameworks/tools popular in Chinese developer ecosystem
- need code examples with Chinese explanations

# How To Search

Use WebSearch with site filter:

- `site:csdn.net {Chinese keywords}`
- `site:blog.csdn.net {Chinese keywords}` (blog posts specifically)

Query language: Chinese keywords + English technical terms.
Example queries:
- `site:csdn.net 自进化 agent 框架 实现`
- `site:blog.csdn.net LLM RAG 架构 最佳实践`
- `site:csdn.net Claude API 调用 教程`

# Standard Output Schema

- `source`: `"csdn"`

# Date Metadata

CSDN articles show publication dates. Extract from snippet or URL path dates.

# Quality Bar

This skill is working when it discovers practical implementation guides and code examples that English-language searches miss.
