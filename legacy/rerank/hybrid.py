"""Hybrid reranking using lexical score plus source hints."""

from __future__ import annotations


from search_mesh.models import SearchHit

from .lexical import dedup_hits, harmonic_position_bonus, lexical_score


PROVIDER_HINTS = {
    "github_code": 4,
    "github_repos": 3,
    "github_issues": 2,
    "huggingface_datasets": 2,
    "searxng": 1,
    "ddgs": 1,
}


def rerank_hits(
    query: str,
    hits: list[SearchHit],
    *,
    preferred_content_types: list[str] | None = None,
    rerank_profile: str = "hybrid",
    max_per_domain: int | None = None,
) -> list[SearchHit]:
    unique_hits = dedup_hits(list(hits or []), max_per_domain=max_per_domain)
    if rerank_profile == "none":
        return unique_hits

    def sort_key(hit: SearchHit) -> tuple[int, int, int]:
        lexical = lexical_score(
            query, hit, preferred_content_types=preferred_content_types
        )
        provider_hint = PROVIDER_HINTS.get(str(hit.provider or "").strip(), 0)
        position_bonus = harmonic_position_bonus(int(hit.rank or 1))
        hybrid = lexical + provider_hint + int(hit.score_hint or 0) + position_bonus
        if rerank_profile == "lexical":
            hybrid = lexical
        return (hybrid, lexical, position_bonus)

    return sorted(unique_hits, key=sort_key, reverse=True)
