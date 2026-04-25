from __future__ import annotations

import asyncio
import importlib.util
import json
from pathlib import Path
from types import ModuleType
from typing import Any

import httpx
import pytest

from autosearch.core.models import SubQuery

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
