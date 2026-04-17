# Self-written, plan v2.3 § 13.5
import asyncio
import json
import time
import uuid
from collections.abc import AsyncIterator, Awaitable, Callable
from typing import Any

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, StreamingResponse
from pydantic import BaseModel

from autosearch import __version__
from autosearch.channels.demo import DemoChannel
from autosearch.core.models import SearchMode
from autosearch.core.pipeline import Pipeline, PipelineResult
from autosearch.llm.client import LLMClient
from autosearch.server.openai_compat import (
    ChatCompletionChunk,
    ChatCompletionChunkChoice,
    ChatCompletionDelta,
    ChatCompletionRequest,
    ChatCompletionResponse,
    ChatCompletionUsage,
    ChatCompletionChoice,
    ChatMessage,
    ModelInfo,
    ModelsResponse,
)

try:
    from sse_starlette.sse import EventSourceResponse
except ImportError:
    EventSourceResponse = None

type EventCallback = Callable[[dict[str, Any]], Awaitable[None] | None]
type PipelineFactory = Callable[[EventCallback | None], Pipeline]


class SearchRequest(BaseModel):
    query: str
    mode: SearchMode = SearchMode.FAST


_DEFAULT_OPENAI_MODEL = "autosearch"
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


def _openai_error_response(
    *,
    message: str,
    error_type: str,
    status_code: int,
    code: str | None = None,
) -> JSONResponse:
    error: dict[str, str] = {
        "message": message,
        "type": error_type,
    }
    if code is not None:
        error["code"] = code
    return JSONResponse(status_code=status_code, content={"error": error})


def _openai_usage() -> ChatCompletionUsage:
    return ChatCompletionUsage(prompt_tokens=0, completion_tokens=0, total_tokens=0)


def _chat_completion_id() -> str:
    return f"chatcmpl-{uuid.uuid4().hex}"


def _resolve_model_name(request_model: str) -> str:
    return request_model.strip() or _DEFAULT_OPENAI_MODEL


def _mode_from_reasoning_effort(reasoning_effort: str | None) -> SearchMode:
    if reasoning_effort in {"medium", "high"}:
        return SearchMode.DEEP
    return SearchMode.FAST


def _extract_query(messages: list[ChatMessage]) -> str:
    if not messages or messages[-1].role != "user":
        raise ValueError("The last message must have role 'user'.")
    return messages[-1].content


def _chat_completion_response(
    *,
    result: PipelineResult,
    model: str,
    response_id: str,
    created: int,
) -> ChatCompletionResponse:
    return ChatCompletionResponse(
        id=response_id,
        created=created,
        model=model,
        choices=[
            ChatCompletionChoice(
                message=ChatMessage(role="assistant", content=result.markdown or ""),
            )
        ],
        usage=_openai_usage(),
    )


async def _chat_completion_stream(
    *,
    result: PipelineResult,
    model: str,
    response_id: str,
    created: int,
) -> AsyncIterator[str]:
    role_chunk = ChatCompletionChunk(
        id=response_id,
        created=created,
        model=model,
        choices=[
            ChatCompletionChunkChoice(
                delta=ChatCompletionDelta(role="assistant"),
            )
        ],
    )
    yield _encode_sse(role_chunk.model_dump(exclude_none=True))

    content_chunk = ChatCompletionChunk(
        id=response_id,
        created=created,
        model=model,
        choices=[
            ChatCompletionChunkChoice(
                delta=ChatCompletionDelta(content=result.markdown or ""),
                finish_reason="stop",
            )
        ],
    )
    yield _encode_sse(content_chunk.model_dump(exclude_none=True))
    yield "data: [DONE]\n\n"


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


@app.get("/v1/models")
async def list_models() -> ModelsResponse:
    return ModelsResponse(data=[ModelInfo(id=_DEFAULT_OPENAI_MODEL)])


@app.post("/v1/chat/completions")
async def chat_completions(request: ChatCompletionRequest):
    try:
        query = _extract_query(request.messages)
    except ValueError as exc:
        return _openai_error_response(
            message=str(exc),
            error_type="invalid_request_error",
            status_code=400,
            code="invalid_messages",
        )

    model_name = _resolve_model_name(request.model)
    mode = _mode_from_reasoning_effort(request.reasoning_effort)
    response_id = _chat_completion_id()
    created = int(time.time())

    try:
        result = await _default_pipeline_factory(None).run(query, mode_hint=mode)
    except Exception as exc:
        return _openai_error_response(
            message=str(exc),
            error_type="server_error",
            status_code=500,
            code="internal_error",
        )

    if result.status == "needs_clarification":
        question = result.clarification.question or "More detail is required."
        return _openai_error_response(
            message=f"Clarification needed: {question}",
            error_type="clarification_required",
            status_code=400,
            code="clarification_required",
        )

    if request.stream:
        return StreamingResponse(
            _chat_completion_stream(
                result=result,
                model=model_name,
                response_id=response_id,
                created=created,
            ),
            media_type="text/event-stream",
        )

    return _chat_completion_response(
        result=result,
        model=model_name,
        response_id=response_id,
        created=created,
    )


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
