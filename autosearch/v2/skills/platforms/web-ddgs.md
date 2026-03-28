---
name: web-ddgs
type: platform
version: "1.0"
requires: [python3, ddgs]
triggers: [web, search, website, article, blog, tutorial, documentation]
cost: free
platforms: [duckduckgo]
dimensions: []
---
## Purpose
Search the public web through DuckDuckGo when broad web coverage is needed for articles, tutorials, websites, and documentation.

## When to Use
- Use when the task is general web discovery rather than a platform-specific search.
- Requires `python3` and the `ddgs` package in the active environment.
- Prefer this skill for documentation, blog posts, tutorials, and product pages across many domains.
- Do not rely on it alone for date-sensitive claims because result timestamps are usually unavailable.

## Execute
1. Define inputs, defaults, and output path.
```bash
QUERY="${QUERY:-ai agent}"
LIMIT="${LIMIT:-10}"
OUT="${OUT:-/tmp/web-ddgs.jsonl}"
NOW="${NOW:-$(date -u +%Y-%m-%dT%H:%M:%SZ)}"
SINCE="${SINCE:-1970-01-01T00:00:00Z}"
export QUERY LIMIT OUT NOW SINCE
```
2. Run a DuckDuckGo text search and convert the results into AutoSearch JSONL.
```bash
python3 - <<'PY'
import json
import os
import re
from urllib.parse import urlparse

from ddgs import DDGS

def clean(text, limit=320):
    text = re.sub(r"\s+", " ", (text or "")).strip()
    return text[: limit - 3] + "..." if len(text) > limit else text

query = os.environ["QUERY"]
limit = int(os.environ["LIMIT"])
now = os.environ["NOW"]

with DDGS() as ddgs:
    results = list(ddgs.text(query, max_results=limit) or [])

with open(os.environ["OUT"], "w", encoding="utf-8") as out:
    for item in results:
        href = item.get("href") or item.get("url")
        if not href:
            continue
        domain = urlparse(href).netloc.lower()
        row = {
            "url": href,
            "title": clean(item.get("title") or href, limit=240),
            "source": "web-ddgs",
            "snippet": clean(item.get("body") or item.get("snippet") or ""),
            "found_at": now,
            "query": query,
            "metadata": {
                "domain": domain,
                "href": href,
            },
        }
        print(json.dumps(row, ensure_ascii=False), file=out)
PY
```

## Parse
Write UTF-8 JSONL to `$OUT`. Each line uses the base schema and adds `domain` and `href` in `metadata`, where `domain` is derived from the result URL and `href` preserves the original DuckDuckGo result link.

## Score Hints
- `relevance`: exact keyword overlap in the title is a strong signal for web results.
- `diversity`: distinct domains improve coverage when many articles say similar things.
- `efficiency`: this skill is useful when one broad query can surface docs, tutorials, and official sites together.
- Extra signal: high-authority technical domains such as vendor docs, standards bodies, major code hosts, and established engineering publications usually outrank generic content farms.

## Known Limitations
- DuckDuckGo text results usually do not expose reliable publish dates, so `SINCE` is defined for interface consistency but not enforced here.
- Result quality can vary by query phrasing, region, and remote rate limiting.
- The `ddgs` package must already be installed; otherwise the import fails immediately.
- If results are empty or malformed, retry with more specific keywords, quoted phrases, or a site qualifier in `QUERY`.

## Evolution Notes
- Tune: add optional domain allowlists or site-specific query templates for official-doc searches.
- Tried: keep parsing minimal and depend on URL-derived `domain` instead of scraping pages.
- Next: add optional news-mode or image-mode variants if the runner needs those modalities.
