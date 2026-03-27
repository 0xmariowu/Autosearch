"""Filter search results by domain quality and content relevance."""

name = "quality_filter"
description = "Filter search results by quality: remove low-value domains (LinkedIn posts, marketing, paywalled), keep high-value sources (GitHub, arXiv, official docs). Sorts high-quality results first."
when = "After collecting results, before final output. Removes noise and keeps signal."
input_type = "hits"
output_type = "hits"
input_schema = {
    "type": "object",
    "properties": {
        "input": {
            "type": "array",
            "items": {"type": "object"},
            "description": "List of hit dicts to filter",
        },
        "context": {
            "type": "object",
            "properties": {
                "min_title_len": {"type": "integer", "default": 10},
            },
        },
    },
    "required": ["input"],
}

_HIGH_VALUE_DOMAINS = {
    "github.com", "arxiv.org", "huggingface.co", "pytorch.org", "tensorflow.org",
    "docs.python.org", "learn.microsoft.com", "developer.mozilla.org",
    "en.wikipedia.org", "stackoverflow.com", "news.ycombinator.com",
    "paperswithcode.com", "kaggle.com", "openai.com", "anthropic.com",
    "deepmind.google", "ai.meta.com",
}

_LOW_VALUE_DOMAINS = {
    "linkedin.com", "facebook.com", "instagram.com", "tiktok.com",
    "pinterest.com", "slideshare.net", "quora.com",
    "youtube.com",  # usually not useful as a link (no code/text)
}

_SKIP_PATTERNS = [
    "/login", "/signup", "/register", "/pricing",
    "/careers", "/jobs", "/about-us", "/contact",
]


def _domain_match(domain, domain_set):
    """Exact domain match: domain == d or domain ends with .d"""
    return any(domain == d or domain.endswith("." + d) for d in domain_set)


def run(hits, **context):
    if not hits or not isinstance(hits, list):
        return []

    min_title_len = context.get("min_title_len", 10)
    filtered = []

    for hit in hits:
        if not isinstance(hit, dict):
            continue

        url = str(hit.get("url", "")).strip()
        title = str(hit.get("title", "")).strip()

        # Skip empty
        if not url or not title or len(title) < min_title_len:
            continue

        # Skip low-value URL patterns
        if any(pattern in url.lower() for pattern in _SKIP_PATTERNS):
            continue

        # Extract domain
        from urllib.parse import urlparse
        try:
            domain = urlparse(url).netloc.lower().replace("www.", "")
        except Exception:
            domain = ""

        # Skip low value domains
        if _domain_match(domain, _LOW_VALUE_DOMAINS):
            continue

        # Classify quality
        is_high = _domain_match(domain, _HIGH_VALUE_DOMAINS)
        hit["domain"] = domain
        hit["quality_tier"] = "high" if is_high else "medium"
        filtered.append(hit)

    # Sort: high quality first, then by score
    filtered.sort(
        key=lambda h: (
            0 if h.get("quality_tier") == "high" else 1,
            -int(h.get("score_hint", 0) or 0),
        )
    )
    return filtered


def test():
    sample = [
        {"url": "https://github.com/org/repo", "title": "Great AI Framework", "score_hint": 100},
        {"url": "https://linkedin.com/posts/someone", "title": "My thoughts on AI", "score_hint": 50},
        {"url": "https://arxiv.org/abs/2301.00001", "title": "A Paper on LLMs", "score_hint": 30},
        {"url": "https://example.com/signup", "title": "Sign up for free", "score_hint": 200},
        {"url": "https://blog.example.com/ai-tools", "title": "Top AI Tools 2026", "score_hint": 80},
    ]
    result = run(sample)
    # LinkedIn and signup should be removed
    urls = [h["url"] for h in result]
    assert "https://linkedin.com/posts/someone" not in urls, "LinkedIn should be filtered"
    assert "https://example.com/signup" not in urls, "Signup page should be filtered"
    assert len(result) == 3
    # GitHub should be first (high value)
    assert result[0]["quality_tier"] == "high"
    return "ok"
