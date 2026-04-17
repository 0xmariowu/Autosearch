# Self-written, plan v2.3 § 13.5
from datetime import datetime
from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field


class SearchMode(StrEnum):
    FAST = "fast"
    DEEP = "deep"


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
