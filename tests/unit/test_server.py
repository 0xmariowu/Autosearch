# Self-written, plan v2.3 § 13.5 Presentation
import json

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
        markdown="# Test\n\nBody",
        iterations=2,
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
    def __init__(
        self,
        result: PipelineResult | None = None,
        exc: Exception | None = None,
    ) -> None:
        self.result = result
        self.exc = exc
        self.calls: list[tuple[str, SearchMode]] = []

    async def run(self, query: str, mode_hint: SearchMode | None = None) -> PipelineResult:
        assert mode_hint is not None
        self.calls.append((query, mode_hint))
        if self.exc is not None:
            raise self.exc
        assert self.result is not None
        return self.result


def _install_pipeline_factory(monkeypatch, pipeline: _StubPipeline) -> None:
    monkeypatch.setattr(server_main, "_default_pipeline_factory", lambda: pipeline)


def _parse_sse_events(body: str) -> list[dict[str, object]]:
    events: list[dict[str, object]] = []
    for line in body.splitlines():
        if not line.startswith("data:"):
            continue
        events.append(json.loads(line.removeprefix("data:").strip()))
    return events


def test_health_returns_ok() -> None:
    client = TestClient(server_main.app)

    response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_search_streams_started_and_finished_events(monkeypatch) -> None:
    pipeline = _StubPipeline(result=_ok_result())
    _install_pipeline_factory(monkeypatch, pipeline)
    client = TestClient(server_main.app)

    response = client.post("/search", json={"query": "test query"})

    events = _parse_sse_events(response.text)

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/event-stream")
    assert events[0] == {"type": "started", "query": "test query"}
    assert any(event == {"type": "progress", "phase": "M0"} for event in events)
    assert {
        "type": "finished",
        "markdown": "# Test\n\nBody",
        "iterations": 2,
        "status": "ok",
    } in events
    assert pipeline.calls == [("test query", SearchMode.FAST)]


def test_search_streams_needs_clarification_event(monkeypatch) -> None:
    pipeline = _StubPipeline(result=_clarification_result())
    _install_pipeline_factory(monkeypatch, pipeline)
    client = TestClient(server_main.app)

    response = client.post("/search", json={"query": "test query", "mode": "deep"})

    events = _parse_sse_events(response.text)

    assert response.status_code == 200
    assert {
        "type": "needs_clarification",
        "question": "Which deployment target do you care about?",
    } in events
    assert pipeline.calls == [("test query", SearchMode.DEEP)]
