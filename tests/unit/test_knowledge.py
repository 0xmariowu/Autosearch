# Self-written, plan v2.3 § 13.5
from pydantic import BaseModel

from autosearch.core.knowledge import KnowledgeRecaller
from autosearch.core.models import Gap, KnowledgeRecall


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


async def test_knowledge_recall_returns_structured_result() -> None:
    client = DummyClient(
        {
            "known_facts": ["SQLite FTS5 includes BM25 ranking support."],
            "gaps": [{"topic": "Current provider limits", "reason": "Needs fresh verification"}],
        }
    )

    result = await KnowledgeRecaller().recall("SQLite FTS5 for search relevance", client)

    assert result == KnowledgeRecall(
        known_facts=["SQLite FTS5 includes BM25 ranking support."],
        gaps=[Gap(topic="Current provider limits", reason="Needs fresh verification")],
    )
    assert client.calls == 1
    assert client.response_models == [KnowledgeRecall]


async def test_knowledge_recall_allows_empty_gaps() -> None:
    client = DummyClient({"known_facts": ["Typer is a Python CLI framework."], "gaps": []})

    result = await KnowledgeRecaller().recall("What is Typer?", client)

    assert result.known_facts == ["Typer is a Python CLI framework."]
    assert result.gaps == []


async def test_knowledge_recall_calls_client_once_per_request() -> None:
    client = DummyClient({"known_facts": [], "gaps": []})
    recaller = KnowledgeRecaller()

    await recaller.recall("Need a quick grounding pass", client)

    assert client.calls == 1
    assert (
        "Return only what you can state confidently without doing any search." in client.prompts[0]
    )
