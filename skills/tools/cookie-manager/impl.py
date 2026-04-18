# Self-written, plan autosearch-0418-channels-and-skills.md § F002a
from __future__ import annotations

import importlib
import json
import subprocess
import sys
from collections.abc import Iterable, Mapping
from pathlib import Path
from typing import Any

import structlog

LOGGER = structlog.get_logger(__name__).bind(component="cookie_manager")


class CookieManager:
    """Resolve per-channel cookie from: ~/.autosearch/cookies/{channel}.json → keychain → rookiepy.

    Security: never log cookie values. Log channel name + source only.
    """

    def __init__(
        self,
        cookies_dir: Path | None = None,
        enable_keychain: bool = True,
        enable_rookiepy: bool = False,
    ) -> None:
        self.cookies_dir = (
            cookies_dir if cookies_dir is not None else Path("~/.autosearch/cookies").expanduser()
        )
        self.enable_keychain = enable_keychain
        self.enable_rookiepy = enable_rookiepy

    def get_cookie(self, channel: str) -> dict[str, str] | None:
        """Return a cookie dict (name→value) or None if unavailable.

        Sources tried in order: cookies_dir (file-based json) → keychain (macOS only,
        stub for non-darwin) → rookiepy (if enabled, lazy-imported).
        """

        cookie = self._load_from_file(channel)
        if cookie is not None:
            LOGGER.info("cookie_resolved", channel=channel, source="file")
            return cookie

        if self.enable_keychain and sys.platform == "darwin":
            cookie = self._load_from_keychain(channel)
            if cookie is not None:
                LOGGER.info("cookie_resolved", channel=channel, source="keychain")
                return cookie

        if self.enable_rookiepy:
            cookie = self._load_from_rookiepy(channel)
            if cookie is not None:
                LOGGER.info("cookie_resolved", channel=channel, source="rookiepy")
                return cookie

        LOGGER.info("cookie_unavailable", channel=channel, reason="not_found")
        return None

    def has_cookie(self, channel: str) -> bool:
        return self.get_cookie(channel) is not None

    def _load_from_file(self, channel: str) -> dict[str, str] | None:
        cookie_path = self.cookies_dir / f"{channel}.json"
        if not cookie_path.is_file():
            return None

        try:
            raw_text = cookie_path.read_text(encoding="utf-8")
        except OSError:
            LOGGER.warning("cookie_source_failed", channel=channel, reason="file_read_error")
            return None

        return self._parse_cookie_payload(
            raw_text,
            channel=channel,
            malformed_reason="malformed_json",
            empty_reason="empty_json",
            invalid_reason="invalid_cookie_mapping",
        )

    def _load_from_keychain(self, channel: str) -> dict[str, str] | None:
        for service_name in (
            f"autosearch.cookie.{channel}",
            f"autosearch.{channel}",
            channel,
        ):
            try:
                result = subprocess.run(
                    [
                        "security",
                        "find-generic-password",
                        "-s",
                        service_name,
                        "-a",
                        channel,
                        "-w",
                    ],
                    check=False,
                    capture_output=True,
                    text=True,
                )
            except OSError:
                LOGGER.warning(
                    "cookie_source_failed", channel=channel, reason="keychain_unavailable"
                )
                return None

            if result.returncode != 0:
                continue

            return self._parse_cookie_payload(
                result.stdout,
                channel=channel,
                malformed_reason="keychain_malformed_json",
                empty_reason="keychain_empty_json",
                invalid_reason="keychain_invalid_cookie_mapping",
            )

        return None

    def _load_from_rookiepy(self, channel: str) -> dict[str, str] | None:
        try:
            rookiepy = importlib.import_module("rookiepy")
        except ImportError:
            LOGGER.warning("cookie_source_failed", channel=channel, reason="rookiepy_import_error")
            return None

        for loader_name in (
            "chrome",
            "chromium",
            "brave",
            "edge",
            "firefox",
            "opera",
            "safari",
        ):
            loader = getattr(rookiepy, loader_name, None)
            if not callable(loader):
                continue

            cookies = self._call_rookiepy_loader(loader, channel)
            normalized = self._normalize_rookiepy_cookies(cookies, channel)
            if normalized:
                return normalized

        LOGGER.warning("cookie_source_failed", channel=channel, reason="rookiepy_no_cookie")
        return None

    def _call_rookiepy_loader(self, loader: Any, channel: str) -> object | None:
        call_specs = (
            {"domains": [channel]},
            {"domain_name": channel},
            {},
        )
        for kwargs in call_specs:
            try:
                return loader(**kwargs)
            except TypeError:
                continue
            except Exception:
                return None

        try:
            return loader(channel)
        except TypeError:
            return None
        except Exception:
            return None

    def _normalize_rookiepy_cookies(
        self,
        cookies: object | None,
        channel: str,
    ) -> dict[str, str] | None:
        if cookies is None:
            return None

        if isinstance(cookies, Mapping):
            normalized = self._coerce_cookie_mapping(cookies)
            return normalized if normalized else None

        if not isinstance(cookies, Iterable) or isinstance(cookies, str | bytes):
            return None

        normalized: dict[str, str] = {}
        for entry in cookies:
            name: object | None = None
            value: object | None = None
            domain: object | None = None

            if isinstance(entry, Mapping):
                name = entry.get("name")
                value = entry.get("value")
                domain = entry.get("domain")
            else:
                name = getattr(entry, "name", None)
                value = getattr(entry, "value", None)
                domain = getattr(entry, "domain", None)

            if not isinstance(name, str) or not isinstance(value, str):
                continue
            if isinstance(domain, str) and channel not in domain:
                continue
            normalized[name] = value

        return normalized or None

    def _parse_cookie_payload(
        self,
        raw_text: str,
        *,
        channel: str,
        malformed_reason: str,
        empty_reason: str,
        invalid_reason: str,
    ) -> dict[str, str] | None:
        try:
            payload = json.loads(raw_text)
        except json.JSONDecodeError:
            LOGGER.warning("cookie_source_failed", channel=channel, reason=malformed_reason)
            return None

        normalized = self._coerce_cookie_mapping(payload)
        if normalized is None:
            reason = empty_reason if payload == {} else invalid_reason
            LOGGER.warning("cookie_source_failed", channel=channel, reason=reason)
            return None

        return normalized

    def _coerce_cookie_mapping(self, payload: object) -> dict[str, str] | None:
        if not isinstance(payload, Mapping) or not payload:
            return None

        normalized: dict[str, str] = {}
        for name, value in payload.items():
            if not isinstance(name, str) or not isinstance(value, str):
                return None
            normalized[name] = value
        return normalized
