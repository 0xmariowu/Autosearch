from __future__ import annotations

import asyncio
import math
from datetime import UTC, datetime
from typing import TYPE_CHECKING

import structlog

from autosearch.core.context_compaction import ContextCompactor
from autosearch.core.models import Evidence, EvidenceDigest

if TYPE_CHECKING:
    from autosearch.llm.client import LLMClient
    from autosearch.persistence.session_store import SessionStore


class EvidenceDelegator:
    """Parallel slice-level digestion."""

    def __init__(
        self,
        *,
        client: LLMClient,
        slice_size: int = 15,
        max_workers: int = 4,
        token_budget_per_slice: int = 6000,
        store: SessionStore | None = None,
        session_id: str | None = None,
    ) -> None:
        if slice_size <= 0:
            raise ValueError("slice_size must be greater than 0")
        if max_workers <= 0:
            raise ValueError("max_workers must be greater than 0")
        if token_budget_per_slice <= 0:
            raise ValueError("token_budget_per_slice must be greater than 0")

        self.client = client
        self.slice_size = slice_size
        self.max_workers = max_workers
        self.token_budget_per_slice = token_budget_per_slice
        self.store = store
        self.session_id = session_id
        self.logger = structlog.get_logger(__name__).bind(component="evidence_delegator")

    async def delegate(
        self,
        evidence: list[Evidence],
        query: str,
    ) -> list[EvidenceDigest]:
        """Return one digest per slice. Empty evidence produces no digests."""

        if not evidence:
            return []

        slices = self._partition_evidence(evidence)
        self.logger.info(
            "delegation_started",
            evidence_count=len(evidence),
            slice_count=len(slices),
            max_workers=self.max_workers,
        )

        if len(slices) == 1:
            digest = await self._digest_slice(slices[0], query)
            if digest is None:
                self.logger.warning("slice_failed", slice_index=0, error="no digest returned")
                return []
            self.logger.info(
                "slice_completed", slice_index=0, digest_tokens_after=digest.token_count_after
            )
            return [digest]

        results = await asyncio.gather(
            *(self._digest_slice(slice_evidence, query) for slice_evidence in slices),
            return_exceptions=True,
        )

        digests: list[EvidenceDigest] = []
        for index, result in enumerate(results):
            if isinstance(result, Exception):
                self.logger.warning("slice_failed", slice_index=index, error=str(result))
                continue
            if result is None:
                self.logger.warning("slice_failed", slice_index=index, error="no digest returned")
                continue
            self.logger.info(
                "slice_completed",
                slice_index=index,
                digest_tokens_after=result.token_count_after,
            )
            digests.append(result)
        return digests

    async def delegate_with_meta(
        self,
        evidence: list[Evidence],
        query: str,
    ) -> tuple[list[EvidenceDigest], EvidenceDigest | None]:
        """Return per-slice digests and an optional meta-digest over those digests."""

        digests = await self.delegate(evidence, query)
        if len(digests) <= 1:
            return digests, None

        meta_evidence = [
            self._digest_to_evidence(index, digest) for index, digest in enumerate(digests)
        ]
        compactor = self._make_compactor()
        meta_tokens_before = sum(compactor._count_tokens(item) for item in meta_evidence)
        prompt = compactor._build_prompt(query, meta_evidence)

        try:
            llm_digest = await self.client.complete(prompt, EvidenceDigest)
        except Exception as exc:
            self.logger.warning("meta_digest_failed", error=str(exc))
            return digests, None

        meta_digest = compactor._finalize_digest(llm_digest, meta_evidence, meta_tokens_before)
        meta_digest = meta_digest.model_copy(
            update={
                "source_urls": self._collect_digest_source_urls(digests),
                "evidence_count": sum(digest.evidence_count for digest in digests),
            }
        )
        meta_digest = meta_digest.model_copy(
            update={"token_count_after": self._count_digest_tokens(meta_digest)}
        )
        self.logger.info(
            "meta_digest_generated",
            slice_count=len(digests),
            meta_tokens_after=meta_digest.token_count_after,
        )
        return digests, meta_digest

    def _partition_evidence(self, evidence: list[Evidence]) -> list[list[Evidence]]:
        effective_slice_size = self.slice_size
        if len(evidence) > self.max_workers * self.slice_size:
            effective_slice_size = math.ceil(len(evidence) / self.max_workers)
        return [
            evidence[index : index + effective_slice_size]
            for index in range(0, len(evidence), effective_slice_size)
        ]

    async def _digest_slice(
        self,
        slice_evidence: list[Evidence],
        query: str,
    ) -> EvidenceDigest | None:
        if not slice_evidence:
            return None

        compactor = self._make_compactor()
        slice_tokens = sum(compactor._count_tokens(item) for item in slice_evidence)
        threshold = compactor.token_budget * compactor.compact_when_over_pct

        if slice_tokens < threshold:
            return await self._force_digest(compactor, slice_evidence, query, slice_tokens)

        _, digest = await compactor.compact(slice_evidence, query)
        return digest

    async def _force_digest(
        self,
        compactor: ContextCompactor,
        evidence: list[Evidence],
        query: str,
        token_count_before: int,
    ) -> EvidenceDigest:
        prompt = compactor._build_prompt(query, evidence)
        llm_digest = await self.client.complete(prompt, EvidenceDigest)
        digest = compactor._finalize_digest(llm_digest, evidence, token_count_before)
        await compactor._store_artifact_best_effort(
            kind="compacted_digest",
            payload=digest,
        )
        return digest

    def _make_compactor(self) -> ContextCompactor:
        return ContextCompactor(
            token_budget=self.token_budget_per_slice,
            hot_set_size=0,
            client=self.client,
            store=self.store,
            session_id=self.session_id,
        )

    def _digest_to_evidence(self, index: int, digest: EvidenceDigest) -> Evidence:
        return Evidence(
            url=digest.source_urls[0] if digest.source_urls else f"digest://slice-{index + 1}",
            title=digest.topic or f"Slice digest {index + 1}",
            snippet=digest.key_findings[0] if digest.key_findings else None,
            content=self._render_digest_as_content(digest),
            source_channel="delegation_digest",
            fetched_at=digest.compressed_at or datetime.now(UTC),
        )

    def _render_digest_as_content(self, digest: EvidenceDigest) -> str:
        lines = [f"Topic: {digest.topic}", "Key findings:"]
        lines.extend(f"- {finding}" for finding in digest.key_findings)
        lines.append("Source URLs:")
        lines.extend(f"- {url}" for url in digest.source_urls)
        lines.append(f"Evidence count: {digest.evidence_count}")
        return "\n".join(lines)

    def _collect_digest_source_urls(self, digests: list[EvidenceDigest]) -> list[str]:
        seen: set[str] = set()
        urls: list[str] = []
        for digest in digests:
            for url in digest.source_urls:
                if url in seen:
                    continue
                seen.add(url)
                urls.append(url)
        return urls

    def _count_digest_tokens(self, digest: EvidenceDigest) -> int:
        return self._make_compactor()._count_tokens(self._digest_to_evidence(0, digest))
