from __future__ import annotations

import datetime
import math
import re

WORD_RE = re.compile(r"\w+")
DATE_FIELDS = ("published_at", "created_utc", "updated_at")
RELEVANCE_WEIGHT = 0.45
RECENCY_WEIGHT = 0.25
ENGAGEMENT_WEIGHT = 0.30
SOURCE_ALIASES = {
    "github": "github-repos",
    "x": "twitter",
}


PLATFORM_FORMULAS = {
    "reddit": lambda m: (
        0.50 * math.log1p(m.get("score", 0))
        + 0.35 * math.log1p(m.get("num_comments", 0))
        + 0.05 * (m.get("upvote_ratio", 0.5) * 10)
        + 0.10 * math.log1p(_top_comment_score(m))
    ),
    "hn": lambda m: (
        0.55 * math.log1p(m.get("points", 0))
        + 0.45 * math.log1p(m.get("num_comments", 0))
    ),
    "youtube": lambda m: (
        0.50 * math.log1p(m.get("views", 0))
        + 0.35 * math.log1p(m.get("likes", 0))
        + 0.15 * math.log1p(m.get("num_comments", 0))
    ),
    "github-repos": lambda m: (
        0.70 * math.log1p(m.get("stars", 0)) + 0.30 * math.log1p(m.get("forks", 0))
    ),
    "stackoverflow": lambda m: (
        0.50 * math.log1p(m.get("score", 0))
        + 0.30 * math.log1p(m.get("answer_count", 0))
        + 0.20 * float(m.get("is_answered", False))
    ),
    "twitter": lambda m: (
        0.50 * math.log1p(m.get("likes", 0))
        + 0.30 * math.log1p(m.get("reposts", 0))
        + 0.20 * math.log1p(m.get("replies", 0))
    ),
}


def score_results(results: list[dict], query: str) -> None:
    """Add metadata['composite_score'] (0-100) to each result, then sort descending."""
    try:
        from lib.query_type import detect_query_type, get_source_penalty
    except ImportError:
        detect_query_type = None
        get_source_penalty = None

    query_type = detect_query_type(query) if detect_query_type else "breaking_news"

    normalize_engagement_scores(results)

    for result in results:
        relevance = semantic_score(query, result)
        recency = freshness_score(result)
        engagement = _clamp01(_coerce_float(result.get("engagement_score"), 0.5))
        composite = (
            RELEVANCE_WEIGHT * relevance
            + RECENCY_WEIGHT * recency
            + ENGAGEMENT_WEIGHT * engagement
        )
        score_100 = max(0, min(100, int(round(_clamp01(composite) * 100))))

        # Apply query-type source penalty (e.g., web-ddgs penalized for opinion queries)
        if get_source_penalty is not None:
            penalty = get_source_penalty(query_type, result.get("source", ""))
            score_100 = max(0, score_100 - int(penalty))

        result.setdefault("metadata", {})["composite_score"] = score_100

    # Clean up internal engagement_score from top-level result dict
    for result in results:
        result.pop("engagement_score", None)

    results.sort(
        key=lambda r: r.get("metadata", {}).get("composite_score", 0), reverse=True
    )


def rescore_enriched(results: list[dict], query: str) -> None:
    """Update composite_score for results that have extracted_content.

    After content enrichment, relevance based on full content is much
    more accurate than snippet-based relevance. Re-score and re-sort.
    """
    changed = False
    for result in results:
        content = result.get("metadata", {}).get("extracted_content", "")
        if not content:
            continue
        # Re-compute relevance on full content instead of snippet
        query_tokens = {token.lower() for token in WORD_RE.findall(query or "")}
        content_tokens = {token.lower() for token in WORD_RE.findall(content)}
        union = query_tokens | content_tokens
        content_relevance = (
            len(query_tokens & content_tokens) / len(union) if union else 0.0
        )

        recency = freshness_score(result)
        old_score = result.get("metadata", {}).get("composite_score", 50)
        engagement_proxy = _clamp01(old_score / 100.0)

        new_composite = (
            0.60 * content_relevance + 0.20 * engagement_proxy + 0.20 * recency
        )
        new_score = max(0, min(100, int(round(_clamp01(new_composite) * 100))))
        result["metadata"]["composite_score"] = new_score
        changed = True

    if changed:
        results.sort(
            key=lambda r: r.get("metadata", {}).get("composite_score", 0),
            reverse=True,
        )


def semantic_score(query: str, result: dict) -> float:
    query_tokens = {token.lower() for token in WORD_RE.findall(query or "")}
    title = str(result.get("title", "") or "")
    snippet = str(result.get("snippet", "") or "")
    text_tokens = {token.lower() for token in WORD_RE.findall(f"{title} {snippet}")}
    union = query_tokens | text_tokens
    if not union:
        return 0.0
    return len(query_tokens & text_tokens) / len(union)


def freshness_score(result: dict) -> float:
    return _freshness_score_at(result, datetime.datetime.now(datetime.timezone.utc))


def _top_comment_score(metadata: dict) -> int:
    value = metadata.get("top_comment_score", 0)
    try:
        return int(value)
    except (TypeError, ValueError):
        return 0


def raw_engagement(source: str, metadata: dict) -> float:
    platform = SOURCE_ALIASES.get((source or "").lower(), (source or "").lower())
    formula = PLATFORM_FORMULAS.get(platform)
    if formula is None:
        return 0.0
    return float(formula(metadata))


def normalize_engagement_scores(results: list[dict]) -> None:
    groups: dict[str, list[tuple[dict, float]]] = {}

    for result in results:
        source = str(result.get("source", "") or "")
        metadata = _merged_metrics(result)
        score = raw_engagement(source, metadata)
        groups.setdefault(source, []).append((result, score))

    for group in groups.values():
        values = [score for _, score in group]
        low = min(values)
        high = max(values)

        if low == high:
            for result, _ in group:
                result["engagement_score"] = 0.5
            continue

        scale = high - low
        for result, score in group:
            result["engagement_score"] = (score - low) / scale


def _freshness_score_at(result: dict, now: datetime.datetime | None = None) -> float:
    now = now or datetime.datetime.now(datetime.timezone.utc)
    value = _get_date_value(result)
    if not value:
        return 0.5

    parsed = _parse_iso_datetime(value)
    if parsed is None:
        return 0.5

    age_days = (now.date() - parsed.astimezone(datetime.timezone.utc).date()).days
    score = 1.0 - (age_days / 180.0)
    return _clamp01(score)


def _get_date_value(result: dict) -> str:
    metadata = result.get("metadata")
    if not isinstance(metadata, dict):
        metadata = {}

    for name in DATE_FIELDS:
        value = metadata.get(name)
        if isinstance(value, str) and value:
            return value
    return ""


def _parse_iso_datetime(value: str) -> datetime.datetime | None:
    text = value.strip()
    if not text:
        return None

    try:
        parsed = datetime.datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError:
        return None

    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=datetime.timezone.utc)
    return parsed


def _merged_metrics(result: dict) -> dict:
    merged: dict = {}
    metadata = result.get("metadata")
    if isinstance(metadata, dict):
        merged.update(metadata)

    for key, value in result.items():
        if key == "metadata":
            continue
        merged.setdefault(key, value)

    return merged


def _coerce_float(value: object, default: float) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _clamp01(value: float) -> float:
    return max(0.0, min(1.0, value))
