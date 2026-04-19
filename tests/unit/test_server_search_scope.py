# Self-written, F103 API scope gating
import asyncio
import json

from fastapi.testclient import TestClient

import autosearch.server.main as server_main
from autosearch.core.models import ClarifyResult, SearchMode
from autosearch.core.pipeline import PipelineResult
from autosearch.core.search_scope import SearchScope


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
        iterations=1,
    )


class _StubPipeline:
    def __init__(
        self,
        result: PipelineResult,
        emitted_events: list[dict[str, object]] | None = None,
    ) -> None:
        self.result = result
        self.emitted_events = emitted_events or []
        self.on_event = None
        self.calls: list[tuple[str, SearchMode, SearchScope | None]] = []

    async def run(
        self,
        query: str,
        mode_hint: SearchMode | None = None,
        *,
        scope: SearchScope | None = None,
    ) -> PipelineResult:
        assert mode_hint is not None
        self.calls.append((query, mode_hint, scope))
        for event in self.emitted_events:
            if self.on_event is None:
                continue
            maybe_coro = self.on_event(event)
            if asyncio.iscoroutine(maybe_coro):
                await maybe_coro
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


def test_search_emits_scope_needed_when_scope_omitted(monkeypatch) -> None:
    pipeline = _StubPipeline(result=_ok_result())
    _install_pipeline_factory(monkeypatch, pipeline)
    client = TestClient(server_main.app)

    response = client.post("/search", json={"query": "test query"})

    events = _parse_sse_events(response.text)

    assert response.status_code == 200
    assert [event["field"] for event in events] == [
        "channel_scope",
        "depth",
        "output_format",
    ]
    assert all(event["type"] == "scope_needed" for event in events)
    assert pipeline.calls == []


def test_search_emits_scope_needed_when_scope_partially_explicit_none(monkeypatch) -> None:
    pipeline = _StubPipeline(result=_ok_result())
    _install_pipeline_factory(monkeypatch, pipeline)
    client = TestClient(server_main.app)

    response = client.post(
        "/search",
        json={"query": "test query", "scope": {"channel_scope": None}},
    )

    events = _parse_sse_events(response.text)

    assert response.status_code == 200
    assert [event["field"] for event in events] == [
        "channel_scope",
        "depth",
        "output_format",
    ]
    assert all(event["type"] == "scope_needed" for event in events)
    assert pipeline.calls == []


def test_search_runs_pipeline_when_scope_complete(monkeypatch) -> None:
    pipeline = _StubPipeline(
        result=_ok_result(),
        emitted_events=[{"type": "phase", "phase": "M0", "status": "start"}],
    )
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
    assert all(event["type"] != "scope_needed" for event in events)
    assert any(event["type"] == "phase" for event in events)
    assert pipeline.calls == [
        ("test query", SearchMode.FAST, SearchScope(channel_scope="all", depth="fast"))
    ]


def test_search_resolves_depth_comprehensive_to_search_mode(monkeypatch) -> None:
    pipeline = _StubPipeline(result=_ok_result())
    _install_pipeline_factory(monkeypatch, pipeline)
    client = TestClient(server_main.app)

    response = client.post(
        "/search",
        json={
            "query": "test query",
            "scope": {
                "channel_scope": "all",
                "depth": "comprehensive",
                "output_format": "md",
            },
        },
    )

    assert response.status_code == 200
    assert pipeline.calls == [
        (
            "test query",
            SearchMode.COMPREHENSIVE,
            SearchScope(channel_scope="all", depth="comprehensive"),
        )
    ]
