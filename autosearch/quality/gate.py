# Source: open_deep_research/src/legacy/prompts.py:L168-L198 (adapted)
# Source: open_deep_research/src/legacy/state.py:L32-L38 (adapted)
import structlog

from autosearch.core.models import EvaluationResult, Evidence, Gap, GradeOutcome, Rubric, Section
from autosearch.llm.client import LLMClient
from autosearch.skills.prompts import load_prompt

SECTION_GRADER_PROMPT = load_prompt("m8_section_grader")


class QualityGate:
    def __init__(self) -> None:
        self.logger = structlog.get_logger(__name__).bind(component="quality_gate")

    async def evaluate(
        self,
        section: Section,
        rubrics: list[Rubric],
        evidences: list[Evidence],
        client: LLMClient,
    ) -> EvaluationResult:
        prompt = SECTION_GRADER_PROMPT.format(
            topic=_report_topic(rubrics),
            section_topic=section.heading,
            section=section.content,
            rubrics=_format_rubrics(rubrics),
            evidence_context=_format_evidence(evidences),
            number_of_follow_up_gaps=max(1, len(rubrics) or 1),
        )
        self.logger.info(
            "quality_gate_started",
            section_heading=section.heading,
            rubrics=len(rubrics),
            evidences=len(evidences),
        )
        result = await client.complete(prompt, EvaluationResult)
        normalized = _normalize_result(result, section.heading)
        self.logger.info(
            "quality_gate_completed",
            section_heading=section.heading,
            grade=normalized.grade.value,
            follow_up_gaps=len(normalized.follow_up_gaps),
        )
        return normalized


def _report_topic(rubrics: list[Rubric]) -> str:
    if not rubrics:
        return (
            "The overall report topic is unspecified; use the section topic and evidence provided."
        )
    return "The report should satisfy these rubrics:\n" + "\n".join(
        f"- {rubric.text} (weight={rubric.weight})" for rubric in rubrics
    )


def _format_rubrics(rubrics: list[Rubric]) -> str:
    if not rubrics:
        return "- No explicit rubrics provided"
    return "\n".join(f"- {rubric.text} (weight={rubric.weight})" for rubric in rubrics)


def _format_evidence(evidences: list[Evidence]) -> str:
    if not evidences:
        return "- No evidence provided"
    formatted: list[str] = []
    for index, evidence in enumerate(evidences, start=1):
        content = evidence.content or evidence.snippet or ""
        formatted.append(
            "\n".join(
                [
                    f"[{index}] {evidence.title}",
                    f"URL: {evidence.url}",
                    f"Channel: {evidence.source_channel}",
                    f"Content: {content[:500] if content else '(none)'}",
                ]
            )
        )
    return "\n\n".join(formatted)


def _normalize_result(result: EvaluationResult, section_heading: str) -> EvaluationResult:
    if result.grade == GradeOutcome.PASS:
        return result.model_copy(update={"follow_up_gaps": []})
    if result.follow_up_gaps:
        return result
    return result.model_copy(
        update={
            "follow_up_gaps": [
                Gap(
                    topic=section_heading,
                    reason="The section does not yet adequately address the topic using the "
                    "available evidence and rubrics.",
                )
            ]
        }
    )
