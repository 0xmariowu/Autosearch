# Source: open_deep_research/src/legacy/graph.py:L235-L354 (adapted)
import asyncio
from dataclasses import dataclass

import structlog
from pydantic import BaseModel, Field

from autosearch.channels.base import Channel
from autosearch.core.context_compaction import ContextCompactor
from autosearch.core.evidence import EvidenceProcessor
from autosearch.core.models import Evidence, Gap, SubQuery
from autosearch.llm.client import LLMClient
from autosearch.persistence.session_store import SessionStore
from autosearch.skills.prompts import load_prompt

GAP_REFLECTION_PROMPT = load_prompt("m3_gap_reflection")
GAP_REFLECTION_PERSPECTIVE_PROMPT = load_prompt("m3_gap_reflection_perspective")
PERSPECTIVE_LABELS_PROMPT = load_prompt("m3_perspective_labels")
SEARCH_REFLECTION_PROMPT = load_prompt("m3_search_reflection")
FOLLOW_UP_QUERY_PROMPT = load_prompt("m3_follow_up_query")
FALLBACK_THRESHOLD = 5
SUBQUERY_BATCH_SIZE = 3
logger = structlog.get_logger(__name__)


@dataclass(frozen=True)
class IterationBudget:
    max_iterations: int = 5
    per_channel_rate_limit: float = 0.5
    subquery_batch_size: int = SUBQUERY_BATCH_SIZE
    context_token_budget: int = 16000
    compact_hot_set_size: int = 10
    compact_trigger_pct: float = 0.8
    num_perspectives: int = 0


class _GapReflectionResponse(BaseModel):
    gaps: list[Gap] = Field(default_factory=list)


class _PerspectiveResponse(BaseModel):
    labels: list[str] = Field(default_factory=list)


class _FollowUpQueryResponse(BaseModel):
    subqueries: list[SubQuery] = Field(default_factory=list)


async def generate_perspectives(
    query: str,
    client: LLMClient,
    *,
    num_perspectives: int = 3,
) -> list[str]:
    """Generate short perspective labels from the query alone."""

    requested_count = num_perspectives
    if requested_count > 3:
        logger.warning(
            "num_perspectives_clamped",
            requested=requested_count,
            actual=3,
        )
    requested_count = max(1, min(requested_count, 3))
    prompt = PERSPECTIVE_LABELS_PROMPT.format(
        query=query,
        num_perspectives=requested_count,
    )
    try:
        response = await client.complete(prompt, _PerspectiveResponse)
    except Exception:
        return ["default"]

    labels = _clean_perspective_labels(response.labels, limit=requested_count)
    return labels or ["default"]


class IterationController:
    def __init__(
        self,
        evidence_processor: EvidenceProcessor | None = None,
        *,
        store: SessionStore | None = None,
        session_id: str | None = None,
    ) -> None:
        self.evidence_processor = evidence_processor or EvidenceProcessor()
        self.routing_trace: dict[str, object] = {}
        self.logger = structlog.get_logger(__name__).bind(component="iteration_controller")
        self._empty_counts: dict[str, int] = {}
        self._store = store
        self._session_id = session_id

    async def run(
        self,
        query: str,
        initial_queries: list[SubQuery],
        channels: list[Channel],
        budget: IterationBudget,
        client: LLMClient,
        priority_channels: set[str] | None = None,
        skip_channels: set[str] | None = None,
    ) -> tuple[list[Evidence], list[dict[str, object]]]:
        self._empty_counts = {}
        effective_priority = set(priority_channels or [])
        effective_skip = set(skip_channels or [])
        self.routing_trace = _initial_routing_trace(
            channels,
            priority_channels=effective_priority,
            skip_channels=effective_skip,
        )
        research_trace: list[dict[str, object]] = []
        if budget.max_iterations <= 0 or not initial_queries or not channels:
            return [], research_trace

        active_queries = _dedup_subqueries(initial_queries)
        perspectives = ["default"]
        if budget.num_perspectives >= 2:
            perspectives = await generate_perspectives(
                query,
                client,
                num_perspectives=budget.num_perspectives,
            )
        multi_perspective = budget.num_perspectives >= 2 and len(perspectives) >= 2
        perspective_mode = "multi" if multi_perspective else "single"
        active_perspective_count = len(perspectives) if multi_perspective else 1
        accumulated_evidence: list[Evidence] = []
        compactor = ContextCompactor(
            token_budget=budget.context_token_budget,
            hot_set_size=budget.compact_hot_set_size,
            compact_when_over_pct=budget.compact_trigger_pct,
            client=client,
            store=self._store if self._store is not None and self._session_id is not None else None,
            session_id=self._session_id
            if self._store is not None and self._session_id is not None
            else None,
        )
        batch_size = max(1, budget.subquery_batch_size)

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

            collected_batch_gaps: list[Gap] = []
            subquery_batches = _partition_subqueries(active_queries, batch_size)
            round_evidence_count = 0
            self.logger.info(
                "iteration_phase_started",
                phase="search",
                iteration=iteration,
                channels=len(channels),
                subqueries=len(active_queries),
                batches=len(subquery_batches),
            )
            # When an iteration collapses to one batch, the aggregate reflection already sees the
            # same evidence, so skip the narrower reflection call to avoid duplicate LLM work.
            run_batch_reflection = len(subquery_batches) > 1
            for batch_index, batch_subqueries in enumerate(subquery_batches, start=1):
                self.logger.info(
                    "iteration_batch_started",
                    iteration=iteration,
                    batch_index=batch_index,
                    subqueries=len(batch_subqueries),
                    channels=len(channels),
                )
                batch_evidence = await self._search(
                    batch_subqueries,
                    channels,
                    iteration,
                    priority_channels=effective_priority,
                    skip_channels=effective_skip,
                )
                round_evidence_count += len(batch_evidence)
                accumulated_evidence = self._dedup_accumulated_evidence(
                    accumulated_evidence + batch_evidence
                )
                batch_gaps: list[Gap] = []
                if run_batch_reflection:
                    if multi_perspective:
                        batch_gaps = _dedup_gaps(
                            [
                                gap
                                for gaps in (
                                    await self._per_search_reflect_multi_perspective(
                                        batch_evidence=batch_evidence,
                                        query=query,
                                        client=client,
                                        batch_subqueries=batch_subqueries,
                                        perspectives=perspectives,
                                    )
                                ).values()
                                for gap in gaps
                            ]
                        )
                    else:
                        batch_gaps = await self._per_search_reflect(
                            batch_evidence=batch_evidence,
                            query=query,
                            client=client,
                            batch_subqueries=batch_subqueries,
                        )
                    collected_batch_gaps.extend(batch_gaps)

                digest_id: int | str | None = None
                hot, digest = await compactor.compact(accumulated_evidence, query)
                if digest is not None:
                    accumulated_evidence = hot
                    digest_id = (
                        compactor.last_digest_artifact_id
                        if compactor.last_digest_artifact_id is not None
                        else digest.compressed_at.isoformat()
                    )

                research_trace.append(
                    {
                        "iteration": iteration,
                        "batch_index": batch_index,
                        "subqueries": [subquery.text for subquery in batch_subqueries],
                        "gaps": [gap.model_dump(mode="json") for gap in batch_gaps],
                        "digest_id_if_any": digest_id,
                    }
                )
                if multi_perspective:
                    research_trace[-1]["perspective"] = list(perspectives)
                self.logger.info(
                    "iteration_batch_completed",
                    iteration=iteration,
                    batch_index=batch_index,
                    evidences=len(batch_evidence),
                    accumulated=len(accumulated_evidence),
                    gaps=len(batch_gaps),
                    compacted=digest is not None,
                    perspective_mode=perspective_mode,
                    num_perspectives=active_perspective_count,
                )
            self.logger.info(
                "iteration_phase_completed",
                phase="search",
                iteration=iteration,
                evidences=round_evidence_count,
            )

            self.logger.info(
                "iteration_phase_started",
                phase="summarize",
                iteration=iteration,
                accumulated_before=len(accumulated_evidence),
            )
            accumulated_evidence = self._summarize(accumulated_evidence, query)
            self.logger.info(
                "iteration_phase_completed",
                phase="summarize",
                iteration=iteration,
                accumulated_after=len(accumulated_evidence),
            )

            self.logger.info("iteration_phase_started", phase="reflect", iteration=iteration)
            if multi_perspective:
                gaps = _dedup_gaps(
                    [
                        gap
                        for gaps in (
                            await self._reflect_multi_perspective(
                                query=query,
                                iteration=iteration,
                                max_iterations=budget.max_iterations,
                                subqueries=active_queries,
                                evidences=accumulated_evidence,
                                perspectives=perspectives,
                                client=client,
                            )
                        ).values()
                        for gap in gaps
                    ]
                )
            else:
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
                perspective_mode=perspective_mode,
                num_perspectives=active_perspective_count,
            )

            all_gaps = _dedup_gaps(gaps + collected_batch_gaps)

            if iteration >= budget.max_iterations or not all_gaps:
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
                gaps=all_gaps,
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

        return accumulated_evidence, research_trace

    def empty_counts_by_channel(self) -> dict[str, int]:
        return dict(self._empty_counts)

    async def _search(
        self,
        subqueries: list[SubQuery],
        channels: list[Channel],
        iteration: int,
        priority_channels: set[str] | None = None,
        skip_channels: set[str] | None = None,
    ) -> list[Evidence]:
        effective_priority = set(priority_channels or [])
        effective_skip = set(skip_channels or [])
        self._ensure_routing_trace(
            channels,
            priority_channels=effective_priority,
            skip_channels=effective_skip,
        )

        runnable_channels = [channel for channel in channels if channel.name not in effective_skip]
        skipped_names = [channel.name for channel in channels if channel.name in effective_skip]
        _extend_unique_names(self.routing_trace, "skipped_channels", skipped_names)

        if not effective_priority:
            rest_names = [channel.name for channel in runnable_channels]
            _extend_unique_names(self.routing_trace, "rest_ran", rest_names)
            return await self._run_channel_batch(subqueries, runnable_channels, iteration)

        priority_batch = [
            channel for channel in runnable_channels if channel.name in effective_priority
        ]
        rest_batch = [
            channel for channel in runnable_channels if channel.name not in effective_priority
        ]

        priority_names = [channel.name for channel in priority_batch]
        _extend_unique_names(self.routing_trace, "priority_ran", priority_names)
        priority_evidence = await self._run_channel_batch(subqueries, priority_batch, iteration)
        self.routing_trace["priority_evidence_count"] = int(
            self.routing_trace.get("priority_evidence_count", 0)
        ) + len(priority_evidence)

        if len(priority_evidence) >= FALLBACK_THRESHOLD or not rest_batch:
            return priority_evidence

        self.routing_trace["fallback_triggered"] = True
        rest_names = [channel.name for channel in rest_batch]
        _extend_unique_names(self.routing_trace, "rest_ran", rest_names)
        rest_evidence = await self._run_channel_batch(subqueries, rest_batch, iteration)
        return priority_evidence + rest_evidence

    async def _run_channel_batch(
        self,
        subqueries: list[SubQuery],
        channels: list[Channel],
        iteration: int,
    ) -> list[Evidence]:
        if not subqueries or not channels:
            return []

        tasks = [channel.search(subquery) for subquery in subqueries for channel in channels]
        task_metadata = [
            (channel.name, subquery.text) for subquery in subqueries for channel in channels
        ]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        evidences: list[Evidence] = []
        for (channel_name, query_text), result in zip(task_metadata, results, strict=True):
            evidences.extend(
                await self._handle_search_result(
                    channel_name=channel_name,
                    query_text=query_text,
                    result=result,
                    iteration=iteration,
                )
            )

        return evidences

    async def _handle_search_result(
        self,
        *,
        channel_name: str,
        query_text: str,
        result: list[Evidence] | Exception,
        iteration: int,
    ) -> list[Evidence]:
        if isinstance(result, Exception):
            self.logger.warning(
                "channel_search_failed",
                iteration=iteration,
                channel=channel_name,
                subquery=query_text,
                error=str(result),
            )
            return []
        if result == []:
            self._empty_counts[channel_name] = self._empty_counts.get(channel_name, 0) + 1
            self.logger.warning(
                "channel_empty_result",
                channel=channel_name,
                subquery=query_text[:80],
            )
        return result

    def _ensure_routing_trace(
        self,
        channels: list[Channel],
        *,
        priority_channels: set[str],
        skip_channels: set[str],
    ) -> None:
        expected_priority = _ordered_channel_names(
            channels,
            include=priority_channels,
            exclude=skip_channels,
        )
        expected_skip = _ordered_channel_names(channels, include=skip_channels)

        if (
            self.routing_trace.get("priority") == expected_priority
            and self.routing_trace.get("skip") == expected_skip
        ):
            return

        self.routing_trace = _initial_routing_trace(
            channels,
            priority_channels=priority_channels,
            skip_channels=skip_channels,
        )

    def _summarize(self, evidences: list[Evidence], query: str) -> list[Evidence]:
        deduped = self._dedup_accumulated_evidence(evidences)
        return self.evidence_processor.rerank_bm25(deduped, query, top_k=len(deduped))

    def _dedup_accumulated_evidence(self, evidences: list[Evidence]) -> list[Evidence]:
        deduped = self.evidence_processor.dedup_urls(evidences)
        return self.evidence_processor.dedup_simhash(deduped)

    async def _reflect(
        self,
        query: str,
        iteration: int,
        max_iterations: int,
        subqueries: list[SubQuery],
        evidences: list[Evidence],
        client: LLMClient,
    ) -> list[Gap]:
        return await self._reflect_for_perspective(
            query=query,
            iteration=iteration,
            max_iterations=max_iterations,
            subqueries=subqueries,
            evidences=evidences,
            perspective=None,
            client=client,
        )

    async def _reflect_multi_perspective(
        self,
        *,
        query: str,
        iteration: int,
        max_iterations: int,
        subqueries: list[SubQuery],
        evidences: list[Evidence],
        perspectives: list[str],
        client: LLMClient,
    ) -> dict[str, list[Gap]]:
        results = await asyncio.gather(
            *[
                self._reflect_for_perspective(
                    query=query,
                    iteration=iteration,
                    max_iterations=max_iterations,
                    subqueries=subqueries,
                    evidences=evidences,
                    perspective=perspective,
                    client=client,
                )
                for perspective in perspectives
            ]
        )
        return dict(zip(perspectives, results, strict=True))

    async def _reflect_for_perspective(
        self,
        *,
        query: str,
        iteration: int,
        max_iterations: int,
        subqueries: list[SubQuery],
        evidences: list[Evidence],
        perspective: str | None,
        client: LLMClient,
    ) -> list[Gap]:
        prompt_template = (
            GAP_REFLECTION_PERSPECTIVE_PROMPT if perspective else GAP_REFLECTION_PROMPT
        )
        prompt = prompt_template.format(
            query=query,
            iteration=iteration,
            max_iterations=max_iterations,
            perspective=perspective or "",
            subqueries=_format_subqueries(subqueries),
            evidence_context=_format_evidence(evidences, max_items=12),
        )
        response = await client.complete(prompt, _GapReflectionResponse)
        return _dedup_gaps(response.gaps)

    async def _per_search_reflect(
        self,
        *,
        batch_evidence: list[Evidence],
        query: str,
        client: LLMClient,
        batch_subqueries: list[SubQuery] | None = None,
    ) -> list[Gap]:
        return await self._per_search_reflect_for_perspective(
            batch_evidence=batch_evidence,
            query=query,
            client=client,
            batch_subqueries=batch_subqueries,
            perspective=None,
        )

    async def _per_search_reflect_multi_perspective(
        self,
        *,
        batch_evidence: list[Evidence],
        query: str,
        client: LLMClient,
        batch_subqueries: list[SubQuery] | None = None,
        perspectives: list[str],
    ) -> dict[str, list[Gap]]:
        results = await asyncio.gather(
            *[
                self._per_search_reflect_for_perspective(
                    batch_evidence=batch_evidence,
                    query=query,
                    client=client,
                    batch_subqueries=batch_subqueries,
                    perspective=perspective,
                )
                for perspective in perspectives
            ]
        )
        return dict(zip(perspectives, results, strict=True))

    async def _per_search_reflect_for_perspective(
        self,
        *,
        batch_evidence: list[Evidence],
        query: str,
        client: LLMClient,
        batch_subqueries: list[SubQuery] | None = None,
        perspective: str | None,
    ) -> list[Gap]:
        prompt = SEARCH_REFLECTION_PROMPT.format(
            query=query,
            batch_subqueries=_format_subqueries(batch_subqueries or []),
            batch_evidence_context=_format_evidence(batch_evidence, max_items=6),
        )
        if perspective:
            prompt = _prepend_perspective_block(prompt, perspective)
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


def _partition_subqueries(subqueries: list[SubQuery], batch_size: int) -> list[list[SubQuery]]:
    if not subqueries:
        return []
    normalized_batch_size = max(1, batch_size)
    return [
        subqueries[index : index + normalized_batch_size]
        for index in range(0, len(subqueries), normalized_batch_size)
    ]


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


def _clean_perspective_labels(labels: list[str], *, limit: int) -> list[str]:
    seen: set[str] = set()
    cleaned: list[str] = []
    for label in labels:
        normalized = " ".join(label.strip().split())
        if not normalized or len(normalized) > 60:
            continue
        dedup_key = normalized.casefold()
        if dedup_key in seen:
            continue
        seen.add(dedup_key)
        cleaned.append(normalized)
        if len(cleaned) >= limit:
            break
    return cleaned


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


def _prepend_perspective_block(prompt: str, perspective: str) -> str:
    return f"<Perspective lens>\n{perspective}\n</Perspective lens>\n\n{prompt}"


def _initial_routing_trace(
    channels: list[Channel],
    *,
    priority_channels: set[str],
    skip_channels: set[str],
) -> dict[str, object]:
    skipped = _ordered_channel_names(channels, include=skip_channels)
    priority = _ordered_channel_names(
        channels,
        include=priority_channels,
        exclude=skip_channels,
    )
    return {
        "priority": priority,
        "skip": skipped,
        "priority_ran": [],
        "rest_ran": [],
        "priority_evidence_count": 0,
        "fallback_triggered": False,
        "skipped_channels": list(skipped),
    }


def _ordered_channel_names(
    channels: list[Channel],
    *,
    include: set[str],
    exclude: set[str] | None = None,
) -> list[str]:
    excluded = exclude or set()
    return [
        channel.name
        for channel in channels
        if channel.name in include and channel.name not in excluded
    ]


def _extend_unique_names(trace: dict[str, object], key: str, names: list[str]) -> None:
    existing = trace.get(key)
    if not isinstance(existing, list):
        existing = []
        trace[key] = existing

    seen = {name for name in existing if isinstance(name, str)}
    for name in names:
        if name in seen:
            continue
        existing.append(name)
        seen.add(name)
