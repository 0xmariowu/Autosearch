import json

from pydantic import BaseModel

from autosearch.llm.client import LLMClient


class DemoResponse(BaseModel):
    answer: str


class FactsResponse(BaseModel):
    known_facts: list[str]


class StubProvider:
    name = "stub"

    def __init__(self, response: str) -> None:
        self.response = response
        self.calls = 0

    async def complete(self, prompt: str, response_model: type[BaseModel]) -> str:
        _ = prompt
        _ = response_model
        self.calls += 1
        return self.response


def _make_client(response: str) -> tuple[LLMClient, StubProvider]:
    provider = StubProvider(response)
    client = LLMClient(provider_name="stub", providers={"stub": provider})
    return client, provider


def test_strip_code_fences_leaves_clean_json_unchanged() -> None:
    raw = '{"answer":"ok"}'

    stripped = LLMClient._strip_code_fences(raw)

    assert stripped == raw
    assert LLMClient._strip_code_fences(stripped) == raw
    assert json.loads(stripped) == {"answer": "ok"}


def test_strip_code_fences_removes_json_language_tag() -> None:
    raw = '```json\n{"answer":"ok"}\n```'

    stripped = LLMClient._strip_code_fences(raw)

    assert stripped == '{"answer":"ok"}'
    assert json.loads(stripped) == {"answer": "ok"}


def test_strip_code_fences_removes_bare_fences() -> None:
    raw = '```\n{"answer":"ok"}\n```'

    stripped = LLMClient._strip_code_fences(raw)

    assert stripped == '{"answer":"ok"}'
    assert json.loads(stripped) == {"answer": "ok"}


def test_strip_code_fences_handles_outer_whitespace() -> None:
    raw = '  \n\t```JSON\n{"answer":"ok"}\n```\n  '

    stripped = LLMClient._strip_code_fences(raw)

    assert stripped == '{"answer":"ok"}'
    assert json.loads(stripped) == {"answer": "ok"}


def test_strip_code_fences_handles_known_facts_bug_repro() -> None:
    raw = '```json\n{"known_facts":["RAG combines retrieval systems with generative models."]}\n```'

    stripped = LLMClient._strip_code_fences(raw)

    parsed = FactsResponse.model_validate(json.loads(stripped))
    assert parsed.known_facts == ["RAG combines retrieval systems with generative models."]


async def test_llm_client_complete_parses_fenced_provider_response() -> None:
    client, provider = _make_client('```json\n{"answer":"ok"}\n```')

    result = await client.complete("test prompt", DemoResponse)

    assert result.answer == "ok"
    assert provider.calls == 1
