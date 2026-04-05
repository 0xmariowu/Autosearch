from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from lib.enrichment import JINA_READER_PREFIX, enrich_content


def _make_result(
    *,
    url: str = "https://example.com/article",
    source: str = "web",
    composite_score: float = 50,
) -> dict:
    return {
        "url": url,
        "title": "Test result",
        "snippet": "Snippet",
        "source": source,
        "query": "test query",
        "metadata": {"composite_score": composite_score},
    }


def _make_response(
    *,
    status_code: int = 200,
    is_error: bool = False,
    text: str = "",
) -> MagicMock:
    response = MagicMock()
    response.status_code = status_code
    response.is_error = is_error
    response.text = text
    return response


def _make_async_client(get_impl: AsyncMock) -> AsyncMock:
    mock_client = AsyncMock()
    mock_client.get = get_impl
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=False)
    return mock_client


@pytest.mark.asyncio
async def test_enrich_content_stores_extracted() -> None:
    result = _make_result()
    mock_response = _make_response(
        text=(
            "# Title\n\n"
            + ("Relevant paragraph about the topic. " * 6)
            + "\n\n"
            + ("Irrelevant footer text. " * 6)
        )
    )
    mock_client = _make_async_client(AsyncMock(return_value=mock_response))

    with (
        patch("lib.enrichment.httpx.AsyncClient", return_value=mock_client),
        patch(
            "lib.content_processing.filter_relevant_paragraphs",
            return_value="Filtered topic paragraph. " * 4,
        ),
    ):
        await enrich_content([result], "topic", max_items=1)

    assert result["metadata"]["extracted_content"] == "Filtered topic paragraph. " * 4


@pytest.mark.asyncio
async def test_enrich_content_skips_reddit() -> None:
    result = _make_result(source="reddit", url="https://reddit.com/r/test/comments/1")

    with patch("lib.enrichment.httpx.AsyncClient") as mock_async_client:
        await enrich_content([result], "topic", max_items=1)

    mock_async_client.assert_not_called()
    assert "extracted_content" not in result["metadata"]


@pytest.mark.asyncio
async def test_enrich_content_skips_low_score() -> None:
    result = _make_result(composite_score=29)

    with patch("lib.enrichment.httpx.AsyncClient") as mock_async_client:
        await enrich_content([result], "topic", max_items=1)

    mock_async_client.assert_not_called()
    assert "extracted_content" not in result["metadata"]


@pytest.mark.asyncio
async def test_enrich_content_bm25_filters() -> None:
    result = _make_result()
    original_text = (
        "# Title\n\n"
        + ("Relevant paragraph about the topic. " * 8)
        + "\n\n"
        + ("Irrelevant footer text. " * 12)
    )
    filtered_text = "Relevant paragraph about the topic. " * 4
    mock_response = _make_response(text=original_text)
    mock_client = _make_async_client(AsyncMock(return_value=mock_response))

    with (
        patch("lib.enrichment.httpx.AsyncClient", return_value=mock_client),
        patch(
            "lib.content_processing.filter_relevant_paragraphs",
            return_value=filtered_text,
        ),
    ):
        await enrich_content([result], "topic", max_items=1)

    assert result["metadata"]["extracted_content"] == filtered_text
    assert len(result["metadata"]["extracted_content"]) < len(original_text)


@pytest.mark.asyncio
async def test_enrich_content_fallback_httpx() -> None:
    result = _make_result()
    jina_error = _make_response(status_code=502, is_error=True, text="bad gateway")
    direct_html = _make_response(
        text=(
            "<html><body><article>"
            + ("Direct fallback content about the topic. " * 6)
            + "</article></body></html>"
        )
    )
    mock_client = _make_async_client(AsyncMock(side_effect=[jina_error, direct_html]))

    with (
        patch("lib.enrichment.httpx.AsyncClient", return_value=mock_client),
        patch("lib.content_processing.is_blocked", return_value=(False, "")),
        patch(
            "lib.content_processing.prune_html",
            return_value="Direct fallback content about the topic. " * 6,
        ),
        patch(
            "lib.content_processing.filter_relevant_paragraphs",
            return_value="Direct fallback content about the topic. " * 4,
        ),
    ):
        await enrich_content([result], "topic", max_items=1)

    assert result["metadata"]["extracted_content"] == (
        "Direct fallback content about the topic. " * 4
    )
    assert mock_client.get.await_count == 2
    assert (
        mock_client.get.await_args_list[0].args[0]
        == f"{JINA_READER_PREFIX}{result['url']}"
    )
    assert mock_client.get.await_args_list[1].args[0] == result["url"]


@pytest.mark.asyncio
async def test_enrich_content_bail_on_429() -> None:
    first = _make_result(url="https://example.com/first", composite_score=90)
    second = _make_result(url="https://example.com/second", composite_score=80)
    rate_limited = _make_response(status_code=429, is_error=True, text="")
    mock_client = _make_async_client(AsyncMock(return_value=rate_limited))

    async def gather_sequential(*aws, return_exceptions=False):
        results = []
        for awaitable in aws:
            try:
                results.append(await awaitable)
            except Exception as exc:
                if return_exceptions:
                    results.append(exc)
                else:
                    raise
        return results

    with (
        patch("lib.enrichment.httpx.AsyncClient", return_value=mock_client),
        patch("lib.enrichment.asyncio.create_task", side_effect=lambda coro: coro),
        patch("lib.enrichment.asyncio.gather", side_effect=gather_sequential),
    ):
        await enrich_content([first, second], "topic", max_items=2)

    assert mock_client.get.await_count == 1
    assert "extracted_content" not in first["metadata"]
    assert "extracted_content" not in second["metadata"]


@pytest.mark.asyncio
async def test_enrich_content_empty_results() -> None:
    await enrich_content([], "topic")


@pytest.mark.asyncio
async def test_enrich_content_truncates_to_3000() -> None:
    result = _make_result()
    mock_response = _make_response(text="Source text " * 20)
    mock_client = _make_async_client(AsyncMock(return_value=mock_response))
    long_filtered = "x" * 3500

    with (
        patch("lib.enrichment.httpx.AsyncClient", return_value=mock_client),
        patch(
            "lib.content_processing.filter_relevant_paragraphs",
            return_value=long_filtered,
        ),
    ):
        await enrich_content([result], "topic", max_items=1)

    assert len(result["metadata"]["extracted_content"]) == 3000
    assert result["metadata"]["extracted_content"] == long_filtered[:3000]
