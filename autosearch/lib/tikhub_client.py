from __future__ import annotations

import asyncio
import os
import re
from collections.abc import Mapping

import httpx
import structlog

LOGGER = structlog.get_logger(__name__).bind(component="tikhub_client")

BASE_URL = "https://api.tikhub.io"
HTTP_TIMEOUT_SECONDS = 30.0
RETRYABLE_STATUS_CODES = {500, 502, 503, 504}
RETRY_DELAYS_SECONDS = (1.0, 2.0, 4.0)
SENSITIVE_KEY_PATTERN = re.compile(r"(authorization|token|auth|api[_-]?key)", re.IGNORECASE)
BEARER_PATTERN = re.compile(r"bearer\s+[a-z0-9._~+/=-]+", re.IGNORECASE)


class TikhubError(RuntimeError):
    """Base error for sanitized TikHub failures."""

    def __init__(
        self,
        message: str,
        *,
        status_code: int | None = None,
        detail: object | None = None,
    ) -> None:
        self.status_code = status_code
        self.detail = detail

        suffix = []
        if status_code is not None:
            suffix.append(f"status={status_code}")
        if detail is not None:
            suffix.append(f"detail={detail!r}")

        rendered = message if not suffix else f"{message} ({', '.join(suffix)})"
        super().__init__(rendered)


class TikhubBudgetExhausted(TikhubError):
    """Raised when TikHub rejects a request due to exhausted credit."""


class TikhubRateLimited(TikhubError):
    """Raised when TikHub reports the caller is rate limited."""


class TikhubUpstreamError(TikhubError):
    """Raised when TikHub returns a known upstream validation or auth failure."""


def _is_sensitive_key(key: str, *, extra_sensitive_keys: frozenset[str]) -> bool:
    return key in extra_sensitive_keys or bool(SENSITIVE_KEY_PATTERN.search(key))


def _sanitize_json(
    value: object,
    *,
    parent_key: str | None = None,
    extra_sensitive_keys: frozenset[str] = frozenset(),
) -> object:
    if isinstance(value, Mapping):
        sanitized: dict[str, object] = {}
        for raw_key, raw_value in value.items():
            key = str(raw_key)
            key_lower = key.lower()

            if parent_key == "detail" and key_lower == "headers":
                continue
            if _is_sensitive_key(key_lower, extra_sensitive_keys=extra_sensitive_keys):
                sanitized[key] = "[REDACTED]"
                continue

            sanitized[key] = _sanitize_json(
                raw_value,
                parent_key=key_lower,
                extra_sensitive_keys=extra_sensitive_keys,
            )
        return sanitized

    if isinstance(value, list):
        return [
            _sanitize_json(
                item,
                parent_key=parent_key,
                extra_sensitive_keys=extra_sensitive_keys,
            )
            for item in value
        ]

    if isinstance(value, str):
        return BEARER_PATTERN.sub("[REDACTED]", value)

    return value


def _sanitize_response_json(
    response: httpx.Response,
    *,
    extra_sensitive_keys: frozenset[str] = frozenset(),
) -> dict[str, object]:
    try:
        payload = response.json()
    except ValueError:
        return {"error": "non_json_response"}

    sanitized = _sanitize_json(payload, extra_sensitive_keys=extra_sensitive_keys)
    if isinstance(sanitized, dict):
        return sanitized

    return {"payload": sanitized}


def _normalize_base_url(base_url: str) -> str:
    return base_url[:-1] if base_url.endswith("/") else base_url


class TikhubClient:
    def __init__(
        self,
        api_key: str | None = None,
        base_url: str | None = None,
        proxy_token: str | None = None,
        http_client: httpx.AsyncClient | None = None,
    ) -> None:
        self.http_client = http_client
        explicit_base_url = _normalize_base_url(base_url) if base_url is not None else None
        proxy_url = os.getenv("AUTOSEARCH_PROXY_URL")
        env_proxy_url = _normalize_base_url(proxy_url) if proxy_url else None

        if explicit_base_url is not None and api_key is not None:
            self.base_url = explicit_base_url
            self._auth_header_value = f"Bearer {api_key}"
            return

        if explicit_base_url is not None and proxy_token is not None:
            self.base_url = explicit_base_url
            self._auth_header_value = f"Bearer {proxy_token}"
            return

        if env_proxy_url:
            resolved_proxy_token = proxy_token or os.getenv("AUTOSEARCH_PROXY_TOKEN")
            if not resolved_proxy_token:
                raise ValueError(
                    "AUTOSEARCH_PROXY_TOKEN is required when AUTOSEARCH_PROXY_URL is set."
                )

            self.base_url = explicit_base_url or env_proxy_url
            self._auth_header_value = f"Bearer {resolved_proxy_token}"
            return

        tikhub_base_url = os.getenv("TIKHUB_BASE_URL")
        env_tikhub_base_url = _normalize_base_url(tikhub_base_url) if tikhub_base_url else None
        self.base_url = explicit_base_url or env_tikhub_base_url or BASE_URL

        resolved_api_key = api_key or os.getenv("TIKHUB_API_KEY")
        if not resolved_api_key:
            raise ValueError("TIKHUB_API_KEY is required for TikHub access.")

        self._auth_header_value = f"Bearer {resolved_api_key}"

    async def get(
        self,
        path: str,
        params: dict[str, object],
        extra_headers: dict[str, str] | None = None,
    ) -> dict[str, object]:
        url = self._build_url(path)
        headers = {"Authorization": self._auth_header_value}
        if extra_headers:
            headers.update(extra_headers)

        for attempt in range(len(RETRY_DELAYS_SECONDS) + 1):
            try:
                response = await self._request(url, headers=headers, params=params)
            except httpx.HTTPError as exc:
                raise TikhubError("TikHub request failed before receiving a response") from exc

            if response.status_code == 200:
                try:
                    payload = response.json()
                except ValueError as exc:
                    raise TikhubError(
                        "TikHub returned invalid JSON",
                        status_code=response.status_code,
                    ) from exc

                if not isinstance(payload, dict):
                    raise TikhubError(
                        "TikHub returned a non-object JSON payload",
                        status_code=response.status_code,
                        detail={"payload": _sanitize_json(payload)},
                    )

                return payload

            if response.status_code in RETRYABLE_STATUS_CODES and attempt < len(
                RETRY_DELAYS_SECONDS
            ):
                delay_seconds = RETRY_DELAYS_SECONDS[attempt]
                LOGGER.warning(
                    "tikhub_request_retry",
                    path=path,
                    status_code=response.status_code,
                    attempt=attempt + 1,
                    delay_seconds=delay_seconds,
                )
                await asyncio.sleep(delay_seconds)
                continue

            detail = _sanitize_response_json(response)
            raise self._error_for_status(path=path, status_code=response.status_code, detail=detail)

        raise AssertionError("unreachable")

    async def post(self, path: str, body: dict[str, object]) -> dict[str, object]:
        url = self._build_url(path)
        headers = {"Authorization": self._auth_header_value}

        for attempt in range(len(RETRY_DELAYS_SECONDS) + 1):
            try:
                response = await self._post_request(url, headers=headers, body=body)
            except httpx.HTTPError as exc:
                raise TikhubError("TikHub request failed before receiving a response") from exc

            if response.status_code == 200:
                try:
                    payload = response.json()
                except ValueError as exc:
                    raise TikhubError(
                        "TikHub returned invalid JSON",
                        status_code=response.status_code,
                    ) from exc

                if not isinstance(payload, dict):
                    raise TikhubError(
                        "TikHub returned a non-object JSON payload",
                        status_code=response.status_code,
                        detail={"payload": _sanitize_json(payload)},
                    )

                return payload

            if response.status_code in RETRYABLE_STATUS_CODES and attempt < len(
                RETRY_DELAYS_SECONDS
            ):
                delay_seconds = RETRY_DELAYS_SECONDS[attempt]
                LOGGER.warning(
                    "tikhub_request_retry",
                    path=path,
                    status_code=response.status_code,
                    attempt=attempt + 1,
                    delay_seconds=delay_seconds,
                )
                await asyncio.sleep(delay_seconds)
                continue

            detail = _sanitize_response_json(response)
            raise self._error_for_status(path=path, status_code=response.status_code, detail=detail)

        raise AssertionError("unreachable")

    async def check_balance(self) -> dict[str, object]:
        payload = await self.get("/api/v1/tikhub/user/get_user_daily_usage", {})
        sanitized = _sanitize_json(
            payload,
            extra_sensitive_keys=frozenset({"user_email"}),
        )
        if isinstance(sanitized, dict):
            return sanitized

        return {"payload": sanitized}

    def _build_url(self, path: str) -> str:
        normalized_path = path if path.startswith("/") else f"/{path}"
        # Callers pass full API paths, so only strip a duplicate /api/v1 when base_url already embeds it.
        if self.base_url.endswith("/api/v1") and (
            normalized_path == "/api/v1" or normalized_path.startswith("/api/v1/")
        ):
            normalized_path = normalized_path.removeprefix("/api/v1")

        return f"{self.base_url}{normalized_path}"

    async def _request(
        self,
        url: str,
        *,
        headers: dict[str, str],
        params: dict[str, object],
    ) -> httpx.Response:
        if self.http_client is not None:
            return await self.http_client.get(url, headers=headers, params=params)

        async with httpx.AsyncClient(timeout=HTTP_TIMEOUT_SECONDS) as client:
            return await client.get(url, headers=headers, params=params)

    async def _post_request(
        self,
        url: str,
        *,
        headers: dict[str, str],
        body: dict[str, object],
    ) -> httpx.Response:
        post_headers = {**headers, "Content-Type": "application/json"}
        if self.http_client is not None:
            return await self.http_client.post(url, headers=post_headers, json=body)

        async with httpx.AsyncClient(timeout=HTTP_TIMEOUT_SECONDS) as client:
            return await client.post(url, headers=post_headers, json=body)

    @staticmethod
    def _error_for_status(
        *,
        path: str,
        status_code: int,
        detail: dict[str, object],
    ) -> TikhubError:
        message = f"TikHub request to {path} failed"

        if status_code == 402:
            return TikhubBudgetExhausted(message, status_code=status_code, detail=detail)
        if status_code == 429:
            return TikhubRateLimited(message, status_code=status_code, detail=detail)
        if status_code in {400, 403, 422}:
            return TikhubUpstreamError(message, status_code=status_code, detail=detail)

        return TikhubError(message, status_code=status_code, detail=detail)
