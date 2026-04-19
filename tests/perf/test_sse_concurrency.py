# Self-written, plan v2.3 § 13.5
import asyncio
import time

import httpx
import pytest

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
        markdown="# Perf\n\nConcurrent stream response.",
        iterations=1,
    )


class _ImmediatePipeline:
    def __init__(
        self,
        call_log: list[tuple[str, SearchMode | None]],
        result: PipelineResult,
        on_event=None,
    ) -> None:
        self.call_log = call_log
        self.result = result
        self.on_event = on_event

    async def run(
        self,
        query: str,
        mode_hint: SearchMode | None = None,
        *,
        scope=None,
    ) -> PipelineResult:
        _ = scope
        self.call_log.append((query, mode_hint))
        await asyncio.sleep(0)
        return self.result


@pytest.mark.perf
@pytest.mark.asyncio
async def test_chat_completion_stream_handles_ten_concurrent_requests(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    call_log: list[tuple[str, SearchMode | None]] = []

    monkeypatch.setattr(
        server_main,
        "_default_pipeline_factory",
        lambda on_event=None: _ImmediatePipeline(call_log, _ok_result(), on_event=on_event),
    )

    async def send_stream_request(
        client: httpx.AsyncClient,
        index: int,
    ) -> httpx.Response:
        return await client.post(
            "/v1/chat/completions",
            json={
                "messages": [{"role": "user", "content": f"concurrency test {index}"}],
                "stream": True,
            },
        )

    started_at = time.perf_counter()
    transport = httpx.ASGITransport(app=server_main.app)
    async with httpx.AsyncClient(
        transport=transport,
        base_url="http://testserver",
    ) as client:
        responses = await asyncio.gather(
            *(send_stream_request(client, index) for index in range(10))
        )
    elapsed = time.perf_counter() - started_at

    assert len(responses) == 10
    assert all(response.status_code == 200 for response in responses)
    assert all(
        response.headers["content-type"].startswith("text/event-stream") for response in responses
    )
    assert all("data: [DONE]\n\n" in response.text for response in responses)
    assert elapsed < 5.0
    assert len(call_log) == 10
