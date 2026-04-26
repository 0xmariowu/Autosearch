from __future__ import annotations

import asyncio
import importlib.util
import json
from pathlib import Path
from types import ModuleType
from typing import Any

import httpx
import pytest
from structlog.testing import capture_logs

from autosearch.core.models import SubQuery
from autosearch.core.redact import redact_url

ROOT = Path(__file__).resolve().parents[2]
SECRET_TOKEN = "P0_SECRET_TOKEN_1234567890"
SECRET_SIG = "X_AMZ_SECRET_SIG"
SIGNED_URL = (
    f"https://example.com/video.mp4?access_token={SECRET_TOKEN}&X-Amz-Signature={SECRET_SIG}"
)


class TimeoutClient:
    async def get(self, *_args: object, **_kwargs: object) -> httpx.Response:
        raise httpx.TimeoutException("timed out")

    async def post(self, *_args: object, **_kwargs: object) -> httpx.Response:
        raise httpx.TimeoutException("timed out")


class SyncTimeoutClient:
    def post(self, *_args: object, **_kwargs: object) -> httpx.Response:
        raise httpx.TimeoutException("timed out")


def _load_tool(tool_key: str, relative_path: str) -> ModuleType:
    path = ROOT / relative_path
    spec = importlib.util.spec_from_file_location(f"{tool_key}_leak_under_test", path)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _audio_file(tmp_path: Path) -> str:
    path = tmp_path / "audio.mp3"
    path.write_bytes(b"fake mp3")
    return str(path)


def _run_fetch_jina(_monkeypatch: pytest.MonkeyPatch, _tmp_path: Path) -> Any:
    module = _load_tool("fetch_jina", "autosearch/skills/tools/fetch-jina/fetch.py")
    return asyncio.run(module.fetch(SIGNED_URL, http_client=TimeoutClient()))


def _run_fetch_crawl4ai(_monkeypatch: pytest.MonkeyPatch, _tmp_path: Path) -> Any:
    module = _load_tool("fetch_crawl4ai", "autosearch/skills/tools/fetch-crawl4ai/fetch.py")

    class CacheMode:
        BYPASS = object()

    class BrowserConfig:
        def __init__(self, **_kwargs: object) -> None:
            pass

    class CrawlerRunConfig:
        def __init__(self, **_kwargs: object) -> None:
            pass

    class AsyncWebCrawler:
        def __init__(self, **_kwargs: object) -> None:
            pass

        async def __aenter__(self) -> "AsyncWebCrawler":
            return self

        async def __aexit__(self, *_args: object) -> None:
            return None

        async def arun(self, *_args: object, **_kwargs: object) -> object:
            raise TimeoutError("timed out")

    crawl4ai = ModuleType("crawl4ai")
    crawl4ai.CacheMode = CacheMode
    crawl4ai.BrowserConfig = BrowserConfig
    crawl4ai.CrawlerRunConfig = CrawlerRunConfig
    crawl4ai.AsyncWebCrawler = AsyncWebCrawler
    return module.fetch(SIGNED_URL, crawl4ai_module=crawl4ai)


def _run_fetch_firecrawl(monkeypatch: pytest.MonkeyPatch, _tmp_path: Path) -> Any:
    module = _load_tool(
        "fetch_firecrawl", "autosearch/skills/tools/fetch-firecrawl/methods/scrape.py"
    )

    class Response:
        def raise_for_status(self) -> None:
            return None

        def json(self) -> dict[str, object]:
            return {"data": {"markdown": "body", "metadata": {}}}

    class AsyncClient:
        def __init__(self, **_kwargs: object) -> None:
            pass

        async def __aenter__(self) -> "AsyncClient":
            return self

        async def __aexit__(self, *_args: object) -> None:
            return None

        async def post(self, *_args: object, **_kwargs: object) -> Response:
            return Response()

    monkeypatch.setenv("FIRECRAWL_API_KEY", "test-key")
    monkeypatch.setattr(module.httpx, "AsyncClient", AsyncClient)
    result = asyncio.run(module.search(SubQuery(text=SIGNED_URL, rationale="leak test")))
    return [item.model_dump(mode="json") for item in result]


def _run_video_openai(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> Any:
    module = _load_tool(
        "video_openai", "autosearch/skills/tools/video-to-text-openai/transcribe.py"
    )
    monkeypatch.setenv("OPENAI_API_KEY", "test-key")
    monkeypatch.setattr(module, "_prepare_audio", lambda _source: _audio_file(tmp_path))
    return module.transcribe(SIGNED_URL, http_client=SyncTimeoutClient())


def _run_video_groq(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> Any:
    module = _load_tool("video_groq", "autosearch/skills/tools/video-to-text-groq/transcribe.py")
    monkeypatch.setenv("GROQ_API_KEY", "test-key")
    monkeypatch.setattr(module, "_prepare_audio", lambda _source: _audio_file(tmp_path))
    return module.transcribe(SIGNED_URL, http_client=SyncTimeoutClient())


def _run_video_local(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> Any:
    module = _load_tool("video_local", "autosearch/skills/tools/video-to-text-local/transcribe.py")
    monkeypatch.setattr(module, "_prepare_audio", lambda _source: _audio_file(tmp_path))

    class MlxWhisper:
        @staticmethod
        def transcribe(*_args: object, **_kwargs: object) -> dict[str, object]:
            raise module.ModelDownloadError("offline")

    return module.transcribe(SIGNED_URL, mlx_whisper_module=MlxWhisper)


BCUT_SIGNED_URL = "https://cdn.example.com/audio.mp3?Signature=ABCD&Expires=999"


def _load_bcut_tool() -> ModuleType:
    return _load_tool("video_bcut", "autosearch/skills/tools/video-to-text-bcut/transcribe.py")


def _assert_no_bcut_signature(value: Any) -> None:
    serialized = json.dumps(value, sort_keys=True, default=str)
    assert "Signature=" not in serialized
    assert "ABCD" not in serialized


def _configure_bcut_audio_extraction_failed(
    module: ModuleType, monkeypatch: pytest.MonkeyPatch
) -> None:
    def fail_extract(source: str, _output_wav: Path) -> None:
        raise RuntimeError(f"yt-dlp failed for {source}")

    monkeypatch.setattr(module, "_extract_audio_to_wav", fail_extract)


def _configure_bcut_api_failed(module: ModuleType, monkeypatch: pytest.MonkeyPatch) -> None:
    def extract_audio(_source: str, output_wav: Path) -> None:
        output_wav.write_bytes(b"fake wav")

    async def fail_transcribe(_audio_path: Path) -> list[dict[str, object]]:
        raise RuntimeError(f"bcut failed for {BCUT_SIGNED_URL}")

    monkeypatch.setattr(module, "_extract_audio_to_wav", extract_audio)
    monkeypatch.setattr(module, "_bcut_transcribe", fail_transcribe)


def _configure_bcut_unexpected_error(module: ModuleType, monkeypatch: pytest.MonkeyPatch) -> None:
    def extract_audio(_source: str, output_wav: Path) -> None:
        output_wav.write_bytes(b"fake wav")

    async def transcribe_audio(_audio_path: Path) -> list[dict[str, object]]:
        return [{"transcript": "hello", "words": []}]

    def fail_build_segments(_utterances: list[dict[str, object]]) -> list[dict[str, object]]:
        raise RuntimeError(f"unexpected failure for {BCUT_SIGNED_URL}")

    monkeypatch.setattr(module, "_extract_audio_to_wav", extract_audio)
    monkeypatch.setattr(module, "_bcut_transcribe", transcribe_audio)
    monkeypatch.setattr(module, "_build_segments", fail_build_segments)


BCUT_FAILURE_CONFIGURERS = (
    _configure_bcut_audio_extraction_failed,
    _configure_bcut_api_failed,
    _configure_bcut_unexpected_error,
)


def test_bcut_log_redacts_source(monkeypatch: pytest.MonkeyPatch) -> None:
    for configure_failure in BCUT_FAILURE_CONFIGURERS:
        module = _load_bcut_tool()
        configure_failure(module, monkeypatch)

        with capture_logs() as logs:
            asyncio.run(module.transcribe(BCUT_SIGNED_URL))

        _assert_no_bcut_signature(logs)


def test_bcut_result_reason_redacts_source(monkeypatch: pytest.MonkeyPatch) -> None:
    for configure_failure in BCUT_FAILURE_CONFIGURERS:
        module = _load_bcut_tool()
        configure_failure(module, monkeypatch)

        result = asyncio.run(module.transcribe(BCUT_SIGNED_URL))

        assert result["ok"] is False
        _assert_no_bcut_signature(result["reason"])


def test_bcut_structured_output_redacts_source(monkeypatch: pytest.MonkeyPatch) -> None:
    module = _load_bcut_tool()
    _configure_bcut_audio_extraction_failed(module, monkeypatch)

    result = asyncio.run(module.transcribe(BCUT_SIGNED_URL))

    assert result["source"] == redact_url(BCUT_SIGNED_URL)
    _assert_no_bcut_signature(result["source"])


def test_bcut_handles_non_string_source() -> None:
    module = _load_bcut_tool()

    result = asyncio.run(module.transcribe(None))

    assert result == {"ok": False, "source": "", "reason": "source must be a string"}


def test_bcut_unexpected_error_no_traceback_leak(monkeypatch: pytest.MonkeyPatch) -> None:
    module = _load_bcut_tool()
    _configure_bcut_unexpected_error(module, monkeypatch)

    with capture_logs() as logs:
        result = asyncio.run(module.transcribe(BCUT_SIGNED_URL))

    assert result["ok"] is False
    assert any(log.get("event") == "bcut_unexpected_error" for log in logs)
    for log in logs:
        serialized = json.dumps(log, sort_keys=True, default=str)
        assert "Signature=" not in serialized
        assert not log.get("exc_info")


@pytest.mark.parametrize(
    ("tool_key", "runner"),
    [
        ("fetch_jina", _run_fetch_jina),
        ("fetch_crawl4ai", _run_fetch_crawl4ai),
        ("fetch_firecrawl", _run_fetch_firecrawl),
        ("video_openai", _run_video_openai),
        ("video_groq", _run_video_groq),
        ("video_local", _run_video_local),
    ],
    ids=[
        "fetch_jina_leak",
        "fetch_crawl4ai_leak",
        "fetch_firecrawl_leak",
        "video_openai_leak",
        "video_groq_leak",
        "video_local_leak",
    ],
)
def test_tool_does_not_leak_url_secrets(
    tool_key: str,
    runner: Any,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    result = runner(monkeypatch, tmp_path)
    serialized = json.dumps(result, sort_keys=True)
    assert tool_key
    assert SECRET_TOKEN not in serialized
    assert SECRET_SIG not in serialized
