"""Filter results by freshness based on content category."""

name = "freshness_check"
description = "Check if search results are fresh enough for their content category. Financial data must be < 1 day old, software info < 30 days, breaking news < 1 day, historical facts can be any age. Adds freshness_status field."
when = "After collecting results, when time-sensitivity matters. Especially important for financial, news, and software topics."
input_type = "hits"
output_type = "hits"

input_schema = {
    "type": "object",
    "properties": {
        "input": {
            "type": "array",
            "items": {"type": "object"},
            "description": "List of hit dicts with url, title, snippet, provider fields",
        },
        "context": {
            "type": "object",
            "properties": {
                "category": {"type": "string", "enum": ["financial", "breaking_news", "technology", "software", "science", "historical", "default"], "default": "default"},
            },
        },
    },
    "required": ["input"],
}

from datetime import datetime, timedelta

# Copied from Jina node-deepresearch QUESTION_FRESHNESS table
_MAX_AGE_DAYS = {
    "financial": 0.1,         # ~2.4 hours
    "breaking_news": 1,
    "current_events": 3,
    "technology": 14,
    "software": 30,
    "science": 90,
    "legal": 90,
    "medical": 180,
    "educational": 365,
    "historical": 36500,      # ~100 years (effectively no limit)
    "factual": 36500,
    "default": 365,
}


def run(hits, **context):
    if not hits or not isinstance(hits, list):
        return hits if isinstance(hits, list) else []
    hits = [h for h in hits if isinstance(h, dict)]
    if not hits:
        return []

    category = context.get("category", "default")
    max_age = _MAX_AGE_DAYS.get(category, _MAX_AGE_DAYS["default"])
    cutoff = datetime.now() - timedelta(days=max_age)
    cutoff_str = cutoff.strftime("%Y-%m-%d")

    for hit in hits:
        created = str(hit.get("created") or hit.get("published_at") or "")
        if not created or len(created) < 10:
            hit["freshness_status"] = "unknown"
            continue

        date_str = created[:10]  # YYYY-MM-DD
        try:
            if date_str >= cutoff_str:
                hit["freshness_status"] = "fresh"
            else:
                hit["freshness_status"] = "stale"
        except Exception:
            hit["freshness_status"] = "unknown"

    return hits


def test():
    today = datetime.now().strftime("%Y-%m-%d")
    old_date = "2020-01-01"

    sample = [
        {"title": "A", "created": today},
        {"title": "B", "created": old_date},
        {"title": "C", "created": ""},
    ]
    result = run(sample, category="software")  # 30 day limit
    assert result[0]["freshness_status"] == "fresh"
    assert result[1]["freshness_status"] == "stale"
    assert result[2]["freshness_status"] == "unknown"
    return "ok"
