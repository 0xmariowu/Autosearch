from __future__ import annotations

import asyncio
import json
import os
import shlex
from pathlib import Path
from typing import Any

from harness.base import (
    AdapterConfig,
    QueryCategory,
    ScrapeResult,
    error_result,
    short_circuit_results,
)

try:
    from dotenv import load_dotenv
except ImportError:

    def load_dotenv(dotenv_path: Path) -> bool:
        if not dotenv_path.exists():
            return False

        loaded = False
        for raw_line in dotenv_path.read_text(encoding="utf-8").splitlines():
            line = raw_line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, value = line.split("=", 1)
            os.environ.setdefault(key.strip(), value.strip().strip("'\""))
            loaded = True
        return loaded


try:
    from e2b_code_interpreter import AsyncSandbox as E2BSandbox
except ImportError:
    from e2b import AsyncSandbox as E2BSandbox

ROOT = Path(__file__).resolve().parents[3]
ENV_PATH = ROOT / ".env"
GLOBAL_SANDBOX_SEMAPHORE = asyncio.Semaphore(20)


def load_e2b_api_key() -> str:
    load_dotenv(ENV_PATH)
    api_key = os.environ.get("E2B_API_KEY")
    if not api_key:
        raise RuntimeError(f"E2B_API_KEY not found in environment or {ENV_PATH}")
    return api_key


async def create_sandbox(adapter: AdapterConfig):
    load_e2b_api_key()
    return await E2BSandbox.create(template=adapter.template, timeout=600)


async def _run_command(
    sandbox: Any, command: str, *, timeout: int, cwd: str | None = None
):
    return await sandbox.commands.run(command, cwd=cwd, timeout=timeout)


async def setup_adapter(sandbox: Any, adapter: AdapterConfig) -> None:
    setup_dir = f"/tmp/as-matrix/{adapter.path_id}"
    await _run_command(sandbox, f"mkdir -p {shlex.quote(setup_dir)}", timeout=30)
    await sandbox.files.write(
        f"{setup_dir}/setup.sh",
        adapter.setup_script.read_text(encoding="utf-8"),
    )
    await sandbox.files.write(
        f"{setup_dir}/run.py",
        adapter.run_script.read_text(encoding="utf-8"),
    )
    await _run_command(
        sandbox, f"chmod +x {shlex.quote(setup_dir)}/setup.sh", timeout=30
    )
    command = "bash setup.sh"
    result = await _run_command(
        sandbox, command, cwd=setup_dir, timeout=adapter.setup_timeout_s
    )
    if result.exit_code != 0:
        raise RuntimeError(result.stderr or result.stdout or "adapter setup failed")


async def run_adapter_query(
    sandbox: Any,
    adapter: AdapterConfig,
    *,
    query: str,
    query_category: QueryCategory,
) -> ScrapeResult:
    command = " ".join(
        [
            "python",
            shlex.quote(adapter.run_script.name),
            "--query",
            shlex.quote(query),
            "--query-category",
            shlex.quote(query_category),
        ]
    )
    try:
        result = await _run_command(
            sandbox,
            command,
            cwd=f"/tmp/as-matrix/{adapter.path_id}",
            timeout=adapter.run_timeout_s,
        )
    except Exception as exc:
        status = "timeout" if "timeout" in type(exc).__name__.lower() else "error"
        return error_result(
            adapter=adapter,
            query=query,
            query_category=query_category,
            status=status,
            error=f"{type(exc).__name__}: {exc}",
        )

    total_ms = None
    payload: dict[str, Any] = {}

    try:
        payload = json.loads(result.stdout.strip())
        total_ms = payload.get("total_ms")
    except json.JSONDecodeError as exc:
        return error_result(
            adapter=adapter,
            query=query,
            query_category=query_category,
            status="error",
            error=f"invalid JSON output: {exc}",
            total_ms=total_ms,
            sample=result.stdout[:200] or None,
        )

    if result.exit_code != 0:
        payload["status"] = "error"
        payload["error"] = (
            payload.get("error") or result.stderr or "adapter command failed"
        )

    payload.setdefault("platform", adapter.platform)
    payload.setdefault("path_id", adapter.path_id)
    payload.setdefault("repo", adapter.repo)
    payload.setdefault("query", query)
    payload.setdefault("query_category", query_category)
    payload.setdefault("anti_bot_signals", [])
    try:
        return ScrapeResult.model_validate(payload)
    except Exception as exc:
        return error_result(
            adapter=adapter,
            query=query,
            query_category=query_category,
            status="error",
            error=f"invalid result payload: {type(exc).__name__}: {exc}",
            total_ms=total_ms,
            sample=result.stdout[:200] or None,
        )


async def run_adapter_batch(
    adapter: AdapterConfig,
    queries: list[tuple[str, QueryCategory]],
    *,
    reps: int,
) -> list[ScrapeResult]:
    async with GLOBAL_SANDBOX_SEMAPHORE:
        sandbox = None
        try:
            try:
                sandbox = await create_sandbox(adapter)
                await setup_adapter(sandbox, adapter)
            except Exception as exc:
                return short_circuit_results(
                    adapter=adapter,
                    pending_queries=queries,
                    reps=reps,
                    reason=f"{type(exc).__name__}: {exc}",
                )

            warmup_query, warmup_category = queries[0]
            warmup = await run_adapter_query(
                sandbox,
                adapter,
                query=warmup_query,
                query_category=warmup_category,
            )
            if warmup.status in {"error", "timeout"}:
                return [warmup] + short_circuit_results(
                    adapter=adapter,
                    pending_queries=queries[1:],
                    reps=reps,
                    reason=f"warmup failed: {warmup.error or warmup.status}",
                )

            results = [warmup]
            consecutive_failures = 0

            for query_index, (query, query_category) in enumerate(queries):
                for rep_index in range(reps):
                    if query_index == 0 and rep_index == 0:
                        if warmup.status in {"error", "timeout"}:
                            consecutive_failures += 1
                        else:
                            consecutive_failures = 0
                        continue

                    scrape_result = await run_adapter_query(
                        sandbox,
                        adapter,
                        query=query,
                        query_category=query_category,
                    )
                    results.append(scrape_result)

                    if scrape_result.status in {"error", "timeout"}:
                        consecutive_failures += 1
                    else:
                        consecutive_failures = 0

                    if consecutive_failures >= adapter.circuit_breaker_failures:
                        pending: list[tuple[str, QueryCategory]] = []
                        if rep_index + 1 < reps:
                            pending.extend(
                                [(query, query_category)] * (reps - rep_index - 1)
                            )
                        for remaining_query, remaining_category in queries[
                            query_index + 1 :
                        ]:
                            pending.extend(
                                [(remaining_query, remaining_category)] * reps
                            )
                        return results + short_circuit_results(
                            adapter=adapter,
                            pending_queries=pending,
                            reps=1,
                            reason="circuit breaker: 5 consecutive failures",
                        )

            return results
        finally:
            if sandbox is not None:
                await sandbox.kill()
