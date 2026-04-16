from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import sys
import time
import types
from http.cookiejar import Cookie, LWPCookieJar
from pathlib import Path

REPO = "https://github.com/1dot75cm/xueqiu"
PLATFORM = "xueqiu"
PATH_ID = "xueqiu__1dot75cm"
WORKSPACE_REPO = Path("/tmp/as-matrix/xueqiu")
COOKIE_HOME = Path("/tmp/as-matrix/xueqiu-cookie-home")


def _result_payload(
    query: str, query_category: str, elapsed_ms: int, **extra: object
) -> dict[str, object]:
    payload: dict[str, object] = {
        "platform": PLATFORM,
        "path_id": PATH_ID,
        "repo": REPO,
        "query": query,
        "query_category": query_category,
        "total_ms": elapsed_ms,
        "anti_bot_signals": [],
    }
    payload.update(extra)
    return payload


def _clean_text(value: object) -> str:
    return " ".join(str(value or "").split())


def _extract_item_text(item: object) -> str:
    if isinstance(item, str):
        return _clean_text(item)
    if isinstance(item, dict):
        for key in ("title", "text", "name", "symbol", "description", "target"):
            value = item.get(key)
            if value:
                return _clean_text(value)
        return _clean_text(json.dumps(item, ensure_ascii=False))

    for key in ("title", "text", "name", "symbol", "description", "target"):
        value = getattr(item, key, None)
        if value:
            return _clean_text(value)

    return _clean_text(repr(item))


def _summarize_items(
    items: list[object], max_items: int = 20
) -> tuple[int, int, str | None]:
    limited_items = list(items[:max_items])
    if not limited_items:
        return 0, 0, None

    texts = [_extract_item_text(item) for item in limited_items]
    avg_len = int(sum(len(text) for text in texts) / len(texts))
    sample = texts[0][:200] if texts else None
    return len(limited_items), avg_len, sample or None


def _make_cookie(name: str, value: str, domain: str = ".xueqiu.com") -> Cookie:
    return Cookie(
        version=0,
        name=name,
        value=value,
        port=None,
        port_specified=False,
        domain=domain,
        domain_specified=True,
        domain_initial_dot=domain.startswith("."),
        path="/",
        path_specified=True,
        secure=False,
        expires=None,
        discard=True,
        comment=None,
        comment_url=None,
        rest={"HttpOnly": None},
        rfc2109=False,
    )


def _ensure_cookie_file() -> Path | None:
    cookie_text = ""
    for env_name in ("AS_MATRIX_XUEQIU_COOKIE", "XUEQIU_COOKIE"):
        cookie_text = os.environ.get(env_name, "").strip()
        if cookie_text:
            break

    cookie_path_value = ""
    for env_name in ("AS_MATRIX_XUEQIU_COOKIE_FILE", "XUEQIU_COOKIE_FILE"):
        cookie_path_value = os.environ.get(env_name, "").strip()
        if cookie_path_value:
            break

    target_file = COOKIE_HOME / ".xueqiu" / "cookie"
    target_file.parent.mkdir(parents=True, exist_ok=True)

    if cookie_path_value:
        source_file = Path(cookie_path_value)
        if not source_file.exists():
            raise FileNotFoundError(f"cookie file not found: {source_file}")
        shutil.copyfile(source_file, target_file)
        return target_file

    if cookie_text:
        jar = LWPCookieJar(str(target_file))
        for part in cookie_text.split(";"):
            name, _, value = part.strip().partition("=")
            if name and value:
                jar.set_cookie(_make_cookie(name, value))
        jar.save(ignore_discard=True, ignore_expires=True)
        return target_file

    return None


def _install_browsercookie_stub() -> None:
    if "browsercookie" in sys.modules:
        return
    stub = types.ModuleType("browsercookie")
    stub.load = lambda *args, **kwargs: []
    sys.modules["browsercookie"] = stub


def _classify_status(message: str) -> str:
    lowered = message.lower()
    if "timeout" in lowered:
        return "timeout"
    if any(token in lowered for token in ("cookie", "login", "webdriver", "chrome", "chromedriver")):
        return "needs_login"
    return "error"


def run(query: str, query_category: str) -> dict[str, object]:
    started = time.perf_counter()
    try:
        if not WORKSPACE_REPO.exists():
            raise FileNotFoundError(
                f"Repository not found at {WORKSPACE_REPO}; run setup.sh first."
            )

        cookie_file = _ensure_cookie_file()
        if cookie_file is None:
            elapsed_ms = int((time.perf_counter() - started) * 1000)
            return _result_payload(
                query,
                query_category,
                elapsed_ms,
                status="needs_login",
                items_returned=0,
                avg_content_len=0,
                sample=None,
                error=(
                    "needs_login: upstream xueqiu.search() expects a cookie jar; "
                    "provide XUEQIU_COOKIE or XUEQIU_COOKIE_FILE"
                ),
            )

        os.environ["TESTDIR"] = str(COOKIE_HOME)
        if str(WORKSPACE_REPO) not in sys.path:
            sys.path.insert(0, str(WORKSPACE_REPO))

        _install_browsercookie_stub()
        import xueqiu

        items: list[object] = []
        errors: list[str] = []
        for query_type, kwargs in (
            ("post", {"source": "all", "sort": "time"}),
            ("stock", {}),
        ):
            try:
                response = xueqiu.search(query=query, query_type=query_type, count=20, page=1, **kwargs)
                current_items = list((response or {}).get("list") or [])
                if current_items:
                    items = current_items
                    break
            except Exception as exc:
                errors.append(f"{query_type}: {type(exc).__name__}: {exc}")

        if not items and errors:
            raise RuntimeError(" ; ".join(errors))

        items_returned, avg_content_len, sample = _summarize_items(items)
        elapsed_ms = int((time.perf_counter() - started) * 1000)
        return _result_payload(
            query,
            query_category,
            elapsed_ms,
            status="ok" if items_returned else "empty",
            items_returned=items_returned,
            avg_content_len=avg_content_len,
            sample=sample,
        )
    except Exception as exc:
        elapsed_ms = int((time.perf_counter() - started) * 1000)
        message = f"{type(exc).__name__}: {exc}"
        return _result_payload(
            query,
            query_category,
            elapsed_ms,
            status=_classify_status(message),
            error=message,
        )


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--query", required=True)
    parser.add_argument("--query-category", required=True)
    args = parser.parse_args()

    print(json.dumps(run(args.query, args.query_category), ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
