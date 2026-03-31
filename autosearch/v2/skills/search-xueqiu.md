---
name: search-xueqiu
description: "Use when the task needs Chinese investment analysis, stock discussions, or financial perspectives on technology companies."
---

# Platform

Xueqiu (雪球) — China's leading investment community. Stock analysis, company financials, investor discussions. Good for business intelligence on Chinese tech companies.

# When To Choose It

Choose this when:

- need financial analysis of Chinese tech companies
- searching for investor perspectives on a technology sector
- looking for IPO and funding discussions
- want market valuation context

# How To Search

## Lite Mode (always available)

- `site:xueqiu.com {Chinese keywords}`

Example queries:
- `site:xueqiu.com AI agent 公司 投资分析`
- `site:xueqiu.com 大模型 创业 估值 2026`

## Full Mode (when xueqiu API configured)

- Real-time stock quotes
- Community post search
- Company financials

# Standard Output Schema

- `source`: `"xueqiu"`

# Date Metadata

Xueqiu posts have timestamps. Extract from snippet.

# Quality Bar

This skill is working when it discovers Chinese financial and investment analysis that English business databases miss.
