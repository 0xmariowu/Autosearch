---
name: extract-dates
description: "Use after collecting results to extract publication and update dates from all available signals and write them to metadata fields judge.py expects."
---

# Purpose

judge.py scores freshness by checking `metadata.published_at`, `metadata.created_utc`, and `metadata.updated_at`.
Most raw search results do not include these fields, but the dates are often extractable from other signals.
Without date extraction, freshness scores near zero even when most content is recent.

# Date Sources (Priority Order)

Try these sources in order. Stop at the first successful extraction per result.

## 1. Structured API Fields (most reliable)

- GitHub `updatedAt` → `metadata.updated_at`
- GitHub `createdAt` → `metadata.created_utc`
- GitHub `pushedAt` → use as fallback for `updated_at` if updatedAt missing
- arXiv API `published` field → `metadata.published_at`
- Reddit `created_utc` → `metadata.created_utc`
- HN `time` field → `metadata.created_utc`

## 2. ID-Embedded Dates

- arXiv paper IDs encode submission date: `2403.12345` = March 2024, `2603.24517` = March 2026
  Parse: first 2 digits = year (20xx), next 2 digits = month
  Write to `metadata.published_at` as `20{YY}-{MM}-01T00:00:00Z`

## 3. URL Path Date Segments

Scan the URL path for date patterns:
- `/2025/03/15/article-name` → 2025-03-15
- `/blog/2026-01-article` → 2026-01
- `/posts/20250315-topic` → 2025-03-15

Only extract when the pattern is unambiguous (4-digit year followed by 1-2 digit month).
Do not guess from 2-digit numbers that could be anything.

## 4. Snippet/Title Text Patterns

Scan the snippet and title for date mentions:
- "Published March 15, 2025" → 2025-03-15
- "Updated: 2026-01-20" → 2026-01-20
- "NeurIPS 2023" → 2023-12-01 (conference month approximation)
- "ICLR 2025" → 2025-05-01
- "ICML 2024" → 2024-07-01
- "(2025)" after a paper title → 2025-01-01

Conference date approximation is acceptable — the freshness window is 183 days, so month-level accuracy is sufficient.

## 5. HTTP Headers (if page was fetched)

If fetch-webpage.md retrieved full content:
- `Last-Modified` header → `metadata.updated_at`
- `<meta property="article:published_time">` → `metadata.published_at`
- `<meta name="date">` → `metadata.published_at`

# Output Format

All dates must be ISO 8601: `YYYY-MM-DDTHH:MM:SSZ`
If only year-month is known, use first of month: `2025-03-01T00:00:00Z`
If only year is known, use January first: `2025-01-01T00:00:00Z`

# Rules

- If no date can be extracted, leave the fields absent. Do not invent dates.
- If multiple dates are available, prefer the most specific one.
- `published_at` = when the content was first created
- `updated_at` = when the content was last modified
- `created_utc` = Unix-convention creation time (same as published_at for most sources)
- judge.py checks all three fields; having any one is sufficient for freshness scoring.

# Quality Bar

After date extraction, at least 60% of results should have at least one date field populated.
If the rate is below 60%, the sources likely have dates that the extraction rules above do not cover — consider adding a new rule.
