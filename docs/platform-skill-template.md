# Platform Skill Standard Sections

Append these sections to the END of every platform search skill (before any existing "Quality Bar" section, or at the very end if none exists).
Do NOT replace existing content — only APPEND.
If the skill already has similar content (like search-ddgs.md and search-github-repos.md which already have date extraction notes), merge intelligently — don't duplicate.

## Section to append:

```markdown
# Standard Output Schema

Write each result as a JSON line conforming to the canonical evidence schema:

```json
{
  "url": "canonical URL",
  "title": "result title",
  "snippet": "description or summary",
  "source": "{PLATFORM_TAG}",
  "query": "the query that found this",
  "metadata": {}
}
```

The `source` field must be exactly `{PLATFORM_TAG}` for this platform.
judge.py uses `source` for diversity scoring — inconsistent tags hurt the diversity dimension.

After collecting results, pass them to normalize-results.md for cross-platform dedup and extract-dates.md for freshness metadata.

# Date Metadata

Extract dates from platform-specific fields and write to metadata:

- `metadata.published_at` — when the content was created (ISO 8601)
- `metadata.updated_at` — when the content was last modified (ISO 8601)
- `metadata.created_utc` — creation timestamp (ISO 8601)

See extract-dates.md for the full extraction priority and format rules.
Missing dates score as zero freshness in judge.py.
```

## Platform-specific PLATFORM_TAG values:

- search-ddgs.md → `web-ddgs`
- search-exa.md → `exa`
- search-github-code.md → `github`
- search-github-issues.md → `github`
- search-github-repos.md → `github`
- search-hackernews.md → `hn`
- search-hn-exa.md → `hn`
- search-huggingface.md → `hf`
- search-reddit.md → `reddit`
- search-reddit-exa.md → `reddit`
- search-searxng.md → `searxng`
- search-tavily.md → `tavily`
- search-twitter-exa.md → `twitter`
- search-twitter-xreach.md → `twitter`
