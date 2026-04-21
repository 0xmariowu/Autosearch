from __future__ import annotations

from datetime import UTC, datetime
from urllib.parse import urlparse

import httpx
import structlog

LOGGER = structlog.get_logger(__name__).bind(component="tool", skill="fetch-jina")

DEFAULT_TIMEOUT_SECONDS = 30.0
JINA_READER_PREFIX = "https://r.jina.ai/"
ANTI_BOT_STATUS_CODES = {401, 403, 418, 429, 451}
ANTI_BOT_DOMAINS = (
    "zhihu.com",
    "xiaohongshu.com",
    "xhslink.com",
)
ANTI_BOT_MARKERS = (
    "access denied",
    "anti-bot",
    "blocked",
    "captcha",
    "forbidden",
    "login required",
    "robot",
    "security verification",
    "verify you are human",
    "安全验证",
    "访问验证",
)

FetchJinaResult = dict[str, object]


async def fetch(
    url: str,
    *,
    timeout_seconds: float = DEFAULT_TIMEOUT_SECONDS,
    http_client: httpx.AsyncClient | None = None,
) -> FetchJinaResult:
    """Fetch a public URL as Markdown via Jina Reader."""
    reader_url = build_reader_url(url)

    try:
        response = await _get(reader_url, timeout_seconds=timeout_seconds, http_client=http_client)
    except httpx.TimeoutException as exc:
        LOGGER.warning("fetch_jina_timeout", url=url, reason=str(exc))
        return _failure(
            url=url,
            reader_url=reader_url,
            reason="timeout",
            message="Jina Reader request timed out",
        )
    except httpx.HTTPError as exc:
        LOGGER.warning("fetch_jina_http_error", url=url, reason=str(exc))
        return _failure(
            url=url,
            reader_url=reader_url,
            reason="network_error",
            message=str(exc) or exc.__class__.__name__,
        )
    except Exception as exc:  # pragma: no cover - defensive boundary for runtime tools
        LOGGER.warning("fetch_jina_unexpected_error", url=url, reason=str(exc))
        return _failure(
            url=url,
            reader_url=reader_url,
            reason="network_error",
            message=str(exc) or exc.__class__.__name__,
        )

    status_code = response.status_code
    markdown = response.text
    content_type = response.headers.get("content-type")
    title = _extract_title(markdown)

    if status_code >= 400:
        if _looks_like_jina_refusal(url=url, status_code=status_code, body=markdown):
            return _failure(
                url=url,
                reader_url=reader_url,
                reason="jina_refused",
                message=f"Jina Reader refused or could not access the target URL ({status_code})",
                status=status_code,
                title=title,
                content_type=content_type,
                suggest_fallback="fetch-crawl4ai",
            )
        return _failure(
            url=url,
            reader_url=reader_url,
            reason="http_status",
            message=f"Jina Reader returned HTTP {status_code}",
            status=status_code,
            title=title,
            content_type=content_type,
        )

    return {
        "ok": True,
        "url": url,
        "reader_url": reader_url,
        "markdown": markdown,
        "metadata": _metadata(
            status=status_code,
            title=title,
            content_type=content_type,
        ),
    }


def build_reader_url(url: str) -> str:
    return f"{JINA_READER_PREFIX}{url}"


async def _get(
    reader_url: str,
    *,
    timeout_seconds: float,
    http_client: httpx.AsyncClient | None,
) -> httpx.Response:
    if http_client is not None:
        return await http_client.get(reader_url, timeout=timeout_seconds)

    async with httpx.AsyncClient(timeout=timeout_seconds, follow_redirects=True) as client:
        return await client.get(reader_url)


def _failure(
    *,
    url: str,
    reader_url: str,
    reason: str,
    message: str,
    status: int | None = None,
    title: str | None = None,
    content_type: str | None = None,
    suggest_fallback: str | None = None,
) -> FetchJinaResult:
    result: FetchJinaResult = {
        "ok": False,
        "url": url,
        "reader_url": reader_url,
        "markdown": None,
        "reason": reason,
        "message": message,
        "metadata": _metadata(status=status, title=title, content_type=content_type),
    }
    if suggest_fallback is not None:
        result["suggest_fallback"] = suggest_fallback
    return result


def _metadata(
    *,
    status: int | None,
    title: str | None,
    content_type: str | None,
) -> dict[str, object]:
    metadata: dict[str, object] = {
        "title": title,
        "fetched_at": datetime.now(UTC).isoformat().replace("+00:00", "Z"),
        "status": status,
    }
    if content_type is not None:
        metadata["content_type"] = content_type
    return metadata


def _extract_title(markdown: str) -> str | None:
    for line in markdown.splitlines():
        stripped = line.strip()
        if not stripped:
            continue
        lower = stripped.lower()
        if lower.startswith("title:"):
            return stripped.split(":", maxsplit=1)[1].strip() or None
        if stripped.startswith("#"):
            return stripped.lstrip("#").strip() or None
    return None


def _looks_like_jina_refusal(*, url: str, status_code: int, body: str) -> bool:
    if status_code not in ANTI_BOT_STATUS_CODES:
        return False

    normalized_body = body.lower()
    if any(marker in normalized_body for marker in ANTI_BOT_MARKERS):
        return True

    hostname = urlparse(url).hostname or ""
    return any(hostname == domain or hostname.endswith(f".{domain}") for domain in ANTI_BOT_DOMAINS)
