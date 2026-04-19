# Self-written for task F201

---
name: package_search
description: Discover packages across PyPI (exact-name lookup) and npm (full-text search) registries.
version: 1
languages: [en, mixed]
methods:
  - id: api_search
    impl: methods/api_search.py
    requires: []
    rate_limit: {per_min: 20, per_hour: 300}
fallback_chain: [api_search]
when_to_use:
  query_languages: [en, mixed]
  query_types: [library, package, sdk, dependency, installation]
  domain_hints: [software, programming]
quality_hint:
  typical_yield: medium
  chinese_native: false
---

`package_search` helps discover software packages across two public registries: PyPI for Python packages and npm for JavaScript and Node.js packages. It combines exact-name PyPI lookups with npm full-text search so package-related queries can still return useful evidence even when one registry has limited recall.

## Known Quirks

- PyPI has no official JSON search API, so this channel only does exact-name lookups against `/pypi/<name>/json`; multi-word queries are split into tokens and only the first 5 tokens are tried.
- npm supports real full-text search through the public registry search endpoint and is the broader-recall half of this channel.
- Descriptions are truncated to 300 characters for snippets, and PyPI README-sized `description` content is intentionally excluded in favor of the shorter `summary`.
