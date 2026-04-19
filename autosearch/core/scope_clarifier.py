# Self-written, plan autosearch-0419-channels-scope-proxy.md § F101
from __future__ import annotations

from autosearch.core.search_scope import ScopeQuestion, SearchScope

_DOMAIN_FOLLOWUPS_QUESTION = ScopeQuestion(
    field="domain_followups",
    prompt=(
        "Any domain-specific angle, sub-topic, or framing to prioritize? "
        "(comma-separated, or leave empty)"
    ),
    options=[],
)

_CHANNEL_SCOPE_QUESTION = ScopeQuestion(
    field="channel_scope",
    prompt="Which channel scope should the search cover?",
    options=["all", "en_only", "zh_only", "mixed"],
)

_DEPTH_QUESTION = ScopeQuestion(
    field="depth",
    prompt="How deep should the search go?",
    options=["fast", "deep", "comprehensive"],
)

_FORMAT_QUESTION = ScopeQuestion(
    field="output_format",
    prompt="Output format for the report?",
    options=["md", "html"],
)


class ScopeClarifier:
    """Return clarification questions for SearchScope fields the caller omitted.

    Questions are asked in the same order the CLI/API should collect them, with domain
    context first and UX/output preferences after that.
    """

    def __init__(self) -> None:
        pass

    def questions_for(
        self,
        provided: dict[str, object] | None = None,
    ) -> list[ScopeQuestion]:
        """Return ordered questions for fields the caller did not explicitly provide.

        `provided` is a flat dict of field names the caller asserts were explicitly set.
        Missing keys or None values trigger a question for that field.
        """
        provided = provided or {}
        questions: list[ScopeQuestion] = []

        if provided.get("domain_followups") is None:
            questions.append(_DOMAIN_FOLLOWUPS_QUESTION)
        if provided.get("channel_scope") is None:
            questions.append(_CHANNEL_SCOPE_QUESTION)
        if provided.get("depth") is None:
            questions.append(_DEPTH_QUESTION)
        if provided.get("output_format") is None:
            questions.append(_FORMAT_QUESTION)

        return questions

    @staticmethod
    def apply_answers(
        base: SearchScope,
        answers: dict[str, object],
    ) -> SearchScope:
        """Return a new SearchScope with non-None answers applied over `base`.

        Raises ValidationError if any provided value does not satisfy the target field.
        """
        merged = base.model_dump()
        for field, value in answers.items():
            if value is None:
                continue
            if field == "domain_followups" and isinstance(value, str):
                merged[field] = [part.strip() for part in value.split(",") if part.strip()]
            else:
                merged[field] = value
        return SearchScope(**merged)
