# Self-written, plan autosearch-0419-channels-scope-proxy.md § F101
from __future__ import annotations

from typing import Literal, TypeVar

from pydantic import BaseModel, ConfigDict, Field

from autosearch.core.models import SearchMode

ChannelScope = Literal["all", "en_only", "zh_only", "mixed"]
Depth = Literal["fast", "deep", "comprehensive"]
OutputFormat = Literal["md", "html"]
T = TypeVar("T")


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


def depth_to_mode(depth: str | None) -> SearchMode | None:
    if depth is None:
        return None
    normalized = depth.lower()
    if normalized == "fast":
        return SearchMode.FAST
    if normalized == "deep":
        return SearchMode.DEEP
    if normalized == "comprehensive":
        return SearchMode.COMPREHENSIVE
    raise ValueError(f"invalid depth: {depth}")


def filter_channels_by_scope(channels: list[T], channel_scope: str) -> list[T]:
    """Return channels whose languages match the scope filter.

    - "all" / "mixed" -> no filter
    - "en_only" -> drop channels missing "en" from languages
    - "zh_only" -> drop channels missing "zh" from languages
    """

    if channel_scope in ("all", "mixed"):
        return list(channels)
    required = {"en_only": "en", "zh_only": "zh"}.get(channel_scope)
    if required is None:
        return list(channels)
    return [channel for channel in channels if required in getattr(channel, "languages", [])]
