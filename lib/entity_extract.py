from __future__ import annotations

import re
from collections import Counter

MAX_ENTITIES = 5
ACADEMIC_SOURCES = {"arxiv", "semantic-scholar", "google-scholar"}
GENERIC_HANDLES = {
    "amazon",
    "apple",
    "github",
    "google",
    "meta",
    "microsoft",
    "openai",
    "reddit",
    "twitter",
    "x",
    "youtube",
}
HANDLE_RE = re.compile(r"@(\w{1,15})")
NAME_PART = r"(?:[A-Z][A-Za-z'`-]+|[A-Z]\.)"
AUTHOR_NAME = rf"{NAME_PART}(?:\s+{NAME_PART}){{1,3}}"
AUTHOR_LIST_PATTERNS = [
    re.compile(
        rf"\b(?:authors?|by)\s*:?\s*((?:{AUTHOR_NAME})(?:\s*(?:,|and)\s*{AUTHOR_NAME})+)"
    ),
    re.compile(rf"\b((?:{AUTHOR_NAME})(?:\s*(?:,|and)\s*{AUTHOR_NAME})+)"),
]
SINGLE_AUTHOR_PATTERN = re.compile(rf"\bby\s+({AUTHOR_NAME})\b")


def _top_items(counter: Counter[str], limit: int = MAX_ENTITIES) -> list[str]:
    return [
        item
        for item, _count in sorted(counter.items(), key=lambda pair: (-pair[1], pair[0]))[
            :limit
        ]
    ]


def extract_subreddits(results: list[dict]) -> list[str]:
    counts: Counter[str] = Counter()

    for result in results:
        if result.get("source") != "reddit":
            continue
        metadata = result.get("metadata") or {}
        subreddit = str(metadata.get("subreddit") or "").strip()
        subreddit = subreddit.removeprefix("r/").strip()
        if subreddit:
            counts[subreddit.lower()] += 1

    return _top_items(counts)


def _normalize_handle(handle: str) -> str:
    return handle.lstrip("@").strip().lower()


def extract_x_handles(results: list[dict]) -> list[str]:
    counts: Counter[str] = Counter()

    for result in results:
        if result.get("source") != "twitter":
            continue

        text = " ".join(
            part for part in (result.get("title", ""), result.get("snippet", "")) if part
        )
        for handle in HANDLE_RE.findall(text):
            normalized = _normalize_handle(handle)
            if normalized and normalized not in GENERIC_HANDLES:
                counts[normalized] += 1

        metadata = result.get("metadata") or {}
        author_handle = _normalize_handle(str(metadata.get("author_handle") or ""))
        if author_handle and author_handle not in GENERIC_HANDLES:
            counts[author_handle] += 1

    return _top_items(counts)


def _normalize_author(name: str) -> str:
    return re.sub(r"\s+", " ", name.strip(" ,.;:"))


def _extract_author_names(text: str) -> list[str]:
    authors: list[str] = []

    for pattern in AUTHOR_LIST_PATTERNS:
        for match in pattern.findall(text):
            parts = re.split(r"\s*(?:,|and)\s*", match)
            authors.extend(_normalize_author(part) for part in parts if part.strip())

    for match in SINGLE_AUTHOR_PATTERN.findall(text):
        authors.append(_normalize_author(match))

    return [author for author in authors if author]


def extract_authors(results: list[dict]) -> list[str]:
    counts: Counter[str] = Counter()

    for result in results:
        if result.get("source") not in ACADEMIC_SOURCES:
            continue

        metadata = result.get("metadata") or {}
        text = " ".join(
            part
            for part in (
                result.get("title", ""),
                result.get("snippet", ""),
                str(metadata.get("authors") or ""),
            )
            if part
        )
        for author in _extract_author_names(text):
            counts[author] += 1

    return _top_items(counts)


def extract_entities(results: list[dict]) -> dict[str, list[str]]:
    return {
        "subreddits": extract_subreddits(results),
        "x_handles": extract_x_handles(results),
        "authors": extract_authors(results),
    }
