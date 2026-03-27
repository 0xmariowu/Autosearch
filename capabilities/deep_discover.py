"""Discover new URLs by crawling top results and extracting outbound links."""

import re
import urllib.request
from urllib.parse import urlparse

name = "deep_discover"
description = "Take your best search results, crawl each page, and extract all outbound links to discover related URLs you haven't found yet. For GitHub repos, fetches README directly for reliable link extraction."
when = "After initial search rounds when discovery rate is slowing. Expands from breadth search to depth by following links."
input_type = "hits"
output_type = "urls"
input_schema = {
    "type": "object",
    "properties": {
        "input": {
            "type": "array",
            "items": {"type": "object"},
            "description": "List of hit dicts (with url field) to crawl for link discovery",
        },
        "context": {
            "type": "object",
            "properties": {
                "max_crawl": {"type": "integer", "default": 10, "description": "Max pages to crawl"},
            },
        },
    },
    "required": ["input"],
}

_SKIP_PATTERNS = [
    "javascript:", "mailto:", "#",
    "login", "signup", "signin", "register",
    "linkedin.com/in/", "twitter.com/intent",
    ".css", ".js", ".png", ".jpg", ".gif", ".svg", ".ico",
    ".woff", ".ttf", ".eot", ".mp4", ".mp3",
    "githubassets.com", "s3.amazonaws.com",
    "cloudfront.net", "fonts.googleapis.com", "cdn.",
    "google.com/search", "bing.com/search",
]


def _extract_github_readme_links(owner, repo):
    """Fetch GitHub README and extract URLs."""
    urls = []
    for branch in ["main", "master"]:
        try:
            readme_url = f"https://raw.githubusercontent.com/{owner}/{repo}/{branch}/README.md"
            with urllib.request.urlopen(readme_url, timeout=8) as resp:
                content = resp.read().decode("utf-8", errors="ignore")
            found = re.findall(r"https?://[^\s\)\]\"\'>]+", content)
            urls.extend(found)
            break
        except Exception:
            continue
    return urls


def _extract_page_links(url):
    """Fetch page HTML and extract URLs."""
    try:
        from acquisition.fetch_pipeline import fetch_page

        page = fetch_page(url)
        if not page or not page.get("raw_html"):
            return []
        from acquisition.reference_extractor import extract_references

        refs = extract_references(url, page["raw_html"])
        return [
            ref.get("url", "") if isinstance(ref, dict) else str(ref) for ref in refs
        ]
    except Exception:
        return []


def run(hits, **context):
    if not hits or not isinstance(hits, list):
        return []

    hits = [h for h in hits if isinstance(h, dict) and h.get("url")]
    if not hits:
        return []

    max_crawl = context.get("max_crawl", 10)

    # Sort by score, take top N
    hits.sort(
        key=lambda h: int(h.get("score_hint", h.get("consensus_count", 0)) or 0),
        reverse=True,
    )
    to_crawl = hits[:max_crawl]

    existing_urls = set(h.get("url", "") for h in hits)
    new_urls = []
    seen = set()

    for hit in to_crawl:
        url = hit["url"]
        found_links = []

        # GitHub repos: use README extraction (more reliable than HTML)
        try:
            parsed = urlparse(url)
            if "github.com" in parsed.netloc:
                parts = parsed.path.strip("/").split("/")
                if len(parts) >= 2:
                    owner, repo = parts[0], parts[1]
                    found_links = _extract_github_readme_links(owner, repo)
        except Exception:
            pass

        # Non-GitHub or GitHub failed: try HTML extraction
        if not found_links:
            found_links = _extract_page_links(url)

        # Filter and collect new URLs
        for link in found_links:
            link = link.strip().rstrip(".,;:)")
            if (
                link
                and link not in existing_urls
                and link not in seen
                and link.startswith("http")
                and not any(skip in link.lower() for skip in _SKIP_PATTERNS)
            ):
                seen.add(link)
                new_urls.append(link)

    return new_urls


def test():
    # Verify imports
    from acquisition.fetch_pipeline import fetch_page  # noqa: F401
    from acquisition.reference_extractor import extract_references  # noqa: F401

    return "ok"
