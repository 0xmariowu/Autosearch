# Self-written, plan v2.3 § 13.5 Presentation
import asyncio
import json

from fastapi.testclient import TestClient

import autosearch.server.main as server_main
from autosearch.core.models import ClarifyResult, SearchMode
from autosearch.core.pipeline import PipelineResult


def _ok_result() -> PipelineResult:
    return PipelineResult(
        delivery_status="ok",
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
        delivery_status="needs_clarification",
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
        on_event=None,
        emitted_events: list[dict[str, object]] | None = None,
    ) -> None:
        self.result = result
        self.exc = exc
        self.on_event = on_event
        self.emitted_events = emitted_events or []
        self.calls: list[tuple[str, SearchMode]] = []

    async def run(
        self,
        query: str,
        mode_hint: SearchMode | None = None,
        *,
        scope=None,
    ) -> PipelineResult:
        assert mode_hint is not None
        _ = scope
        self.calls.append((query, mode_hint))
        for event in self.emitted_events:
            if self.on_event is None:
                continue
            maybe_coro = self.on_event(event)
            if asyncio.iscoroutine(maybe_coro):
                await maybe_coro
        if self.exc is not None:
            raise self.exc
        assert self.result is not None
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

    response = client.post(
        "/search",
        json={
            "query": "test query",
            "scope": {
                "channel_scope": "all",
                "depth": "fast",
                "output_format": "md",
            },
        },
    )

    events = _parse_sse_events(response.text)

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/event-stream")
    assert events[0] == {"type": "started", "query": "test query"}
    assert {
        "type": "finished",
        "markdown": "# Test\n\nBody",
        "iterations": 2,
        "delivery_status": "ok",
    } in events
    assert pipeline.calls == [("test query", SearchMode.FAST)]


def test_search_streams_needs_clarification_event(monkeypatch) -> None:
    pipeline = _StubPipeline(result=_clarification_result())
    _install_pipeline_factory(monkeypatch, pipeline)
    client = TestClient(server_main.app)

    response = client.post(
        "/search",
        json={
            "query": "test query",
            "mode": "deep",
            "scope": {
                "channel_scope": "all",
                "depth": "deep",
                "output_format": "md",
            },
        },
    )

    events = _parse_sse_events(response.text)

    assert response.status_code == 200
    assert {
        "type": "finished",
        "delivery_status": "needs_clarification",
        "iterations": 0,
        "question": "Which deployment target do you care about?",
    } in events
    assert pipeline.calls == [("test query", SearchMode.DEEP)]
