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
from urllib.parse import urlparse, urlunparse, parse_qs, urlencode

import httpx

# --- Configuration ---

CHANNELS_FILE = Path(__file__).parent / "state" / "channels.json"
DEFAULT_TIMEOUT = 30  # seconds per channel
DEFAULT_MAX_RESULTS = 10


# --- URL Normalization ---

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


def normalize_url(url: str) -> str:
    """Canonicalize a URL for dedup."""
    try:
        parsed = urlparse(url)
        # Lowercase hostname
        netloc = parsed.netloc.lower()
        # Remove tracking params
        if parsed.query:
            params = parse_qs(parsed.query, keep_blank_values=True)
            cleaned = {
                k: v for k, v in params.items() if k.lower() not in TRACKING_PARAMS
            }
            query = urlencode(cleaned, doseq=True)
        else:
            query = ""
        # Remove fragment
        fragment = ""
        # Remove trailing slash from path
        path = parsed.path.rstrip("/") or "/"
        # Strip /tree/main, /blob/main from GitHub repo URLs
        if "github.com" in netloc:
            path = re.sub(r"/(tree|blob)/main/?$", "", path)
            path = re.sub(r"/(tree|blob)/master/?$", "", path)
        return urlunparse((parsed.scheme, netloc, path, parsed.params, query, fragment))
    except Exception:
        return url


# --- Date Extraction ---

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


def extract_date(text: str, url: str = "") -> str | None:
    """Try to extract a date from text and URL. Returns ISO 8601 or None."""
    # arXiv ID pattern: 2403.12345 = March 2024
    m = re.search(r"(\d{2})(\d{2})\.\d{4,5}", url + " " + text)
    if m:
        yy, mm = m.group(1), m.group(2)
        if 1 <= int(mm) <= 12 and 20 <= int(yy) <= 30:
            return f"20{yy}-{mm}-01T00:00:00Z"

    # URL path date: /2025/03/15/
    m = re.search(r"/(\d{4})/(\d{1,2})/(\d{1,2})/", url)
    if m:
        return f"{m.group(1)}-{int(m.group(2)):02d}-{int(m.group(3)):02d}T00:00:00Z"

    # Text pattern: "March 15, 2025" or "2025-03-15"
    m = re.search(r"(\d{4})-(\d{2})-(\d{2})", text)
    if m:
        return f"{m.group(1)}-{m.group(2)}-{m.group(3)}T00:00:00Z"

    # "Published Jan 2026"
    for month_name, month_num in MONTH_MAP.items():
        pattern = rf"(?:published|updated|posted|date)?\s*{month_name}\w*\.?\s+\d{{1,2}},?\s+(\d{{4}})"
        m = re.search(pattern, text.lower())
        if m:
            return f"{m.group(1)}-{month_num}-01T00:00:00Z"

    # Just year: "(2025)" after a paper title
    m = re.search(r"\((\d{4})\)", text)
    if m and 2020 <= int(m.group(1)) <= 2030:
        return f"{m.group(1)}-01-01T00:00:00Z"

    return None


# --- Result Builder ---


def make_result(
    url: str,
    title: str,
    snippet: str,
    source: str,
    query: str,
    extra_metadata: dict | None = None,
) -> dict:
    """Build a canonical evidence entry."""
    canonical_url = normalize_url(url)
    metadata: dict[str, Any] = {}

    # Extract date
    date = extract_date(snippet + " " + title, url)
    if date:
        metadata["published_at"] = date

    if extra_metadata:
        metadata.update(extra_metadata)

    return {
        "url": canonical_url,
        "title": title.strip(),
        "snippet": snippet.strip()[:500],
        "source": source,
        "query": query,
        "metadata": metadata,
    }


# --- Search Methods ---


async def search_ddgs_site(query: str, site: str, max_results: int = 10) -> list[dict]:
    """Search via DuckDuckGo with site: filter."""
    try:
        from duckduckgo_search import DDGS

        full_query = f"site:{site} {query}"
        results = []
        with DDGS() as ddgs:
            for r in ddgs.text(full_query, max_results=max_results):
                results.append(
                    make_result(
                        url=r.get("href", ""),
                        title=r.get("title", ""),
                        snippet=r.get("body", ""),
                        source=site.split(".")[0],  # zhihu.com -> zhihu
                        query=full_query,
                    )
                )
        return results
    except Exception as e:
        print(f"[search_runner] ddgs site:{site} error: {e}", file=sys.stderr)
        return []


async def search_ddgs_web(query: str, max_results: int = 10) -> list[dict]:
    """General web search via DuckDuckGo."""
    try:
        from duckduckgo_search import DDGS

        results = []
        with DDGS() as ddgs:
            for r in ddgs.text(query, max_results=max_results):
                results.append(
                    make_result(
                        url=r.get("href", ""),
                        title=r.get("title", ""),
                        snippet=r.get("body", ""),
                        source="web-ddgs",
                        query=query,
                    )
                )
        return results
    except Exception as e:
        print(f"[search_runner] ddgs web error: {e}", file=sys.stderr)
        return []


async def search_gh_repos(query: str, max_results: int = 20) -> list[dict]:
    """Search GitHub repos via gh CLI."""
    try:
        cmd = [
            "gh",
            "search",
            "repos",
            query,
            f"--limit={max_results}",
            "--sort=stars",
            "--json=fullName,url,description,stargazersCount,updatedAt,language",
        ]
        proc = await asyncio.create_subprocess_exec(
            *cmd, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE
        )
        stdout, stderr = await asyncio.wait_for(
            proc.communicate(), timeout=DEFAULT_TIMEOUT
        )
        if proc.returncode != 0:
            print(f"[search_runner] gh repos error: {stderr.decode()}", file=sys.stderr)
            return []

        repos = json.loads(stdout.decode())
        results = []
        for r in repos:
            lang_raw = r.get("language", "")
            lang_name = lang_raw if isinstance(lang_raw, str) else ""
            metadata = {"stars": r.get("stargazersCount", 0)}
            if r.get("updatedAt"):
                metadata["updated_at"] = r["updatedAt"]
            if lang_name:
                metadata["language"] = lang_name
            results.append(
                make_result(
                    url=r.get("url", ""),
                    title=r.get("fullName", ""),
                    snippet=r.get("description", "") or "",
                    source="github",
                    query=query,
                    extra_metadata=metadata,
                )
            )
        return results
    except Exception as e:
        print(f"[search_runner] gh repos error: {e}", file=sys.stderr)
        return []


async def search_gh_issues(query: str, max_results: int = 10) -> list[dict]:
    """Search GitHub issues via gh CLI."""
    try:
        cmd = [
            "gh",
            "search",
            "issues",
            query,
            f"--limit={max_results}",
            "--json=title,url,body,createdAt,repository",
        ]
        proc = await asyncio.create_subprocess_exec(
            *cmd, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE
        )
        stdout, stderr = await asyncio.wait_for(
            proc.communicate(), timeout=DEFAULT_TIMEOUT
        )
        if proc.returncode != 0:
            return []

        issues = json.loads(stdout.decode())
        results = []
        for r in issues:
            repo = r.get("repository", {})
            repo_name = repo.get("nameWithOwner", "") if isinstance(repo, dict) else ""
            metadata = {}
            if r.get("createdAt"):
                metadata["created_utc"] = r["createdAt"]
            results.append(
                make_result(
                    url=r.get("url", ""),
                    title=f"[{repo_name}] {r.get('title', '')}",
                    snippet=(r.get("body", "") or "")[:300],
                    source="github",
                    query=query,
                    extra_metadata=metadata,
                )
            )
        return results
    except Exception as e:
        print(f"[search_runner] gh issues error: {e}", file=sys.stderr)
        return []


SEMANTIC_SCHOLAR_RETRY_DELAYS = [2.0, 5.0]  # seconds between retries on 429


async def _ss_get(client: httpx.AsyncClient, url: str, **kwargs) -> httpx.Response:
    """Semantic Scholar GET with retry on 429 rate limit."""
    resp = await client.get(url, **kwargs)
    for delay in SEMANTIC_SCHOLAR_RETRY_DELAYS:
        if resp.status_code != 429:
            break
        print(
            f"[search_runner] semantic scholar 429, retry in {delay}s", file=sys.stderr
        )
        await asyncio.sleep(delay)
        resp = await client.get(url, **kwargs)
    return resp


async def search_semantic_scholar(
    query: str, max_results: int = 10, mode: str = "search"
) -> list[dict]:
    """Search Semantic Scholar API."""
    try:
        async with httpx.AsyncClient(timeout=DEFAULT_TIMEOUT) as client:
            if mode == "citations":
                # query should be a paper ID or title
                # First find the paper
                resp = await _ss_get(
                    client,
                    "https://api.semanticscholar.org/graph/v1/paper/search",
                    params={"query": query, "limit": 1, "fields": "paperId,title"},
                )
                if resp.status_code != 200:
                    return []
                papers = resp.json().get("data", [])
                if not papers:
                    return []
                paper_id = papers[0]["paperId"]

                # Get citations
                resp = await _ss_get(
                    client,
                    f"https://api.semanticscholar.org/graph/v1/paper/{paper_id}/citations",
                    params={
                        "limit": max_results,
                        "fields": "title,url,year,citationCount,authors",
                    },
                )
                if resp.status_code != 200:
                    return []
                citations = resp.json().get("data", [])
                results = []
                for c in citations:
                    cp = c.get("citingPaper", {})
                    if not cp.get("title"):
                        continue
                    authors = ", ".join(
                        a.get("name", "") for a in (cp.get("authors") or [])[:3]
                    )
                    metadata = {}
                    if cp.get("year"):
                        metadata["published_at"] = f"{cp['year']}-01-01T00:00:00Z"
                    if cp.get("citationCount"):
                        metadata["citations"] = cp["citationCount"]
                    results.append(
                        make_result(
                            url=cp.get("url")
                            or f"https://api.semanticscholar.org/paper/{cp.get('paperId', '')}",
                            title=cp.get("title", ""),
                            snippet=f"Authors: {authors}. Year: {cp.get('year', 'N/A')}. Citations: {cp.get('citationCount', 0)}",
                            source="semantic-scholar",
                            query=query,
                            extra_metadata=metadata,
                        )
                    )
                return results
            else:
                # Regular search
                resp = await _ss_get(
                    client,
                    "https://api.semanticscholar.org/graph/v1/paper/search",
                    params={
                        "query": query,
                        "limit": max_results,
                        "fields": "title,url,year,citationCount,authors,abstract",
                    },
                )
                if resp.status_code != 200:
                    print(
                        f"[search_runner] semantic scholar {resp.status_code}",
                        file=sys.stderr,
                    )
                    return []
                papers = resp.json().get("data", [])
                results = []
                for p in papers:
                    authors = ", ".join(
                        a.get("name", "") for a in (p.get("authors") or [])[:3]
                    )
                    metadata = {}
                    if p.get("year"):
                        metadata["published_at"] = f"{p['year']}-01-01T00:00:00Z"
                    if p.get("citationCount"):
                        metadata["citations"] = p["citationCount"]
                    results.append(
                        make_result(
                            url=p.get("url") or "",
                            title=p.get("title", ""),
                            snippet=p.get("abstract", "") or f"Authors: {authors}",
                            source="semantic-scholar",
                            query=query,
                            extra_metadata=metadata,
                        )
                    )
                return results
    except Exception as e:
        print(f"[search_runner] semantic scholar error: {e}", file=sys.stderr)
        return []


async def search_arxiv(query: str, max_results: int = 10) -> list[dict]:
    """Search arXiv API (Atom feed)."""
    try:
        import xml.etree.ElementTree as ET

        ns = {"a": "http://www.w3.org/2005/Atom"}
        search_terms = " AND ".join(f"all:{w}" for w in query.split()[:4])
        async with httpx.AsyncClient(timeout=DEFAULT_TIMEOUT) as client:
            resp = await client.get(
                "https://export.arxiv.org/api/query",
                params={
                    "search_query": search_terms,
                    "max_results": max_results,
                    "sortBy": "relevance",
                },
            )
            if resp.status_code != 200:
                print(f"[search_runner] arxiv {resp.status_code}", file=sys.stderr)
                return []
            root = ET.fromstring(resp.text)
            results = []
            for entry in root.findall("a:entry", ns):
                title_el = entry.find("a:title", ns)
                id_el = entry.find("a:id", ns)
                summary_el = entry.find("a:summary", ns)
                published_el = entry.find("a:published", ns)
                if title_el is None or id_el is None:
                    continue
                title = (
                    title_el.text.strip().replace("\n", " ") if title_el.text else ""
                )
                url = id_el.text.strip() if id_el.text else ""
                snippet = (
                    summary_el.text.strip()[:300]
                    if summary_el is not None and summary_el.text
                    else ""
                )
                metadata = {}
                if published_el is not None and published_el.text:
                    metadata["published_at"] = published_el.text.strip()
                authors = [a.find("a:name", ns) for a in entry.findall("a:author", ns)]
                author_names = ", ".join(
                    a.text for a in authors[:3] if a is not None and a.text
                )
                if author_names:
                    metadata["authors"] = author_names
                results.append(
                    make_result(
                        url=url,
                        title=title,
                        snippet=snippet,
                        source="arxiv",
                        query=query,
                        extra_metadata=metadata,
                    )
                )
            return results
    except Exception as e:
        print(f"[search_runner] arxiv error: {e}", file=sys.stderr)
        return []


async def search_hn(query: str, max_results: int = 10) -> list[dict]:
    """Search Hacker News via Algolia API."""
    try:
        async with httpx.AsyncClient(timeout=DEFAULT_TIMEOUT) as client:
            resp = await client.get(
                "https://hn.algolia.com/api/v1/search",
                params={"query": query, "hitsPerPage": max_results, "tags": "story"},
            )
            if resp.status_code != 200:
                return []
            hits = resp.json().get("hits", [])
            results = []
            for h in hits:
                metadata = {}
                if h.get("created_at"):
                    metadata["created_utc"] = h["created_at"]
                if h.get("points"):
                    metadata["points"] = h["points"]
                url = (
                    h.get("url")
                    or f"https://news.ycombinator.com/item?id={h.get('objectID', '')}"
                )
                results.append(
                    make_result(
                        url=url,
                        title=h.get("title", ""),
                        snippet=f"Points: {h.get('points', 0)} | Comments: {h.get('num_comments', 0)}",
                        source="hn",
                        query=query,
                        extra_metadata=metadata,
                    )
                )
            return results
    except Exception as e:
        print(f"[search_runner] hn error: {e}", file=sys.stderr)
        return []


# --- Channel Router ---


# Load channel config
def load_channels() -> dict:
    """Load channels.json config."""
    if CHANNELS_FILE.exists():
        return json.loads(CHANNELS_FILE.read_text())
    return {}


# Map channel names to search methods
CHANNEL_METHODS = {
    # Site search channels (use ddgs site:)
    "zhihu": lambda q, n: search_ddgs_site(q, "zhihu.com", n),
    "csdn": lambda q, n: search_ddgs_site(q, "csdn.net", n),
    "juejin": lambda q, n: search_ddgs_site(q, "juejin.cn", n),
    "36kr": lambda q, n: search_ddgs_site(q, "36kr.com", n),
    "infoq-cn": lambda q, n: search_ddgs_site(q, "infoq.cn", n),
    "stackoverflow": lambda q, n: search_ddgs_site(q, "stackoverflow.com", n),
    "devto": lambda q, n: search_ddgs_site(q, "dev.to", n),
    "producthunt": lambda q, n: search_ddgs_site(q, "producthunt.com", n),
    "crunchbase": lambda q, n: search_ddgs_site(q, "crunchbase.com", n),
    "g2": lambda q, n: search_ddgs_site(q, "g2.com", n),
    "papers-with-code": lambda q, n: search_arxiv(q, n),
    "arxiv": lambda q, n: search_arxiv(q, n),
    "reddit": lambda q, n: search_ddgs_site(q, "reddit.com", n),
    "google-scholar": lambda q, n: search_ddgs_site(q, "scholar.google.com", n),
    "linkedin": lambda q, n: search_ddgs_site(q, "linkedin.com", n),
    "weibo": lambda q, n: search_ddgs_site(q, "weibo.com", n),
    "xueqiu": lambda q, n: search_ddgs_site(q, "xueqiu.com", n),
    "bilibili": lambda q, n: search_ddgs_site(q, "bilibili.com", n),
    "xiaohongshu": lambda q, n: search_ddgs_site(q, "xiaohongshu.com", n),
    "wechat": lambda q, n: search_ddgs_site(q, "mp.weixin.qq.com", n),
    "youtube": lambda q, n: search_ddgs_site(q, "youtube.com", n),
    "douyin": lambda q, n: search_ddgs_site(q, "douyin.com", n),
    "xiaoyuzhou": lambda q, n: search_ddgs_site(q, "xiaoyuzhoufm.com", n),
    "conference-talks": lambda q, n: search_ddgs_site(q, "youtube.com", n),
    "npm-pypi": lambda q, n: search_ddgs_site(q, "npmjs.com", n),
    "rss": lambda q, n: search_ddgs_web(f"{q} RSS feed", n),
    # Dedicated API channels
    "web-ddgs": lambda q, n: search_ddgs_web(q, n),
    "github-repos": lambda q, n: search_gh_repos(q, n),
    "github-issues": lambda q, n: search_gh_issues(q, n),
    "semantic-scholar": lambda q, n: search_semantic_scholar(q, n),
    "citation-graph": lambda q, n: search_semantic_scholar(q, n, mode="citations"),
    "hn": lambda q, n: search_hn(q, n),
}


async def run_single_query(query_obj: dict) -> list[dict]:
    """Execute a single query on its channel."""
    channel = query_obj.get("channel", "web-ddgs")
    query = query_obj.get("query", "")
    max_results = query_obj.get("max_results", DEFAULT_MAX_RESULTS)

    if not query:
        return []

    method = CHANNEL_METHODS.get(channel)
    if method is None:
        # Try dynamic site search from channels.json
        channels_config = load_channels()
        ch_config = channels_config.get(channel, {})
        site = ch_config.get("site")
        if site:
            return await search_ddgs_site(query, site, max_results)
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
    """Deduplicate by normalized URL."""
    seen: dict[str, dict] = {}
    for r in results:
        url = r.get("url", "")
        if not url:
            continue
        key = normalize_url(url)
        if key in seen:
            # Keep the one with more metadata
            existing = seen[key]
            if len(json.dumps(r.get("metadata", {}))) > len(
                json.dumps(existing.get("metadata", {}))
            ):
                seen[key] = r
        else:
            seen[key] = r
    return list(seen.values())


async def main(queries: list[dict]) -> None:
    """Run queries with smart batching: API queries parallel, ddgs queries batched."""
    if not queries:
        return

    # Split: dedicated API queries (parallel) vs ddgs queries (batched)
    DDGS_METHODS = {"site_search", "ddgs_web"}
    ddgs_queries = []
    api_queries = []

    channels_config = load_channels()
    for q in queries:
        channel = q.get("channel", "web-ddgs")
        ch_config = channels_config.get(channel, {})
        ch_method = ch_config.get("method", "")

        if (
            channel in ("web-ddgs", "rss")
            or ch_config.get("site")
            or ch_method in DDGS_METHODS
        ):
            ddgs_queries.append(q)
        else:
            api_queries.append(q)

    # API queries: run all in parallel (each has independent rate limits)
    api_tasks = [run_single_query(q) for q in api_queries]

    # DDGS queries: batch 3 at a time with 1.5s delay between batches
    DDGS_BATCH_SIZE = 3
    DDGS_BATCH_DELAY = 1.5

    async def run_ddgs_batched() -> list[list[dict]]:
        all_results: list[list[dict]] = []
        for i in range(0, len(ddgs_queries), DDGS_BATCH_SIZE):
            batch = ddgs_queries[i : i + DDGS_BATCH_SIZE]
            batch_tasks = [run_single_query(q) for q in batch]
            batch_results = await asyncio.gather(*batch_tasks, return_exceptions=True)
            for br in batch_results:
                if isinstance(br, Exception):
                    print(f"[search_runner] ddgs batch error: {br}", file=sys.stderr)
                else:
                    all_results.append(br)
            if i + DDGS_BATCH_SIZE < len(ddgs_queries):
                await asyncio.sleep(DDGS_BATCH_DELAY)
        return all_results

    # Run API and DDGS concurrently (but DDGS internally batched)
    async def empty_results():
        return []

    api_future = (
        asyncio.gather(*api_tasks, return_exceptions=True)
        if api_tasks
        else empty_results()
    )
    ddgs_future = run_ddgs_batched()

    api_results, ddgs_results = await asyncio.gather(api_future, ddgs_future)
    results_lists = list(api_results) + list(ddgs_results)

    # Flatten
    all_results = []
    for i, result in enumerate(results_lists):
        if isinstance(result, Exception):
            print(f"[search_runner] query {i} exception: {result}", file=sys.stderr)
            continue
        all_results.extend(result)

    # Dedup
    unique_results = dedup_results(all_results)

    # Output JSONL to stdout
    for r in unique_results:
        print(json.dumps(r, ensure_ascii=False))

    # Summary to stderr
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

    # Read input
    if arg == "-":
        raw = sys.stdin.read()
    elif arg.startswith("["):
        raw = arg
    else:
        raw = Path(arg).read_text()

    try:
        queries = json.loads(raw)
    except json.JSONDecodeError as e:
        print(f"[search_runner] invalid JSON: {e}", file=sys.stderr)
        sys.exit(2)

    asyncio.run(main(queries))
