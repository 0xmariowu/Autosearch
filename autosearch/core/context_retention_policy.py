"""Context-retention-policy: trim evidence list to a token budget."""

from __future__ import annotations


def trim_to_budget(
    evidence_list: list[dict],
    token_budget: int,
    *,
    score_key: str = "score",
) -> list[dict]:
    """Return evidence items that fit within token_budget, highest score first.

    Token estimation: len(str(item)) // 4 (rough approximation).
    Items are sorted by score descending before trimming, so the most
    relevant items are kept. Items with no score field are treated as 0.
    """
    if token_budget <= 0:
        return []

    scored = sorted(
        evidence_list,
        key=lambda item: float(item.get(score_key) or 0),
        reverse=True,
    )

    kept: list[dict] = []
    used = 0
    for item in scored:
        cost = max(1, len(str(item)) // 4)
        if used + cost > token_budget:
            break
        kept.append(item)
        used += cost

    return kept
