# Source: openperplex_backend_os/main.py:L14-L77 (adapted)
import asyncio
import json
from collections.abc import AsyncIterator, Awaitable, Callable
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

type EventCallback = Callable[[dict[str, Any]], Awaitable[None] | None]
type PipelineFactory = Callable[[EventCallback | None], Pipeline]


class SearchRequest(BaseModel):
    query: str
    mode: SearchMode = SearchMode.FAST


app = FastAPI(title="AutoSearch", version=__version__)
_DEV_ALLOWED_ORIGINS = [
    "http://localhost:3000",
    "http://localhost:5173",
    "http://localhost:8080",
    "http://127.0.0.1:3000",
    "http://127.0.0.1:5173",
    "http://127.0.0.1:8080",
]
app.add_middleware(
    CORSMiddleware,
    allow_origins=_DEV_ALLOWED_ORIGINS,
    allow_credentials=False,
    allow_methods=["GET", "POST"],
    allow_headers=["Content-Type"],
)


def _default_pipeline_factory(on_event: EventCallback | None = None) -> Pipeline:
    return Pipeline(llm=LLMClient(), channels=[DemoChannel()], on_event=on_event)


def _terminal_payload(result: PipelineResult) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "type": "finished",
        "iterations": result.iterations,
        "status": result.status,
    }
    if result.status == "needs_clarification":
        payload["question"] = result.clarification.question or "More detail is required."
        return payload
    payload["markdown"] = result.markdown or ""
    return payload


def _encode_sse(payload: dict[str, Any]) -> str:
    return f"data: {json.dumps(payload, ensure_ascii=False)}\n\n"


async def _event_payloads(
    query: str,
    mode: SearchMode,
    pipeline_factory: PipelineFactory,
) -> AsyncIterator[dict[str, Any]]:
    queue: asyncio.Queue[dict[str, Any]] = asyncio.Queue()

    yield {"type": "started", "query": query}
    pipeline_task = asyncio.create_task(pipeline_factory(queue.put).run(query, mode_hint=mode))

    while not pipeline_task.done():
        try:
            yield queue.get_nowait()
        except asyncio.QueueEmpty:
            await asyncio.sleep(0)

    while not queue.empty():
        yield queue.get_nowait()

    try:
        result = await pipeline_task
    except Exception as exc:
        if queue.empty():
            yield {"type": "error", "message": str(exc)}
        return

    yield _terminal_payload(result)


async def _streaming_events(
    query: str,
    mode: SearchMode,
    pipeline_factory: PipelineFactory,
) -> AsyncIterator[str]:
    async for payload in _event_payloads(query, mode, pipeline_factory):
        yield _encode_sse(payload)


async def _eventsource_events(
    query: str,
    mode: SearchMode,
    pipeline_factory: PipelineFactory,
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
