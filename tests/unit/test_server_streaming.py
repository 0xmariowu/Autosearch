# Self-written, plan v2.3 § 13.5 Progress streaming
import asyncio
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
        iterations=1,
    )


class _StreamingStubPipeline:
    def __init__(self, on_event=None) -> None:
        self.on_event = on_event

    async def run(self, query: str, mode_hint: SearchMode | None = None) -> PipelineResult:
        _ = query
        _ = mode_hint
        for event in [
            {"type": "phase", "phase": "M0", "status": "start"},
            {"type": "iteration", "round": 1, "new_evidence": 2, "running_evidence": 2},
            {"type": "phase", "phase": "M0", "status": "complete"},
        ]:
            if self.on_event is None:
                continue
            maybe_coro = self.on_event(event)
            if asyncio.iscoroutine(maybe_coro):
                await maybe_coro
        return _ok_result()


def _parse_sse_events(body: str) -> list[dict[str, object]]:
    events: list[dict[str, object]] = []
    for line in body.splitlines():
        if not line.startswith("data:"):
            continue
        events.append(json.loads(line.removeprefix("data:").strip()))
    return events


def test_search_streams_phase_events_before_finished(monkeypatch) -> None:
    monkeypatch.setattr(
        server_main,
        "_default_pipeline_factory",
        lambda on_event=None: _StreamingStubPipeline(on_event=on_event),
    )
    client = TestClient(server_main.app)

    response = client.post("/search", json={"query": "test query"})

    events = _parse_sse_events(response.text)
    phase_index = next(index for index, event in enumerate(events) if event["type"] == "phase")
    finished_index = next(
        index for index, event in enumerate(events) if event["type"] == "finished"
    )

    assert response.status_code == 200
    assert phase_index < finished_index
