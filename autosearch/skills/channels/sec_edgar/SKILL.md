---
name: sec_edgar
description: US public company filings (10-K, 10-Q, 8-K) via SEC EDGAR full-text search — financial and regulatory disclosures for research.
version: 1
languages: [en]
methods:
  - id: api_search
    impl: methods/api_search.py
    requires: []
    rate_limit: {per_min: 10, per_hour: 600}
fallback_chain: [api_search]
when_to_use:
  query_languages: [en]
  query_types: [financial, filing, company, regulatory, sec-disclosure]
  avoid_for: [academic, social, multimedia]
quality_hint:
  typical_yield: medium
  chinese_native: false
---

## Overview

SEC EDGAR is the US Securities and Exchange Commission's full-text search across public company filings. For any US-listed company, EDGAR provides authoritative 10-K (annual report), 10-Q (quarterly), 8-K (current event), and proxy or insider filings.

## When to Choose It

- Choose it for US company research, especially financial history, risk factors, regulatory disclosures, and management discussion.
- Choose it when a query implies a publicly traded US company, such as a ticker, "SEC filing", "10-K", or "earnings report".
- Avoid it for general tech news, academic papers, or non-US companies.

## How To Search

- `api_search` queries `https://efts.sec.gov/LATEST/search-index?q=<query>` and maps `hits.hits[*]._source` into filing evidence. Filing URLs are synthesized from `ciks[0]` and `adsh` to point at the SEC Archives index page for the exact filing.

## Known Quirks

- SEC enforces a User-Agent policy. Every request must carry a contact string or the endpoint may effectively block access.
- The search endpoint returns filing metadata only, not filing-body excerpts. Snippets are synthesized from form type and filing dates.
- Coverage is limited to SEC-registered filers, so pure non-US companies are out of scope unless they file with the SEC.
