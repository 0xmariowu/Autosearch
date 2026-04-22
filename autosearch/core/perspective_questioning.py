"""Perspective-questioning: generate multi-viewpoint sub-questions for a topic."""

from __future__ import annotations

from dataclasses import dataclass

_VIEWPOINTS = ["user", "expert", "critic", "competitor"]

_TEMPLATES: dict[str, str] = {
    "user": "From a practitioner's perspective: what practical problems does {topic} solve, and where does it fall short?",
    "expert": "From a domain expert's perspective: what are the key technical constraints or nuances of {topic} that non-experts miss?",
    "critic": "From a skeptic's perspective: what are the strongest objections to {topic}, and where is the evidence weakest?",
    "competitor": "From a competitor's perspective: how does {topic} compare to alternatives, and where do alternatives win?",
}


@dataclass
class SubQuestion:
    viewpoint: str
    question: str


def generate_perspectives(topic: str, n: int = 4) -> list[SubQuestion]:
    """Generate n sub-questions covering different viewpoints on a topic.

    n is clamped to [1, len(_VIEWPOINTS)]. Viewpoints are always selected
    in the order: user → expert → critic → competitor.
    """
    if not topic or not topic.strip():
        return []

    n = max(1, min(n, len(_VIEWPOINTS)))
    selected = _VIEWPOINTS[:n]

    return [
        SubQuestion(
            viewpoint=viewpoint,
            question=_TEMPLATES[viewpoint].format(topic=topic.strip()),
        )
        for viewpoint in selected
    ]
