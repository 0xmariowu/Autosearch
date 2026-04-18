# Self-written, plan autosearch-0418-channels-and-skills.md § F002a
from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path
from types import ModuleType

import pytest


def _load_module(module_name: str, path: Path) -> ModuleType:
    spec = importlib.util.spec_from_file_location(module_name, path)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    return module


def _cookie_manager_module() -> ModuleType:
    root = Path(__file__).resolve().parents[2]
    return _load_module(
        "test_cookie_manager_impl",
        root / "skills" / "tools" / "cookie-manager" / "impl.py",
    )


class _CapturingLogger:
    def __init__(self) -> None:
        self.infos: list[tuple[str, dict[str, object]]] = []
        self.warnings: list[tuple[str, dict[str, object]]] = []

    def info(self, event: str, **kwargs: object) -> None:
        self.infos.append((event, kwargs))

    def warning(self, event: str, **kwargs: object) -> None:
        self.warnings.append((event, kwargs))


def test_get_cookie_from_json_file(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    module = _cookie_manager_module()
    logger = _CapturingLogger()
    monkeypatch.setattr(module, "LOGGER", logger)

    cookies_dir = tmp_path / "cookies"
    cookies_dir.mkdir()
    expected = {"z_c0": "token-123", "sessionid": "value-456"}
    (cookies_dir / "zhihu.json").write_text(json.dumps(expected), encoding="utf-8")

    manager = module.CookieManager(cookies_dir=cookies_dir)

    assert manager.get_cookie("zhihu") == expected
    assert logger.infos == [("cookie_resolved", {"channel": "zhihu", "source": "file"})]
    assert logger.warnings == []


def test_get_cookie_returns_none_when_file_missing(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    module = _cookie_manager_module()
    logger = _CapturingLogger()
    monkeypatch.setattr(module, "LOGGER", logger)

    manager = module.CookieManager(cookies_dir=tmp_path / "cookies")

    assert manager.get_cookie("zhihu") is None
    assert logger.infos == [("cookie_unavailable", {"channel": "zhihu", "reason": "not_found"})]
    assert logger.warnings == []


def test_get_cookie_returns_none_and_warns_on_malformed_json(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    module = _cookie_manager_module()
    logger = _CapturingLogger()
    monkeypatch.setattr(module, "LOGGER", logger)

    cookies_dir = tmp_path / "cookies"
    cookies_dir.mkdir()
    (cookies_dir / "zhihu.json").write_text("{not-json", encoding="utf-8")

    manager = module.CookieManager(cookies_dir=cookies_dir, enable_keychain=False)

    assert manager.get_cookie("zhihu") is None
    assert logger.warnings == [
        ("cookie_source_failed", {"channel": "zhihu", "reason": "malformed_json"})
    ]
    assert logger.infos == [("cookie_unavailable", {"channel": "zhihu", "reason": "not_found"})]


def test_get_cookie_does_not_log_values(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    module = _cookie_manager_module()
    logger = _CapturingLogger()
    monkeypatch.setattr(module, "LOGGER", logger)

    secret_value = "supersecret-cookie-value"
    cookies_dir = tmp_path / "cookies"
    cookies_dir.mkdir()
    (cookies_dir / "zhihu.json").write_text(
        json.dumps({"sessionid": secret_value}),
        encoding="utf-8",
    )

    manager = module.CookieManager(cookies_dir=cookies_dir)

    assert manager.get_cookie("zhihu") == {"sessionid": secret_value}
    serialized_logs = " ".join(
        [event + repr(kwargs) for event, kwargs in logger.infos + logger.warnings]
    )
    assert secret_value not in serialized_logs


def test_has_cookie_matches_get_cookie(tmp_path: Path) -> None:
    module = _cookie_manager_module()

    cookies_dir = tmp_path / "cookies"
    cookies_dir.mkdir()
    (cookies_dir / "zhihu.json").write_text(json.dumps({"sessionid": "abc"}), encoding="utf-8")

    manager = module.CookieManager(cookies_dir=cookies_dir, enable_keychain=False)

    assert manager.has_cookie("zhihu") is True
    assert manager.has_cookie("weibo") is False


def test_keychain_disabled_on_non_darwin(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    module = _cookie_manager_module()
    manager = module.CookieManager(cookies_dir=tmp_path / "cookies")
    called = False

    def _unexpected(_: str) -> dict[str, str] | None:
        nonlocal called
        called = True
        return {"sessionid": "should-not-happen"}

    monkeypatch.setattr(module.sys, "platform", "linux")
    monkeypatch.setattr(manager, "_load_from_keychain", _unexpected)

    assert manager.get_cookie("zhihu") is None
    assert called is False


def test_rookiepy_lazy_import_failure_is_handled(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    module = _cookie_manager_module()
    logger = _CapturingLogger()
    monkeypatch.setattr(module, "LOGGER", logger)

    def _import_module(name: str) -> ModuleType:
        if name == "rookiepy":
            raise ImportError("boom")
        raise AssertionError(f"unexpected import: {name}")

    monkeypatch.setattr(module.importlib, "import_module", _import_module)
    manager = module.CookieManager(
        cookies_dir=tmp_path / "cookies",
        enable_keychain=False,
        enable_rookiepy=True,
    )

    assert manager.get_cookie("zhihu") is None
    assert ("cookie_source_failed", {"channel": "zhihu", "reason": "rookiepy_import_error"}) in (
        logger.warnings
    )
