---
name: github
type: platform
version: "1.0"
requires: [gh, python3]
triggers: [github, repo, repository, open source, code, library, framework]
cost: free
platforms: [github]
dimensions: []
---
## Purpose
Search GitHub repositories and issues for a query when code discovery, project health, and open-source discussion are likely to matter.

## When to Use
- Use when the task asks for repositories, libraries, frameworks, issue threads, or active open-source code.
- Requires a non-interactive `gh` CLI session with access to GitHub search.
- Prefer this skill when stars, maintenance recency, and issue activity are useful ranking signals.
- Do not use it as the only source for non-GitHub facts, closed-source products, or official documentation claims.

## Execute
1. Define inputs, defaults, and temporary paths.
```bash
QUERY="${QUERY:-ai agent}"
LIMIT="${LIMIT:-10}"
OUT="${OUT:-/tmp/github.jsonl}"
NOW="${NOW:-$(date -u +%Y-%m-%dT%H:%M:%SZ)}"
SINCE="${SINCE:-1970-01-01T00:00:00Z}"
RAW_REPOS="$(mktemp)"
RAW_ISSUES="$(mktemp)"
export QUERY LIMIT OUT NOW SINCE RAW_REPOS RAW_ISSUES
```
2. Fetch repository matches.
```bash
gh search repos "$QUERY" \
  --json name,url,description,stargazersCount,updatedAt,language,forksCount \
  --limit "$LIMIT" \
  > "$RAW_REPOS"
```
3. Fetch issue matches.
```bash
gh search issues "$QUERY" \
  --json title,url,body,repository,createdAt,commentsCount \
  --limit "$LIMIT" \
  > "$RAW_ISSUES"
```
4. Merge, filter, and convert the responses into AutoSearch JSONL.
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

def repo_name(repo):
    if isinstance(repo, str):
        return repo
    if isinstance(repo, dict):
        return repo.get("nameWithOwner") or repo.get("fullName") or repo.get("name") or ""
    return ""

since = parse_iso(os.environ["SINCE"])
now = os.environ["NOW"]
query = os.environ["QUERY"]

with open(os.environ["RAW_REPOS"], encoding="utf-8") as fh:
    repos = json.load(fh)
with open(os.environ["RAW_ISSUES"], encoding="utf-8") as fh:
    issues = json.load(fh)

with open(os.environ["OUT"], "w", encoding="utf-8") as out:
    for item in repos:
        updated = parse_iso(item.get("updatedAt"))
        if since and updated and updated < since:
            continue
        row = {
            "url": item.get("url"),
            "title": item.get("name") or item.get("url"),
            "source": "github",
            "snippet": clean(item.get("description", "")),
            "found_at": now,
            "query": query,
            "metadata": {
                "result_type": "repo",
                "stars": item.get("stargazersCount", 0),
                "language": item.get("language"),
                "updated_at": item.get("updatedAt"),
                "forks": item.get("forksCount", 0),
            },
        }
        print(json.dumps(row, ensure_ascii=False), file=out)

    for item in issues:
        created = parse_iso(item.get("createdAt"))
        if since and created and created < since:
            continue
        row = {
            "url": item.get("url"),
            "title": item.get("title") or item.get("url"),
            "source": "github",
            "snippet": clean(item.get("body", "")),
            "found_at": now,
            "query": query,
            "metadata": {
                "result_type": "issue",
                "comments": item.get("commentsCount", 0),
                "repository": repo_name(item.get("repository")),
                "published_at": item.get("createdAt"),
            },
        }
        print(json.dumps(row, ensure_ascii=False), file=out)
PY
```

## Parse
Write UTF-8 JSONL to `$OUT`. Each line uses the base schema `url`, `title`, `source`, `snippet`, `found_at`, `query`, and `metadata`. Repository results add `stars`, `language`, `updated_at`, and `forks` in `metadata`; issue results add `comments`, `repository`, and `published_at` in `metadata`.

## Score Hints
- `relevance`: repository names, issue titles, and snippets that closely match `QUERY` are stronger.
- `freshness`: recent `updated_at` for repositories and recent `created_at` for issues are better for fast-moving topics.
- `quantity`: a balanced mix of repository and issue hits improves coverage over code and maintenance discussion.
- `efficiency`: one GitHub query can return both implementation candidates and active problem reports.
- Extra signal: higher `stars`, a non-empty description, language match, and higher issue `comments` often indicate more useful results.

## Known Limitations
- Requires `gh` authentication and network access; unauthenticated or rate-limited sessions can fail or return partial results.
- `SINCE` is applied after fetch, so very old hits can still be downloaded before filtering.
- GitHub issue search can still be noisy for broad terms and may surface stale discussions for ambiguous queries.
- If the response is empty or malformed, rerun with a narrower query, add language qualifiers, or verify that `gh auth status` is healthy.

## Evolution Notes
- Tune: add optional sort variants such as `updated` or `stars` when recall is good but ranking is weak.
- Tried: repository plus issue search in one skill so ranking can blend project quality with maintenance chatter.
- Next: add optional owner or language query templates for narrower engineering searches.
