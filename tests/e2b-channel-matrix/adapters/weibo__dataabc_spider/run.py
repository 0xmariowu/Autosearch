from __future__ import annotations

import argparse
import importlib
import json
import re
import sys
import time
from pathlib import Path

REPO = "https://github.com/dataabc/weiboSpider"
PLATFORM = "weibo"
PATH_ID = "weibo__dataabc_spider"
WORKSPACE_REPO = Path("/tmp/as-matrix/weiboSpider")
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


def _top_level_modules(repo_path: Path) -> list[str]:
    modules: list[str] = []
    for child in sorted(repo_path.iterdir(), key=lambda item: item.name):
        if child.name.startswith("."):
            continue
        if child.is_dir() and (child / "__init__.py").exists():
            modules.append(child.name)
        elif child.is_file() and child.suffix == ".py" and child.stem != "__init__":
            modules.append(child.stem)
    return modules


def _repo_mentions_keyword_search(repo_path: Path) -> bool:
    patterns = (
        re.compile(r"def\s+search\w*\s*\("),
        re.compile(r"""add_argument\((['"])--query\1"""),
        re.compile(r"keyword\s*="),
    )
    for py_file in repo_path.rglob("*.py"):
        if any(part.startswith(".") for part in py_file.parts):
            continue
        try:
            text = py_file.read_text(encoding="utf-8", errors="ignore")
        except OSError:
            continue
        if any(pattern.search(text) for pattern in patterns):
            return True
    return False


def run(query: str, query_category: str) -> dict[str, object]:
    started = time.perf_counter()

    try:
        if not WORKSPACE_REPO.exists():
            raise ModuleNotFoundError(f"repository not found at {WORKSPACE_REPO}")

        import_candidates = [
            name
            for name in _top_level_modules(WORKSPACE_REPO)
            if "weibo" in name.lower() or "spider" in name.lower()
        ]
        imported_module = None
        last_import_error: Exception | None = None
        for module_name in import_candidates:
            try:
                imported_module = importlib.import_module(module_name)
                break
            except Exception as exc:
                last_import_error = exc

        if imported_module is None and last_import_error is not None:
            raise last_import_error

        if _repo_mentions_keyword_search(WORKSPACE_REPO):
            raise AttributeError(
                "keyword-search entrypoint is unclear in dataabc/weiboSpider; "
                "adapter only supports returning empty when no search entry is available"
            )

        elapsed_ms = int((time.perf_counter() - started) * 1000)
        return _result_payload(
            query,
            query_category,
            elapsed_ms,
            status="empty",
            items_returned=0,
            avg_content_len=0,
            sample=None,
            note=(
                "dataabc/weiboSpider is a user-id timeline fetcher; no supported "
                "keyword-search entrypoint was found for query-based search."
            ),
        )
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

    payload = run(args.query, args.query_category)
    print(json.dumps(payload, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
