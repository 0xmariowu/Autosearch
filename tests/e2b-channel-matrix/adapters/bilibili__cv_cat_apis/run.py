from __future__ import annotations

import argparse
import asyncio
import importlib.util
import inspect
import json
import sys
import time
from pathlib import Path

REPO = "https://github.com/cv-cat/BilibiliApis"
PLATFORM = "bilibili"
PATH_ID = "bilibili__cv_cat_apis"
WORKSPACE_REPO = Path("/tmp/as-matrix/BilibiliApis")
if str(WORKSPACE_REPO) not in sys.path:
    sys.path.insert(0, str(WORKSPACE_REPO))


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


def _extract_item_text(item: object) -> str:
    if isinstance(item, str):
        return item
    if not isinstance(item, dict):
        return str(item)

    for key in (
        "content",
        "snippet",
        "body",
        "description",
        "summary",
        "title",
        "text",
        "author",
        "url",
    ):
        value = item.get(key)
        if value:
            return str(value)

    return json.dumps(item, ensure_ascii=False)


def _summarize_items(
    items: list[object], max_items: int = 20
) -> tuple[int, int, str | None]:
    limited_items = list(items[:max_items])
    if not limited_items:
        return 0, 0, None

    texts = [_extract_item_text(item) for item in limited_items]
    avg_len = int(sum(len(text) for text in texts) / len(texts))
    sample = " ".join(texts[0].split())[:200]
    return len(limited_items), avg_len, sample or None


def _candidate_modules(repo_path: Path) -> list[Path]:
    candidates: list[tuple[int, str, Path]] = []
    for py_file in repo_path.rglob("*.py"):
        if any(part.startswith(".") for part in py_file.parts):
            continue
        relative = py_file.relative_to(repo_path)
        if any(part in {"tests", "test", "docs"} for part in relative.parts):
            continue
        score = 0
        joined = "/".join(relative.parts).lower()
        stem = py_file.stem.lower()
        if "search" in stem:
            score += 4
        if "search" in joined:
            score += 3
        try:
            text = py_file.read_text(encoding="utf-8", errors="ignore")
        except OSError:
            text = ""
        if "def search(" in text:
            score += 6
        if "search" in text.lower():
            score += 1
        if score:
            candidates.append((score, joined, py_file))
    candidates.sort(key=lambda item: (-item[0], item[1]))
    return [path for _, _, path in candidates]


def _load_module(module_path: Path) -> object:
    spec = importlib.util.spec_from_file_location(
        f"as_matrix_{module_path.stem}", module_path
    )
    if spec is None or spec.loader is None:
        raise ImportError(f"cannot load module from {module_path}")

    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


async def _invoke_search(search_fn: object, query: str) -> object:
    signature = inspect.signature(search_fn)
    params = list(signature.parameters.values())

    kwargs: dict[str, object] = {}
    args: list[object] = []
    if "keyword" in signature.parameters:
        kwargs["keyword"] = query
    elif "query" in signature.parameters:
        kwargs["query"] = query
    elif len(params) == 1:
        args.append(query)
    else:
        raise AttributeError(
            f"callable 'search' has unsupported signature: {signature}"
        )

    result = search_fn(*args, **kwargs)
    if inspect.isawaitable(result):
        return await result
    return result


def _normalize_items(response: object) -> list[object]:
    if isinstance(response, list):
        return response
    if not isinstance(response, dict):
        return [response]

    if isinstance(response.get("result"), list):
        result_groups = response["result"]
        if result_groups and isinstance(result_groups[0], dict) and "data" in result_groups[0]:
            flattened: list[object] = []
            for group in result_groups:
                data = group.get("data")
                if isinstance(data, list):
                    flattened.extend(data)
            return flattened
        return result_groups

    for key in ("data", "items", "list", "results"):
        value = response.get(key)
        if isinstance(value, list):
            return value

    return [response]


async def _run(query: str, query_category: str) -> dict[str, object]:
    started = time.perf_counter()

    try:
        if not WORKSPACE_REPO.exists():
            raise ModuleNotFoundError(f"repository not found at {WORKSPACE_REPO}")

        candidates = _candidate_modules(WORKSPACE_REPO)
        if not candidates:
            raise ImportError("no search-related Python module discovered in clone")

        module_errors: list[str] = []
        for module_path in candidates:
            try:
                module = _load_module(module_path)
            except Exception as exc:
                module_errors.append(
                    f"{module_path.relative_to(WORKSPACE_REPO)} -> {type(exc).__name__}: {exc}"
                )
                continue

            search_fn = getattr(module, "search", None)
            if search_fn is None or not callable(search_fn):
                module_errors.append(
                    f"{module_path.relative_to(WORKSPACE_REPO)} -> "
                    "AttributeError: no callable named 'search'"
                )
                continue

            response = await _invoke_search(search_fn, query)
            items = _normalize_items(response)
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

        raise AttributeError("; ".join(module_errors[:3]))
    except Exception as exc:
        elapsed_ms = int((time.perf_counter() - started) * 1000)
        return _result_payload(
            query,
            query_category,
            elapsed_ms,
            status="error",
            error=f"{type(exc).__name__}: {exc}",
        )


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--query", required=True)
    parser.add_argument("--query-category", required=True)
    args = parser.parse_args()

    payload = asyncio.run(_run(args.query, args.query_category))
    print(json.dumps(payload, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
