# Self-written, plan v2.3 § 13.5
from pydantic import BaseModel, Field


class ClarifyOutput(BaseModel):
    need_clarification: bool
    question: str | None = None
    rubric: list[str] = Field(default_factory=list)
