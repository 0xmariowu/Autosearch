"""Extract concise learnings from search results."""

name = "learnings_extract"
description = "After a search round, extract concise, information-dense learning strings from the results. These learnings are passed to the next round's query generation to avoid redundant searches and build on discoveries."
when = "After each search round, before generating the next round of queries. The extracted learnings improve query quality over time."
input_type = "hits"
output_type = "learnings"

input_schema = {
    "type": "object",
    "properties": {
        "input": {
            "type": "array",
            "items": {"type": "object"},
            "description": "List of hit dicts from search results",
        },
        "context": {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "The query that produced these hits"},
            },
        },
    },
    "required": ["input"],
}


def _extract_from_hits(hits, query=""):
    """Extract learnings without LLM — keyword and pattern based."""
    learnings = []
    seen_domains = set()
    valid_hits = [h for h in hits if isinstance(h, dict)]
    for hit in valid_hits[:20]:  # top 20 only
        title = str(hit.get("title") or "")
        snippet = str(hit.get("snippet") or hit.get("body") or "")
        url = str(hit.get("url") or "")

        # Extract domain insight
        from urllib.parse import urlparse
        try:
            domain = urlparse(url).netloc
        except Exception:
            domain = ""

        if domain and domain not in seen_domains:
            seen_domains.add(domain)

        # Extract learning from title + snippet
        text = f"{title}. {snippet}".strip()
        if len(text) > 20:
            # Truncate to concise learning
            learning = text[:200].strip()
            if learning and learning not in learnings:
                learnings.append(learning)

    # Add meta-learnings
    if seen_domains:
        learnings.append(f"Found results from {len(seen_domains)} unique domains: {', '.join(sorted(seen_domains)[:5])}")

    return learnings[:10]  # cap at 10


def run(hits, **context):
    query = context.get("query", "")
    use_llm = context.get("use_llm", False)

    if not hits:
        return []

    # If input is already a list of strings, return them as learnings
    if isinstance(hits, list) and all(isinstance(x, str) for x in hits):
        return hits

    if use_llm:
        try:
            return _llm_extract(hits, query)
        except Exception:
            pass

    return _extract_from_hits(hits, query)


def _llm_extract(hits, query):
    """Use LLM to extract learnings (dzhng pattern)."""
    import json as _json
    import os
    import urllib.request

    api_key = os.environ.get("ANTHROPIC_API_KEY", "")
    if not api_key:
        return _extract_from_hits(hits, query)

    # Prepare context
    context_str = "\n".join(
        f"- {h.get('title', '')} ({h.get('url', '')}): {str(h.get('snippet', h.get('body', '')))[:100]}"
        for h in hits[:15]
    )

    prompt = f"""Given these search results for query "{query}":

{context_str}

Extract 5-10 concise, information-dense learnings. Each learning should be a single sentence that captures a key fact or insight. Focus on:
1. What's new or surprising
2. Patterns across multiple results
3. Gaps or contradictions found
4. Specific names, numbers, or dates mentioned

Return JSON array of strings: ["learning 1", "learning 2", ...]"""

    payload = _json.dumps({
        "model": "claude-haiku-4-5-20251001",
        "max_tokens": 512,
        "messages": [{"role": "user", "content": prompt}],
    }).encode()

    req = urllib.request.Request(
        "https://api.anthropic.com/v1/messages",
        data=payload,
        headers={
            "Content-Type": "application/json",
            "x-api-key": api_key,
            "anthropic-version": "2023-06-01",
        },
    )

    with urllib.request.urlopen(req, timeout=15) as resp:
        result = _json.loads(resp.read())

    text = result.get("content", [{}])[0].get("text", "")
    start = text.find("[")
    end = text.rfind("]") + 1
    if start >= 0 and end > start:
        return _json.loads(text[start:end])

    return _extract_from_hits(hits, query)


def test():
    sample_hits = [
        {"title": "LangChain Agent Framework", "url": "https://github.com/langchain-ai/langchain", "snippet": "Build context-aware reasoning applications"},
        {"title": "AutoGPT", "url": "https://github.com/Significant-Gravitas/AutoGPT", "snippet": "Autonomous AI agent platform"},
        {"title": "CrewAI", "url": "https://github.com/crewAIInc/crewAI", "snippet": "Framework for orchestrating AI agents"},
    ]
    result = run(sample_hits, query="AI agent framework")
    assert isinstance(result, list)
    assert len(result) > 0
    assert all(isinstance(l, str) for l in result)
    return "ok"
