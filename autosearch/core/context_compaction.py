from __future__ import annotations

import structlog

from autosearch.core.models import Evidence, EvidenceDigest
from autosearch.llm.client import LLMClient
from autosearch.observability.cost import estimate_tokens
from autosearch.skills.prompts import load_prompt

EVIDENCE_COMPACTION_PROMPT = load_prompt("m3_evidence_compaction")
_MAX_EVIDENCE_FIELD_CHARS = 1000


class ContextCompactor:
    """Token-budget-triggered evidence compression."""

    def __init__(
        self,
        *,
        token_budget: int = 16000,
        hot_set_size: int = 10,
        compact_when_over_pct: float = 0.8,
        client: LLMClient | None = None,
    ) -> None:
        if token_budget <= 0:
            raise ValueError("token_budget must be greater than 0")
        if hot_set_size < 0:
            raise ValueError("hot_set_size must be greater than or equal to 0")
        if not 0 < compact_when_over_pct <= 1:
            raise ValueError("compact_when_over_pct must be between 0 and 1")

        self.token_budget = token_budget
        self.hot_set_size = hot_set_size
        self.compact_when_over_pct = compact_when_over_pct
        self.client = client
        self.logger = structlog.get_logger(__name__).bind(component="context_compactor")

    async def compact(
        self,
        evidence: list[Evidence],
        query: str,
    ) -> tuple[list[Evidence], EvidenceDigest | None]:
        """Return a hot evidence tail and an optional digest for the evicted slice."""

        if not evidence:
            return [], None

        total_tokens = sum(self._count_tokens(item) for item in evidence)
        threshold = self.token_budget * self.compact_when_over_pct
        if total_tokens < threshold:
            return evidence, None

        hot, cold = self._split_evidence(evidence)
        if not cold:
            self.logger.debug(
                "compaction_skipped_no_cold_evidence",
                total_tokens=total_tokens,
                budget=self.token_budget,
                hot_set_size=self.hot_set_size,
            )
            return evidence, None

        cold_tokens = sum(self._count_tokens(item) for item in cold)
        self.logger.info(
            "compaction_triggered",
            total_tokens=total_tokens,
            budget=self.token_budget,
            cold_count=len(cold),
        )

        prompt = self._build_prompt(query, cold)
        try:
            client = self.client or LLMClient()
            llm_digest = await client.complete(prompt, EvidenceDigest)
        except Exception as exc:
            self.logger.warning("compaction_skipped_llm_error", error=str(exc))
            return evidence, None

        digest = self._finalize_digest(llm_digest, cold, cold_tokens)
        self.logger.info(
            "compaction_completed",
            key_findings_count=len(digest.key_findings),
            before_tokens=digest.token_count_before,
            after_tokens=digest.token_count_after,
        )
        return hot, digest

    def _count_tokens(self, evidence: Evidence) -> int:
        return estimate_tokens(self._serialize_evidence_for_count(evidence))

    def _build_prompt(self, query: str, cold_evidence: list[Evidence]) -> str:
        return EVIDENCE_COMPACTION_PROMPT.format(
            query=query,
            cold_evidence_context=self._format_cold_evidence(cold_evidence),
        )

    def _split_evidence(self, evidence: list[Evidence]) -> tuple[list[Evidence], list[Evidence]]:
        if self.hot_set_size == 0:
            return [], list(evidence)
        return list(evidence[-self.hot_set_size :]), list(evidence[: -self.hot_set_size])

    def _finalize_digest(
        self,
        llm_digest: EvidenceDigest,
        cold_evidence: list[Evidence],
        cold_tokens: int,
    ) -> EvidenceDigest:
        digest = llm_digest.model_copy(
            update={
                "source_urls": self._collect_source_urls(cold_evidence),
                "evidence_count": len(cold_evidence),
                "token_count_before": cold_tokens,
            }
        )
        token_count_after = estimate_tokens(self._render_digest_for_count(digest))
        return digest.model_copy(update={"token_count_after": token_count_after})

    def _serialize_evidence_for_count(self, evidence: Evidence) -> str:
        parts = [
            (evidence.title or "").strip(),
            (evidence.snippet or "").strip(),
            (evidence.content or "").strip(),
        ]
        return "\n".join(part for part in parts if part)

    def _format_cold_evidence(self, evidence: list[Evidence]) -> str:
        if not evidence:
            return "- No cold evidence"

        formatted: list[str] = []
        for index, item in enumerate(evidence, start=1):
            snippet = self._trim_text(item.snippet)
            content = self._trim_text(item.content)
            lines = [
                f"[{index}] {item.title}",
                f"URL: {item.url}",
                f"Snippet: {snippet or '(none)'}",
                f"Content: {content or '(none)'}",
            ]
            formatted.append("\n".join(lines))
        return "\n\n".join(formatted)

    def _collect_source_urls(self, evidence: list[Evidence]) -> list[str]:
        seen: set[str] = set()
        urls: list[str] = []
        for item in evidence:
            if item.url in seen:
                continue
            seen.add(item.url)
            urls.append(item.url)
        return urls

    def _render_digest_for_count(self, digest: EvidenceDigest) -> str:
        lines = [f"Topic: {digest.topic}", "Key findings:"]
        lines.extend(f"- {finding}" for finding in digest.key_findings)
        lines.append("Source URLs:")
        lines.extend(f"- {url}" for url in digest.source_urls)
        return "\n".join(lines)

    def _trim_text(self, text: str | None) -> str:
        if not text:
            return ""
        if len(text) <= _MAX_EVIDENCE_FIELD_CHARS:
            return text
        return f"{text[:_MAX_EVIDENCE_FIELD_CHARS].rstrip()}..."
