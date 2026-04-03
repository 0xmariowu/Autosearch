---
name: search-npm-pypi
description: "Use when the task needs to discover specific packages, libraries, or SDKs available in npm or PyPI registries."
---

# Platform

npm (JavaScript/TypeScript) and PyPI (Python) package registries. Discover actual installable packages, check download counts, find alternatives.

# When To Choose It

Choose this when:

- looking for libraries that implement a specific capability
- need to verify a package exists and is actively maintained
- want to compare competing packages by popularity (downloads)
- searching for SDKs for a specific service or API

# How To Search

- `site:npmjs.com {package keywords}` for JavaScript/TypeScript
- `site:pypi.org {package keywords}` for Python

Example queries:
- `site:pypi.org self-evolving agent framework`
- `site:npmjs.com semantic scholar API client`
- `site:pypi.org LLM evaluation harness`

# Standard Output Schema

- `source`: `"npm-pypi"`

# Date Metadata

Package pages show last publish date. Extract from snippet.

# Quality Bar

This skill is working when it discovers installable packages that GitHub repo search misses (many packages have different names than their repos).
