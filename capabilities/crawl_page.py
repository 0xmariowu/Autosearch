"""Fetch and extract content from web pages."""

name = "crawl_page"
description = "Fetch one or more URLs and return extracted document content (title, text, markdown)."
when = "When you have URLs and need their page content for analysis or evidence extraction."
input_type = "urls"
output_type = "documents"


def run(input, **context):
    from acquisition import fetch_document

    query = context.get("query", "")
    urls = [input] if isinstance(input, str) else list(input or [])
    results = []
    for url in urls:
        try:
            doc = fetch_document(str(url).strip(), query=query)
            results.append(
                {
                    "url": doc.url,
                    "final_url": doc.final_url,
                    "title": doc.title,
                    "text": doc.text,
                    "markdown": doc.clean_markdown or doc.text,
                    "html": doc.raw_html,
                }
            )
        except Exception as exc:
            results.append({"url": str(url).strip(), "error": str(exc)})
    return results


def health_check():
    from acquisition.crawl4ai_adapter import crawl4ai_available

    if crawl4ai_available():
        return {"status": "ok", "message": "crawl4ai available"}
    return {"status": "ok", "message": "native fetch only (crawl4ai not installed)"}


def test():
    from acquisition import fetch_document  # noqa: F401
    from acquisition.crawl4ai_adapter import crawl4ai_available  # noqa: F401

    return "ok"
