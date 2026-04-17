# Self-written, plan v2.3 § 2
import re
from dataclasses import dataclass, field
from typing import Literal

import structlog

from autosearch.channels.base import Channel
from autosearch.core.clarify import Clarifier
from autosearch.core.evidence import EvidenceProcessor
from autosearch.core.iteration import IterationBudget, IterationController
from autosearch.core.knowledge import KnowledgeRecaller
from autosearch.core.models import (
    ClarifyRequest,
    ClarifyResult,
    EvaluationResult,
    Evidence,
    Gap,
    GradeOutcome,
    SearchMode,
    Section,
    SubQuery,
)
from autosearch.core.strategy import QueryStrategist
from autosearch.llm.client import LLMClient
from autosearch.quality.gate import QualityGate
from autosearch.synthesis.report import ReportSynthesizer

_SECTION_HEADING_RE = re.compile(r"^##\s+(.+?)\s*$")
_INLINE_CITATION_RE = re.compile(r"\[(\d+)\]")


@dataclass(frozen=True)
class PipelineResult:
    status: Literal["ok", "needs_clarification"]
    clarification: ClarifyResult
    markdown: str | None = None
    evidences: list[Evidence] = field(default_factory=list)
    quality: EvaluationResult | None = None
    iterations: int = 0


class Pipeline:
    def __init__(
        self,
        llm: LLMClient,
        channels: list[Channel],
        budget: IterationBudget = IterationBudget(),
        top_k_evidence: int = 20,
    ) -> None:
        self.llm = llm
        self.channels = channels
        self.budget = budget
        self.top_k_evidence = top_k_evidence
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
            evidence_processor=self.evidence_processor
        )

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

        if clarification.need_clarification:
            self.logger.info("pipeline_run_completed", status="needs_clarification")
            return PipelineResult(
                status="needs_clarification",
                clarification=clarification,
                iterations=0,
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

        self.logger.info(
            "pipeline_run_completed",
            status="ok",
            evidences=len(processed_evidences),
            iterations=iteration_controller.iterations_executed,
        )
        return PipelineResult(
            status="ok",
            clarification=clarification,
            markdown=markdown,
            evidences=processed_evidences,
            quality=quality,
            iterations=iteration_controller.iterations_executed,
        )

    def _finalize_evidences(self, evidences: list[Evidence], query: str) -> list[Evidence]:
        deduped = self.evidence_processor.dedup_urls(evidences)
        deduped = self.evidence_processor.dedup_simhash(deduped)
        return self.evidence_processor.rerank_bm25(
            deduped,
            query,
            top_k=self.top_k_evidence,
        )


class _TrackingIterationController(IterationController):
    def __init__(self, evidence_processor: EvidenceProcessor) -> None:
        super().__init__(evidence_processor=evidence_processor)
        self.iterations_executed = 0

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
