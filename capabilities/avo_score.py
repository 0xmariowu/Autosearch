"""Score search results using AVO multi-dimensional evaluation."""

name = "avo_score"
description = "Score a search result across 4 dimensions: quantity (unique URLs vs target), diversity (source variety via Simpson index), relevance (content quality proxy), efficiency (URLs per step). Returns total score 0-1."
when = "After completing a search run, to evaluate how well the strategy performed. Used by AVO evolution loop."
input_type = "any"
output_type = "scores"
input_schema = {
    "type": "object",
    "properties": {
        "input": {
            "type": "object",
            "description": "Search result dict with evidence list and steps_used",
        },
        "context": {
            "type": "object",
            "properties": {
                "target_count": {
                    "type": "integer",
                    "default": 100,
                    "description": "Target number of unique URLs",
                },
            },
        },
    },
    "required": ["input"],
}

from collections import Counter


def run(result, **context):
    if not isinstance(result, dict):
        return {
            "total": 0,
            "unique_urls": 0,
            "quantity_score": 0,
            "diversity": 0,
            "relevance": 0,
            "efficiency": 0,
        }

    evidence = result.get("evidence", [])
    if not isinstance(evidence, list):
        evidence = []
    evidence = [e for e in evidence if isinstance(e, dict)]

    target = context.get("target_count", 100)
    steps = max(result.get("steps_used", 1), 1)

    # Dimension 1: Quantity
    urls = set(e.get("url", "") for e in evidence if e.get("url"))
    unique_count = len(urls)
    quantity_score = min(unique_count / max(target, 1), 1.0)

    # Dimension 2: Diversity (Simpson's)
    sources = Counter(e.get("provider", e.get("source", "unknown")) for e in evidence)
    total = sum(sources.values())
    if total > 1:
        diversity = 1 - sum(n * (n - 1) for n in sources.values()) / (
            total * (total - 1)
        )
    else:
        diversity = 0.0

    # Dimension 3: Relevance (proxy: title length > 10)
    if evidence:
        relevant = sum(1 for e in evidence if len(str(e.get("title", ""))) > 10)
        relevance = relevant / len(evidence)
    else:
        relevance = 0.0

    # Dimension 4: Efficiency (URLs per step, 10/step = perfect)
    efficiency = min(unique_count / steps / 10, 1.0)

    total_score = round(
        0.4 * quantity_score + 0.2 * diversity + 0.2 * relevance + 0.2 * efficiency, 4
    )

    return {
        "total": total_score,
        "unique_urls": unique_count,
        "quantity_score": round(quantity_score, 4),
        "diversity": round(diversity, 4),
        "relevance": round(relevance, 4),
        "efficiency": round(efficiency, 4),
        "steps_used": steps,
        "target": target,
    }


def test():
    result = {
        "evidence": [
            {"url": "a.com", "title": "Framework A long title", "provider": "github"},
            {"url": "b.com", "title": "Framework B long title", "provider": "web"},
            {"url": "c.com", "title": "Framework C long title", "provider": "github"},
        ],
        "steps_used": 5,
    }
    scores = run(result, target_count=10)
    assert 0 < scores["total"] <= 1, f"Score out of range: {scores['total']}"
    assert scores["unique_urls"] == 3
    assert scores["diversity"] > 0
    assert scores["relevance"] > 0
    assert scores["efficiency"] > 0

    # Empty result
    empty = run({})
    assert empty["total"] == 0
    return "ok"
