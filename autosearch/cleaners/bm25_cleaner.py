# Self-written, plan v2.3 § 13.5 F104
from __future__ import annotations

import re
from dataclasses import dataclass
from typing import ClassVar

from bs4 import BeautifulSoup, Tag
from rank_bm25 import BM25Okapi

from autosearch.cleaners.base import Cleaner


@dataclass(frozen=True)
class _Candidate:
    index: int
    html: str
    tokens: tuple[str, ...]


class BM25Cleaner(Cleaner):
    """Query-aware HTML compression that keeps only BM25-relevant blocks."""

    CANDIDATE_TAGS: ClassVar[tuple[str, ...]] = (
        "p",
        "li",
        "pre",
        "blockquote",
        "h1",
        "h2",
        "h3",
        "h4",
        "h5",
        "h6",
    )
    TOKEN_PATTERN: ClassVar[re.Pattern[str]] = re.compile(r"\w+")

    def __init__(
        self,
        top_k: int = 15,
        min_score: float = 0.0,
        user_query_weight: float = 1.0,
    ) -> None:
        self.top_k = top_k
        self.min_score = min_score
        self.user_query_weight = user_query_weight

    def clean(self, html: str, query: str | None = None) -> str:
        if query is None:
            return html

        query_tokens = self._tokenize(query)
        if not query_tokens:
            return html

        if not html:
            return ""

        soup = BeautifulSoup(html, "html.parser")
        if soup.body is None:
            soup = BeautifulSoup(f"<body>{html}</body>", "html.parser")

        body = soup.body
        if body is None:
            return ""

        candidates = self._extract_candidates(body)
        if not candidates:
            return ""

        if len(candidates) == 1:
            return candidates[0].html

        scored_candidates = [candidate for candidate in candidates if candidate.tokens]
        if not scored_candidates:
            return ""

        bm25 = BM25Okapi([list(candidate.tokens) for candidate in scored_candidates])
        scores = bm25.get_scores(query_tokens)
        selected_indexes = self._select_candidate_indexes(scored_candidates, scores)
        if not selected_indexes:
            return ""

        return "\n".join(
            candidate.html for candidate in candidates if candidate.index in selected_indexes
        )

    def _extract_candidates(self, body: Tag) -> list[_Candidate]:
        candidates: list[_Candidate] = []
        for index, tag in enumerate(body.find_all(self.CANDIDATE_TAGS)):
            text = tag.get_text(" ", strip=True)
            if not text:
                continue
            candidates.append(
                _Candidate(
                    index=index,
                    html=str(tag),
                    tokens=tuple(self._tokenize(text)),
                )
            )
        return candidates

    def _select_candidate_indexes(
        self,
        candidates: list[_Candidate],
        scores: list[float],
    ) -> set[int]:
        scored_candidates = list(zip(candidates, scores, strict=True))
        ranked_candidates = sorted(scored_candidates, key=lambda item: item[1], reverse=True)

        selected_indexes: set[int] = set()
        if self.top_k > 0:
            selected_indexes.update(
                candidate.index for candidate, score in ranked_candidates if score > self.min_score
            )
            if len(selected_indexes) > self.top_k:
                top_indexes = {
                    candidate.index
                    for candidate, score in ranked_candidates[: self.top_k]
                    if score > self.min_score
                }
                selected_indexes = top_indexes

        if self.min_score > 0:
            selected_indexes.update(
                candidate.index for candidate, score in scored_candidates if score >= self.min_score
            )

        return selected_indexes

    def _tokenize(self, text: str) -> list[str]:
        return self.TOKEN_PATTERN.findall(text.lower())
