from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from statistics import median
from typing import Literal, Optional

from pydantic import BaseModel, Field

QueryCategory = Literal["consumer", "tech", "finance", "celebrity", "general"]
ResultStatus = Literal["ok", "anti_bot", "timeout", "error", "needs_login", "empty"]
Grade = Literal["GREEN", "YELLOW", "RED", "INSUFFICIENT"]


class ScrapeResult(BaseModel):
    platform: str
    path_id: str
    repo: str
    query: str
    query_category: QueryCategory
    status: ResultStatus
    http_code: Optional[int] = None
    items_returned: int = 0
    avg_content_len: int = 0
    first_byte_ms: Optional[int] = None
    total_ms: Optional[int] = None
    error: Optional[str] = None
    sample: Optional[str] = None
    anti_bot_signals: list[str] = Field(default_factory=list)


@dataclass(frozen=True)
class AdapterConfig:
    platform: str
    path_id: str
    repo: str
    setup_script: Path
    run_script: Path
    template: str = "base"
    setup_timeout_s: int = 300
    run_timeout_s: int = 120
    max_items: int = 20
    warmup_query_count: int = 1
    circuit_breaker_failures: int = 5


def truncate_text(value: Optional[str], limit: int = 200) -> Optional[str]:
    if not value:
        return None
    text = " ".join(str(value).split())
    return text[:limit] if text else None


def extract_item_text(item: object) -> str:
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
    ):
        value = item.get(key)
        if value:
            return str(value)

    return json.dumps(item, ensure_ascii=False)


def summarize_items(
    items: list[object], max_items: int = 20
) -> tuple[int, int, Optional[str]]:
    limited_items = list(items[:max_items])
    if not limited_items:
        return 0, 0, None

    texts = [extract_item_text(item) for item in limited_items]
    avg_len = int(sum(len(text) for text in texts) / len(texts))
    return len(limited_items), avg_len, truncate_text(texts[0])


def error_result(
    *,
    adapter: AdapterConfig,
    query: str,
    query_category: QueryCategory,
    status: ResultStatus,
    error: Optional[str] = None,
    total_ms: Optional[int] = None,
    sample: Optional[str] = None,
    anti_bot_signals: Optional[list[str]] = None,
    http_code: Optional[int] = None,
) -> ScrapeResult:
    return ScrapeResult(
        platform=adapter.platform,
        path_id=adapter.path_id,
        repo=adapter.repo,
        query=query,
        query_category=query_category,
        status=status,
        http_code=http_code,
        total_ms=total_ms,
        error=truncate_text(error, limit=500),
        sample=truncate_text(sample),
        anti_bot_signals=anti_bot_signals or [],
    )


def synthetic_result(
    *,
    adapter: AdapterConfig,
    query: str,
    query_category: QueryCategory,
    ordinal: int,
) -> ScrapeResult:
    return ScrapeResult(
        platform=adapter.platform,
        path_id=adapter.path_id,
        repo=adapter.repo,
        query=query,
        query_category=query_category,
        status="ok",
        items_returned=min(adapter.max_items, 3 + ordinal),
        avg_content_len=240 + ordinal * 10,
        first_byte_ms=80 + ordinal * 5,
        total_ms=200 + ordinal * 25,
        sample=f"synthetic result for {adapter.path_id}: {query}",
    )


def short_circuit_results(
    *,
    adapter: AdapterConfig,
    pending_queries: list[tuple[str, QueryCategory]],
    reps: int,
    reason: str,
    status: ResultStatus = "error",
) -> list[ScrapeResult]:
    results: list[ScrapeResult] = []
    for query, query_category in pending_queries:
        for _ in range(reps):
            results.append(
                error_result(
                    adapter=adapter,
                    query=query,
                    query_category=query_category,
                    status=status,
                    error=reason,
                )
            )
    return results


def median_total_ms(results: list[ScrapeResult]) -> float:
    values = [result.total_ms for result in results if result.total_ms is not None]
    if not values:
        return 0.0
    return float(median(values))
