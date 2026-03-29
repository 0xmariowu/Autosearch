---
name: hackernews
type: platform
version: "1.0"
requires: [curl, python3]
triggers: [hackernews, hn, show hn, launch, startup, developer]
cost: free
platforms: [hackernews]
dimensions: []
---
## Purpose
Search Hacker News stories for a query when launch visibility, developer interest, and technical discussion are likely to matter.

## When to Use
- Use when the task mentions Hacker News directly or when developer community reaction is valuable.
- Requires `curl` and `python3`, and works against the public HN Algolia search API.
- Prefer this skill for launches, startup discussion, developer tools, and technical trend discovery.
- Do not use it as the only source for official facts or for topics that need broad non-technical coverage.

## Execute
1. Define inputs, defaults, and temporary paths.
```bash
QUERY="${QUERY:-ai agent}"
LIMIT="${LIMIT:-10}"
OUT="${OUT:-/tmp/hackernews.jsonl}"
NOW="${NOW:-$(date -u +%Y-%m-%dT%H:%M:%SZ)}"
SINCE="${SINCE:-1970-01-01T00:00:00Z}"
RAW="$(mktemp)"
export QUERY LIMIT OUT NOW SINCE RAW
```
2. Fetch matching stories from the public Algolia API.
```bash
curl -sG 'https://hn.algolia.com/api/v1/search' \
  --data-urlencode "query=$QUERY" \
  --data-urlencode 'tags=story' \
  --data-urlencode "hitsPerPage=$LIMIT" \
  > "$RAW"
```
3. Convert timestamps, apply `SINCE`, and write AutoSearch JSONL.
```bash
python3 - <<'PY'
import datetime
import json
import os
import re

def parse_iso(value):
    if not value:
        return None
    return datetime.datetime.fromisoformat(value.replace("Z", "+00:00"))

def utc_iso(ts):
    return datetime.datetime.fromtimestamp(ts, tz=datetime.timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")

def clean(text, limit=320):
    text = re.sub(r"\s+", " ", (text or "")).strip()
    return text[: limit - 3] + "..." if len(text) > limit else text

since = parse_iso(os.environ["SINCE"])
query = os.environ["QUERY"]
now = os.environ["NOW"]

with open(os.environ["RAW"], encoding="utf-8") as fh:
    data = json.load(fh)

with open(os.environ["OUT"], "w", encoding="utf-8") as out:
    for hit in data.get("hits", []):
        created_at_i = hit.get("created_at_i")
        published_at = utc_iso(created_at_i) if isinstance(created_at_i, int) else hit.get("created_at")
        published_dt = parse_iso(published_at) if published_at else None
        if since and published_dt and published_dt < since:
            continue
        hn_id = hit.get("objectID")
        url = hit.get("url") or f"https://news.ycombinator.com/item?id={hn_id}"
        row = {
            "url": url,
            "title": hit.get("title") or hit.get("story_title") or url,
            "source": "hackernews",
            "snippet": clean(hit.get("story_text") or hit.get("comment_text") or ""),
            "found_at": now,
            "query": query,
            "metadata": {
                "hn_id": hn_id,
                "points": hit.get("points", 0),
                "num_comments": hit.get("num_comments", 0),
                "author": hit.get("author"),
                "published_at": published_at,
            },
        }
        print(json.dumps(row, ensure_ascii=False), file=out)
PY
```

## Parse
Write UTF-8 JSONL to `$OUT`. Each line uses the base schema and adds `hn_id`, `points`, `num_comments`, `author`, and `published_at` in `metadata`. When Algolia returns no outbound URL, `url` falls back to the canonical Hacker News discussion link for the item ID.

## Score Hints
- `relevance`: exact query terms in the story title usually matter more than loose body matches.
- `freshness`: recent `published_at` is a strong signal for launches, product chatter, and fast-moving topics.
- `quantity`: multiple relevant stories from one query indicate strong topic resonance on HN.
- `efficiency`: HN is high-signal for developer and startup topics because one query often surfaces both launches and critiques.
- Extra signal: higher `points` and `num_comments` often indicate deeper or more influential discussion.

## Known Limitations
- Coverage is heavily biased toward technical, startup, and developer audiences.
- The public Algolia index can lag or omit some stories, especially for niche or very recent posts.
- `SINCE` is applied after fetch, so the API can still return older results before they are filtered locally.
- If results are empty or malformed, retry with shorter product terms, quoted names, or a larger `LIMIT`.

## Evolution Notes
- Tune: experiment with `tags`, typo-tolerant phrasing, and alternative sort orders for better recall.
- Tried: convert `created_at_i` to canonical UTC timestamps and preserve HN discussion URLs when outbound links are missing.
- Next: add optional comment search when discussion detail matters more than launch discovery.
