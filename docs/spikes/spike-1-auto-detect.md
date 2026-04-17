# Spike 1: Provider Auto-Detect Harness

## Goal

Validate the M1 `LLMClient` auto-detect path and structured-output reliability before wiring it into later milestones.

- Scope: 30 calls x 4 providers x 1 schema = 120 total calls.
- Providers: `claude_code`, `anthropic`, `openai`, `gemini`.
- Schema: `ClarifyResult`.
- Pass criteria: fail rate `< 5%` per provider, per plan v2.3 § 6.

## Local Harness

Run this from the repo root after exporting any provider credentials you want to test:

```python
import asyncio

from autosearch.core.models import ClarifyResult
from autosearch.llm.client import LLMClient

RUNS = 30
PROMPT = (
    "You are the M1 clarify step. Return JSON only. "
    "Decide whether the query 'best AI coding setup for a solo founder' needs clarification. "
    "Always include rubrics and a mode recommendation."
)


async def probe(provider_name: str) -> tuple[int, list[str]]:
    failures = 0
    notes: list[str] = []
    for index in range(RUNS):
        try:
            client = LLMClient(provider_name=provider_name)
            await client.complete(PROMPT, ClarifyResult)
        except Exception as exc:  # noqa: BLE001
            failures += 1
            notes.append(f"run {index + 1}: {type(exc).__name__}: {exc}")
    return failures, notes


async def main() -> None:
    for provider_name in ("claude_code", "anthropic", "openai", "gemini"):
        try:
            failures, notes = await probe(provider_name)
        except Exception as exc:  # noqa: BLE001
            print(provider_name, "setup_error", exc)
            continue

        fail_rate = failures / RUNS
        print(
            provider_name,
            {
                "fail_count": failures,
                "fail_rate": round(fail_rate, 4),
                "notes": notes[:3],
            },
        )


asyncio.run(main())
```

## Result Table

| provider | fail_count | fail_rate | notes |
|---|---:|---:|---|
| claude_code |  |  |  |
| anthropic |  |  |  |
| openai |  |  |  |
| gemini |  |  |  |
