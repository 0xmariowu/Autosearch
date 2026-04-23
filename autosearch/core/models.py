# Self-written, plan v2.3 § 13.5
import re
from collections.abc import Iterator
from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import StrEnum
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class SearchMode(StrEnum):
    FAST = "fast"
    DEEP = "deep"
    COMPREHENSIVE = "comprehensive"


class SubQuery(BaseModel):
    model_config = ConfigDict(frozen=True)

    text: str
    rationale: str


class LinkRef(BaseModel):
    model_config = ConfigDict(frozen=True)

    href: str
    text: str
    internal: bool = False


class TableData(BaseModel):
    model_config = ConfigDict(frozen=True)

    headers: list[str] = Field(default_factory=list)
    rows: list[dict[str, str]] = Field(default_factory=list)


class MediaRef(BaseModel):
    model_config = ConfigDict(frozen=True)

    src: str
    alt: str = ""
    kind: Literal["image", "video"] = "image"


class FetchedPage(BaseModel):
    model_config = ConfigDict(frozen=True)

    url: str
    status_code: int
    fetched_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    html: str = ""
    cleaned_html: str = ""
    markdown: str = ""
    links: list[LinkRef] = Field(default_factory=list)
    metadata: dict[str, str] = Field(default_factory=dict)
    tables: list[TableData] = Field(default_factory=list)
    media: list[MediaRef] = Field(default_factory=list)

    def slim(self) -> "FetchedPage":
        """Return a copy with bulky HTML fields removed for serialization."""
        return self.model_copy(update={"html": "", "cleaned_html": ""})


class Evidence(BaseModel):
    model_config = ConfigDict(frozen=True)

    url: str
    title: str
    snippet: str | None = None
    content: str | None = None
    source_channel: str
    fetched_at: datetime
    score: float | None = None
    source_page: FetchedPage | None = None

    def to_slim_dict(self) -> dict:
        """Return a serialized form with a slimmed source_page when present."""
        data = self.model_dump()
        if self.source_page is not None:
            data["source_page"] = self.source_page.slim().model_dump()
        return data

    def to_context_dict(self, max_content_chars: int = 500) -> dict:
        """Minimal dict optimised for AI context injection.

        1:1 from Agent-Reach agent_reach/channels/xiaohongshu.py:format_xhs_result
        Strips fetched_at, source_page, and truncates content — cuts token usage ~60%.
        """
        d: dict = {"url": self.url, "title": self.title}
        text = self.snippet or self.content or ""
        if text:
            d["snippet"] = text[:max_content_chars]
        if self.source_channel:
            d["source"] = self.source_channel
        if self.score and self.score > 0:
            d["score"] = round(self.score, 2)
        return d


class EvidenceDigest(BaseModel):
    model_config = ConfigDict(frozen=True)

    topic: str = ""
    key_findings: list[str] = Field(default_factory=list)
    source_urls: list[str] = Field(default_factory=list)
    evidence_count: int = 0
    compressed_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    token_count_before: int = 0
    token_count_after: int = 0


class OutlineNode(BaseModel):
    """Hierarchical outline tree used by synthesis for section-scoped retrieval."""

    model_config = ConfigDict(extra="forbid")

    heading: str
    level: int = Field(ge=0, le=6)
    children: list["OutlineNode"] = Field(default_factory=list)
    section_query: str | None = None

    def get_subtree_headings(
        self,
        root_name: str | None = None,
        separator: str = " > ",
    ) -> list[str]:
        """Return this subtree as breadcrumb headings in depth-first order."""
        headings: list[str] = []
        prefix = [root_name] if root_name else []

        def visit(node: OutlineNode, ancestors: list[str]) -> None:
            current = ancestors
            if node.heading:
                current = [*ancestors, node.heading]
                headings.append(separator.join(current))
            for child in node.children:
                visit(child, current)

        visit(self, prefix)
        return headings

    def walk_leaves(self) -> Iterator["OutlineNode"]:
        """Yield leaf nodes in document order."""
        if not self.children:
            yield self
            return
        for child in self.children:
            yield from child.walk_leaves()

    def walk_depth_first(self) -> Iterator["OutlineNode"]:
        """Yield this node and all descendants in document order."""
        yield self
        for child in self.children:
            yield from child.walk_depth_first()


_MARKDOWN_HEADING_RE = re.compile(r"^\s*(#{1,6})\s+(.*?)\s*$")
_TRAILING_HASHES_RE = re.compile(r"\s+#+\s*$")


def parse_markdown_outline(markdown: str) -> OutlineNode:
    """Parse a markdown heading outline into an OutlineNode tree."""
    root = OutlineNode(heading="", level=0)
    parsed_headings: list[tuple[int, str]] = []

    for raw_line in markdown.splitlines():
        match = _MARKDOWN_HEADING_RE.match(raw_line)
        if not match:
            continue
        heading = _TRAILING_HASHES_RE.sub("", match.group(2)).strip()
        if not heading:
            continue
        parsed_headings.append((len(match.group(1)), heading))

    if not parsed_headings:
        root.children.extend(
            OutlineNode(heading=line.strip(), level=1)
            for line in markdown.splitlines()
            if line.strip()
        )
        return root

    stack: list[OutlineNode] = [root]
    for level, heading in parsed_headings:
        node = OutlineNode(heading=heading, level=level)
        while stack and stack[-1].level >= level:
            stack.pop()
        parent = stack[-1] if stack else root
        parent.children.append(node)
        stack.append(node)

    if len(root.children) == 1 and root.children[0].level == 1:
        return root.children[0]
    return root


class Gap(BaseModel):
    model_config = ConfigDict(frozen=True)

    topic: str
    reason: str


class Rubric(BaseModel):
    model_config = ConfigDict(frozen=True)

    text: str
    weight: float = 1.0


class Section(BaseModel):
    model_config = ConfigDict(frozen=True)

    heading: str
    content: str
    ref_ids: list[int]


class ClarifyRequest(BaseModel):
    model_config = ConfigDict(frozen=True)

    query: str
    mode_hint: SearchMode | None = None


class ClarifyResult(BaseModel):
    model_config = ConfigDict(frozen=True)

    need_clarification: bool
    question: str | None = None
    question_options: list[str] = Field(default_factory=list)
    verification: str | None = None
    rubrics: list[Rubric] = Field(default_factory=list)
    mode: SearchMode
    query_type: str | None = None
    channel_priority: list[str] = Field(default_factory=list)
    channel_skip: list[str] = Field(default_factory=list)


class KnowledgeRecall(BaseModel):
    model_config = ConfigDict(frozen=True)

    known_facts: list[str]
    gaps: list[Gap]


class GradeOutcome(StrEnum):
    PASS = "pass"
    FAIL = "fail"


class EvaluationResult(BaseModel):
    model_config = ConfigDict(frozen=True)

    grade: GradeOutcome
    follow_up_gaps: list[Gap]


class ResearchTurn(BaseModel):
    """One research step the iteration engine took."""

    model_config = ConfigDict(extra="forbid")

    iteration: int
    batch_index: int = 0
    perspective: str | None = None
    question: str
    answer: str
    search_queries: list[str] = Field(default_factory=list)
    evidence_ids: list[str] = Field(default_factory=list)
    digest_trace_id: int | None = None


class EvidenceSnippet(BaseModel):
    """A chunk of evidence content used for section-scoped retrieval."""

    model_config = ConfigDict(extra="forbid")

    evidence_id: str
    text: str
    offset: int = Field(ge=0)
    source_url: str
    source_title: str = ""


@dataclass(frozen=True)
class PipelineResult:
    delivery_status: Literal["ok", "needs_clarification"]
    clarification: ClarifyResult
    markdown: str | None = None
    evidences: list[Evidence] = field(default_factory=list)
    channel_empty_calls: dict[str, int] = field(default_factory=dict)
    reasoning_events: list[dict[str, object]] = field(default_factory=list)
    research_trace: list[dict[str, object]] = field(default_factory=list)
    routing_trace: dict[str, object] = field(default_factory=dict)
    quality: EvaluationResult | None = None
    iterations: int = 0
    session_id: str | None = None
    cost: float = 0.0
    prompt_tokens: int = 0
    completion_tokens: int = 0


OutlineNode.model_rebuild()
