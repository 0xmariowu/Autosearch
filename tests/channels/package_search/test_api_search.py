# Self-written for task F201
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
        / "package_search"
        / "methods"
        / "api_search.py"
    )
    spec = importlib.util.spec_from_file_location("test_package_search_api_search", module_path)
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


def _query(text: str) -> SubQuery:
    return SubQuery(text=text, rationale="Need package registry coverage")


def _client(handler) -> httpx.AsyncClient:
    return httpx.AsyncClient(transport=httpx.MockTransport(handler))


@pytest.mark.asyncio
async def test_search_combines_npm_and_pypi_results() -> None:
    async def handler(request: httpx.Request) -> httpx.Response:
        assert request.headers["accept"] == "application/json"
        assert request.headers["user-agent"] == MODULE.USER_AGENT

        if request.url.host == "registry.npmjs.org":
            assert request.url.params["text"] == "fastapi"
            assert request.url.params["size"] == "10"
            return httpx.Response(
                200,
                json={
                    "total": 1,
                    "objects": [
                        {
                            "package": {
                                "name": "fastify",
                                "description": "Fast and low overhead web framework, for Node.js",
                                "version": "5.1.0",
                                "links": {
                                    "npm": "https://www.npmjs.com/package/fastify",
                                },
                            }
                        }
                    ],
                },
                request=request,
            )

        assert request.url.host == "pypi.org"
        assert request.url.path == "/pypi/fastapi/json"
        return httpx.Response(
            200,
            json={
                "info": {
                    "name": "fastapi",
                    "summary": "FastAPI framework, high performance, easy to learn.",
                    "package_url": "https://pypi.org/project/fastapi/",
                    "version": "0.115.0",
                }
            },
            request=request,
        )

    async with _client(handler) as http_client:
        results = await search(_query("fastapi"), http_client=http_client)

    assert [item.source_channel for item in results] == [
        "package_search:npm",
        "package_search:pypi",
    ]
    assert [item.title for item in results] == [
        "fastify 5.1.0",
        "fastapi 0.115.0",
    ]


@pytest.mark.asyncio
async def test_pypi_single_token_exact_lookup_maps_to_evidence() -> None:
    async def handler(request: httpx.Request) -> httpx.Response:
        if request.url.host == "registry.npmjs.org":
            return httpx.Response(200, json={"total": 0, "objects": []}, request=request)

        assert request.url.path == "/pypi/fastapi/json"
        return httpx.Response(
            200,
            json={
                "info": {
                    "name": "fastapi",
                    "summary": "FastAPI framework, high performance, easy to learn.",
                    "home_page": "https://github.com/fastapi/fastapi",
                    "package_url": "https://pypi.org/project/fastapi/",
                    "version": "0.115.0",
                }
            },
            request=request,
        )

    async with _client(handler) as http_client:
        results = await search(_query("fastapi"), http_client=http_client)

    assert len(results) == 1
    assert results[0].url == "https://pypi.org/project/fastapi/"
    assert results[0].title == "fastapi 0.115.0"
    assert results[0].snippet == "FastAPI framework, high performance, easy to learn."
    assert results[0].content == "FastAPI framework, high performance, easy to learn."
    assert results[0].source_channel == "package_search:pypi"


@pytest.mark.asyncio
async def test_pypi_404_is_silent_no_warning_log(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    logger = _Logger()
    monkeypatch.setattr(MODULE, "LOGGER", logger)

    async def handler(request: httpx.Request) -> httpx.Response:
        if request.url.host == "registry.npmjs.org":
            return httpx.Response(200, json={"total": 0, "objects": []}, request=request)

        return httpx.Response(404, json={"message": "Not Found"}, request=request)

    async with _client(handler) as http_client:
        results = await search(_query("missingpkg"), http_client=http_client)

    assert results == []
    assert logger.events == []


@pytest.mark.asyncio
async def test_pypi_splits_multi_word_query_into_tokens() -> None:
    requested_tokens: list[str] = []

    async def handler(request: httpx.Request) -> httpx.Response:
        if request.url.host == "registry.npmjs.org":
            return httpx.Response(200, json={"total": 0, "objects": []}, request=request)

        requested_tokens.append(request.url.path.split("/")[2])
        return httpx.Response(404, json={"message": "Not Found"}, request=request)

    async with _client(handler) as http_client:
        await search(_query("llm agent framework"), http_client=http_client)

    assert sorted(requested_tokens) == ["agent", "framework", "llm"]


@pytest.mark.asyncio
async def test_pypi_caps_at_max_pypi_tokens() -> None:
    requested_tokens: list[str] = []

    async def handler(request: httpx.Request) -> httpx.Response:
        if request.url.host == "registry.npmjs.org":
            return httpx.Response(200, json={"total": 0, "objects": []}, request=request)

        requested_tokens.append(request.url.path.split("/")[2])
        return httpx.Response(404, json={"message": "Not Found"}, request=request)

    async with _client(handler) as http_client:
        await search(
            _query("one two three four five six seven eight nine ten"),
            http_client=http_client,
            max_pypi_tokens=5,
        )

    assert sorted(requested_tokens) == ["five", "four", "one", "three", "two"]


@pytest.mark.asyncio
async def test_npm_maps_objects_list_to_evidence() -> None:
    async def handler(request: httpx.Request) -> httpx.Response:
        if request.url.host == "registry.npmjs.org":
            return httpx.Response(
                200,
                json={
                    "total": 2,
                    "objects": [
                        {
                            "package": {
                                "name": "express",
                                "description": "Fast, unopinionated, minimalist web framework",
                                "version": "4.21.2",
                                "links": {
                                    "npm": "https://www.npmjs.com/package/express",
                                },
                            }
                        },
                        {
                            "package": {
                                "name": "vite",
                                "description": "Next generation frontend tooling",
                                "version": "5.4.0",
                                "links": {
                                    "npm": "https://www.npmjs.com/package/vite",
                                },
                            }
                        },
                    ],
                },
                request=request,
            )

        return httpx.Response(404, json={"message": "Not Found"}, request=request)

    async with _client(handler) as http_client:
        results = await search(_query("frontend tooling"), http_client=http_client)

    assert len(results) == 2
    assert [item.url for item in results] == [
        "https://www.npmjs.com/package/express",
        "https://www.npmjs.com/package/vite",
    ]
    assert [item.title for item in results] == [
        "express 4.21.2",
        "vite 5.4.0",
    ]
    assert [item.source_channel for item in results] == [
        "package_search:npm",
        "package_search:npm",
    ]


@pytest.mark.asyncio
async def test_search_returns_empty_on_both_failed(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    logger = _Logger()
    monkeypatch.setattr(MODULE, "LOGGER", logger)

    async def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(500, json={"message": "server error"}, request=request)

    async with _client(handler) as http_client:
        results = await search(_query("fastapi"), http_client=http_client)

    assert results == []
    assert len(logger.events) == 2
    assert {event for event, _ in logger.events} == {"package_search_source_failed"}

    reasons_by_source = {
        str(kwargs["source"]): str(kwargs["reason"]) for _, kwargs in logger.events
    }
    assert set(reasons_by_source) == {"npm", "pypi:fastapi"}
    assert "500" in reasons_by_source["npm"]
    assert "500" in reasons_by_source["pypi:fastapi"]
