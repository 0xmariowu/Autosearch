# Self-written, plan v2.3 § 13.5
from pydantic import BaseModel

from autosearch.core.clarify import Clarifier
from autosearch.core.models import ClarifyRequest, SearchMode


class DummyClient:
    def __init__(self, payload: dict[str, object]) -> None:
        self.payload = payload
        self.calls = 0
        self.prompts: list[str] = []
        self.response_models: list[type[BaseModel]] = []

    async def complete(self, prompt: str, response_model: type[BaseModel]) -> BaseModel:
        self.calls += 1
        self.prompts.append(prompt)
        self.response_models.append(response_model)
        return response_model.model_validate(self.payload)


async def test_clarifier_returns_question_for_ambiguous_query() -> None:
    client = DummyClient(
        {
            "need_clarification": True,
            "question": "Do you want a consumer recommendation or an engineering comparison?",
            "verification": "",
            "rubrics": [
                "States the target audience",
                "Compares named options directly",
                "Uses sources newer than one year when possible",
            ],
            "mode": "deep",
        }
    )

    result = await Clarifier().clarify(ClarifyRequest(query="best search tools"), client)

    assert result.need_clarification is True
    assert result.question == "Do you want a consumer recommendation or an engineering comparison?"
    assert result.verification is None
    assert result.mode is SearchMode.DEEP
    assert client.calls == 1


async def test_clarifier_returns_rubrics_and_mode_for_clear_query() -> None:
    client = DummyClient(
        {
            "need_clarification": False,
            "question": "",
            "verification": "I have enough information to compare the four providers and will start research now.",
            "rubrics": [
                "Covers all four providers",
                "Includes pricing citations",
                "Calls out current model support",
            ],
            "mode": "fast",
        }
    )

    result = await Clarifier().clarify(
        ClarifyRequest(query="Compare Claude, OpenAI, Gemini, and Anthropic API pricing"),
        client,
    )

    assert result.need_clarification is False
    assert result.question is None
    assert result.verification is not None
    assert [rubric.text for rubric in result.rubrics] == [
        "Covers all four providers",
        "Includes pricing citations",
        "Calls out current model support",
    ]
    assert all(rubric.weight == 1.0 for rubric in result.rubrics)
    assert result.mode is SearchMode.FAST


async def test_clarifier_includes_mode_hint_when_provided() -> None:
    client = DummyClient(
        {
            "need_clarification": False,
            "question": "",
            "verification": "I have enough information to proceed.",
            "rubrics": [
                "Names the comparison set",
                "Uses fresh sources",
                "Explains the tradeoffs clearly",
            ],
            "mode": "deep",
        }
    )

    result = await Clarifier().clarify(
        ClarifyRequest(
            query="Research the long-term tradeoffs of local vs hosted code search",
            mode_hint=SearchMode.DEEP,
        ),
        client,
    )

    assert result.mode is SearchMode.DEEP
    assert "The user prefers deep mode." in client.prompts[0]
    assert client.calls == 1
