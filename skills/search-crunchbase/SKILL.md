---
name: search-crunchbase
description: "Use when the task needs startup funding data, company profiles, investor information, or business intelligence about technology companies."
---

# Platform

Crunchbase — comprehensive startup and business database. Funding rounds, company profiles, key people, investors. Essential for competitive analysis and market research.

# When To Choose It

Choose this when:

- need funding information for a company or sector
- searching for companies building products in a specific domain
- want investor and acquisition data
- need company size, founding date, or key personnel

# How To Search

- `site:crunchbase.com {company or sector keywords}`

Example queries:
- `site:crunchbase.com self-evolving AI agent funding`
- `site:crunchbase.com "AI agent" startup series A 2025 2026`
- `site:crunchbase.com Letta funding`

# Standard Output Schema

- `source`: `"crunchbase"`

# Date Metadata

Crunchbase entries have funding round dates. Extract from snippet.

# Quality Bar

This skill is working when it discovers verified funding and company data that press releases and blog posts don't provide with precision.
