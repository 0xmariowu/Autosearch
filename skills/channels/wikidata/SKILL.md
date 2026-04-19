---
name: wikidata
description: Structured entity data (people, places, concepts) from Wikidata knowledge graph.
version: 1
languages: [en, mixed]
methods:
  - id: api_search
    impl: methods/api_search.py
    requires: []
    rate_limit: {per_min: 60, per_hour: 2000}
fallback_chain: [api_search]
when_to_use:
  query_languages: [en, mixed]
  query_types: [entity-definition, disambiguation, structured-facts]
  domain_hints: [science, history, culture, people, places]
quality_hint:
  typical_yield: medium
  chinese_native: false
---

## Overview

Wikidata provides authoritative structured entity descriptions for people, places, organizations, scientific concepts, and other knowledge-graph items through the public Wikidata Action API. It is useful when the query needs compact entity definitions, disambiguation, or canonical identifiers rather than long-form narrative content.

## Known Quirks

- Results expose short entity descriptions, not long-form article content.
- `language=en` is hardcoded in v1.
- `type=item` intentionally filters out lexemes and properties.
