# Self-written, plan v2.3 § 13.5
from fastapi.testclient import TestClient

import autosearch.server.main as server_main
from autosearch.core.models import ClarifyResult, SearchMode
from autosearch.core.pipeline import PipelineResult


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
        iterations=1,
    )


def _clarification_result() -> PipelineResult:
    return PipelineResult(
        status="needs_clarification",
        clarification=ClarifyResult(
            need_clarification=True,
            question="Which deployment target do you care about?",
            verification=None,
            rubrics=[],
            mode=SearchMode.DEEP,
        ),
        iterations=0,
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


def test_list_models_returns_autosearch_model() -> None:
    client = TestClient(server_main.app)

    response = client.get("/v1/models")

    assert response.status_code == 200
    assert response.json() == {
        "object": "list",
        "data": [{"id": "autosearch", "object": "model", "owned_by": "autosearch"}],
    }


def test_chat_completions_returns_non_stream_response(monkeypatch) -> None:
    pipeline = _StubPipeline(result=_ok_result())
    _install_pipeline_factory(monkeypatch, pipeline)
    client = TestClient(server_main.app)

    response = client.post(
        "/v1/chat/completions",
        json={"messages": [{"role": "user", "content": "test"}]},
    )

    payload = response.json()

    assert response.status_code == 200
    assert payload["object"] == "chat.completion"
    assert payload["model"] == "autosearch"
    assert payload["choices"][0]["message"]["content"] == "<canned markdown>"
    assert payload["choices"][0]["finish_reason"] == "stop"
    assert payload["usage"] == {
        "prompt_tokens": 0,
        "completion_tokens": 0,
        "total_tokens": 0,
    }
    assert pipeline.calls == [("test", SearchMode.FAST)]


def test_chat_completions_streams_sse_chunks(monkeypatch) -> None:
    pipeline = _StubPipeline(result=_ok_result())
    _install_pipeline_factory(monkeypatch, pipeline)
    client = TestClient(server_main.app)

    response = client.post(
        "/v1/chat/completions",
        json={"messages": [{"role": "user", "content": "test"}], "stream": True},
    )

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/event-stream")
    assert "data: {" in response.text
    assert "data: [DONE]\n\n" in response.text
    assert pipeline.calls == [("test", SearchMode.FAST)]


def test_chat_completions_rejects_last_non_user_message() -> None:
    client = TestClient(server_main.app)

    response = client.post(
        "/v1/chat/completions",
        json={"messages": [{"role": "assistant", "content": "test"}]},
    )

    payload = response.json()

    assert response.status_code == 400
    assert payload["error"]["type"] == "invalid_request_error"
    assert payload["error"]["code"] == "invalid_messages"


def test_chat_completions_returns_clarification_error(monkeypatch) -> None:
    pipeline = _StubPipeline(result=_clarification_result())
    _install_pipeline_factory(monkeypatch, pipeline)
    client = TestClient(server_main.app)

    response = client.post(
        "/v1/chat/completions",
        json={"messages": [{"role": "user", "content": "test"}]},
    )

    payload = response.json()

    assert response.status_code == 400
    assert payload["error"]["type"] == "clarification_required"
    assert payload["error"]["code"] == "clarification_required"
    assert payload["error"]["message"] == (
        "Clarification needed: Which deployment target do you care about?"
    )


def test_chat_completions_maps_high_reasoning_effort_to_deep(monkeypatch) -> None:
    pipeline = _StubPipeline(result=_ok_result())
    _install_pipeline_factory(monkeypatch, pipeline)
    client = TestClient(server_main.app)

    response = client.post(
        "/v1/chat/completions",
        json={
            "messages": [{"role": "user", "content": "test"}],
            "reasoning_effort": "high",
        },
    )

    assert response.status_code == 200
    assert pipeline.calls == [("test", SearchMode.DEEP)]
