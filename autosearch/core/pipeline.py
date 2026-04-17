# Self-written, plan v2.3 § 2
import asyncio
import re
import uuid

import structlog

from autosearch.channels.base import Channel
from autosearch.core.clarify import Clarifier
from autosearch.core.evidence import EvidenceProcessor
from autosearch.core.iteration import IterationBudget, IterationController
from autosearch.core.knowledge import KnowledgeRecaller
from autosearch.core.models import (
    ClarifyRequest,
    Evidence,
    Gap,
    GradeOutcome,
    PipelineResult,
    SearchMode,
    Section,
    SubQuery,
)
from autosearch.core.strategy import QueryStrategist
from autosearch.llm.client import LLMClient
from autosearch.observability.cost import CostTracker
from autosearch.persistence.session_store import SessionStore
from autosearch.quality.gate import QualityGate
from autosearch.synthesis.report import ReportSynthesizer

_SECTION_HEADING_RE = re.compile(r"^##\s+(.+?)\s*$")
_INLINE_CITATION_RE = re.compile(r"\[(\d+)\]")


class Pipeline:
    def __init__(
        self,
        llm: LLMClient | None = None,
        channels: list[Channel] | None = None,
        budget: IterationBudget = IterationBudget(),
        top_k_evidence: int = 20,
        cost_tracker: CostTracker | None = None,
        session_store: SessionStore | None = None,
    ) -> None:
        self.llm = llm or LLMClient(cost_tracker=cost_tracker)
        if cost_tracker is not None:
            self.llm.cost_tracker = cost_tracker
        self.cost_tracker = self.llm.cost_tracker
        self.channels = list(channels or [])
        self.budget = budget
        self.top_k_evidence = top_k_evidence
        self.session_store = session_store
        self.knowledge_recaller = KnowledgeRecaller()
        self.clarifier = Clarifier()
        self.query_strategist = QueryStrategist()
        self.evidence_processor = EvidenceProcessor()
        self.report_synthesizer = ReportSynthesizer()
        self.quality_gate = QualityGate()
        self.logger = structlog.get_logger(__name__).bind(component="pipeline")

    async def run(
        self,
        query: str,
        mode_hint: SearchMode | None = None,
    ) -> PipelineResult:
        iteration_controller = _TrackingIterationController(
            evidence_processor=self.evidence_processor,
            session_store=self.session_store,
            session_id=_new_session_id() if self.session_store is not None else None,
        )
        session_id = iteration_controller.session_id
        session_created = False
        session_mode = mode_hint.value if mode_hint is not None else None
        final_status = "error"
        final_markdown: str | None = None

        try:
            self.logger.info("pipeline_phase_started", phase="m0_recall", query=query)
            recall = await self.knowledge_recaller.recall(query, self.llm)
            self.logger.info(
                "pipeline_phase_completed",
                phase="m0_recall",
                known_facts=len(recall.known_facts),
                gaps=len(recall.gaps),
            )

            self.logger.info(
                "pipeline_phase_started",
                phase="m1_clarify",
                mode_hint=mode_hint.value if mode_hint is not None else None,
            )
            clarification = await self.clarifier.clarify(
                ClarifyRequest(query=query, mode_hint=mode_hint),
                self.llm,
            )
            self.logger.info(
                "pipeline_phase_completed",
                phase="m1_clarify",
                need_clarification=clarification.need_clarification,
                rubrics=len(clarification.rubrics),
                mode=clarification.mode.value,
            )

            session_mode = clarification.mode.value
            await self._ensure_session_created(
                session_id=session_id,
                query=query,
                mode=session_mode,
                session_created=session_created,
            )
            session_created = True

            if clarification.need_clarification:
                final_status = "needs_clarification"
                self.logger.info("pipeline_run_completed", status=final_status)
                return PipelineResult(
                    status=final_status,
                    clarification=clarification,
                    iterations=0,
                    session_id=session_id,
                    cost=self._current_cost(),
                )

            self.logger.info(
                "pipeline_phase_started",
                phase="m2_strategy",
                requested_subqueries=_initial_subquery_count(clarification.mode),
            )
            initial_queries = await self.query_strategist.generate_subqueries(
                clarify=clarification,
                recall=recall,
                client=self.llm,
                n=_initial_subquery_count(clarification.mode),
            )
            self.logger.info(
                "pipeline_phase_completed",
                phase="m2_strategy",
                subqueries=len(initial_queries),
            )

            self.logger.info(
                "pipeline_phase_started",
                phase="m3_iteration",
                subqueries=len(initial_queries),
                channels=len(self.channels),
                max_iterations=self.budget.max_iterations,
            )
            evidences = await iteration_controller.run(
                query=query,
                initial_queries=initial_queries,
                channels=self.channels,
                budget=self.budget,
                client=self.llm,
            )
            self.logger.info(
                "pipeline_phase_completed",
                phase="m3_iteration",
                evidences=len(evidences),
                iterations=iteration_controller.iterations_executed,
            )

            self.logger.info(
                "pipeline_phase_started",
                phase="m5_evidence_processing",
                evidences=len(evidences),
                top_k=self.top_k_evidence,
            )
            processed_evidences = self._finalize_evidences(evidences, query)
            self.logger.info(
                "pipeline_phase_completed",
                phase="m5_evidence_processing",
                evidences=len(processed_evidences),
            )

            self.logger.info(
                "pipeline_phase_started",
                phase="m7_synthesis",
                evidences=len(processed_evidences),
            )
            markdown = await self.report_synthesizer.synthesize(
                query=query,
                evidences=processed_evidences,
                rubrics=clarification.rubrics,
                client=self.llm,
            )
            self.logger.info(
                "pipeline_phase_completed",
                phase="m7_synthesis",
                markdown_chars=len(markdown),
            )

            first_section = _extract_first_section(markdown)
            self.logger.info(
                "pipeline_phase_started",
                phase="m8_quality_gate",
                section_heading=first_section.heading,
            )
            quality = await self.quality_gate.evaluate(
                section=first_section,
                rubrics=clarification.rubrics,
                evidences=processed_evidences,
                client=self.llm,
            )
            self.logger.info(
                "pipeline_phase_completed",
                phase="m8_quality_gate",
                grade=quality.grade.value,
                follow_up_gaps=len(quality.follow_up_gaps),
            )

            if quality.grade is GradeOutcome.FAIL:
                retry_queries = _subqueries_from_gaps(quality.follow_up_gaps)
                if retry_queries:
                    retry_budget = IterationBudget(
                        max_iterations=1,
                        per_channel_rate_limit=self.budget.per_channel_rate_limit,
                    )
                    self.logger.info(
                        "pipeline_quality_retry_started",
                        retry_subqueries=len(retry_queries),
                    )
                    retry_evidences = await iteration_controller.run(
                        query=query,
                        initial_queries=retry_queries,
                        channels=self.channels,
                        budget=retry_budget,
                        client=self.llm,
                    )
                    processed_evidences = self._finalize_evidences(
                        processed_evidences + retry_evidences,
                        query,
                    )
                    markdown = await self.report_synthesizer.synthesize(
                        query=query,
                        evidences=processed_evidences,
                        rubrics=clarification.rubrics,
                        client=self.llm,
                    )
                    self.logger.info(
                        "pipeline_quality_retry_completed",
                        retry_evidences=len(retry_evidences),
                        total_evidences=len(processed_evidences),
                        markdown_chars=len(markdown),
                    )

            await self._record_final_evidences(session_id, processed_evidences)
            final_markdown = markdown
            final_status = "ok"
            self.logger.info(
                "pipeline_run_completed",
                status=final_status,
                evidences=len(processed_evidences),
                iterations=iteration_controller.iterations_executed,
            )
            return PipelineResult(
                status=final_status,
                clarification=clarification,
                markdown=markdown,
                evidences=processed_evidences,
                quality=quality,
                iterations=iteration_controller.iterations_executed,
                session_id=session_id,
                cost=self._current_cost(),
            )
        finally:
            if session_id is not None:
                if not session_created:
                    fallback_mode = session_mode or _fallback_session_mode(mode_hint)
                    await self._ensure_session_created(
                        session_id=session_id,
                        query=query,
                        mode=fallback_mode,
                        session_created=False,
                    )
                await self._finish_session(
                    session_id=session_id,
                    status=final_status,
                    markdown=final_markdown,
                )

    def _finalize_evidences(self, evidences: list[Evidence], query: str) -> list[Evidence]:
        deduped = self.evidence_processor.dedup_urls(evidences)
        deduped = self.evidence_processor.dedup_simhash(deduped)
        return self.evidence_processor.rerank_bm25(
            deduped,
            query,
            top_k=self.top_k_evidence,
        )

    async def _ensure_session_created(
        self,
        session_id: str | None,
        query: str,
        mode: str,
        session_created: bool,
    ) -> None:
        if self.session_store is None or session_id is None or session_created:
            return
        await self.session_store.create_session(session_id, query, mode)

    async def _record_final_evidences(
        self,
        session_id: str | None,
        evidences: list[Evidence],
    ) -> None:
        if self.session_store is None or session_id is None:
            return
        for rank, evidence in enumerate(evidences, start=1):
            await self.session_store.add_evidence(session_id, rank, evidence)

    async def _finish_session(
        self,
        session_id: str,
        status: str,
        markdown: str | None,
    ) -> None:
        if self.session_store is None:
            return
        await self.session_store.finish_session(
            session_id=session_id,
            status=status,
            markdown=markdown,
            cost=self._current_cost(),
        )

    def _current_cost(self) -> float:
        if self.cost_tracker is None:
            return 0.0
        return self.cost_tracker.total()


class _TrackingIterationController(IterationController):
    def __init__(
        self,
        evidence_processor: EvidenceProcessor,
        session_store: SessionStore | None = None,
        session_id: str | None = None,
    ) -> None:
        super().__init__(evidence_processor=evidence_processor)
        self.iterations_executed = 0
        self.session_store = session_store
        self.session_id = session_id

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
            result_count = 0
            if isinstance(result, Exception):
                self.logger.warning(
                    "channel_search_failed",
                    iteration=iteration,
                    channel=channel_name,
                    subquery=query_text,
                    error=str(result),
                )
            else:
                result_count = len(result)
                evidences.extend(result)

            if self.session_store is not None and self.session_id is not None:
                await self.session_store.add_query_log(
                    self.session_id,
                    query_text,
                    channel_name,
                    result_count,
                )

        return evidences

    async def _reflect(
        self,
        query: str,
        iteration: int,
        max_iterations: int,
        subqueries: list[SubQuery],
        evidences: list[Evidence],
        client: LLMClient,
    ) -> list[Gap]:
        self.iterations_executed += 1
        return await super()._reflect(
            query=query,
            iteration=iteration,
            max_iterations=max_iterations,
            subqueries=subqueries,
            evidences=evidences,
            client=client,
        )


def _initial_subquery_count(mode: SearchMode) -> int:
    if mode is SearchMode.FAST:
        return 3
    return 5


def _fallback_session_mode(mode_hint: SearchMode | None) -> str:
    if mode_hint is not None:
        return mode_hint.value
    return "unknown"


def _new_session_id() -> str:
    return uuid.uuid4().hex[:12]


def _subqueries_from_gaps(gaps: list[Gap]) -> list[SubQuery]:
    seen: set[str] = set()
    subqueries: list[SubQuery] = []
    for gap in gaps:
        text = gap.topic.strip()
        key = text.casefold()
        if not text or key in seen:
            continue
        seen.add(key)
        subqueries.append(SubQuery(text=text, rationale=gap.reason.strip() or text))
    return subqueries


def _extract_first_section(markdown: str) -> Section:
    heading: str | None = None
    content_lines: list[str] = []

    for line in markdown.splitlines():
        heading_match = _SECTION_HEADING_RE.match(line)
        if heading_match is None:
            if heading is not None:
                content_lines.append(line)
            continue

        candidate_heading = heading_match.group(1).strip()
        if heading is None and candidate_heading not in {"References", "Sources"}:
            heading = candidate_heading
            continue
        if heading is not None:
            break

    if heading is None:
        content = markdown.strip()
        return Section(
            heading="Overview",
            content=content,
            ref_ids=_extract_ref_ids(content),
        )

    content = "\n".join(content_lines).strip()
    return Section(
        heading=heading,
        content=content,
        ref_ids=_extract_ref_ids(content),
    )


def _extract_ref_ids(content: str) -> list[int]:
    seen: set[int] = set()
    ref_ids: list[int] = []
    for match in _INLINE_CITATION_RE.finditer(content):
        ref_id = int(match.group(1))
        if ref_id in seen:
            continue
        seen.add(ref_id)
        ref_ids.append(ref_id)
    return ref_ids
