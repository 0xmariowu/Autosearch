# Source: open_deep_research/src/open_deep_research/prompts.py:L3-L41 (adapted)
from datetime import date
from textwrap import dedent

import structlog
from pydantic import BaseModel, Field

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

    Assess whether you need to ask a clarifying question, or if the user has already provided
    enough information for you to start research. IMPORTANT: If you can see in the messages
    history that you have already asked a clarifying question, you almost always do not need to
    ask another one. Only ask another question if ABSOLUTELY NECESSARY.

    If there are acronyms, abbreviations, or unknown terms, ask the user to clarify.
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
    """
).strip()


class _ClarifyCompletion(BaseModel):
    need_clarification: bool
    question: str = ""
    verification: str = ""
    rubrics: list[str] = Field(default_factory=list)
    mode: SearchMode


class Clarifier:
    def __init__(self) -> None:
        self.logger = structlog.get_logger(__name__).bind(component="clarifier")

    async def clarify(self, req: ClarifyRequest, client: LLMClient) -> ClarifyResult:
        self.logger.info(
            "clarify_started",
            query=req.query,
            mode_hint=req.mode_hint.value if req.mode_hint is not None else None,
        )
        prompt = CLARIFY_PROMPT.format(
            messages=req.query,
            date=date.today().isoformat(),
            mode_preference=_mode_preference_text(req.mode_hint),
        )
        completion = await client.complete(prompt, _ClarifyCompletion)
        result = ClarifyResult(
            need_clarification=completion.need_clarification,
            question=_normalize_optional_text(completion.question),
            verification=_normalize_optional_text(completion.verification),
            rubrics=[Rubric(text=text.strip()) for text in completion.rubrics if text.strip()],
            mode=completion.mode,
        )
        self.logger.info(
            "clarify_completed",
            need_clarification=result.need_clarification,
            rubrics=len(result.rubrics),
            mode=result.mode.value,
        )
        return result


def _mode_preference_text(mode_hint: SearchMode | None) -> str:
    if mode_hint is None:
        return "The user did not state a preferred research mode."
    return (
        f"The user prefers {mode_hint.value} mode. Treat that as the default recommendation "
        "unless the request clearly calls for the other mode."
    )


def _normalize_optional_text(value: str) -> str | None:
    stripped = value.strip()
    return stripped or None
