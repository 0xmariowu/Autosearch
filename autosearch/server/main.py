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
from pydantic import BaseModel, ValidationError, field_validator

from autosearch import __version__
from autosearch.core.channel_bootstrap import _build_channels
from autosearch.core.models import SearchMode
from autosearch.core.pipeline import Pipeline, PipelineResult
from autosearch.core.scope_clarifier import ScopeClarifier
from autosearch.core.search_scope import ScopeQuestion, SearchScope, depth_to_mode
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
    scope: SearchScope | None = None

    @field_validator("scope", mode="before")
    @classmethod
    def _normalize_scope(cls, value: Any) -> Any:
        if isinstance(value, dict):
            return {key: item for key, item in value.items() if item is not None}
        return value


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
    return Pipeline(
        llm=LLMClient(),
        channels=_build_channels(),
        on_event=on_event,
    )


def _terminal_payload(result: PipelineResult) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "type": "finished",
        "iterations": result.iterations,
        "delivery_status": result.delivery_status,
        "channel_empty_calls": result.channel_empty_calls,
        "routing_trace": result.routing_trace,
    }
    if result.delivery_status == "needs_clarification":
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


def _openai_usage(result: PipelineResult) -> ChatCompletionUsage:
    prompt_tokens = result.prompt_tokens
    completion_tokens = result.completion_tokens
    return ChatCompletionUsage(
        prompt_tokens=prompt_tokens,
        completion_tokens=completion_tokens,
        total_tokens=prompt_tokens + completion_tokens,
    )


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
    scope: SearchScope,
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
        usage=_openai_usage(result),
        metadata={"scope_used": scope.model_dump()},
        **_chat_completion_result_fields(result),
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
        **_chat_completion_result_fields(result),
    )
    yield _encode_sse(content_chunk.model_dump(exclude_none=True))
    yield "data: [DONE]\n\n"


async def _event_payloads(
    query: str,
    mode: SearchMode,
    scope: SearchScope,
    pipeline_factory: PipelineFactory,
) -> AsyncIterator[dict[str, Any]]:
    queue: asyncio.Queue[dict[str, Any]] = asyncio.Queue()

    yield {"type": "started", "query": query}
    pipeline_task = asyncio.create_task(
        pipeline_factory(queue.put).run(query, mode_hint=mode, scope=scope)
    )

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


async def _scope_needed_payloads(
    questions: list[ScopeQuestion],
) -> AsyncIterator[dict[str, Any]]:
    for question in questions:
        yield {
            "type": "scope_needed",
            "field": question.field,
            "prompt": question.prompt,
            "options": question.options,
        }


async def _encoded_streaming_payloads(
    payloads: AsyncIterator[dict[str, Any]],
) -> AsyncIterator[str]:
    async for payload in payloads:
        yield _encode_sse(payload)


async def _encoded_eventsource_payloads(
    payloads: AsyncIterator[dict[str, Any]],
) -> AsyncIterator[dict[str, str]]:
    async for payload in payloads:
        yield {"data": json.dumps(payload, ensure_ascii=False)}


def _chat_completion_result_fields(result: PipelineResult) -> dict[str, Any]:
    response_fields: dict[str, Any] = {}
    visited_urls = _visited_urls(result)
    if visited_urls is not None:
        response_fields["visitedURLs"] = visited_urls

    reasoning_content = _reasoning_content(result)
    if reasoning_content is not None:
        response_fields["reasoning_content"] = reasoning_content
    return response_fields


def _visited_urls(result: PipelineResult) -> list[str] | None:
    seen: set[str] = set()
    visited_urls: list[str] = []
    for evidence in result.evidences:
        url = evidence.url.strip()
        if not url or url in seen:
            continue
        seen.add(url)
        visited_urls.append(url)
    return visited_urls or None


def _reasoning_content(result: PipelineResult) -> str | None:
    rubrics: list[str] = []
    subqueries: list[str] = []
    gap_rounds: dict[int, list[str]] = {}
    saw_iteration = False
    current_round: int | None = None
    quality_grade: str | None = None
    quality_follow_up_count: int | None = None

    for event in result.reasoning_events:
        event_type = event.get("type")

        if event_type == "rubrics":
            rubrics = _event_items(event)
            continue

        if event_type == "subqueries" and event.get("phase") == "M2":
            subqueries = _event_items(event)
            continue

        if event_type == "iteration":
            round_value = event.get("round")
            if isinstance(round_value, int):
                saw_iteration = True
                current_round = round_value
                gap_rounds.setdefault(round_value, [])
            continue

        if event_type == "gap":
            if current_round is None:
                continue
            gap_line = _format_gap(event)
            if gap_line is not None:
                gap_rounds.setdefault(current_round, []).append(gap_line)
            continue

        if event_type == "quality":
            grade = event.get("grade")
            if isinstance(grade, str) and grade:
                quality_grade = grade
            follow_up_count = event.get("follow_up_count")
            if isinstance(follow_up_count, int):
                quality_follow_up_count = follow_up_count

    if not rubrics:
        rubrics = [
            rubric.text.strip() for rubric in result.clarification.rubrics if rubric.text.strip()
        ]

    lines: list[str] = []

    if rubrics:
        lines.append("M1 Rubrics:")
        lines.extend(f"- {rubric}" for rubric in rubrics)

    if subqueries:
        lines.append("M2 Subqueries:")
        lines.extend(f"- {subquery}" for subquery in subqueries)

    if saw_iteration:
        lines.append("M3 Gap Reflection:")
        for round_number, gaps in gap_rounds.items():
            if gaps:
                lines.append(f"- Round {round_number}: {'; '.join(gaps)}")
            else:
                lines.append(f"- Round {round_number}: no major gaps identified.")

    if quality_grade is not None or quality_follow_up_count is not None:
        lines.append("M8 Quality:")
        grade_text = quality_grade or "unknown"
        if quality_follow_up_count is None:
            lines.append(f"- Grade: {grade_text}")
        else:
            lines.append(f"- Grade: {grade_text}; follow-up gaps: {quality_follow_up_count}")

    if not lines:
        return None
    return "\n".join(lines)


def _event_items(event: dict[str, object]) -> list[str]:
    raw_items = event.get("items")
    if not isinstance(raw_items, list):
        return []

    items: list[str] = []
    for raw_item in raw_items:
        if not isinstance(raw_item, str):
            continue
        item = raw_item.strip()
        if item:
            items.append(item)
    return items


def _format_gap(event: dict[str, object]) -> str | None:
    topic = event.get("topic")
    if not isinstance(topic, str):
        return None
    topic_text = topic.strip()
    if not topic_text:
        return None

    reason = event.get("reason")
    if not isinstance(reason, str):
        return topic_text
    reason_text = reason.strip()
    if not reason_text:
        return topic_text
    return f"{topic_text} ({reason_text})"


async def _streaming_events(
    query: str,
    mode: SearchMode,
    scope: SearchScope,
    pipeline_factory: PipelineFactory,
) -> AsyncIterator[str]:
    async for payload in _encoded_streaming_payloads(
        _event_payloads(query, mode, scope, pipeline_factory)
    ):
        yield payload


async def _eventsource_events(
    query: str,
    mode: SearchMode,
    scope: SearchScope,
    pipeline_factory: PipelineFactory,
) -> AsyncIterator[dict[str, str]]:
    async for payload in _encoded_eventsource_payloads(
        _event_payloads(query, mode, scope, pipeline_factory)
    ):
        yield payload


def _scope_questions(request: SearchRequest) -> list[ScopeQuestion]:
    if request.scope is None:
        provided: dict[str, str] | None = None
    else:
        provided = {
            field: getattr(request.scope, field) for field in request.scope.model_fields_set
        }
    return ScopeClarifier().questions_for(provided)


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

    raw_scope_input = (request.metadata or {}).get("scope")
    if raw_scope_input is None:
        scope = SearchScope()
        mode = _mode_from_reasoning_effort(request.reasoning_effort)
    else:
        if not isinstance(raw_scope_input, dict):
            return _openai_error_response(
                message="metadata.scope must be an object.",
                error_type="invalid_request_error",
                status_code=400,
                code="invalid_scope",
            )
        try:
            scope = SearchScope(
                **{key: value for key, value in raw_scope_input.items() if value is not None}
            )
        except ValidationError as exc:
            return _openai_error_response(
                message=str(exc),
                error_type="invalid_request_error",
                status_code=400,
                code="invalid_scope",
            )
        mode = depth_to_mode(scope.depth)
        assert mode is not None

    model_name = _resolve_model_name(request.model)
    response_id = _chat_completion_id()
    created = int(time.time())

    try:
        result = await _default_pipeline_factory(None).run(query, mode_hint=mode, scope=scope)
    except Exception as exc:
        return _openai_error_response(
            message=str(exc),
            error_type="server_error",
            status_code=500,
            code="internal_error",
        )

    if result.delivery_status == "needs_clarification":
        question = result.clarification.question or "More detail is required."
        return _openai_error_response(
            message=f"Clarification needed: {question}",
            error_type="clarification_required",
            status_code=400,
            code="clarification_required",
        )

    if request.stream:
        # Keep streamed chunks stable for v1 clients; scope metadata is echoed only on
        # the non-streaming response envelope.
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
        scope=scope,
    ).model_dump(exclude_none=True)


@app.post("/search")
async def search(request: SearchRequest):
    questions = _scope_questions(request)
    if questions:
        if EventSourceResponse is not None:
            return EventSourceResponse(
                _encoded_eventsource_payloads(_scope_needed_payloads(questions))
            )
        return StreamingResponse(
            _encoded_streaming_payloads(_scope_needed_payloads(questions)),
            media_type="text/event-stream",
        )

    mode = request.mode
    if request.scope is not None:
        resolved_mode = depth_to_mode(request.scope.depth)
        assert resolved_mode is not None
        mode = resolved_mode

    if EventSourceResponse is not None:
        return EventSourceResponse(
            _eventsource_events(
                request.query,
                mode,
                request.scope,
                _default_pipeline_factory,
            )
        )
    return StreamingResponse(
        _streaming_events(
            request.query,
            mode,
            request.scope,
            _default_pipeline_factory,
        ),
        media_type="text/event-stream",
    )
