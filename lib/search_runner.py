#!/usr/bin/env python3
"""AutoSearch parallel search runner.

Claude calls this once via Bash. It searches all channels in parallel,
normalizes results, deduplicates, and returns clean JSONL to stdout.

Usage:
    python search_runner.py queries.json
    python search_runner.py '[{"channel":"zhihu","query":"AI agent"}]'
    echo '[...]' | python search_runner.py -

Input: JSON array of query objects:
    [{"channel": "zhihu", "query": "自进化 AI agent", "max_results": 10}]

Output: JSONL to stdout (one result per line), errors to stderr.
"""

from __future__ import annotations

import asyncio
import json
import re
import sys
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, urlencode, urlparse, urlunparse
from channels import load_channels as load_channel_plugins

DEFAULT_TIMEOUT = 30
DEFAULT_MAX_RESULTS = 10
TRACKING_PARAMS = {
    "utm_source",
    "utm_medium",
    "utm_campaign",
    "utm_term",
    "utm_content",
    "ref",
    "source",
    "fbclid",
    "gclid",
    "mc_cid",
    "mc_eid",
}
MONTH_MAP = {
    "jan": "01",
    "feb": "02",
    "mar": "03",
    "apr": "04",
    "may": "05",
    "jun": "06",
    "jul": "07",
    "aug": "08",
    "sep": "09",
    "oct": "10",
    "nov": "11",
    "dec": "12",
}


def normalize_url(url: str) -> str:
    try:
        parsed = urlparse(url)
        query = ""
        if parsed.query:
            params = parse_qs(parsed.query, keep_blank_values=True)
            query = urlencode(
                {k: v for k, v in params.items() if k.lower() not in TRACKING_PARAMS},
                doseq=True,
            )
        path = parsed.path.rstrip("/") or "/"
        netloc = parsed.netloc.lower()
        if netloc == "github.com" or netloc.endswith(".github.com"):
            path = re.sub(r"/(tree|blob)/(main|master)/?$", "", path)
        return urlunparse(
            (parsed.scheme, parsed.netloc.lower(), path, parsed.params, query, "")
        )
    except Exception:
        return url


def extract_date(text: str, url: str = "") -> str | None:
    combined = f"{url} {text}"
    if match := re.search(r"(\d{2})(\d{2})\.\d{4,5}", combined):
        yy, mm = match.groups()
        if 20 <= int(yy) <= 30 and 1 <= int(mm) <= 12:
            return f"20{yy}-{mm}-01T00:00:00Z"
    if match := re.search(r"/(\d{4})/(\d{1,2})/(\d{1,2})/", url):
        year, month, day = match.groups()
        return f"{year}-{int(month):02d}-{int(day):02d}T00:00:00Z"
    if match := re.search(r"(\d{4})-(\d{2})-(\d{2})", text):
        year, month, day = match.groups()
        return f"{year}-{month}-{day}T00:00:00Z"
    lowered = text.lower()
    for month_name, month_num in MONTH_MAP.items():
        pattern = rf"(?:published|updated|posted|date)?\s*{month_name}\w*\.?\s+\d{{1,2}},?\s+(\d{{4}})"
        if match := re.search(pattern, lowered):
            return f"{match.group(1)}-{month_num}-01T00:00:00Z"
    if match := re.search(r"\((\d{4})\)", text):
        year = int(match.group(1))
        if 2020 <= year <= 2030:
            return f"{year}-01-01T00:00:00Z"
    return None


def make_result(
    url: str,
    title: str,
    snippet: str,
    source: str,
    query: str,
    extra_metadata: dict | None = None,
) -> dict:
    metadata: dict[str, Any] = {}
    if date := extract_date(f"{snippet} {title}", url):
        metadata["published_at"] = date
    if extra_metadata:
        metadata.update(extra_metadata)
    return {
        "url": normalize_url(url),
        "title": title.strip(),
        "snippet": snippet.strip()[:500],
        "source": source,
        "query": query,
        "metadata": metadata,
    }


CHANNEL_METHODS = load_channel_plugins()


async def run_single_query(query_obj: dict) -> list[dict]:
    channel = query_obj.get("channel", "web-ddgs")
    query = query_obj.get("query", "")
    max_results = query_obj.get("max_results", DEFAULT_MAX_RESULTS)
    if not query:
        return []
    method = CHANNEL_METHODS.get(channel)
    if method is None:
        print(f"[search_runner] unknown channel: {channel}", file=sys.stderr)
        return []
    try:
        return await asyncio.wait_for(
            method(query, max_results), timeout=DEFAULT_TIMEOUT
        )
    except asyncio.TimeoutError:
        print(f"[search_runner] timeout: {channel} '{query}'", file=sys.stderr)
        return []


def dedup_results(results: list[dict]) -> list[dict]:
    seen: dict[str, dict] = {}
    for result in results:
        url = result.get("url", "")
        if not url:
            continue
        key = normalize_url(url)
        if key not in seen or len(json.dumps(result.get("metadata", {}))) > len(
            json.dumps(seen[key].get("metadata", {}))
        ):
            seen[key] = result
    return list(seen.values())


async def main(queries: list[dict]) -> None:
    if not queries:
        return
    results_lists = await asyncio.gather(
        *(run_single_query(query) for query in queries), return_exceptions=True
    )
    all_results: list[dict] = []
    for index, result in enumerate(results_lists):
        if isinstance(result, Exception):
            print(f"[search_runner] query {index} exception: {result}", file=sys.stderr)
            continue
        all_results.extend(result)
    unique_results = dedup_results(all_results)
    for result in unique_results:
        print(json.dumps(result, ensure_ascii=False))
    print(
        f"[search_runner] {len(unique_results)} results ({len(all_results)} before dedup) from {len(queries)} queries",
        file=sys.stderr,
    )


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python search_runner.py queries.json", file=sys.stderr)
        print(
            '       python search_runner.py \'[{"channel":"zhihu","query":"AI agent"}]\'',
            file=sys.stderr,
        )
        sys.exit(2)
    arg = sys.argv[1]
    raw = (
        sys.stdin.read()
        if arg == "-"
        else arg
        if arg.startswith("[")
        else Path(arg).read_text()
    )
    try:
        queries = json.loads(raw)
    except json.JSONDecodeError as exc:
        print(f"[search_runner] invalid JSON: {exc}", file=sys.stderr)
        sys.exit(2)
    asyncio.run(main(queries))
