# Source: open_deep_research/src/legacy/graph.py:L235-L354 (adapted)
import asyncio
from dataclasses import dataclass

import structlog
from pydantic import BaseModel, Field

from autosearch.channels.base import Channel
from autosearch.core.evidence import EvidenceProcessor
from autosearch.core.models import Evidence, Gap, SubQuery
from autosearch.llm.client import LLMClient
from autosearch.skills.prompts import load_prompt

GAP_REFLECTION_PROMPT = load_prompt("m3_gap_reflection")
FOLLOW_UP_QUERY_PROMPT = load_prompt("m3_follow_up_query")


@dataclass(frozen=True)
class IterationBudget:
    max_iterations: int = 5
    per_channel_rate_limit: float = 0.5


class _GapReflectionResponse(BaseModel):
    gaps: list[Gap] = Field(default_factory=list)


class _FollowUpQueryResponse(BaseModel):
    subqueries: list[SubQuery] = Field(default_factory=list)


class IterationController:
    def __init__(self, evidence_processor: EvidenceProcessor | None = None) -> None:
        self.evidence_processor = evidence_processor or EvidenceProcessor()
        self.logger = structlog.get_logger(__name__).bind(component="iteration_controller")

    async def run(
        self,
        query: str,
        initial_queries: list[SubQuery],
        channels: list[Channel],
        budget: IterationBudget,
        client: LLMClient,
    ) -> list[Evidence]:
        if budget.max_iterations <= 0 or not initial_queries or not channels:
            return []

        active_queries = _dedup_subqueries(initial_queries)
        accumulated_evidence: list[Evidence] = []

        for iteration in range(1, budget.max_iterations + 1):
            if not active_queries:
                self.logger.info(
                    "iteration_phase_completed",
                    phase="route",
                    iteration=iteration,
                    decision="stop",
                    reason="no_active_queries",
                )
                break

            self.logger.info(
                "iteration_phase_started",
                phase="search",
                iteration=iteration,
                channels=len(channels),
                subqueries=len(active_queries),
            )
            round_evidence = await self._search(active_queries, channels, iteration)
            self.logger.info(
                "iteration_phase_completed",
                phase="search",
                iteration=iteration,
                evidences=len(round_evidence),
            )

            self.logger.info(
                "iteration_phase_started",
                phase="summarize",
                iteration=iteration,
                accumulated_before=len(accumulated_evidence),
            )
            accumulated_evidence = self._summarize(accumulated_evidence + round_evidence, query)
            self.logger.info(
                "iteration_phase_completed",
                phase="summarize",
                iteration=iteration,
                accumulated_after=len(accumulated_evidence),
            )

            self.logger.info("iteration_phase_started", phase="reflect", iteration=iteration)
            gaps = await self._reflect(
                query=query,
                iteration=iteration,
                max_iterations=budget.max_iterations,
                subqueries=active_queries,
                evidences=accumulated_evidence,
                client=client,
            )
            self.logger.info(
                "iteration_phase_completed",
                phase="reflect",
                iteration=iteration,
                gaps=len(gaps),
            )

            if iteration >= budget.max_iterations or not gaps:
                self.logger.info(
                    "iteration_phase_completed",
                    phase="route",
                    iteration=iteration,
                    decision="stop",
                    reason=(
                        "max_iterations_reached"
                        if iteration >= budget.max_iterations
                        else "no_remaining_gaps"
                    ),
                )
                break

            self.logger.info("iteration_phase_started", phase="followup", iteration=iteration)
            active_queries = await self._follow_up(
                query=query,
                gaps=gaps,
                evidences=accumulated_evidence,
                client=client,
            )
            self.logger.info(
                "iteration_phase_completed",
                phase="followup",
                iteration=iteration,
                subqueries=len(active_queries),
            )

            if not active_queries:
                self.logger.info(
                    "iteration_phase_completed",
                    phase="route",
                    iteration=iteration,
                    decision="stop",
                    reason="no_follow_up_queries",
                )
                break

            self.logger.info(
                "iteration_phase_completed",
                phase="route",
                iteration=iteration,
                decision="continue",
                next_iteration=iteration + 1,
            )

            if budget.per_channel_rate_limit > 0:
                await asyncio.sleep(budget.per_channel_rate_limit)

        return accumulated_evidence

    async def _search(
        self,
        subqueries: list[SubQuery],
        channels: list[Channel],
        iteration: int,
    ) -> list[Evidence]:
        tasks = [channel.search(subquery) for subquery in subqueries for channel in channels]
        task_metadata = [
            (channel.name, subquery.text) for subquery in subqueries for channel in channels
        ]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        evidences: list[Evidence] = []
        for (channel_name, query_text), result in zip(task_metadata, results, strict=True):
            if isinstance(result, Exception):
                self.logger.warning(
                    "channel_search_failed",
                    iteration=iteration,
                    channel=channel_name,
                    subquery=query_text,
                    error=str(result),
                )
                continue
            evidences.extend(result)

        return evidences

    def _summarize(self, evidences: list[Evidence], query: str) -> list[Evidence]:
        deduped = self.evidence_processor.dedup_urls(evidences)
        deduped = self.evidence_processor.dedup_simhash(deduped)
        return self.evidence_processor.rerank_bm25(deduped, query, top_k=len(deduped))

    async def _reflect(
        self,
        query: str,
        iteration: int,
        max_iterations: int,
        subqueries: list[SubQuery],
        evidences: list[Evidence],
        client: LLMClient,
    ) -> list[Gap]:
        prompt = GAP_REFLECTION_PROMPT.format(
            query=query,
            iteration=iteration,
            max_iterations=max_iterations,
            subqueries=_format_subqueries(subqueries),
            evidence_context=_format_evidence(evidences, max_items=12),
        )
        response = await client.complete(prompt, _GapReflectionResponse)
        return _dedup_gaps(response.gaps)

    async def _follow_up(
        self,
        query: str,
        gaps: list[Gap],
        evidences: list[Evidence],
        client: LLMClient,
    ) -> list[SubQuery]:
        prompt = FOLLOW_UP_QUERY_PROMPT.format(
            query=query,
            gap_context=_format_gaps(gaps),
            evidence_context=_format_evidence(evidences, max_items=8),
        )
        response = await client.complete(prompt, _FollowUpQueryResponse)
        return _dedup_subqueries(response.subqueries)


def _dedup_subqueries(subqueries: list[SubQuery]) -> list[SubQuery]:
    seen: set[str] = set()
    deduped: list[SubQuery] = []
    for subquery in subqueries:
        normalized = subquery.text.strip().casefold()
        if not normalized or normalized in seen:
            continue
        seen.add(normalized)
        deduped.append(subquery)
    return deduped


def _dedup_gaps(gaps: list[Gap]) -> list[Gap]:
    seen: set[tuple[str, str]] = set()
    deduped: list[Gap] = []
    for gap in gaps:
        normalized = (gap.topic.strip().casefold(), gap.reason.strip().casefold())
        if not normalized[0] or normalized in seen:
            continue
        seen.add(normalized)
        deduped.append(gap)
    return deduped


def _format_subqueries(subqueries: list[SubQuery]) -> str:
    if not subqueries:
        return "- None"
    return "\n".join(f"- {subquery.text} ({subquery.rationale})" for subquery in subqueries)


def _format_gaps(gaps: list[Gap]) -> str:
    if not gaps:
        return "- None"
    return "\n".join(f"- {gap.topic}: {gap.reason}" for gap in gaps)


def _format_evidence(evidences: list[Evidence], max_items: int) -> str:
    if not evidences:
        return "- No evidence collected yet"

    formatted: list[str] = []
    for index, evidence in enumerate(evidences[:max_items], start=1):
        body = (evidence.content or evidence.snippet or "").strip()
        excerpt = body[:400] if body else "(no summary available)"
        formatted.append(
            "\n".join(
                [
                    f"[{index}] {evidence.title}",
                    f"URL: {evidence.url}",
                    f"Channel: {evidence.source_channel}",
                    f"Excerpt: {excerpt}",
                ]
            )
        )

    if len(evidences) > max_items:
        formatted.append(f"... {len(evidences) - max_items} additional evidence items omitted")

    return "\n\n".join(formatted)
