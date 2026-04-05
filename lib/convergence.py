from __future__ import annotations

import re
import sys

SIMILARITY_THRESHOLD = 0.40
MAX_RESULTS_LIMIT = 500  # O(N^2) safety guard
STOPWORDS = frozenset(
    {
        "the",
        "a",
        "an",
        "is",
        "are",
        "was",
        "were",
        "in",
        "on",
        "at",
        "to",
        "for",
        "of",
        "and",
        "or",
        "but",
        "not",
        "with",
        "from",
        "by",
        "as",
        "it",
        "this",
        "that",
        "be",
        "have",
        "has",
        "do",
        "will",
        "can",
    }
)


def _tokenize(text: str) -> set[str]:
    tokens = re.sub(r"[^\w\s]", " ", text.lower()).split()
    return {token for token in tokens if len(token) > 1 and token not in STOPWORDS}


def _jaccard(tokens_a: set[str], tokens_b: set[str]) -> float:
    union = tokens_a | tokens_b
    if not union:
        return 0.0
    return len(tokens_a & tokens_b) / len(union)


def cross_source_link(results: list[dict]) -> None:
    if len(results) > MAX_RESULTS_LIMIT:
        print(
            f"warning: skipping cross-source linking for {len(results)} results "
            f"(limit: {MAX_RESULTS_LIMIT})",
            file=sys.stderr,
        )
        return

    title_tokens = [_tokenize(result.get("title", "")) for result in results]

    for i in range(len(results)):
        source_i = results[i].get("source")
        for j in range(i + 1, len(results)):
            source_j = results[j].get("source")
            if source_i == source_j:
                continue

            if _jaccard(title_tokens[i], title_tokens[j]) < SIMILARITY_THRESHOLD:
                continue

            metadata_i = results[i].setdefault("metadata", {})
            metadata_j = results[j].setdefault("metadata", {})
            metadata_i.setdefault("also_on", []).append(source_j)
            metadata_j.setdefault("also_on", []).append(source_i)

    for result in results:
        metadata = result.get("metadata")
        if not metadata or "also_on" not in metadata:
            continue
        metadata["also_on"] = sorted(set(metadata["also_on"]))
