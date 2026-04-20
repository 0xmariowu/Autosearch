# Source: deer-flow/deerflow/community/infoquest/infoquest_client.py:L183-L230 (adapted)
# Self-written, plan v2.3 § 13.5 M5 BM25 + SimHash
from __future__ import annotations

import hashlib
import re

from autosearch.cleaners.pruning_cleaner import PruningCleaner
from autosearch.core.models import Evidence, EvidenceSnippet

_CJK_CHAR_RE = PruningCleaner.CJK_CHAR_RE
_NON_WHITESPACE_RE = re.compile(r"\S+")


class EvidenceProcessor:
    def dedup_urls(self, evs: list[Evidence]) -> list[Evidence]:
        seen_urls: set[str] = set()
        deduped: list[Evidence] = []
        for evidence in evs:
            if evidence.url in seen_urls:
                continue
            seen_urls.add(evidence.url)
            deduped.append(evidence)
        return deduped

    def dedup_simhash(self, evs: list[Evidence], threshold: int = 3) -> list[Evidence]:
        from simhash import Simhash

        kept: list[Evidence] = []
        kept_hashes: list[Simhash] = []
        for evidence in evs:
            text = _simhash_text(evidence)
            fingerprint = Simhash(text)
            if any(fingerprint.distance(existing) <= threshold for existing in kept_hashes):
                continue
            kept.append(evidence)
            kept_hashes.append(fingerprint)
        return kept

    def rerank_bm25(self, evs: list[Evidence], query: str, top_k: int = 20) -> list[Evidence]:
        if top_k <= 0 or not evs:
            return []

        tokenized_corpus = [_tokenize_bm25_text(_bm25_text(evidence)) for evidence in evs]
        query_tokens = _tokenize_bm25_text(query)

        if not query_tokens or not any(tokens for tokens in tokenized_corpus):
            reranked = [evidence.model_copy(update={"score": 0.0}) for evidence in evs]
            return reranked[:top_k]

        from rank_bm25 import BM25Okapi

        bm25 = BM25Okapi(tokenized_corpus)
        scores = bm25.get_scores(query_tokens)
        scored = [
            evidence.model_copy(update={"score": float(score)})
            for evidence, score in zip(evs, scores, strict=True)
        ]
        scored.sort(key=lambda evidence: evidence.score or 0.0, reverse=True)
        return scored[:top_k]

    @staticmethod
    def split_into_snippets(evidence: Evidence, **kwargs: object) -> list[EvidenceSnippet]:
        return split_into_snippets(evidence, **kwargs)

    @staticmethod
    def retrieve_for_section(
        section_query: str,
        snippets: list[EvidenceSnippet],
        top_k: int = 15,
    ) -> list[EvidenceSnippet]:
        return retrieve_for_section(section_query, snippets, top_k=top_k)


def split_into_snippets(
    evidence: Evidence,
    *,
    window_tokens: int = 200,
    overlap_tokens: int = 40,
) -> list[EvidenceSnippet]:
    """Split evidence text into overlapping snippet windows."""
    source_text = _snippet_source_text(evidence)
    if not source_text:
        return []

    step = max(1, window_tokens - overlap_tokens)
    evidence_id = _evidence_id(evidence)
    source_title = evidence.title or ""
    source_url = evidence.url or ""

    if _should_use_character_chunking(source_text):
        if len(source_text) <= window_tokens:
            return [
                EvidenceSnippet(
                    evidence_id=evidence_id,
                    text=source_text,
                    offset=0,
                    source_url=source_url,
                    source_title=source_title,
                )
            ]
        return [
            EvidenceSnippet(
                evidence_id=evidence_id,
                text=source_text[start : min(start + window_tokens, len(source_text))],
                offset=start,
                source_url=source_url,
                source_title=source_title,
            )
            for start in _window_starts(len(source_text), window_tokens, step)
        ]

    token_spans = list(_NON_WHITESPACE_RE.finditer(source_text))
    if not token_spans:
        return []
    if len(token_spans) <= window_tokens:
        return [
            EvidenceSnippet(
                evidence_id=evidence_id,
                text=source_text,
                offset=0,
                source_url=source_url,
                source_title=source_title,
            )
        ]

    snippets: list[EvidenceSnippet] = []
    for start in _window_starts(len(token_spans), window_tokens, step):
        end = min(start + window_tokens, len(token_spans))
        start_char = token_spans[start].start()
        end_char = token_spans[end - 1].end()
        snippets.append(
            EvidenceSnippet(
                evidence_id=evidence_id,
                text=source_text[start_char:end_char],
                offset=start_char,
                source_url=source_url,
                source_title=source_title,
            )
        )
    return snippets


def retrieve_for_section(
    section_query: str,
    snippets: list[EvidenceSnippet],
    *,
    top_k: int = 15,
) -> list[EvidenceSnippet]:
    """BM25-rank snippets against a section query and return the best matches."""
    if not snippets or not section_query.strip():
        return []
    if len(snippets) == 1:
        return snippets[:]

    tokenized_corpus = [_tokenize_bm25_text(snippet.text) for snippet in snippets]
    query_tokens = _tokenize_bm25_text(section_query)
    if not query_tokens:
        return []
    if not any(tokens for tokens in tokenized_corpus):
        return snippets[:] if top_k <= 0 else snippets[:top_k]

    from rank_bm25 import BM25Okapi

    bm25 = BM25Okapi(tokenized_corpus)
    scores = bm25.get_scores(query_tokens)
    ranked = list(zip(snippets, scores, strict=True))
    ranked.sort(key=lambda item: float(item[1]), reverse=True)
    ordered = [snippet for snippet, _ in ranked]
    return ordered if top_k <= 0 else ordered[:top_k]


def split_all_evidence(
    evidences: list[Evidence],
    *,
    window_tokens: int = 200,
    overlap_tokens: int = 40,
) -> list[EvidenceSnippet]:
    """Chunk every evidence item and flatten the snippets into one list."""
    snippets: list[EvidenceSnippet] = []
    for evidence in evidences:
        snippets.extend(
            split_into_snippets(
                evidence,
                window_tokens=window_tokens,
                overlap_tokens=overlap_tokens,
            )
        )
    return snippets


def _window_starts(total_units: int, window_size: int, step: int) -> list[int]:
    starts: list[int] = []
    start = 0
    while start < total_units:
        starts.append(start)
        if start + window_size >= total_units:
            break
        start += step
    return starts


def _snippet_source_text(evidence: Evidence) -> str:
    return evidence.content or evidence.snippet or ""


def _should_use_character_chunking(text: str) -> bool:
    cjk_chars = len(_CJK_CHAR_RE.findall(text))
    if cjk_chars == 0:
        return False
    whitespace_tokens = len(text.split())
    return whitespace_tokens <= max(1, cjk_chars // 8)


def _tokenize_bm25_text(text: str) -> list[str]:
    separated_cjk = _CJK_CHAR_RE.sub(lambda match: f" {match.group(0)} ", text)
    return separated_cjk.split()


def _evidence_id(evidence: Evidence) -> str:
    if evidence.url:
        return evidence.url
    preview = (evidence.content or evidence.snippet or "")[:100]
    payload = f"{evidence.title}\n{preview}"
    return hashlib.sha1(payload.encode("utf-8")).hexdigest()


def _simhash_text(evidence: Evidence) -> str:
    return "\n".join(
        part for part in [evidence.title, evidence.snippet or "", evidence.content or ""] if part
    )


def _bm25_text(evidence: Evidence) -> str:
    return " ".join(
        part for part in [evidence.title, evidence.snippet or "", evidence.content or ""] if part
    )
