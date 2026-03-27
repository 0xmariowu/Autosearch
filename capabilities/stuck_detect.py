"""Detect when search is stuck in a loop and suggest strategy changes."""

name = "stuck_detect"
description = "Detect when the search process is stuck: same URLs appearing repeatedly, discovery rate declining, or same queries being tried. Returns stuck status and concrete suggestions for changing strategy."
when = "After each search round in a multi-round loop. Helps the orchestrator decide when to change strategy."
input_type = "any"
output_type = "report"

input_schema = {
    "type": "object",
    "properties": {
        "input": {"description": "Not used, pass null"},
        "context": {
            "type": "object",
            "properties": {
                "history": {
                    "type": "array",
                    "items": {"type": "object"},
                    "description": "List of round summaries with urls and new_count fields",
                },
            },
            "required": ["history"],
        },
    },
}

_DUPLICATE_THRESHOLD = 3  # Copied from OpenManus: 3 consecutive similar rounds = stuck


def run(input_data, **context):
    history = context.get("history", [])  # list of round summaries

    if len(history) < 2:
        return {"stuck": False, "confidence": 0.0, "suggestions": []}

    # Check 1: URL overlap between recent rounds
    recent = history[-3:] if len(history) >= 3 else history
    url_sets = []
    for rnd in recent:
        urls = set(str(u) for u in (rnd.get("urls") or rnd.get("new_urls") or []))
        url_sets.append(urls)

    if len(url_sets) >= 2:
        overlap_ratios = []
        for i in range(1, len(url_sets)):
            if url_sets[i] and url_sets[i-1]:
                overlap = len(url_sets[i] & url_sets[i-1]) / max(len(url_sets[i]), 1)
                overlap_ratios.append(overlap)
        avg_overlap = sum(overlap_ratios) / max(len(overlap_ratios), 1)
    else:
        avg_overlap = 0.0

    # Check 2: Discovery rate declining
    discovery_rates = [r.get("new_count", r.get("discovery_rate", 0)) for r in recent]
    declining = all(
        discovery_rates[i] <= discovery_rates[i-1]
        for i in range(1, len(discovery_rates))
    ) if len(discovery_rates) >= 2 else False

    # Check 3: Zero new results
    zero_rounds = sum(1 for r in recent if (r.get("new_count", r.get("discovery_rate", 1))) == 0)

    # Determine if stuck
    stuck = False
    confidence = 0.0
    suggestions = []

    if avg_overlap > 0.7:
        stuck = True
        confidence = max(confidence, avg_overlap)
        suggestions.append("High URL overlap between rounds — try completely different query terms")

    if declining and len(discovery_rates) >= 3:
        stuck = True
        confidence = max(confidence, 0.8)
        suggestions.append("Discovery rate declining — try different platforms or use persona_expand for diverse queries")

    if zero_rounds >= 2:
        stuck = True
        confidence = max(confidence, 0.9)
        suggestions.append("Multiple rounds with zero new results — escalate to crawl_page + follow_links on existing high-quality results")

    if not suggestions:
        suggestions.append("Not stuck — continue current strategy")

    return {
        "stuck": stuck,
        "confidence": round(confidence, 2),
        "avg_url_overlap": round(avg_overlap, 2),
        "declining_discovery": declining,
        "zero_rounds": zero_rounds,
        "suggestions": suggestions,
    }


def test():
    # Test stuck detection
    history = [
        {"urls": ["a", "b", "c"], "new_count": 3},
        {"urls": ["a", "b", "d"], "new_count": 2},
        {"urls": ["a", "b", "d"], "new_count": 0},
    ]
    result = run(None, history=history)
    assert result["stuck"], "Should detect stuck state"
    assert result["zero_rounds"] >= 1

    # Test not stuck
    history2 = [
        {"urls": ["a", "b"], "new_count": 5},
        {"urls": ["c", "d", "e"], "new_count": 8},
    ]
    result2 = run(None, history=history2)
    assert not result2["stuck"], "Should not be stuck"
    return "ok"
