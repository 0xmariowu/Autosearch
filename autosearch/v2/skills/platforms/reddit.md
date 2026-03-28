---
name: reddit
type: platform
version: "1.0"
requires: [curl, python3]
triggers: [reddit, discussion, community, opinion, experience, review]
cost: free
platforms: [reddit]
dimensions: []
---
## Purpose
Search Reddit discussions for a query when community opinions, hands-on experience, and review-style evidence are likely to matter.

## When to Use
- Use when the task asks for Reddit directly or when community feedback and user experience are important.
- Requires `curl` and `python3`, and works against Reddit's public JSON endpoint without authentication.
- Prefer this skill for discussion-heavy topics such as product comparisons, usage pain points, and candid reviews.
- Do not use it as the only source for official facts, policy details, or highly time-sensitive claims.

## Execute
1. Define inputs, defaults, and temporary paths.
```bash
QUERY="${QUERY:-ai agent}"
LIMIT="${LIMIT:-10}"
OUT="${OUT:-/tmp/reddit.jsonl}"
NOW="${NOW:-$(date -u +%Y-%m-%dT%H:%M:%SZ)}"
SINCE="${SINCE:-1970-01-01T00:00:00Z}"
RAW="$(mktemp)"
export QUERY LIMIT OUT NOW SINCE RAW
```
2. Fetch Reddit search results from the public JSON API.
```bash
curl -sG 'https://www.reddit.com/search.json' \
  --data-urlencode "q=$QUERY" \
  --data-urlencode 'sort=relevance' \
  --data-urlencode "limit=$LIMIT" \
  -H 'User-Agent: AutoSearch/2.0' \
  > "$RAW"
```
3. Filter by `SINCE` and convert the response into AutoSearch JSONL.
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

def clean(text, limit=320):
    text = re.sub(r"\s+", " ", (text or "")).strip()
    return text[: limit - 3] + "..." if len(text) > limit else text

since = parse_iso(os.environ["SINCE"])
query = os.environ["QUERY"]
now = os.environ["NOW"]

with open(os.environ["RAW"], encoding="utf-8") as fh:
    payload = json.load(fh)

items = payload.get("data", {}).get("children", [])

with open(os.environ["OUT"], "w", encoding="utf-8") as out:
    for child in items:
        item = child.get("data", {})
        created_utc = item.get("created_utc")
        if created_utc is None:
            continue
        created_at = datetime.datetime.fromtimestamp(created_utc, tz=datetime.timezone.utc)
        if since and created_at < since:
            continue
        permalink = item.get("permalink") or ""
        url = f"https://www.reddit.com{permalink}" if permalink.startswith("/") else item.get("url")
        if not url:
            continue
        snippet = clean(item.get("selftext") or item.get("url_overridden_by_dest") or "")
        row = {
            "url": url,
            "title": item.get("title") or url,
            "source": "reddit",
            "snippet": snippet,
            "found_at": now,
            "query": query,
            "metadata": {
                "score": item.get("score", 0),
                "num_comments": item.get("num_comments", 0),
                "subreddit": item.get("subreddit"),
                "author": item.get("author"),
                "created_utc": int(created_utc),
            },
        }
        print(json.dumps(row, ensure_ascii=False), file=out)
PY
```

## Parse
Write UTF-8 JSONL to `$OUT`. Each line uses the base schema and adds `score`, `num_comments`, `subreddit`, `author`, and `created_utc` in `metadata`, where `created_utc` is the original Reddit UNIX timestamp.

## Score Hints
- `relevance`: subreddit fit and title overlap with `QUERY` are strong indicators.
- `freshness`: recent posts usually matter more for fast-changing products or platform behavior.
- `quantity`: several useful threads from different subreddits improve coverage.
- `efficiency`: Reddit often surfaces hands-on experience faster than broader web search.
- Extra signal: high `score` and `num_comments` usually correlate with richer discussion, but niche subreddits can still be valuable with lower totals.

## Known Limitations
- Reddit's public endpoint can rate-limit aggressively and sometimes returns incomplete or inconsistent payloads.
- Search relevance is platform-defined and can bias toward larger subreddits.
- Link posts may have weak `snippet` text because the public search payload often lacks detailed body content.
- If results are empty or malformed, retry with narrower phrasing, include a subreddit name in `QUERY`, or reduce `LIMIT`.

## Evolution Notes
- Tune: append subreddit qualifiers for narrower domain-specific community searches.
- Tried: keep authentication out of scope by using the public JSON endpoint with a fixed user agent.
- Next: add a comment-search variant when discussion depth matters more than post titles.
