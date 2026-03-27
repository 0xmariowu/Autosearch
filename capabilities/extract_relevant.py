"""Extract query-relevant content chunks from documents."""

name = "extract_relevant"
description = "Select the most relevant text chunks from documents using BM25 and semantic scoring."
when = "When you have fetched documents and need to extract only the parts relevant to the query."
input_type = "documents"
output_type = "evidence"


def run(input, **context):
    from acquisition.content_filter import rank_relevant_chunks

    docs = [input] if isinstance(input, dict) else list(input or [])
    query = context.get("query", "")
    limit = context.get("limit", 4)
    results = []
    for doc in docs:
        text = str(doc.get("text") or doc.get("markdown") or "")
        url = str(doc.get("url") or "")
        title = str(doc.get("title") or "")
        if not text.strip():
            continue
        chunks = rank_relevant_chunks(text, query=query, limit=limit)
        for chunk in chunks:
            chunk["url"] = url
            chunk["title"] = title
            results.append(chunk)
    return results


def test():
    from acquisition.content_filter import rank_relevant_chunks

    chunks = rank_relevant_chunks("First paragraph.\n\nSecond paragraph.", query="test")
    assert isinstance(chunks, list)
    return "ok"
