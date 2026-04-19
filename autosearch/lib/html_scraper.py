# Self-written for task F204
from __future__ import annotations

import httpx
import structlog

LOGGER = structlog.get_logger(__name__).bind(component="html_scraper")

DEFAULT_USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 14_0) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
)
DEFAULT_TIMEOUT_SECONDS = 15.0


class HtmlFetchError(RuntimeError):
    """Sanitized fetch failure (status_code + url)."""

    def __init__(self, url: str, *, status_code: int | None = None, reason: str) -> None:
        self.url = url
        self.status_code = status_code
        self.reason = reason
        super().__init__(f"html fetch failed: {reason} (url={url}, status={status_code})")


async def fetch_html(
    url: str,
    *,
    http_client: httpx.AsyncClient | None = None,
    params: dict[str, str] | None = None,
    headers: dict[str, str] | None = None,
    timeout_seconds: float = DEFAULT_TIMEOUT_SECONDS,
) -> str:
    """Fetch HTML with a browser-like UA; raise HtmlFetchError on non-2xx or transport error.

    Caller-provided http_client is used for injection in tests; otherwise a new AsyncClient is built.
    """
    final_headers = {"User-Agent": DEFAULT_USER_AGENT}
    if headers:
        final_headers.update(headers)

    async def _fetch(client: httpx.AsyncClient) -> str:
        try:
            response = await client.get(url, params=params, headers=final_headers)
        except httpx.HTTPError as exc:
            raise HtmlFetchError(url, reason=str(exc)) from exc

        if response.status_code >= 400:
            raise HtmlFetchError(url, status_code=response.status_code, reason="http_error")
        return response.text

    if http_client is not None:
        return await _fetch(http_client)

    async with httpx.AsyncClient(timeout=timeout_seconds, follow_redirects=True) as client:
        return await _fetch(client)
