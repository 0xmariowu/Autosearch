# Self-written, plan v2.3 § 13.5
from dataclasses import dataclass, field
from datetime import datetime
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


class Evidence(BaseModel):
    model_config = ConfigDict(frozen=True)

    url: str
    title: str
    snippet: str | None = None
    content: str | None = None
    source_channel: str
    fetched_at: datetime
    score: float | None = None


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
    reasoning_events: list[dict[str, object]] = field(default_factory=list)
    quality: EvaluationResult | None = None
    iterations: int = 0
    session_id: str | None = None
    cost: float = 0.0
    prompt_tokens: int = 0
    completion_tokens: int = 0
