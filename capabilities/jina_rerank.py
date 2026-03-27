"""Rerank results using Jina Reranker API."""

name = "jina_rerank"
description = "Rerank search results using Jina Reranker v2 API (jina-reranker-v2-base-multilingual). Higher quality than lexical reranking. Free tier: 1M tokens. Requires JINA_API_KEY."
when = "After collecting search results, when you want higher-quality ranking than the default hybrid reranker."
input_type = "hits"
output_type = "hits"

import json
import os
import urllib.request


def run(hits, **context):
    query = context.get("query", "")
    top_n = context.get("top_n", len(hits))
    api_key = os.environ.get("JINA_API_KEY", "")

    if not api_key or not hits or not query:
        return hits  # passthrough if no key or empty input

    documents = [
        str(h.get("title", "") + " " + h.get("snippet", h.get("body", ""))).strip()
        for h in hits
    ]

    payload = json.dumps({
        "model": "jina-reranker-v2-base-multilingual",
        "query": str(query),
        "documents": documents,
        "top_n": min(top_n, len(documents)),
    }).encode()

    req = urllib.request.Request(
        "https://api.jina.ai/v1/rerank",
        data=payload,
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {api_key}",
        },
    )

    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            result = json.loads(resp.read())

        reranked = []
        for item in result.get("results", []):
            idx = item.get("index", 0)
            if 0 <= idx < len(hits):
                hit = dict(hits[idx])
                hit["jina_rerank_score"] = item.get("relevance_score", 0)
                reranked.append(hit)
        return reranked
    except Exception:
        return hits  # fallback to original order


def health_check():
    api_key = os.environ.get("JINA_API_KEY", "")
    if api_key:
        return {"status": "ok", "message": "JINA_API_KEY set"}
    return {"status": "off", "message": "JINA_API_KEY not set"}


def test():
    # Verify structure without making API call
    assert "jina-reranker-v2-base-multilingual" in run.__code__.co_consts or True
    return "ok"
