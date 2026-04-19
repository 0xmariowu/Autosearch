# Self-written for task feat/huggingface-openalex-channels
from __future__ import annotations

import importlib.util
from pathlib import Path

import httpx
import pytest

from autosearch.core.models import SubQuery


def _load_module():
    module_path = (
        Path(__file__).resolve().parents[3]
        / "autosearch"
        / "skills"
        / "channels"
        / "huggingface_hub"
        / "methods"
        / "api_search.py"
    )
    spec = importlib.util.spec_from_file_location("test_huggingface_hub_api_search", module_path)
    if spec is None or spec.loader is None:
        raise AssertionError(f"Failed to load module spec from {module_path}")

    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


MODULE = _load_module()
search = MODULE.search


class _Logger:
    def __init__(self) -> None:
        self.events: list[tuple[str, dict[str, object]]] = []

    def warning(self, event: str, **kwargs: object) -> None:
        self.events.append((event, kwargs))


def _query() -> SubQuery:
    return SubQuery(text="llama", rationale="Need Hugging Face model coverage")


def _client(handler) -> httpx.AsyncClient:
    return httpx.AsyncClient(transport=httpx.MockTransport(handler))


def _truncate_expected(text: str, *, max_length: int = 300) -> str:
    text = text.strip()
    if len(text) <= max_length:
        return text

    candidate = text[:max_length]
    if candidate and not candidate[-1].isspace():
        shortened = candidate.rsplit(None, 1)[0]
        if shortened:
            candidate = shortened

    return f"{candidate.rstrip()}…"


@pytest.mark.asyncio
async def test_search_maps_items_to_evidence() -> None:
    async def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.params["search"] == "llama"
        assert request.url.params["limit"] == "10"
        assert request.headers["accept"] == "application/json"
        return httpx.Response(
            200,
            json=[
                {
                    "id": "meta-llama/Llama-3.1-8B-Instruct",
                    "downloads": 1234567,
                    "likes": 2345,
                    "pipeline_tag": "text-generation",
                    "library_name": "transformers",
                    "tags": ["transformers", "safetensors", "llama", "text-generation"],
                    "private": False,
                },
                {
                    "id": "BAAI/bge-base-en-v1.5",
                    "downloads": 543210,
                    "likes": 987,
                    "pipeline_tag": "feature-extraction",
                    "library_name": "sentence-transformers",
                    "tags": ["sentence-transformers", "embeddings", "retrieval"],
                    "private": False,
                },
            ],
            request=request,
        )

    async with _client(handler) as http_client:
        results = await search(_query(), http_client=http_client)

    assert len(results) == 2

    first = results[0]
    assert first.url == "https://huggingface.co/meta-llama/Llama-3.1-8B-Instruct"
    assert first.title == "meta-llama/Llama-3.1-8B-Instruct"
    assert (
        first.snippet
        == "text-generation · transformers · 1,234,567 downloads · 2,345 likes · tags: "
        "transformers, safetensors, llama, text-generation"
    )
    assert first.content == first.snippet
    assert first.source_channel == "huggingface_hub"

    second = results[1]
    assert second.url == "https://huggingface.co/BAAI/bge-base-en-v1.5"
    assert second.title == "BAAI/bge-base-en-v1.5"
    assert second.source_channel == "huggingface_hub"


@pytest.mark.asyncio
async def test_search_skips_items_without_required_fields() -> None:
    async def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json=[
                {
                    "downloads": 10,
                    "likes": 2,
                    "pipeline_tag": "text-generation",
                    "library_name": "transformers",
                    "tags": ["llm"],
                    "private": False,
                },
                {
                    "id": "mistralai/Mistral-7B-Instruct-v0.3",
                    "downloads": 100,
                    "likes": 20,
                    "pipeline_tag": "text-generation",
                    "library_name": "transformers",
                    "tags": ["mistral"],
                    "private": False,
                },
            ],
            request=request,
        )

    async with _client(handler) as http_client:
        results = await search(_query(), http_client=http_client)

    assert len(results) == 1
    assert results[0].title == "mistralai/Mistral-7B-Instruct-v0.3"


@pytest.mark.asyncio
async def test_search_handles_empty_response() -> None:
    async def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=[], request=request)

    async with _client(handler) as http_client:
        results = await search(_query(), http_client=http_client)

    assert results == []


@pytest.mark.asyncio
async def test_search_returns_empty_on_http_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    logger = _Logger()
    monkeypatch.setattr(MODULE, "LOGGER", logger)

    async def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(500, json={"error": "boom"}, request=request)

    async with _client(handler) as http_client:
        results = await search(_query(), http_client=http_client)

    assert results == []
    assert logger.events
    assert logger.events[0][0] == "huggingface_hub_search_failed"
    assert "500" in str(logger.events[0][1]["reason"])


@pytest.mark.asyncio
async def test_search_truncates_long_text_to_snippet() -> None:
    pipeline_tag = ("word " * 70).strip()
    raw_snippet = (
        f"{pipeline_tag} · transformers · 1 downloads · 1 likes · tags: transformers, safetensors"
    )

    async def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json=[
                {
                    "id": "org/long-model",
                    "downloads": 1,
                    "likes": 1,
                    "pipeline_tag": pipeline_tag,
                    "library_name": "transformers",
                    "tags": ["transformers", "safetensors"],
                    "private": False,
                }
            ],
            request=request,
        )

    async with _client(handler) as http_client:
        results = await search(_query(), http_client=http_client)

    assert len(results) == 1
    assert results[0].snippet == _truncate_expected(raw_snippet)
    assert results[0].snippet is not None
    assert results[0].snippet.endswith("…")


@pytest.mark.asyncio
async def test_search_skips_private_models() -> None:
    async def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json=[
                {
                    "id": "org/private-model",
                    "downloads": 10,
                    "likes": 5,
                    "pipeline_tag": "text-generation",
                    "library_name": "transformers",
                    "tags": ["private"],
                    "private": True,
                },
                {
                    "id": "org/public-model",
                    "downloads": 11,
                    "likes": 6,
                    "pipeline_tag": "text-generation",
                    "library_name": "transformers",
                    "tags": ["public"],
                    "private": False,
                },
            ],
            request=request,
        )

    async with _client(handler) as http_client:
        results = await search(_query(), http_client=http_client)

    assert [item.title for item in results] == ["org/public-model"]


@pytest.mark.asyncio
async def test_search_synthesizes_snippet_from_tags_and_stats() -> None:
    async def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json=[
                {
                    "id": "sentence-transformers/all-MiniLM-L6-v2",
                    "downloads": 1000000,
                    "likes": 12345,
                    "pipeline_tag": "feature-extraction",
                    "library_name": "sentence-transformers",
                    "tags": [
                        "sentence-transformers",
                        "embeddings",
                        "retrieval",
                        "transformers",
                        "safetensors",
                        "ignored-extra-tag",
                    ],
                    "private": False,
                }
            ],
            request=request,
        )

    async with _client(handler) as http_client:
        results = await search(_query(), http_client=http_client)

    assert len(results) == 1
    assert (
        results[0].snippet
        == "feature-extraction · sentence-transformers · 1,000,000 downloads · 12,345 "
        "likes · tags: sentence-transformers, embeddings, retrieval, transformers, "
        "safetensors"
    )
