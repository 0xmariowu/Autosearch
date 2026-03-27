"""Discover new URLs by crawling top results and extracting outbound links."""

name = "deep_discover"
description = "Take your best search results, crawl each page, and extract all outbound links to discover related URLs you haven't found yet. A good repo's README typically links 10+ other repos."
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
                "max_crawl": {"type": "integer", "default": 5, "description": "Max pages to crawl"},
            },
        },
    },
    "required": ["input"],
}


def run(hits, **context):
    if not hits or not isinstance(hits, list):
        return []

    hits = [h for h in hits if isinstance(h, dict) and h.get("url")]
    if not hits:
        return []

    max_crawl = context.get("max_crawl", 5)

    # Sort by score, take top N
    hits.sort(key=lambda h: int(h.get("score_hint", h.get("consensus_count", 0)) or 0), reverse=True)
    to_crawl = hits[:max_crawl]

    existing_urls = set(h.get("url", "") for h in hits)
    new_urls = []
    seen = set()

    for hit in to_crawl:
        url = hit["url"]
        try:
            # Crawl page — fetch_page returns a dict with raw_html key
            from acquisition.fetch_pipeline import fetch_page
            page = fetch_page(url)
            if not page or not page.get("raw_html"):
                continue

            # Extract links from the HTML
            from acquisition.reference_extractor import extract_references
            refs = extract_references(url, page["raw_html"])
            for ref in refs:
                ref_url = ref.get("url", "") if isinstance(ref, dict) else str(ref)
                ref_url = ref_url.strip()
                if (
                    ref_url
                    and ref_url not in existing_urls
                    and ref_url not in seen
                    and ref_url.startswith("http")
                    and not any(skip in ref_url for skip in [
                        "javascript:", "mailto:", "#", "login", "signup",
                        "linkedin.com/in/", "twitter.com/intent",
                    ])
                ):
                    seen.add(ref_url)
                    new_urls.append(ref_url)
        except Exception:
            continue

    return new_urls


def test():
    from acquisition.fetch_pipeline import fetch_page  # noqa: F401
    from acquisition.reference_extractor import extract_references  # noqa: F401
    return "ok"
