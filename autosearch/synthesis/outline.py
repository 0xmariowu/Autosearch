# Source: storm/knowledge_storm/storm_wiki/modules/outline_generation.py:L84-L125 (adapted)
from __future__ import annotations

import re
from collections.abc import Mapping, Sequence
from dataclasses import dataclass

import structlog
from pydantic import BaseModel, Field

from autosearch.core.models import Evidence, OutlineNode, ResearchTurn, parse_markdown_outline
from autosearch.llm.client import LLMClient
from autosearch.skills.prompts import load_prompt

DRAFT_OUTLINE_PROMPT = load_prompt("m4_draft_outline")
REFINE_OUTLINE_PROMPT = load_prompt("m4_refine_outline")
RESEARCH_TRACE_CHAR_CAP = 8000
_MARKDOWN_HEADING_RE = re.compile(r"^\s*#{1,6}\s+\S", re.MULTILINE)
_DEFAULT_RESEARCH_ANSWER = "No explicit reflection answer was recorded."


class OutlineResponse(BaseModel):
    headings: list[str] = Field(default_factory=list)
    markdown: str = ""


@dataclass(frozen=True)
class _NormalizedResearchTurn:
    iteration: int
    batch_index: int
    question: str
    answer: str
    search_queries: tuple[str, ...]


async def draft_outline(query: str, client: LLMClient) -> OutlineNode:
    """Stage 1: draft an outline from the query using parametric knowledge."""
    logger = structlog.get_logger(__name__).bind(component="outline_generator", stage="draft")
    logger.info("outline_draft_started", query=query)

    prompt = DRAFT_OUTLINE_PROMPT.format(query=query)
    response = await client.complete(prompt, OutlineResponse)
    outline = _parse_outline_response(
        response=response,
        fallback_heading=query,
        logger=logger,
    )

    logger.info(
        "outline_draft_completed",
        top_level_sections=len(_top_level_headings(outline)),
    )
    return outline


async def refine_outline(
    query: str,
    draft: OutlineNode,
    research_trace: list[ResearchTurn] | list[dict],
    client: LLMClient,
) -> OutlineNode:
    """Stage 2: refine a draft outline using the research trace."""
    logger = structlog.get_logger(__name__).bind(component="outline_generator", stage="refine")
    normalized_draft = _normalize_outline_tree(draft)
    normalized_trace = _normalize_research_trace(research_trace)

    if not normalized_trace:
        logger.info("outline_refine_skipped", reason="empty_research_trace")
        return _ensure_valid_outline(
            outline=normalized_draft,
            fallback_heading=query,
            logger=logger,
            raw_markdown=_outline_to_markdown(normalized_draft),
        )

    research_dialogue = _format_research_dialogue(
        normalized_trace,
        char_cap=RESEARCH_TRACE_CHAR_CAP,
    )
    prompt = REFINE_OUTLINE_PROMPT.format(
        query=query,
        draft_outline_markdown=_outline_to_markdown(normalized_draft),
        research_dialogue=research_dialogue,
    )
    response = await client.complete(prompt, OutlineResponse)
    outline = _parse_outline_response(
        response=response,
        fallback_heading=query,
        logger=logger,
    )

    logger.info(
        "outline_refine_completed",
        top_level_sections=len(_top_level_headings(outline)),
        research_turns=len(normalized_trace),
    )
    return outline


class OutlineGenerator:
    def __init__(self) -> None:
        self.logger = structlog.get_logger(__name__).bind(component="outline_generator")

    async def outline(
        self,
        query: str,
        evidences: list[Evidence],
        client: LLMClient,
    ) -> list[str]:
        self.logger.info(
            "outline_generation_started",
            query=query,
            evidences=len(evidences),
        )
        draft = await draft_outline(query, client)
        refined = await refine_outline(query, draft, [], client)
        headings = _top_level_headings(refined)
        if not headings:
            headings = [query.strip() or "Overview"]
        self.logger.info("outline_generation_completed", headings=len(headings))
        return headings


def _parse_outline_response(
    *,
    response: OutlineResponse,
    fallback_heading: str,
    logger: structlog.stdlib.BoundLogger,
) -> OutlineNode:
    raw_markdown = _outline_markdown_from_response(response)
    try:
        outline = parse_markdown_outline(raw_markdown)
    except Exception as exc:  # pragma: no cover - defensive guard around parser failures
        logger.warning(
            "outline_parse_failed",
            error=str(exc),
            reason="parser_exception",
        )
        return _fallback_outline(fallback_heading)

    return _ensure_valid_outline(
        outline=outline,
        fallback_heading=fallback_heading,
        logger=logger,
        raw_markdown=raw_markdown,
    )


def _ensure_valid_outline(
    *,
    outline: OutlineNode,
    fallback_heading: str,
    logger: structlog.stdlib.BoundLogger,
    raw_markdown: str,
) -> OutlineNode:
    normalized = _normalize_outline_tree(outline)
    if _MARKDOWN_HEADING_RE.search(raw_markdown) is None:
        logger.warning("outline_parse_failed", reason="missing_markdown_headings")
        return _fallback_outline(fallback_heading)
    if not _outline_has_content(normalized):
        logger.warning("outline_parse_failed", reason="empty_outline_tree")
        return _fallback_outline(fallback_heading)
    return normalized


def _outline_markdown_from_response(response: OutlineResponse) -> str:
    markdown = response.markdown.strip()
    if markdown and _MARKDOWN_HEADING_RE.search(markdown):
        return markdown

    headings_markdown = _headings_to_markdown(response.headings)
    if headings_markdown:
        return headings_markdown

    return markdown


def _headings_to_markdown(headings: Sequence[str]) -> str:
    normalized_headings = _normalize_headings(headings)
    return "\n".join(f"# {heading}" for heading in normalized_headings)


def _normalize_headings(headings: Sequence[str]) -> list[str]:
    seen: set[str] = set()
    normalized: list[str] = []
    for heading in headings:
        cleaned = heading.strip().lstrip("#").strip()
        key = cleaned.casefold()
        if not cleaned or key in seen:
            continue
        seen.add(key)
        normalized.append(cleaned)
    return normalized


def _outline_has_content(outline: OutlineNode) -> bool:
    if outline.heading.strip():
        return True
    return any(_outline_has_content(child) for child in outline.children)


def _normalize_outline_tree(outline: OutlineNode) -> OutlineNode:
    if not outline.heading and not outline.children:
        return OutlineNode(heading="", level=0)
    if not outline.heading:
        return OutlineNode(
            heading="",
            level=0,
            children=[_clone_outline_node(child, level=1) for child in outline.children],
        )
    return _clone_outline_node(outline, level=1)


def _clone_outline_node(node: OutlineNode, *, level: int) -> OutlineNode:
    normalized_heading = node.heading.strip()
    return OutlineNode(
        heading=normalized_heading,
        level=min(level, 6),
        section_query=node.section_query,
        children=[
            _clone_outline_node(child, level=min(level + 1, 6))
            for child in node.children
            if child.heading.strip() or child.children
        ],
    )


def _top_level_headings(outline: OutlineNode) -> list[str]:
    normalized = _normalize_outline_tree(outline)
    if normalized.heading:
        return [normalized.heading]
    return [child.heading for child in normalized.children if child.heading.strip()]


def _outline_to_markdown(outline: OutlineNode) -> str:
    normalized = _normalize_outline_tree(outline)
    lines: list[str] = []
    roots = normalized.children if not normalized.heading else [normalized]
    for root in roots:
        _append_outline_lines(root, level=1, lines=lines)
    return "\n".join(lines)


def _append_outline_lines(node: OutlineNode, *, level: int, lines: list[str]) -> None:
    if node.heading.strip():
        lines.append(f"{'#' * level} {node.heading.strip()}")
    for child in node.children:
        _append_outline_lines(child, level=min(level + 1, 6), lines=lines)


def _normalize_research_trace(
    research_trace: Sequence[ResearchTurn | Mapping[str, object]],
) -> list[_NormalizedResearchTurn]:
    normalized: list[_NormalizedResearchTurn] = []
    for index, entry in enumerate(research_trace, start=1):
        if isinstance(entry, ResearchTurn):
            normalized_turn = _normalize_typed_turn(entry, fallback_iteration=index)
        elif isinstance(entry, Mapping):
            normalized_turn = _normalize_legacy_turn(entry, fallback_iteration=index)
        else:
            continue
        if normalized_turn is not None:
            normalized.append(normalized_turn)
    return normalized


def _normalize_typed_turn(
    turn: ResearchTurn,
    *,
    fallback_iteration: int,
) -> _NormalizedResearchTurn | None:
    search_queries = tuple(_clean_text_list(turn.search_queries))
    question = (
        turn.question.strip() or "; ".join(search_queries) or f"Research turn {fallback_iteration}"
    )
    answer = turn.answer.strip() or _DEFAULT_RESEARCH_ANSWER
    if not question and not answer and not search_queries:
        return None
    return _NormalizedResearchTurn(
        iteration=turn.iteration or fallback_iteration,
        batch_index=turn.batch_index,
        question=question,
        answer=answer,
        search_queries=search_queries,
    )


def _normalize_legacy_turn(
    entry: Mapping[str, object],
    *,
    fallback_iteration: int,
) -> _NormalizedResearchTurn | None:
    subqueries = _clean_text_list(entry.get("subqueries"))
    search_queries = _clean_text_list(entry.get("search_queries")) or subqueries
    question = _clean_text(entry.get("question")) or "; ".join(search_queries)
    answer = _clean_text(entry.get("answer")) or _answer_from_legacy_turn(entry)
    if not question:
        question = f"Research turn {fallback_iteration}"
    if not answer:
        answer = _DEFAULT_RESEARCH_ANSWER
    return _NormalizedResearchTurn(
        iteration=_coerce_int(entry.get("iteration"), default=fallback_iteration),
        batch_index=_coerce_int(entry.get("batch_index"), default=0),
        question=question,
        answer=answer,
        search_queries=tuple(search_queries),
    )


def _answer_from_legacy_turn(entry: Mapping[str, object]) -> str:
    gaps = entry.get("gaps")
    if isinstance(gaps, Sequence) and not isinstance(gaps, str):
        gap_parts = [_format_gap_item(item) for item in gaps]
        gap_parts = [part for part in gap_parts if part]
        if gap_parts:
            return "Observed gaps: " + "; ".join(gap_parts)

    digest_trace_id = entry.get("digest_trace_id")
    if digest_trace_id is None:
        digest_trace_id = entry.get("digest_id_if_any")
    if digest_trace_id is not None:
        return f"Context compaction digest recorded as {digest_trace_id}."

    return _DEFAULT_RESEARCH_ANSWER


def _format_gap_item(item: object) -> str:
    if isinstance(item, Mapping):
        topic = _clean_text(item.get("topic"))
        reason = _clean_text(item.get("reason"))
        if topic and reason:
            return f"{topic} ({reason})"
        return topic or reason
    return _clean_text(item)


def _clean_text(value: object) -> str:
    if isinstance(value, str):
        return " ".join(value.strip().split())
    return ""


def _clean_text_list(value: object) -> list[str]:
    if not isinstance(value, Sequence) or isinstance(value, str):
        return []
    cleaned: list[str] = []
    for item in value:
        text = _clean_text(item)
        if text:
            cleaned.append(text)
    return cleaned


def _coerce_int(value: object, *, default: int) -> int:
    if isinstance(value, bool):
        return default
    if isinstance(value, int):
        return value
    if isinstance(value, str):
        try:
            return int(value.strip())
        except ValueError:
            return default
    return default


def _format_research_dialogue(
    turns: Sequence[_NormalizedResearchTurn],
    *,
    char_cap: int,
) -> str:
    if not turns:
        return "No research trace available."

    blocks = [
        _format_turn_block(index=index, turn=turn) for index, turn in enumerate(turns, start=1)
    ]
    selected: list[str] = []
    current_length = 0

    for block in reversed(blocks):
        separator_length = 2 if selected else 0
        projected_length = current_length + len(block) + separator_length
        if projected_length > char_cap and selected:
            break
        if not selected and len(block) > char_cap:
            selected.append(block[-char_cap:])
            current_length = len(selected[0])
            break
        selected.append(block)
        current_length = projected_length

    selected.reverse()
    dialogue = "\n\n".join(selected)
    if len(selected) < len(blocks):
        prefix = "[... earlier turns omitted ...]\n\n"
        available = max(char_cap - len(prefix), 0)
        dialogue = prefix + dialogue[-available:]
    return dialogue[-char_cap:]


def _format_turn_block(*, index: int, turn: _NormalizedResearchTurn) -> str:
    searched = "; ".join(turn.search_queries) if turn.search_queries else "(none)"
    return "\n".join(
        [
            f"Turn {index} (iteration {turn.iteration}, batch {turn.batch_index}):",
            f"  Q: {turn.question}",
            f"  A: {turn.answer}",
            f"  Searched: {searched}",
        ]
    )


def _fallback_outline(heading: str) -> OutlineNode:
    fallback_heading = heading.strip() or "Overview"
    return OutlineNode(heading=fallback_heading, level=1)
