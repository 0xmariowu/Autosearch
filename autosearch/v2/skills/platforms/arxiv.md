---
name: arxiv
type: platform
version: "1.0"
requires: [curl, python3]
triggers: [arxiv, paper, research, academic, preprint, study]
cost: free
platforms: [arxiv]
dimensions: []
---
## Purpose
Search arXiv preprints for a query when recent academic papers, technical research, and study-oriented evidence are likely to matter.

## When to Use
- Use when the task asks for papers, preprints, research literature, or academic prior art.
- Requires `curl` and `python3`, and works against the public arXiv Atom API.
- Prefer this skill when recency, abstract relevance, and subject-category fit are more important than community discussion.
- Do not use it as the only source for peer-reviewed consensus, citations, or non-arXiv publications.

## Execute
1. Define inputs, defaults, and temporary paths.
```bash
QUERY="${QUERY:-ai agent}"
LIMIT="${LIMIT:-10}"
OUT="${OUT:-/tmp/arxiv.jsonl}"
NOW="${NOW:-$(date -u +%Y-%m-%dT%H:%M:%SZ)}"
SINCE="${SINCE:-1970-01-01T00:00:00Z}"
RAW="$(mktemp)"
export QUERY LIMIT OUT NOW SINCE RAW
```
2. Fetch recent matching entries from the arXiv API.
```bash
curl -sG 'https://export.arxiv.org/api/query' \
  --data-urlencode "search_query=all:$QUERY" \
  --data-urlencode 'start=0' \
  --data-urlencode "max_results=$LIMIT" \
  --data-urlencode 'sortBy=submittedDate' \
  --data-urlencode 'sortOrder=descending' \
  > "$RAW"
```
3. Parse the Atom feed, apply `SINCE`, and convert entries into AutoSearch JSONL.
```bash
python3 - <<'PY'
import datetime
import json
import os
import re
import xml.etree.ElementTree as ET

ATOM = {"atom": "http://www.w3.org/2005/Atom"}

def parse_iso(value):
    if not value:
        return None
    return datetime.datetime.fromisoformat(value.replace("Z", "+00:00"))

def clean(text, limit=480):
    text = re.sub(r"\s+", " ", (text or "")).strip()
    return text[: limit - 3] + "..." if len(text) > limit else text

since = parse_iso(os.environ["SINCE"])
query = os.environ["QUERY"]
now = os.environ["NOW"]
root = ET.parse(os.environ["RAW"]).getroot()

with open(os.environ["OUT"], "w", encoding="utf-8") as out:
    for entry in root.findall("atom:entry", ATOM):
        url = (entry.findtext("atom:id", default="", namespaces=ATOM) or "").strip()
        title = clean(entry.findtext("atom:title", default="", namespaces=ATOM), limit=240)
        summary = clean(entry.findtext("atom:summary", default="", namespaces=ATOM))
        published = (entry.findtext("atom:published", default="", namespaces=ATOM) or "").strip()
        published_dt = parse_iso(published) if published else None
        if since and published_dt and published_dt < since:
            continue
        authors = []
        for author in entry.findall("atom:author", ATOM):
            name = clean(author.findtext("atom:name", default="", namespaces=ATOM), limit=200)
            if name:
                authors.append(name)
        categories = []
        for category in entry.findall("atom:category", ATOM):
            term = category.attrib.get("term")
            if term:
                categories.append(term)
        arxiv_id = url.rsplit("/", 1)[-1] if url else None
        row = {
            "url": url,
            "title": title or url,
            "source": "arxiv",
            "snippet": summary,
            "found_at": now,
            "query": query,
            "metadata": {
                "arxiv_id": arxiv_id,
                "categories": categories,
                "published_at": published,
                "authors": authors,
            },
        }
        print(json.dumps(row, ensure_ascii=False), file=out)
PY
```

## Parse
Write UTF-8 JSONL to `$OUT`. Each line uses the base schema and adds `arxiv_id`, `categories`, `published_at`, and `authors` in `metadata`, with `authors` as a JSON array of display names and `categories` as arXiv subject terms.

## Score Hints
- `relevance`: title and abstract overlap with `QUERY` are the strongest content signals.
- `freshness`: recent `published_at` dates are especially important for active research areas.
- `diversity`: papers spanning multiple useful `categories` can improve topic coverage.
- `efficiency`: arXiv can surface recent technical work quickly without crawling publisher sites.
- Extra signal: category match is often a good proxy for topical fit when keyword overlap is noisy.

## Known Limitations
- arXiv is a preprint server, so results are not guaranteed to be peer reviewed.
- The API response is Atom XML, and malformed network responses can cause parse failures.
- Searches use `all:$QUERY`, which is broad and can return noisy matches for short or overloaded terms.
- If results are empty or malformed, retry with quoted phrases, author names, or a narrower research keyword set.

## Evolution Notes
- Tune: switch between `all:` and field-specific query templates for title-heavy or category-heavy searches.
- Tried: sort by submitted date and preserve full author and category metadata for downstream ranking.
- Next: add optional category filters and citation-enrichment hooks for stronger academic ranking.
