from datetime import datetime

from fastapi.testclient import TestClient

import autosearch.server.main as server_main
from autosearch.core.models import ClarifyResult, Evidence, SearchMode
from autosearch.core.pipeline import PipelineResult
from autosearch.server.openai_compat import ChatCompletionResponse

NOW = datetime(2026, 4, 17, 12, 0, 0)


def _evidence(url: str, title: str) -> Evidence:
    return Evidence(
        url=url,
        title=title,
        snippet=f"Snippet for {title}",
        source_channel="demo",
        fetched_at=NOW,
    )


def _ok_result() -> PipelineResult:
    return PipelineResult(
        status="ok",
        clarification=ClarifyResult(
            need_clarification=False,
            question=None,
            verification="Enough information to proceed.",
            rubrics=[],
            mode=SearchMode.FAST,
        ),
        markdown="<canned markdown>",
        evidences=[
            _evidence("https://example.com/a", "A1"),
            _evidence("https://example.com/b", "B1"),
            _evidence("https://example.com/a", "A2 duplicate"),
            _evidence("https://example.com/c", "C1"),
            _evidence("https://example.com/b", "B2 duplicate"),
        ],
        reasoning_events=[
            {
                "type": "rubrics",
                "phase": "M1",
                "items": [
                    "Use evidence-backed claims",
                    "Highlight current behavior",
                ],
            },
            {
                "type": "subqueries",
                "phase": "M2",
                "items": [
                    "autosearch openai compat metadata",
                    "visited urls response field",
                ],
            },
            {"type": "iteration", "round": 1, "new_evidence": 3, "running_evidence": 3},
            {
                "type": "gap",
                "topic": "Stream final frame metadata",
                "reason": "Need parity with non-stream responses",
            },
            {"type": "quality", "grade": "pass", "follow_up_count": 0},
        ],
        iterations=1,
        prompt_tokens=10,
        completion_tokens=20,
    )


class _StubPipeline:
    def __init__(self, result: PipelineResult) -> None:
        self.result = result
        self.calls: list[tuple[str, SearchMode]] = []
        self.on_event = None

    async def run(self, query: str, mode_hint: SearchMode | None = None) -> PipelineResult:
        assert mode_hint is not None
        self.calls.append((query, mode_hint))
        return self.result


def _install_pipeline_factory(monkeypatch, pipeline: _StubPipeline) -> None:
    monkeypatch.setattr(
        server_main,
        "_default_pipeline_factory",
        lambda on_event=None: _bind_pipeline_callback(pipeline, on_event),
    )


def _bind_pipeline_callback(pipeline: _StubPipeline, on_event) -> _StubPipeline:
    pipeline.on_event = on_event
    return pipeline


def _post_chat_completion(client: TestClient) -> dict[str, object]:
    response = client.post(
        "/v1/chat/completions",
        json={"messages": [{"role": "user", "content": "test"}]},
    )
    assert response.status_code == 200
    return response.json()


def test_chat_completions_includes_visited_urls_when_evidences_exist(monkeypatch) -> None:
    pipeline = _StubPipeline(result=_ok_result())
    _install_pipeline_factory(monkeypatch, pipeline)
    client = TestClient(server_main.app)

    payload = _post_chat_completion(client)

    assert payload["visitedURLs"] == [
        "https://example.com/a",
        "https://example.com/b",
        "https://example.com/c",
    ]


def test_chat_completions_deduplicates_visited_urls_preserving_first_seen_order(
    monkeypatch,
) -> None:
    pipeline = _StubPipeline(result=_ok_result())
    _install_pipeline_factory(monkeypatch, pipeline)
    client = TestClient(server_main.app)

    payload = _post_chat_completion(client)

    assert payload["visitedURLs"] == [
        "https://example.com/a",
        "https://example.com/b",
        "https://example.com/c",
    ]


def test_chat_completions_includes_reasoning_content_sections(monkeypatch) -> None:
    pipeline = _StubPipeline(result=_ok_result())
    _install_pipeline_factory(monkeypatch, pipeline)
    client = TestClient(server_main.app)

    payload = _post_chat_completion(client)

    reasoning_content = payload["reasoning_content"]

    assert isinstance(reasoning_content, str)
    assert "M1 Rubrics:" in reasoning_content
    assert "Use evidence-backed claims" in reasoning_content
    assert "M2 Subqueries:" in reasoning_content
    assert "autosearch openai compat metadata" in reasoning_content
    assert "M3 Gap Reflection:" in reasoning_content
    assert "Stream final frame metadata" in reasoning_content
    assert "M8 Quality:" in reasoning_content


def test_chat_completions_metadata_keeps_openai_shape_valid(monkeypatch) -> None:
    pipeline = _StubPipeline(result=_ok_result())
    _install_pipeline_factory(monkeypatch, pipeline)
    client = TestClient(server_main.app)

    payload = _post_chat_completion(client)
    validated = ChatCompletionResponse.model_validate(payload)

    assert validated.object == "chat.completion"
    assert validated.choices[0].message.content == "<canned markdown>"
    assert validated.usage.total_tokens == 30
