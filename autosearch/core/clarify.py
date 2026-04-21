# Source: open_deep_research/src/open_deep_research/prompts.py:L3-L41 (adapted)
from datetime import date
from textwrap import dedent

import structlog
from pydantic import BaseModel, Field

from autosearch.channels.base import Channel
from autosearch.core.models import ClarifyRequest, ClarifyResult, Rubric, SearchMode
from autosearch.llm.client import LLMClient

CLARIFY_PROMPT = dedent(
    """\
    These are the messages that have been exchanged so far from the user asking for the report:
    <Messages>
    {messages}
    </Messages>

    Today's date is {date}.

    {mode_preference}

    {channel_routing_guidance}

    Assess whether you need to ask a clarifying question, or if the user has already provided
    enough information for you to start research. IMPORTANT: If you can see in the messages
    history that you have already asked a clarifying question, you almost always do not need to
    ask another one. Only ask another question if ABSOLUTELY NECESSARY.

    Only ask for clarification when the query is GENUINELY ambiguous — unknown
    acronym with conflicting expansions, missing critical parameter, or two
    mutually exclusive interpretations. For queries that are broad but
    interpretable ("best practices guide for X", "survey of Y", "comparison of
    Z", "怎么选 Q", "XX 指南") proceed without asking: pick a reasonable scope,
    document it in the rubrics, and let the report reflect that interpretation.
    Only block with need_clarification=true when research cannot meaningfully
    start at all.
    If you need to ask a question, follow these guidelines:
    - Be concise while gathering all necessary information
    - Make sure to gather all the information needed to carry out the research task in a concise,
      well-structured manner
    - Use bullet points or numbered lists if appropriate for clarity. Make sure that this uses
      markdown formatting and will be rendered correctly if the string output is passed to a
      markdown renderer
    - Don't ask for unnecessary information, or information that the user has already provided.
      If you can see that the user has already provided the information, do not ask for it again

    Respond in valid JSON format with these exact keys:
    - "need_clarification": boolean
    - "question": "<question to ask the user to clarify the report scope>"
    - "verification": "<verification message that we will start research>"
    - "rubrics": ["<short binary evaluation criterion>", "..."]
    - "mode": "fast" or "deep"
    - "query_type": "<single category for this query>"
    - "channel_priority": ["<channel name>", "..."]
    - "channel_skip": ["<channel name>", "..."]

    If you need to ask a clarifying question, return:
    - "need_clarification": true
    - "question": "<your clarifying question>"
    - "verification": ""

    If you do not need to ask a clarifying question, return:
    - "need_clarification": false
    - "question": ""
    - "verification": "<acknowledgement message that you will now start research based on the
      provided information>"

    For the verification message when no clarification is needed:
    - Acknowledge that you have sufficient information to proceed
    - Briefly summarize the key aspects of what you understand from their request
    - Confirm that you will now begin the research process
    - Keep the message concise and professional

    For the added fields:
    - Always return 3 to 5 short rubrics, even if you also ask one clarifying question
    - Each rubric must be binary and easy to check in the final report
    - Recommend "fast" for focused or lightweight research and "deep" for broad, comparative,
      time-sensitive, or higher-stakes research
    - Return one short `query_type` label such as "code", "academic", "news", or
      "product-review"
    - `channel_priority` should usually contain 3 to 5 channel names from the available list
      below; return [] only if there is no strong priority preference
    - `channel_skip` should only include channel names from the available list that are clearly
      a poor fit for this query
    - Never invent channel names; only use names from the provided channel list
    - If clarification is needed, still return your best routing guess based on the current query
    """
).strip()


class _ClarifyCompletion(BaseModel):
    need_clarification: bool
    question: str = ""
    verification: str = ""
    rubrics: list[str] = Field(default_factory=list)
    mode: SearchMode
    query_type: str | None = None
    channel_priority: list[str] = Field(default_factory=list)
    channel_skip: list[str] = Field(default_factory=list)


class Clarifier:
    def __init__(self) -> None:
        self.logger = structlog.get_logger(__name__).bind(component="clarifier")

    async def clarify(
        self,
        req: ClarifyRequest,
        client: LLMClient,
        *,
        channels: list[Channel] | None = None,
    ) -> ClarifyResult:
        self.logger.info(
            "clarify_started",
            query=req.query,
            mode_hint=req.mode_hint.value if req.mode_hint is not None else None,
        )
        allowed_channels = _allowed_channel_names(channels or [])
        prompt = CLARIFY_PROMPT.format(
            messages=req.query,
            date=date.today().isoformat(),
            mode_preference=_mode_preference_text(req.mode_hint),
            channel_routing_guidance=_channel_routing_guidance(channels or []),
        )
        completion = await client.complete(prompt, _ClarifyCompletion)
        channel_priority = _normalize_channel_names(
            completion.channel_priority,
            allowed_channels=allowed_channels,
        )
        result = ClarifyResult(
            need_clarification=completion.need_clarification,
            question=_normalize_optional_text(completion.question),
            verification=_normalize_optional_text(completion.verification),
            rubrics=[Rubric(text=text.strip()) for text in completion.rubrics if text.strip()],
            mode=completion.mode,
            query_type=_normalize_optional_text(completion.query_type),
            channel_priority=channel_priority,
            channel_skip=_normalize_channel_names(
                completion.channel_skip,
                allowed_channels=allowed_channels,
                exclude=set(channel_priority),
            ),
        )
        self.logger.info(
            "clarify_completed",
            need_clarification=result.need_clarification,
            rubrics=len(result.rubrics),
            mode=result.mode.value,
            query_type=result.query_type,
            channel_priority=len(result.channel_priority),
            channel_skip=len(result.channel_skip),
        )
        return result


def _mode_preference_text(mode_hint: SearchMode | None) -> str:
    if mode_hint is None:
        return "The user did not state a preferred research mode."
    return (
        f"The user prefers {mode_hint.value} mode. Treat that as the default recommendation "
        "unless the request clearly calls for the other mode."
    )


def _channel_routing_guidance(channels: list[Channel]) -> str:
    if not channels:
        return dedent(
            """\
            No channel catalog is available for routing in this run.
            Return `query_type` if you can infer one, and return empty lists for
            `channel_priority` and `channel_skip`.
            """
        ).strip()

    lines = [
        (
            f"- {channel_name}: {', '.join(query_types)}"
            if query_types
            else f"- {channel_name}: general"
        )
        for channel_name, query_types in _channel_routing_rows(channels)
    ]
    return "\n".join(
        [
            f"Available research channels ({len(lines)} total):",
            *lines,
        ]
    )


def _channel_routing_rows(channels: list[Channel]) -> list[tuple[str, list[str]]]:
    rows: list[tuple[str, list[str]]] = []
    for channel in channels:
        channel_name = getattr(channel, "name", "").strip()
        if not channel_name:
            continue

        metadata = getattr(channel, "_metadata", None)
        when_to_use = getattr(metadata, "when_to_use", None)
        raw_query_types = getattr(when_to_use, "query_types", [])
        query_types = [
            query_type.strip()
            for query_type in raw_query_types
            if isinstance(query_type, str) and query_type.strip()
        ]
        rows.append((channel_name, query_types))
    return rows


def _allowed_channel_names(channels: list[Channel]) -> list[str]:
    return [channel_name for channel_name, _ in _channel_routing_rows(channels)]


def _normalize_optional_text(value: str | None) -> str | None:
    if value is None:
        return None
    stripped = value.strip()
    return stripped or None


def _normalize_channel_names(
    values: list[str],
    *,
    allowed_channels: list[str],
    exclude: set[str] | None = None,
) -> list[str]:
    exclude = exclude or set()
    allowed_lookup = {name.casefold(): name for name in allowed_channels}
    seen: set[str] = set()
    normalized: list[str] = []
    for value in values:
        candidate = value.strip()
        if not candidate:
            continue

        if allowed_lookup:
            canonical = allowed_lookup.get(candidate.casefold())
            if canonical is None:
                continue
            candidate = canonical

        folded = candidate.casefold()
        if candidate in exclude or folded in seen:
            continue
        seen.add(folded)
        normalized.append(candidate)

    return normalized
