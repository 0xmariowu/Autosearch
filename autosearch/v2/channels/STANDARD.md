# Channel Plugin Standard

This document defines the required structure and runtime contract for channel plugins under `autosearch/v2/channels/`.

## 1. Directory Structure

- Each channel is one directory directly under `channels/`.
- A valid channel directory must contain:
  - `SKILL.md`
  - `search.py`
- The directory name is the canonical channel name.
- Directories whose names start with `_` are shared engines, helpers, or internal modules. They are not channels and must not be loaded as channels.
- `__pycache__/` and non-directory entries are ignored.

Example:

```text
channels/
  bilibili/
    SKILL.md
    search.py
  zhihu/
    SKILL.md
    search.py
  _engines/
    baidu.py
```

## 2. `SKILL.md` Format

Each channel must provide `SKILL.md` with YAML frontmatter followed by a free-form Markdown body.

### Required frontmatter fields

- `name`: required. Must match the channel directory name exactly.
- `description`: required. Describes when to use the channel. The first sentence must be 250 characters or fewer.
- `categories`: required. List of channel categories such as `[video, chinese-tech]`, `[academic]`, `[developer]`, `[business]`, or `[social]`.
- `platform`: required. Primary platform domain, for example `bilibili.com`.
- `api_key_required`: required. Boolean.

### Optional frontmatter fields

- `aliases`: optional. List of alternative channel names that resolve to the same channel.

### Body requirements

The Markdown body is free-form, but it must include these sections:

- `When to use`
- `Quality signals`
- `Known limits`

Minimal shape:

```md
---
name: bilibili
description: Use this channel for Chinese video search and creator-led technical content.
categories: [video, chinese-tech]
platform: bilibili.com
api_key_required: false
aliases: [bili]
---

## When to use

Use when the query is likely to be best answered by Bilibili videos or creator uploads.

## Quality signals

- Official accounts
- Strong engagement
- Clear recency

## Known limits

- Search quality varies by keyword
- Snippets may be sparse
```

## 3. `search.py` Interface

Each channel must export this function:

```python
async def search(query: str, max_results: int = 10) -> list[dict]:
```

### Return contract

- Return a list of dictionaries.
- Each result dictionary must contain these keys:
  - `url`
  - `title`
  - `snippet`
  - `source`
  - `query`
  - `metadata`
- `metadata` should be a dictionary. Use an empty dictionary when no extra fields are available.
- `source` should identify the channel or platform consistently.
- `query` must echo the input query used for that search.

### Implementation requirements

- Use `httpx` for all HTTP requests.
- Handle errors internally.
- On failure, return `[]` and print a diagnostic message to `stderr`.
- Do not raise channel-specific runtime errors to the loader for normal request failures.
- Do not perform side effects other than HTTP requests and `stderr` logging.
- Do not write files, mutate global project state, or require interactive input.

### Loader expectations

- The loader imports `search.py` dynamically.
- The loader registers the channel directory name as the primary channel name.
- If `aliases` is present in `SKILL.md`, each alias is registered to the same `search()` function.
- Duplicate names or aliases may be skipped by the loader.

## 4. Shared Engines

- Place reusable backends in `_engines/`.
- Example: `channels/_engines/baidu.py`
- Shared engines may be imported by channel implementations.
- Shared engines are not channel plugins and are not auto-loaded by channel discovery.

## 5. Minimal Examples

### Example `SKILL.md`

```md
---
name: example
description: Use this channel when the target platform is Example and direct platform search is preferred.
categories: [developer]
platform: example.com
api_key_required: false
aliases: [example-search]
---

## When to use

Use for queries where Example is the primary source.

## Quality signals

- Official sources
- Relevant titles
- Recent pages

## Known limits

- Limited snippet quality
```

### Example `search.py`

```python
from __future__ import annotations

import sys

import httpx


async def search(query: str, max_results: int = 10) -> list[dict]:
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.get(
                "https://example.com/search",
                params={"q": query, "limit": max_results},
            )
            response.raise_for_status()
            data = response.json()
    except Exception as exc:
        print(f"[example] search failed: {exc}", file=sys.stderr)
        return []

    results: list[dict] = []
    for item in data.get("results", [])[:max_results]:
        results.append(
            {
                "url": item.get("url", ""),
                "title": item.get("title", ""),
                "snippet": item.get("snippet", ""),
                "source": "example",
                "query": query,
                "metadata": {},
            }
        )
    return results
```
