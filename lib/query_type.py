from __future__ import annotations

import re
from typing import Literal

QueryType = Literal[
    "product",
    "concept",
    "opinion",
    "how_to",
    "comparison",
    "breaking_news",
    "prediction",
]

_QUERY_PATTERNS: dict[QueryType, re.Pattern[str]] = {
    "comparison": re.compile(
        r"\b(?:vs|versus|compared to|comparison|better than|difference between)\b",
        re.IGNORECASE,
    ),
    "how_to": re.compile(
        r"\b(?:how to|tutorial|step by step|setup|install|configure|deploy|best practices|tips)\b",
        re.IGNORECASE,
    ),
    "product": re.compile(
        r"\b(?:price|cost|buy|deal|alternative|subscription|plan|tier)\b",
        re.IGNORECASE,
    ),
    "opinion": re.compile(
        r"\b(?:worth it|thoughts on|opinion|review|experience with|recommend|should i|pros and cons)\b",
        re.IGNORECASE,
    ),
    "prediction": re.compile(
        r"\b(?:predict|forecast|odds|chance|probability|election|outcome)\b",
        re.IGNORECASE,
    ),
    "concept": re.compile(
        r"\b(?:what is|explain|definition|how does|overview|introduction|guide to)\b",
        re.IGNORECASE,
    ),
    "breaking_news": re.compile(
        r"\b(?:latest|breaking|just announced|launched|released|new|update|news|today|this week)\b",
        re.IGNORECASE,
    ),
}

_QUERY_PRIORITY: tuple[QueryType, ...] = (
    "comparison",
    "how_to",
    "product",
    "opinion",
    "prediction",
    "concept",
    "breaking_news",
)

SOURCE_TIERS: dict[QueryType, dict[str, list[str]]] = {
    "product": {
        "tier1": ["reddit", "twitter", "youtube"],
        "tier2": ["web-ddgs", "hn"],
    },
    "concept": {
        "tier1": ["reddit", "hn", "web-ddgs"],
        "tier2": ["youtube", "twitter", "arxiv"],
    },
    "opinion": {
        "tier1": ["reddit", "twitter"],
        "tier2": ["youtube", "hn"],
    },
    "how_to": {
        "tier1": ["youtube", "reddit", "hn"],
        "tier2": ["web-ddgs", "stackoverflow"],
    },
    "comparison": {
        "tier1": ["reddit", "hn", "youtube"],
        "tier2": ["twitter", "web-ddgs"],
    },
    "breaking_news": {
        "tier1": ["twitter", "reddit", "web-ddgs"],
        "tier2": ["hn", "youtube"],
    },
    "prediction": {
        "tier1": ["twitter", "reddit"],
        "tier2": ["web-ddgs", "hn", "youtube"],
    },
}

WEBSEARCH_PENALTY: dict[QueryType, float] = {
    "product": 15.0,
    "concept": 0.0,
    "opinion": 15.0,
    "how_to": 5.0,
    "comparison": 10.0,
    "breaking_news": 10.0,
    "prediction": 15.0,
}

TIEBREAKER_ORDER: dict[QueryType, dict[str, int]] = {
    "breaking_news": {
        "twitter": 0,
        "reddit": 1,
        "web-ddgs": 2,
        "hn": 3,
        "youtube": 4,
    },
    "how_to": {
        "youtube": 0,
        "reddit": 1,
        "hn": 2,
        "web-ddgs": 3,
        "stackoverflow": 4,
        "twitter": 5,
    },
    "prediction": {
        "twitter": 0,
        "reddit": 1,
        "web-ddgs": 2,
        "hn": 3,
        "youtube": 4,
    },
    "concept": {
        "hn": 0,
        "reddit": 1,
        "web-ddgs": 2,
        "youtube": 3,
        "arxiv": 4,
        "twitter": 5,
    },
    "opinion": {
        "reddit": 0,
        "twitter": 1,
        "youtube": 2,
        "hn": 3,
        "web-ddgs": 4,
    },
    "product": {
        "reddit": 0,
        "twitter": 1,
        "youtube": 2,
        "hn": 3,
        "web-ddgs": 4,
    },
    "comparison": {
        "reddit": 0,
        "hn": 1,
        "youtube": 2,
        "twitter": 3,
        "web-ddgs": 4,
    },
}


def detect_query_type(query: str) -> QueryType:
    for query_type in _QUERY_PRIORITY:
        if _QUERY_PATTERNS[query_type].search(query):
            return query_type
    return "breaking_news"


def get_source_penalty(query_type: QueryType, source: str) -> float:
    if source == "web-ddgs":
        return WEBSEARCH_PENALTY[query_type]
    return 0.0


def get_tiebreaker(query_type: QueryType, source: str) -> int:
    return TIEBREAKER_ORDER.get(query_type, {}).get(source, 99)


def is_source_in_tier(query_type: QueryType, source: str) -> bool:
    tiers = SOURCE_TIERS.get(query_type, {})
    return source in tiers.get("tier1", []) or source in tiers.get("tier2", [])
