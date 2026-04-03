"""Expand a single query into 7 diverse queries using cognitive personas."""

name = "persona_expand"
description = "Take one search query and generate 7 diverse alternative queries, each from a different cognitive perspective: Skeptic (counter-evidence), Analyst (precise data), Historian (evolution), Comparator (alternatives), Temporal (recency), Globalizer (authoritative language), Contrarian (opposing view)."
when = "When a single query isn't finding enough results, or you want to explore a topic from multiple angles."
input_type = "query"
output_type = "queries"

input_schema = {
    "type": "object",
    "properties": {
        "input": {
            "type": "string",
            "description": "Original search query to expand into 7 personas",
        },
    },
    "required": ["input"],
}

_PERSONAS = [
    {
        "id": "skeptic",
        "role": "Expert Skeptic",
        "instruction": "Find edge cases, counter-evidence, and things that could go wrong. Search for failures, limitations, and criticisms.",
    },
    {
        "id": "analyst",
        "role": "Detail Analyst",
        "instruction": "Find precise specifications, benchmarks, measurements, and reference data. Search for exact numbers and comparisons.",
    },
    {
        "id": "historian",
        "role": "Historical Researcher",
        "instruction": "Find the evolution, origin story, and legacy issues. Search for how things changed over time and why.",
    },
    {
        "id": "comparator",
        "role": "Comparative Thinker",
        "instruction": "Find alternatives, competitors, and trade-offs. Search for 'X vs Y' and comparison analyses.",
    },
    {
        "id": "temporal",
        "role": "Temporal Context",
        "instruction": "Find the most recent information. Add year or 'latest' or '2026' to make the query time-aware.",
    },
    {
        "id": "globalizer",
        "role": "Globalizer",
        "instruction": "Search in the most authoritative language for this domain. If it's a German product, search in German. If it's a Japanese concept, use Japanese terms.",
    },
    {
        "id": "contrarian",
        "role": "Contrarian",
        "instruction": "Argue against the premise. Search for 'why X is wrong' or 'problems with X' or 'X alternatives'.",
    },
]


def _template_expand(query):
    """Fallback: generate queries using templates (no LLM needed)."""
    q = str(query).strip()
    return [
        {
            "query": f"{q} problems limitations failures",
            "persona": "skeptic",
            "research_goal": f"Find counter-evidence and edge cases for: {q}",
        },
        {
            "query": f"{q} benchmark comparison data",
            "persona": "analyst",
            "research_goal": f"Find precise data and measurements for: {q}",
        },
        {
            "query": f"{q} history evolution origin",
            "persona": "historian",
            "research_goal": f"Find how {q} evolved over time",
        },
        {
            "query": f"{q} vs alternatives comparison",
            "persona": "comparator",
            "research_goal": f"Find alternatives and trade-offs for: {q}",
        },
        {
            "query": f"{q} 2026 latest new",
            "persona": "temporal",
            "research_goal": f"Find the most recent information about: {q}",
        },
        {
            "query": q,
            "persona": "globalizer",
            "research_goal": f"Search in the most authoritative language for: {q}",
        },
        {
            "query": f"why {q} is wrong problems criticism",
            "persona": "contrarian",
            "research_goal": f"Find opposing views on: {q}",
        },
    ]


def run(query, **context):
    use_llm = context.get("use_llm", False)

    if use_llm:
        try:
            return _llm_expand(str(query), context)
        except Exception:
            pass  # fall through to template

    return _template_expand(str(query))


def _llm_expand(query, context):
    """Use LLM to generate persona-specific queries."""
    import json as _json
    import os
    import urllib.request

    api_key = os.environ.get("ANTHROPIC_API_KEY", "")
    if not api_key:
        return _template_expand(query)

    persona_descriptions = "\n".join(
        f"- {p['role']}: {p['instruction']}" for p in _PERSONAS
    )
    prompt = f"""Given this search query: "{query}"

Generate 7 alternative search queries, one for each cognitive persona:
{persona_descriptions}

Return JSON array: [{{"query": "...", "persona": "skeptic|analyst|historian|comparator|temporal|globalizer|contrarian", "research_goal": "..."}}]"""

    payload = _json.dumps(
        {
            "model": "claude-haiku-4-5-20251001",
            "max_tokens": 1024,
            "messages": [{"role": "user", "content": prompt}],
        }
    ).encode()

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
        queries = _json.loads(text[start:end])
        return [
            {
                "query": q["query"],
                "persona": q.get("persona", ""),
                "research_goal": q.get("research_goal", ""),
            }
            for q in queries
        ]

    return _template_expand(query)


def test():
    result = run("AI agent framework")
    assert len(result) == 7, f"Expected 7 queries, got {len(result)}"
    personas = {r["persona"] for r in result}
    assert "skeptic" in personas
    assert "analyst" in personas
    assert "contrarian" in personas
    return "ok"
