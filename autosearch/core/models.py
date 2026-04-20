# Self-written, plan v2.3 § 13.5
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


class EvidenceDigest(BaseModel):
    model_config = ConfigDict(frozen=True)

    topic: str = ""
    key_findings: list[str] = Field(default_factory=list)
    source_urls: list[str] = Field(default_factory=list)
    evidence_count: int = 0
    compressed_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    token_count_before: int = 0
    token_count_after: int = 0


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


@dataclass(frozen=True)
class PipelineResult:
    delivery_status: Literal["ok", "needs_clarification"]
    clarification: ClarifyResult
    markdown: str | None = None
    evidences: list[Evidence] = field(default_factory=list)
    channel_empty_calls: dict[str, int] = field(default_factory=dict)
    reasoning_events: list[dict[str, object]] = field(default_factory=list)
    routing_trace: dict[str, object] = field(default_factory=dict)
    quality: EvaluationResult | None = None
    iterations: int = 0
    session_id: str | None = None
    cost: float = 0.0
    prompt_tokens: int = 0
    completion_tokens: int = 0
