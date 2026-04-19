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
        / "skills"
        / "channels"
        / "github"
        / "methods"
        / "search_public_repos.py"
    )
    spec = importlib.util.spec_from_file_location("test_github_search_public_repos", module_path)
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
    return SubQuery(text="agent framework", rationale="Need public GitHub repo coverage")


def _client(handler) -> httpx.AsyncClient:
    return httpx.AsyncClient(transport=httpx.MockTransport(handler))


@pytest.mark.asyncio
async def test_search_maps_github_repos_to_evidence() -> None:
    async def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.params["q"] == "agent framework"
        assert request.url.params["per_page"] == "10"
        assert request.url.params["sort"] == "stars"
        assert request.url.params["order"] == "desc"
        return httpx.Response(
            200,
            json={
                "total_count": 2,
                "items": [
                    {
                        "full_name": "openai/autosearch",
                        "html_url": "https://github.com/openai/autosearch",
                        "description": "Autonomous search orchestration.",
                        "language": "Python",
                    },
                    {
                        "full_name": "acme/agent-ui",
                        "html_url": "https://github.com/acme/agent-ui",
                        "description": "Frontend for agent workflows.",
                        "language": "TypeScript",
                    },
                ],
            },
            request=request,
        )

    async with _client(handler) as http_client:
        results = await search(_query(), http_client=http_client)

    assert len(results) == 2

    first = results[0]
    assert first.url == "https://github.com/openai/autosearch"
    assert first.title == "openai/autosearch"
    assert first.snippet == "Autonomous search orchestration."
    assert first.content == "Autonomous search orchestration."
    assert first.source_channel == "github:public:Python"

    second = results[1]
    assert second.url == "https://github.com/acme/agent-ui"
    assert second.title == "acme/agent-ui"
    assert second.snippet == "Frontend for agent workflows."
    assert second.content == "Frontend for agent workflows."
    assert second.source_channel == "github:public:TypeScript"


@pytest.mark.asyncio
async def test_search_handles_null_language() -> None:
    async def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={
                "total_count": 1,
                "items": [
                    {
                        "full_name": "owner/repo",
                        "html_url": "https://github.com/owner/repo",
                        "description": "Language omitted.",
                        "language": None,
                    }
                ],
            },
            request=request,
        )

    async with _client(handler) as http_client:
        results = await search(_query(), http_client=http_client)

    assert len(results) == 1
    assert results[0].source_channel == "github:public:unknown"


@pytest.mark.asyncio
async def test_search_sets_user_agent_and_accept_headers() -> None:
    captured: dict[str, str] = {}

    async def handler(request: httpx.Request) -> httpx.Response:
        captured["user_agent"] = request.headers.get("user-agent", "")
        captured["accept"] = request.headers.get("accept", "")
        captured["api_version"] = request.headers.get("x-github-api-version", "")
        return httpx.Response(200, json={"total_count": 0, "items": []}, request=request)

    async with _client(handler) as http_client:
        await search(_query(), http_client=http_client)

    assert captured["user_agent"].startswith("autosearch/")
    assert "application/vnd.github+json" in captured["accept"]
    assert captured["api_version"] == "2022-11-28"


@pytest.mark.asyncio
async def test_search_returns_empty_on_http_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    logger = _Logger()
    monkeypatch.setattr(MODULE, "LOGGER", logger)

    async def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(403, json={"message": "rate limited"}, request=request)

    async with _client(handler) as http_client:
        results = await search(_query(), http_client=http_client)

    assert results == []
    assert logger.events
    assert logger.events[0][0] == "github_search_public_repos_failed"
    assert "403" in str(logger.events[0][1]["reason"])


@pytest.mark.asyncio
async def test_search_returns_empty_on_malformed_payload(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    logger = _Logger()
    monkeypatch.setattr(MODULE, "LOGGER", logger)

    async def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"total_count": 0}, request=request)

    async with _client(handler) as http_client:
        results = await search(_query(), http_client=http_client)

    assert results == []
    assert logger.events == [
        (
            "github_search_public_repos_failed",
            {"reason": "invalid items payload"},
        )
    ]
