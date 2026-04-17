# Source: deer-flow/deerflow/community/infoquest/infoquest_client.py:L183-L230 (adapted)
# Self-written, plan v2.3 § 13.5 M5 BM25 + SimHash
from autosearch.core.models import Evidence


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

        tokenized_corpus = [_bm25_text(evidence).split() for evidence in evs]
        query_tokens = query.split()

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


def _simhash_text(evidence: Evidence) -> str:
    return "\n".join(
        part for part in [evidence.title, evidence.snippet or "", evidence.content or ""] if part
    )


def _bm25_text(evidence: Evidence) -> str:
    return " ".join(
        part for part in [evidence.title, evidence.snippet or "", evidence.content or ""] if part
    )
