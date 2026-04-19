# Self-written, F103 chat scope metadata
from fastapi.testclient import TestClient

import autosearch.server.main as server_main
from autosearch.core.models import ClarifyResult, SearchMode
from autosearch.core.pipeline import PipelineResult
from autosearch.core.search_scope import SearchScope


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
        prompt_tokens=10,
        completion_tokens=20,
    )


class _StubPipeline:
    def __init__(self, result: PipelineResult) -> None:
        self.result = result
        self.calls: list[tuple[str, SearchMode, SearchScope | None]] = []
        self.on_event = None

    async def run(
        self,
        query: str,
        mode_hint: SearchMode | None = None,
        *,
        scope: SearchScope | None = None,
    ) -> PipelineResult:
        assert mode_hint is not None
        self.calls.append((query, mode_hint, scope))
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


def test_chat_completions_accepts_scope_metadata(monkeypatch) -> None:
    pipeline = _StubPipeline(result=_ok_result())
    _install_pipeline_factory(monkeypatch, pipeline)
    client = TestClient(server_main.app)

    response = client.post(
        "/v1/chat/completions",
        json={
            "messages": [{"role": "user", "content": "test"}],
            "metadata": {"scope": {"depth": "deep"}},
        },
    )

    payload = response.json()

    assert response.status_code == 200
    assert pipeline.calls == [("test", SearchMode.DEEP, SearchScope(depth="deep"))]
    assert payload["metadata"]["scope_used"]["depth"] == "deep"


def test_chat_completions_scope_uses_defaults_when_metadata_absent(monkeypatch) -> None:
    pipeline = _StubPipeline(result=_ok_result())
    _install_pipeline_factory(monkeypatch, pipeline)
    client = TestClient(server_main.app)

    response = client.post(
        "/v1/chat/completions",
        json={"messages": [{"role": "user", "content": "test"}]},
    )

    payload = response.json()

    assert response.status_code == 200
    assert pipeline.calls == [("test", SearchMode.FAST, SearchScope())]
    assert payload["metadata"]["scope_used"] == {
        "domain_followups": [],
        "channel_scope": "all",
        "depth": "fast",
        "output_format": "md",
    }


def test_chat_completions_invalid_scope_returns_400() -> None:
    client = TestClient(server_main.app)

    response = client.post(
        "/v1/chat/completions",
        json={
            "messages": [{"role": "user", "content": "test"}],
            "metadata": {"scope": {"depth": "bogus"}},
        },
    )

    payload = response.json()

    assert response.status_code == 400
    assert payload["error"]["type"] == "invalid_request_error"
    assert payload["error"]["code"] == "invalid_scope"


def test_chat_completions_scope_metadata_echoed_on_non_streaming(monkeypatch) -> None:
    pipeline = _StubPipeline(result=_ok_result())
    _install_pipeline_factory(monkeypatch, pipeline)
    client = TestClient(server_main.app)

    response = client.post(
        "/v1/chat/completions",
        json={"messages": [{"role": "user", "content": "test"}]},
    )

    payload = response.json()

    assert response.status_code == 200
    assert payload["metadata"]["scope_used"]["channel_scope"] == "all"
