"""Extract outbound links from fetched documents."""

name = "follow_links"
description = (
    "Extract reference URLs from document HTML for link-following and crawl expansion."
)
when = "When you have fetched documents and need to discover linked pages for deeper exploration."
input_type = "documents"
output_type = "urls"


def run(input, **context):
    from acquisition.reference_extractor import extract_references

    docs = [input] if isinstance(input, dict) else list(input or [])
    limit = context.get("limit", 20)
    all_urls = []
    seen = set()
    for doc in docs:
        base_url = str(doc.get("url") or doc.get("final_url") or "").strip()
        html = str(doc.get("html") or doc.get("raw_html") or doc.get("text") or "")
        if not base_url:
            continue
        refs = extract_references(base_url, html, limit=limit)
        for ref in refs:
            url = str(ref.get("url") or "").strip()
            if url and url not in seen:
                seen.add(url)
                all_urls.append(url)
    return all_urls


def test():
    from acquisition.reference_extractor import extract_references

    refs = extract_references(
        "https://example.com",
        '<a href="https://example.com/page">link</a>',
    )
    assert len(refs) == 1
    assert refs[0]["url"] == "https://example.com/page"
    return "ok"
