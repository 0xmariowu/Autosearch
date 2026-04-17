# Source: openperplex_backend_os/main.py:L14-L77 (adapted)
import json
from collections.abc import AsyncIterator, Callable
from typing import Any

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from autosearch import __version__
from autosearch.channels.demo import DemoChannel
from autosearch.core.models import SearchMode
from autosearch.core.pipeline import Pipeline, PipelineResult
from autosearch.llm.client import LLMClient

try:
    from sse_starlette.sse import EventSourceResponse
except ImportError:
    EventSourceResponse = None


class SearchRequest(BaseModel):
    query: str
    mode: SearchMode = SearchMode.FAST


app = FastAPI(title="AutoSearch", version=__version__)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)


def _default_pipeline_factory() -> Pipeline:
    return Pipeline(llm=LLMClient(), channels=[DemoChannel()])


def _phase_sequence(result: PipelineResult) -> list[str]:
    if result.status == "needs_clarification":
        return ["M0", "M1"]
    return ["M0", "M1", "M2", *(["M3"] * max(1, result.iterations)), "M5", "M7", "M8"]


def _terminal_payload(result: PipelineResult) -> dict[str, Any]:
    if result.status == "needs_clarification":
        return {
            "type": "needs_clarification",
            "question": result.clarification.question or "More detail is required.",
        }
    return {
        "type": "finished",
        "markdown": result.markdown or "",
        "iterations": result.iterations,
        "status": result.status,
    }


def _encode_sse(payload: dict[str, Any]) -> str:
    return f"data: {json.dumps(payload, ensure_ascii=False)}\n\n"


async def _event_payloads(
    query: str,
    mode: SearchMode,
    pipeline_factory: Callable[[], Pipeline],
) -> AsyncIterator[dict[str, Any]]:
    yield {"type": "started", "query": query}
    try:
        result = await pipeline_factory().run(query, mode_hint=mode)
    except Exception as exc:
        yield {"type": "error", "message": str(exc)}
        return

    for phase in _phase_sequence(result):
        yield {"type": "progress", "phase": phase}
    yield _terminal_payload(result)


async def _streaming_events(
    query: str,
    mode: SearchMode,
    pipeline_factory: Callable[[], Pipeline],
) -> AsyncIterator[str]:
    async for payload in _event_payloads(query, mode, pipeline_factory):
        yield _encode_sse(payload)


async def _eventsource_events(
    query: str,
    mode: SearchMode,
    pipeline_factory: Callable[[], Pipeline],
) -> AsyncIterator[dict[str, str]]:
    async for payload in _event_payloads(query, mode, pipeline_factory):
        yield {"data": json.dumps(payload, ensure_ascii=False)}


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/search")
async def search(request: SearchRequest):
    if EventSourceResponse is not None:
        return EventSourceResponse(
            _eventsource_events(request.query, request.mode, _default_pipeline_factory)
        )
    return StreamingResponse(
        _streaming_events(request.query, request.mode, _default_pipeline_factory),
        media_type="text/event-stream",
    )
