---
name: deduplicate
type: strategy
version: "1.0"
requires: [python3]
triggers: [deduplicate, dedup, duplicates, unique]
cost: free
platforms: []
dimensions: [quantity, diversity]
---
## Purpose
Remove duplicate or near-duplicate evidence across platforms before scoring when merged search results would otherwise overcount the same source.

## When to Use
- Use after multiple platform skills have produced a merged evidence JSONL file and before any scoring or synthesis step.
- Prefer this skill when the same URL, GitHub repository, or article title appears through several platforms.
- Supports `IN` for the merged evidence file and writes the deduplicated artifact to `OUT`.
- Do not use it as the only cleanup step if the input contains malformed JSONL; repair or filter invalid lines first.

## Execute
1. Define inputs, defaults, and the deduplicated output path.
```bash
IN="${IN:-/tmp/merged-evidence.jsonl}"
OUT="${OUT:-/tmp/deduplicated-evidence.jsonl}"
export IN OUT
```
2. Normalize URLs, merge duplicate clusters, prefer richer platforms, and write deduplicated JSONL to `$OUT`.
```bash
python3 - <<'PY'
import json
import os
import re
from urllib.parse import parse_qsl, urlencode, urlparse, urlunparse

platform_weight = {
    "github": 5,
    "arxiv": 4,
    "web-ddgs": 3,
    "hackernews": 2,
    "reddit": 1,
}

stopwords = {
    "a", "an", "and", "for", "from", "how", "in", "of", "on", "or", "the", "to", "vs", "with"
}

def normalize_url(url):
    parsed = urlparse((url or "").strip())
    host = parsed.netloc.lower().replace("www.", "")
    query_items = []
    for key, value in parse_qsl(parsed.query, keep_blank_values=True):
        lowered = key.lower()
        if lowered.startswith("utm_") or lowered in {"ref", "ref_src", "source", "src", "fbclid", "gclid", "mc_cid", "mc_eid"}:
            continue
        query_items.append((key, value))
    path = parsed.path.rstrip("/") or "/"
    normalized = parsed._replace(
        scheme="https",
        netloc=host,
        path=path,
        query=urlencode(query_items, doseq=True),
        fragment="",
    )
    return urlunparse(normalized)

def title_tokens(title):
    return {
        token for token in re.findall(r"[a-z0-9]+", (title or "").lower())
        if token not in stopwords
    }

def jaccard(left, right):
    if not left or not right:
        return 0.0
    overlap = len(left & right)
    union = len(left | right)
    return overlap / union if union else 0.0

def github_repo_key(item):
    normalized = normalize_url(item.get("url", ""))
    parsed = urlparse(normalized)
    if parsed.netloc != "github.com":
        return None
    parts = [part for part in parsed.path.split("/") if part]
    if len(parts) < 2:
        return None
    return "/".join(parts[:2]).lower()

def weight(item):
    return platform_weight.get((item.get("source") or "").lower(), 0)

def describe(reason, removed):
    return f"{reason}: removed {removed.get('source', 'unknown')} {normalize_url(removed.get('url', ''))}"

def prefer(current, candidate, reason, removed):
    current.setdefault("metadata", {})
    candidate.setdefault("metadata", {})
    if reason == "same-github-repo":
        if current.get("source") == "github" and candidate.get("source") != "github":
            winner, loser = current, candidate
        elif candidate.get("source") == "github" and current.get("source") != "github":
            winner, loser = candidate, current
        elif weight(candidate) > weight(current):
            winner, loser = candidate, current
        else:
            winner, loser = current, candidate
    elif weight(candidate) > weight(current):
        winner, loser = candidate, current
    elif weight(candidate) == weight(current):
        current_signal = len(current.get("snippet", "")) + len(current.get("metadata", {}))
        candidate_signal = len(candidate.get("snippet", "")) + len(candidate.get("metadata", {}))
        winner, loser = (candidate, current) if candidate_signal > current_signal else (current, candidate)
    else:
        winner, loser = current, candidate

    notes = []
    for item in (winner, loser):
        note = item.get("metadata", {}).get("dedup_note")
        if note:
            notes.append(note)
    notes.append(describe(reason, loser))
    winner["url"] = normalize_url(winner.get("url", ""))
    winner["metadata"]["dedup_note"] = "; ".join(dict.fromkeys(notes))
    return winner

rows = []
with open(os.environ["IN"], encoding="utf-8") as fh:
    for raw_line in fh:
        line = raw_line.strip()
        if not line:
            continue
        item = json.loads(line)
        item.setdefault("metadata", {})
        item["url"] = normalize_url(item.get("url", ""))
        rows.append(item)

survivors = []
for item in rows:
    item_repo = github_repo_key(item)
    item_title = title_tokens(item.get("title", ""))
    merged = False
    for index, current in enumerate(survivors):
        current_repo = github_repo_key(current)
        current_title = title_tokens(current.get("title", ""))
        if item.get("url") and item.get("url") == current.get("url"):
            survivors[index] = prefer(current, item, "normalized-url", item)
            merged = True
            break
        if item_repo and current_repo and item_repo == current_repo and item.get("source") != current.get("source"):
            survivors[index] = prefer(current, item, "same-github-repo", item)
            merged = True
            break
        if jaccard(item_title, current_title) > 0.7:
            survivors[index] = prefer(current, item, "title-similarity", item)
            merged = True
            break
    if not merged:
        survivors.append(item)

with open(os.environ["OUT"], "w", encoding="utf-8") as out:
    for item in survivors:
        print(json.dumps(item, ensure_ascii=False), file=out)
PY
```

## Parse
Write UTF-8 JSONL to `$OUT` using the same per-line schema as the input evidence. Surviving items retain the base fields `url`, `title`, `source`, `snippet`, `found_at`, `query`, and `metadata`; when a duplicate is collapsed into a surviving row, the survivor adds `metadata.dedup_note` describing what was removed and why.

## Score Hints
- `quantity`: the goal is to remove inflated counts from duplicates, not to maximize the raw number of rows.
- `diversity`: keep genuinely distinct platforms and sources whenever they point to different evidence, but collapse mirrored copies of the same source.
- `relevance`: if title-similarity merging is aggressive on generic titles, review the surviving rows before scoring.
- Extra signal: preferring GitHub for the same repository usually preserves richer metadata than web or discussion-site echoes of the same repo.

## Known Limitations
- Title-based Jaccard similarity can over-merge short generic titles such as "Introduction" or "Getting Started".
- URL normalization is heuristic and may miss site-specific tracking parameters that are not in the default strip list.
- GitHub same-repo detection only recognizes canonical `github.com/<owner>/<repo>` URLs.
- If the input is empty or malformed, this skill will produce an empty or failed output; validate JSONL structure before deduplication.

## Evolution Notes
- Tune: platform weights, title similarity threshold, and tracking-parameter strip lists.
- Tried: prioritize same-URL and same-GitHub-repo rules before fuzzy title matching.
- Next: add content-hash or snippet-similarity checks for feeds that syndicate identical article text under different URLs.
