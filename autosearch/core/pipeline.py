# Self-written, plan v2.3 § 2
from collections.abc import Awaitable, Callable
import asyncio
import re
import uuid
from typing import Any

import httpx
import structlog

from autosearch.channels.base import Channel
from autosearch.core.clarify import Clarifier
from autosearch.core.evidence import EvidenceProcessor
from autosearch.core.iteration import IterationBudget, IterationController
from autosearch.core.knowledge import KnowledgeRecaller
from autosearch.core.models import (
    ClarifyRequest,
    ClarifyResult,
    Evidence,
    Gap,
    GradeOutcome,
    PipelineResult,
    SearchMode,
    Section,
    SubQuery,
)
from autosearch.core.search_scope import SearchScope, filter_channels_by_scope
from autosearch.core.strategy import QueryStrategist
from autosearch.llm.client import AllProvidersFailedError, LLMClient
from autosearch.observability.cost import CostTracker
from autosearch.persistence.session_store import SessionStore
from autosearch.quality.gate import QualityGate
from autosearch.synthesis.report import ReportSynthesizer

_SECTION_HEADING_RE = re.compile(r"^##\s+(.+?)\s*$")
_INLINE_CITATION_RE = re.compile(r"\[(\d+)\]")
type PipelineEvent = dict[str, Any]
type PipelineEventCallback = Callable[[PipelineEvent], Awaitable[None] | None]


class Pipeline:
    def __init__(
        self,
        llm: LLMClient | None = None,
        channels: list[Channel] | None = None,
        budget: IterationBudget = IterationBudget(),
        top_k_evidence: int = 20,
        cost_tracker: CostTracker | None = None,
        session_store: SessionStore | None = None,
        on_event: PipelineEventCallback | None = None,
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
        self.on_event = on_event
        self._captured_reasoning_events: list[PipelineEvent] | None = None
        self.logger = structlog.get_logger(__name__).bind(component="pipeline")

    async def run(
        self,
        query: str,
        mode_hint: SearchMode | None = None,
        *,
        scope: SearchScope | None = None,
    ) -> PipelineResult:
        self._captured_reasoning_events = []
        iteration_controller = _TrackingIterationController(
            evidence_processor=self.evidence_processor,
            session_store=self.session_store,
            session_id=_new_session_id() if self.session_store is not None else None,
            on_event=self._emit_event,
        )
        session_id = iteration_controller.session_id
        session_created = False
        session_mode = mode_hint.value if mode_hint is not None else None
        final_status = "error"
        final_markdown: str | None = None
        current_phase = "M0"
        research_trace: list[dict[str, object]] = []

        try:
            active_channels = self.channels
            if scope is not None:
                scoped_channels = filter_channels_by_scope(self.channels, scope.channel_scope)
                if not scoped_channels:
                    self.logger.warning(
                        "channel_scope_filter_empty",
                        channel_scope=scope.channel_scope,
                        original_count=len(self.channels),
                    )
                else:
                    active_channels = scoped_channels

            await self._emit_phase_event(current_phase, "start")
            self.logger.info("pipeline_phase_started", phase="m0_recall", query=query)
            recall = await self.knowledge_recaller.recall(query, self.llm)
            self.logger.info(
                "pipeline_phase_completed",
                phase="m0_recall",
                known_facts=len(recall.known_facts),
                gaps=len(recall.gaps),
            )
            await self._emit_phase_event(current_phase, "complete")

            current_phase = "M1"
            await self._emit_phase_event(current_phase, "start")
            self.logger.info(
                "pipeline_phase_started",
                phase="m1_clarify",
                mode_hint=mode_hint.value if mode_hint is not None else None,
            )
            clarification = await self.clarifier.clarify(
                ClarifyRequest(query=query, mode_hint=mode_hint),
                self.llm,
                channels=active_channels,
            )
            self.logger.info(
                "pipeline_phase_completed",
                phase="m1_clarify",
                need_clarification=clarification.need_clarification,
                rubrics=len(clarification.rubrics),
                mode=clarification.mode.value,
            )
            await self._emit_phase_event(current_phase, "complete")
            await self._emit_event(
                {
                    "type": "rubrics",
                    "phase": current_phase,
                    "items": [rubric.text for rubric in clarification.rubrics],
                }
            )

            session_mode = clarification.mode.value
            await self._ensure_session_created(
                session_id=session_id,
                query=query,
                mode=session_mode,
                session_created=session_created,
            )
            session_created = True
            routing_trace = _build_routing_trace(clarification)

            if clarification.need_clarification:
                final_status = "needs_clarification"
                prompt_tokens, completion_tokens = self._current_token_usage()
                self.logger.info("pipeline_run_completed", status=final_status)
                return PipelineResult(
                    delivery_status=final_status,
                    clarification=clarification,
                    iterations=0,
                    reasoning_events=list(self._captured_reasoning_events or []),
                    research_trace=research_trace,
                    routing_trace=routing_trace,
                    session_id=session_id,
                    cost=self._current_cost(),
                    prompt_tokens=prompt_tokens,
                    completion_tokens=completion_tokens,
                )

            current_phase = "M2"
            await self._emit_phase_event(current_phase, "start")
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
            await self._emit_phase_event(current_phase, "complete")
            await self._emit_event(
                {
                    "type": "subqueries",
                    "phase": current_phase,
                    "items": [subquery.text for subquery in initial_queries],
                }
            )

            if scope is not None:
                await self._emit_event(
                    {
                        "type": "channels_filtered",
                        "scope": scope.channel_scope,
                        "before": len(self.channels),
                        "after": len(active_channels),
                    }
                )

            current_phase = "M3"
            await self._emit_phase_event(current_phase, "start")
            self.logger.info(
                "pipeline_phase_started",
                phase="m3_iteration",
                subqueries=len(initial_queries),
                channels=len(active_channels),
                max_iterations=self.budget.max_iterations,
            )
            evidences, research_trace = await iteration_controller.run(
                query=query,
                initial_queries=initial_queries,
                channels=active_channels,
                budget=self.budget,
                client=self.llm,
                priority_channels=set(clarification.channel_priority),
                skip_channels=set(clarification.channel_skip),
            )
            routing_trace = _build_routing_trace(clarification, iteration_controller.routing_trace)
            self.logger.info(
                "pipeline_phase_completed",
                phase="m3_iteration",
                evidences=len(evidences),
                iterations=iteration_controller.iterations_executed,
            )
            await self._emit_phase_event(current_phase, "complete")

            current_phase = "M5"
            await self._emit_phase_event(current_phase, "start")
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
            await self._emit_phase_event(current_phase, "complete")

            current_phase = "M7"
            await self._emit_phase_event(current_phase, "start")
            self.logger.info(
                "pipeline_phase_started",
                phase="m7_synthesis",
                evidences=len(processed_evidences),
            )
            report = await self.report_synthesizer.synthesize(
                query=query,
                evidences=processed_evidences,
                rubrics=clarification.rubrics,
                client=self.llm,
                research_trace=research_trace,
            )
            markdown = report.markdown
            self.logger.info(
                "pipeline_phase_completed",
                phase="m7_synthesis",
                markdown_chars=len(markdown),
            )
            await self._emit_phase_event(current_phase, "complete")

            first_section = _extract_first_section(markdown)
            current_phase = "M8"
            await self._emit_phase_event(current_phase, "start")
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
            await self._emit_phase_event(current_phase, "complete")
            await self._emit_event(
                {
                    "type": "quality",
                    "grade": quality.grade.value,
                    "follow_up_count": len(quality.follow_up_gaps),
                }
            )

            if quality.grade is GradeOutcome.FAIL:
                retry_queries = _subqueries_from_gaps(quality.follow_up_gaps)
                if retry_queries:
                    retry_budget = IterationBudget(
                        max_iterations=1,
                        per_channel_rate_limit=self.budget.per_channel_rate_limit,
                    )
                    current_phase = "M3"
                    await self._emit_phase_event(current_phase, "start")
                    self.logger.info(
                        "pipeline_quality_retry_started",
                        retry_subqueries=len(retry_queries),
                    )
                    retry_evidences, retry_research_trace = await iteration_controller.run(
                        query=query,
                        initial_queries=retry_queries,
                        channels=active_channels,
                        budget=retry_budget,
                        client=self.llm,
                        priority_channels=set(clarification.channel_priority),
                        skip_channels=set(clarification.channel_skip),
                    )
                    await self._emit_phase_event(current_phase, "complete")
                    research_trace.extend(retry_research_trace)
                    processed_evidences = self._finalize_evidences(
                        processed_evidences + retry_evidences,
                        query,
                    )
                    current_phase = "M7"
                    await self._emit_phase_event(current_phase, "start")
                    report = await self.report_synthesizer.synthesize(
                        query=query,
                        evidences=processed_evidences,
                        rubrics=clarification.rubrics,
                        client=self.llm,
                        research_trace=research_trace,
                    )
                    markdown = report.markdown
                    await self._emit_phase_event(current_phase, "complete")
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
            prompt_tokens, completion_tokens = self._current_token_usage()
            return PipelineResult(
                delivery_status=final_status,
                clarification=clarification,
                markdown=markdown,
                evidences=processed_evidences,
                channel_empty_calls=iteration_controller.empty_counts_by_channel(),
                reasoning_events=list(self._captured_reasoning_events or []),
                research_trace=research_trace,
                routing_trace=routing_trace,
                quality=quality,
                iterations=iteration_controller.iterations_executed,
                session_id=session_id,
                cost=self._current_cost(),
                prompt_tokens=prompt_tokens,
                completion_tokens=completion_tokens,
            )
        except Exception as exc:
            if _should_log_pipeline_traceback(exc):
                self.logger.exception(
                    "pipeline_run_failed",
                    phase=current_phase,
                    error=str(exc),
                )
            else:
                self.logger.warning(
                    "pipeline_run_failed",
                    phase=current_phase,
                    error=str(exc),
                )
            await self._emit_event(
                {
                    "type": "error",
                    "phase": current_phase,
                    "message": str(exc),
                }
            )
            raise
        finally:
            self._captured_reasoning_events = None
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

    def _current_token_usage(self) -> tuple[int, int]:
        if self.cost_tracker is None:
            return 0, 0

        prompt_tokens = 0
        completion_tokens = 0
        for model_totals in self.cost_tracker.breakdown().values():
            prompt_tokens += int(model_totals.get("input_tokens", 0))
            completion_tokens += int(model_totals.get("output_tokens", 0))
        return prompt_tokens, completion_tokens

    async def _emit_phase_event(self, phase: str, status: str) -> None:
        await self._emit_event(
            {
                "type": "phase",
                "phase": phase,
                "status": status,
            }
        )

    async def _emit_event(self, event: PipelineEvent) -> None:
        self._capture_reasoning_event(event)
        if self.on_event is None:
            return
        try:
            maybe_coro = self.on_event(event)
            if asyncio.iscoroutine(maybe_coro):
                await maybe_coro
        except Exception as exc:
            self.logger.warning(
                "pipeline_event_callback_failed",
                event_type=event.get("type"),
                phase=event.get("phase"),
                error=str(exc),
            )

    def _capture_reasoning_event(self, event: PipelineEvent) -> None:
        if self._captured_reasoning_events is None:
            return
        if not _is_reasoning_event(event):
            return

        copied_event: PipelineEvent = {}
        for key, value in event.items():
            if isinstance(value, list):
                copied_event[key] = list(value)
            else:
                copied_event[key] = value
        self._captured_reasoning_events.append(copied_event)


class _TrackingIterationController(IterationController):
    def __init__(
        self,
        evidence_processor: EvidenceProcessor,
        session_store: SessionStore | None = None,
        session_id: str | None = None,
        on_event: Callable[[PipelineEvent], Awaitable[None]] | None = None,
    ) -> None:
        super().__init__(
            evidence_processor=evidence_processor,
            store=session_store,
            session_id=session_id,
        )
        self.iterations_executed = 0
        self.session_store = session_store
        self.session_id = session_id
        self.on_event = on_event
        self._latest_new_evidence_count = 0
        self._latest_iteration_for_search: int | None = None

    async def _search(
        self,
        subqueries: list[SubQuery],
        channels: list[Channel],
        iteration: int,
        priority_channels: set[str] | None = None,
        skip_channels: set[str] | None = None,
    ) -> list[Evidence]:
        evidences = await super()._search(
            subqueries,
            channels,
            iteration,
            priority_channels=priority_channels,
            skip_channels=skip_channels,
        )
        if self._latest_iteration_for_search != iteration:
            self._latest_iteration_for_search = iteration
            self._latest_new_evidence_count = 0
        self._latest_new_evidence_count += len(evidences)
        return evidences

    async def _handle_search_result(
        self,
        *,
        channel_name: str,
        query_text: str,
        result: list[Evidence] | Exception,
        iteration: int,
    ) -> list[Evidence]:
        evidences = await super()._handle_search_result(
            channel_name=channel_name,
            query_text=query_text,
            result=result,
            iteration=iteration,
        )
        result_count = len(evidences)
        if isinstance(result, Exception) and self.on_event is not None:
            await self.on_event(
                {
                    "type": "error",
                    "channel": channel_name,
                    "phase": "search",
                    "subquery": query_text,
                    "message": str(result),
                }
            )

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
        gaps = await super()._reflect(
            query=query,
            iteration=iteration,
            max_iterations=max_iterations,
            subqueries=subqueries,
            evidences=evidences,
            client=client,
        )
        if self.on_event is not None:
            await self.on_event(
                {
                    "type": "iteration",
                    "round": self.iterations_executed,
                    "new_evidence": self._latest_new_evidence_count,
                    "running_evidence": len(evidences),
                }
            )
            for gap in gaps:
                await self.on_event(
                    {
                        "type": "gap",
                        "topic": gap.topic,
                        "reason": gap.reason,
                    }
                )
        self._latest_iteration_for_search = None
        self._latest_new_evidence_count = 0
        return gaps


def _initial_subquery_count(mode: SearchMode) -> int:
    if mode is SearchMode.FAST:
        return 3
    if mode is SearchMode.COMPREHENSIVE:
        return 7
    return 5


def _is_reasoning_event(event: PipelineEvent) -> bool:
    event_type = event.get("type")
    return event_type in {"rubrics", "subqueries", "iteration", "gap", "quality"}


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


def _should_log_pipeline_traceback(error: Exception) -> bool:
    if isinstance(error, AllProvidersFailedError):
        return False
    if isinstance(error, httpx.HTTPStatusError):
        return error.response.status_code not in {400, 401, 403}
    return not (isinstance(error, RuntimeError) and "No LLM provider configured" in str(error))


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


def _build_routing_trace(
    clarification: ClarifyResult,
    runtime_trace: dict[str, object] | None = None,
) -> dict[str, object]:
    trace = dict(runtime_trace or {})
    trace["query_type"] = clarification.query_type
    trace["priority"] = list(clarification.channel_priority)
    trace["skip"] = list(clarification.channel_skip)
    return trace
