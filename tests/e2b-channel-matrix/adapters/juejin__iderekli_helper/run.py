from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import time
from pathlib import Path

REPO = "https://github.com/iDerekLi/juejin-helper"
PLATFORM = "juejin"
PATH_ID = "juejin__iderekli_helper"
WORKSPACE_REPO = Path("/tmp/as-matrix/juejin-helper")


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


def _probe_package() -> dict[str, object]:
    node_bin = shutil.which("node")
    if node_bin is None:
        raise RuntimeError("language_mismatch: node_required")

    probe = subprocess.run(
        [
            node_bin,
            "-e",
            (
                "const fs=require('fs');"
                "const path=require('path');"
                "const repo=process.argv[1];"
                "const pkgDir=path.join(repo,'packages','juejin-helper');"
                "const pkgPath=fs.existsSync(path.join(pkgDir,'package.json'))"
                " ? path.join(pkgDir,'package.json')"
                " : path.join(repo,'package.json');"
                "const pkg=JSON.parse(fs.readFileSync(pkgPath,'utf8'));"
                "console.log(JSON.stringify({"
                "pkgPath,"
                "name:pkg.name||null,"
                "main:pkg.main||null,"
                "module:pkg.module||null,"
                "bin:pkg.bin||null,"
                "scripts:Object.keys(pkg.scripts||{})"
                "}));"
            ),
            str(WORKSPACE_REPO),
        ],
        cwd=WORKSPACE_REPO,
        capture_output=True,
        text=True,
        timeout=15,
        check=False,
    )
    if probe.returncode != 0:
        stderr = (probe.stderr or probe.stdout or "").strip()
        raise RuntimeError(stderr or f"node probe failed with exit code {probe.returncode}")

    lines = [line.strip() for line in probe.stdout.splitlines() if line.strip()]
    if not lines:
        raise RuntimeError("node probe produced no output")
    return json.loads(lines[-1])


def run(query: str, query_category: str) -> dict[str, object]:
    started = time.perf_counter()
    try:
        if not WORKSPACE_REPO.exists():
            raise FileNotFoundError(
                f"Repository not found at {WORKSPACE_REPO}; run setup.sh first."
            )

        pkg_meta = _probe_package()
        scripts = ", ".join(str(item) for item in (pkg_meta.get("scripts") or [])[:6])
        raise RuntimeError(
            "sandbox_infeasible: upstream project automates cookie-backed sign-in/draw "
            f"workflows rather than keyword search (scripts={scripts or 'none'})"
        )
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
        status = "error"
        if "timeout" in message.lower():
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
