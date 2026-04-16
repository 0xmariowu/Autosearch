from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys
import time
from contextlib import contextmanager
from pathlib import Path

REPO = "https://github.com/Cialle/RedCrack"
PLATFORM = "xiaohongshu"
PATH_ID = "xiaohongshu__cialle_redcrack"
WORKSPACE_REPO = Path("/tmp/as-matrix/RedCrack")


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


def _status_from_error(message: str) -> str:
    lowered = message.lower()
    if any(token in lowered for token in ("timeout", "timed out")):
        return "timeout"
    if any(
        token in lowered
        for token in (
            "captcha",
            "verify",
            "slide",
            "滑块",
            "验证码",
            "461",
            "471",
            "406",
            "blockedps",
        )
    ):
        return "anti_bot"
    if any(
        token in lowered
        for token in (
            "login",
            "cookie",
            "token",
            "unauthorized",
            "permission",
            "needscanlogin",
            "401",
            "403",
        )
    ):
        return "needs_login"
    return "error"


def _extract_item_text(item: object) -> str:
    if isinstance(item, str):
        return item
    if not isinstance(item, dict):
        return str(item)

    note_card = item.get("note_card")
    if isinstance(note_card, dict):
        for key in ("display_title", "title", "desc", "content"):
            value = note_card.get(key)
            if value:
                return " ".join(str(value).split())[:300]

    for key in ("content", "desc", "body", "text", "title", "snippet", "summary"):
        value = item.get(key)
        if value:
            return " ".join(str(value).split())[:300]

    return json.dumps(item, ensure_ascii=False)[:300]


def _summarize_items(
    items: list[object], max_items: int = 20
) -> tuple[int, int, str | None]:
    limited_items = list(items[:max_items])
    if not limited_items:
        return 0, 0, None

    texts = [_extract_item_text(item) for item in limited_items]
    avg_len = int(sum(len(text) for text in texts) / len(texts))
    sample = texts[0][:200] if texts else None
    return len(limited_items), avg_len, sample


def _extract_items(response_json: object) -> list[object]:
    if not isinstance(response_json, dict):
        return []
    data = response_json.get("data")
    if not isinstance(data, dict):
        return []
    items = data.get("items")
    if not isinstance(items, list):
        return []
    return [
        item
        for item in items
        if isinstance(item, dict) and item.get("model_type") == "note"
    ]


@contextmanager
def _repo_cwd(path: Path):
    previous = Path.cwd()
    os.chdir(path)
    try:
        yield
    finally:
        os.chdir(previous)


async def _run(query: str, query_category: str) -> dict[str, object]:
    started = time.perf_counter()

    if not WORKSPACE_REPO.exists():
        elapsed_ms = int((time.perf_counter() - started) * 1000)
        return _result_payload(
            query,
            query_category,
            elapsed_ms,
            status="error",
            error=f"Repository not found at {WORKSPACE_REPO}; run setup.sh first.",
        )

    if str(WORKSPACE_REPO) not in sys.path:
        sys.path.insert(0, str(WORKSPACE_REPO))

    session = None
    try:
        with _repo_cwd(WORKSPACE_REPO):
            from request.web.xhs_session import create_xhs_session

            payload = {
                "keyword": query,
                "page": 1,
                "page_size": 20,
                "search_id": "codex",
                "sort": "general",
                "note_type": 0,
                "ext_flags": [],
                "geo": "",
                "image_formats": ["jpg", "webp", "avif"],
            }
            proxy = os.environ.get("AS_MATRIX_PROXY") or os.environ.get("HTTPS_PROXY")
            web_session = (
                os.environ.get("AS_MATRIX_REDXHS_WEB_SESSION")
                or os.environ.get("AS_MATRIX_XHS_WEB_SESSION")
                or os.environ.get("XIAOHONGSHU_WEB_SESSION")
            )
            session = await create_xhs_session(proxy=proxy, web_session=web_session)
            response = await session.request(
                "post",
                url="https://edith.xiaohongshu.com/api/sns/web/v1/search/notes",
                data=payload,
            )
            response_json = await response.json()

        items = _extract_items(response_json)
        items_returned, avg_content_len, sample = _summarize_items(items, max_items=20)
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
        error = f"{type(exc).__name__}: {exc}"
        return _result_payload(
            query,
            query_category,
            elapsed_ms,
            status=_status_from_error(error),
            error=error,
        )
    finally:
        if session is not None:
            try:
                await session.close_session()
            except Exception:
                pass


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--query", required=True)
    parser.add_argument("--query-category", required=True)
    payload = asyncio.run(_run(**vars(parser.parse_args())))
    print(json.dumps(payload, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
