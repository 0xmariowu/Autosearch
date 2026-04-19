# Self-written, plan autosearch-0419-channels-scope-proxy.md § F101
from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

ChannelScope = Literal["all", "en_only", "zh_only", "mixed"]
Depth = Literal["fast", "deep", "comprehensive"]
OutputFormat = Literal["md", "html"]


class SearchScope(BaseModel):
    """User-facing scope parameters collected before the pipeline runs.

    M0.5 clarifier produces one ScopeQuestion per missing field; once filled, downstream
    modules (M1 domain clarifier, M2 strategy, M3 channel filter, M7 synthesizer) consume it.
    """

    model_config = ConfigDict(frozen=True)

    domain_followups: list[str] = Field(default_factory=list)
    channel_scope: ChannelScope = "all"
    depth: Depth = "fast"
    output_format: OutputFormat = "md"


class ScopeQuestion(BaseModel):
    """A single clarification question raised when a scope field is unspecified.

    Produced by `ScopeClarifier.questions_for()` and serialized into API/MCP/CLI flows.
    """

    model_config = ConfigDict(frozen=True)

    field: Literal["domain_followups", "channel_scope", "depth", "output_format"]
    prompt: str
    options: list[str] = Field(default_factory=list)
