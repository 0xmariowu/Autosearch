from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
import time
from pathlib import Path

REPO = "https://github.com/cypggs/jike-cli"
PLATFORM = "jike"
PATH_ID = "jike__cypggs_jike_cli"
WORKSPACE_REPO = Path("/tmp/as-matrix/jike-cli")

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
        return " ".join(item.split())
    if not isinstance(item, dict):
        return " ".join(str(item).split())

    for key in ("content", "body", "text", "title", "snippet", "summary"):
        value = item.get(key)
        if value:
            return " ".join(str(value).split())
    return " ".join(json.dumps(item, ensure_ascii=False).split())[:300]


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


def _token_args() -> list[str]:
    args: list[str] = []
    access_token = ""
    refresh_token = ""
    for env_name in ("AS_MATRIX_JIKE_ACCESS_TOKEN", "JIKE_ACCESS_TOKEN"):
        value = os.environ.get(env_name, "").strip()
        if value:
            access_token = value
            break
    for env_name in ("AS_MATRIX_JIKE_REFRESH_TOKEN", "JIKE_REFRESH_TOKEN"):
        value = os.environ.get(env_name, "").strip()
        if value:
            refresh_token = value
            break
    if access_token:
        args.extend(["--access-token", access_token])
    if refresh_token:
        args.extend(["--refresh-token", refresh_token])
    return args


def _candidate_commands(query: str) -> list[list[str]]:
    executable = shutil.which("jike-cli") or shutil.which("jike")
    if executable is None:
        return []

    token_args = _token_args()
    commands = [
        [executable, "search", query, *token_args],
        [executable, "search", "--keyword", query, *token_args],
        [executable, "search", *token_args, query],
    ]
    deduped: list[list[str]] = []
    seen: set[tuple[str, ...]] = set()
    for command in commands:
        normalized = tuple(part for part in command if part)
        if normalized not in seen:
            deduped.append(list(normalized))
            seen.add(normalized)
    return deduped


def _parse_cli_output(stdout: str) -> list[object]:
    lines = [line.strip() for line in stdout.splitlines() if line.strip()]
    if not lines:
        return []

    for line in reversed(lines):
        try:
            payload = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(payload, list):
            return payload
        if isinstance(payload, dict):
            for key in ("data", "items", "list", "results"):
                value = payload.get(key)
                if isinstance(value, list):
                    return value
            return [payload]

    return [{"text": line} for line in lines]


def run(query: str, query_category: str) -> dict[str, object]:
    started = time.perf_counter()
    try:
        if not WORKSPACE_REPO.exists():
            raise FileNotFoundError(
                f"Repository not found at {WORKSPACE_REPO}; run setup.sh first."
            )

        commands = _candidate_commands(query)
        if not commands:
            raise RuntimeError("entrypoint_missing: jike-cli executable not found after setup")

        last_error = ""
        for command in commands:
            completed = subprocess.run(
                command,
                cwd=WORKSPACE_REPO,
                capture_output=True,
                text=True,
                timeout=15,
                check=False,
            )
            combined = "\n".join(
                part.strip() for part in (completed.stdout, completed.stderr) if part.strip()
            ).strip()
            if completed.returncode == 0:
                items = _parse_cli_output(completed.stdout)
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

            last_error = combined or f"exit code {completed.returncode}"
            lower = last_error.lower()
            if any(token in lower for token in ("login", "token", "cookie", "unauthorized")):
                elapsed_ms = int((time.perf_counter() - started) * 1000)
                return _result_payload(
                    query,
                    query_category,
                    elapsed_ms,
                    status="needs_login",
                    items_returned=0,
                    avg_content_len=0,
                    sample=None,
                    error=f"needs_login: {last_error}",
                )

        raise RuntimeError(last_error or "all candidate jike-cli search invocations failed")
    except subprocess.TimeoutExpired as exc:
        elapsed_ms = int((time.perf_counter() - started) * 1000)
        return _result_payload(
            query,
            query_category,
            elapsed_ms,
            status="timeout",
            error=f"TimeoutExpired: {exc}",
        )
    except Exception as exc:
        elapsed_ms = int((time.perf_counter() - started) * 1000)
        message = f"{type(exc).__name__}: {exc}"
        lower = message.lower()
        status = "error"
        if any(token in lower for token in ("login", "token", "cookie", "unauthorized")):
            status = "needs_login"
        elif any(token in lower for token in ("403", "captcha", "forbidden", "access denied")):
            status = "anti_bot"
        elif "timeout" in lower:
            status = "timeout"
        return _result_payload(
            query,
            query_category,
            elapsed_ms,
            status=status,
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
