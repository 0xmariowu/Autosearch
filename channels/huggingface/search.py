from __future__ import annotations

import asyncio
import os
import sys

import httpx

from lib.search_runner import DEFAULT_TIMEOUT, make_result

HF_API = "https://huggingface.co/api"
HF_TOKEN = os.environ.get("HF_TOKEN", "")
USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/135.0.0.0 Safari/537.36"
)


def _model_snippet(m: dict) -> str:
    """Build a meaningful snippet from model metadata."""
    parts = []
    if m.get("pipeline_tag"):
        parts.append(m["pipeline_tag"])
    tags = [t for t in m.get("tags", []) if not t.startswith("region:")]
    if tags:
        parts.append(", ".join(tags[:5]))
    dl = m.get("downloads", 0)
    if dl:
        parts.append(f"{dl:,} downloads")
    likes = m.get("likes", 0)
    if likes:
        parts.append(f"{likes:,} likes")
    return " · ".join(parts) if parts else m.get("id", "")


async def _search_models(
    client: httpx.AsyncClient, query: str, limit: int
) -> list[dict]:
    resp = await client.get(
        f"{HF_API}/models",
        params={
            "search": query,
            "limit": limit,
            "sort": "downloads",
            "direction": "-1",
        },
    )
    resp.raise_for_status()
    results = []
    for m in resp.json():
        model_id = m.get("id", "")
        if not model_id:
            continue
        metadata = {
            "type": "model",
            "downloads": m.get("downloads", 0),
            "likes": m.get("likes", 0),
            "pipeline_tag": m.get("pipeline_tag", ""),
        }
        results.append(
            make_result(
                url=f"https://huggingface.co/{model_id}",
                title=model_id,
                snippet=_model_snippet(m),
                source="huggingface",
                query=query,
                extra_metadata=metadata,
            )
        )
    return results


async def _search_datasets(
    client: httpx.AsyncClient, query: str, limit: int
) -> list[dict]:
    resp = await client.get(
        f"{HF_API}/datasets",
        params={
            "search": query,
            "limit": limit,
            "sort": "downloads",
            "direction": "-1",
        },
    )
    resp.raise_for_status()
    results = []
    for d in resp.json():
        dataset_id = d.get("id", "")
        if not dataset_id:
            continue
        dl = d.get("downloads", 0)
        likes = d.get("likes", 0)
        parts = [f"Dataset: {dataset_id}"]
        if dl:
            parts.append(f"{dl:,} downloads")
        if likes:
            parts.append(f"{likes:,} likes")
        metadata = {
            "type": "dataset",
            "downloads": dl,
            "likes": likes,
        }
        results.append(
            make_result(
                url=f"https://huggingface.co/datasets/{dataset_id}",
                title=dataset_id,
                snippet=" · ".join(parts),
                source="huggingface",
                query=query,
                extra_metadata=metadata,
            )
        )
    return results


async def search(query: str, max_results: int = 10) -> list[dict]:
    half = max(1, max_results // 2)
    headers: dict[str, str] = {"User-Agent": USER_AGENT}
    if HF_TOKEN:
        headers["Authorization"] = f"Bearer {HF_TOKEN}"

    try:
        async with httpx.AsyncClient(
            timeout=DEFAULT_TIMEOUT,
            headers=headers,
        ) as client:
            models, datasets = await asyncio.gather(
                _search_models(client, query, half),
                _search_datasets(client, query, half),
                return_exceptions=True,
            )
            # Handle partial failures — one sub-search failing shouldn't kill both
            model_list = models if isinstance(models, list) else []
            dataset_list = datasets if isinstance(datasets, list) else []

            if isinstance(models, Exception):
                print(f"[huggingface] models search failed: {models}", file=sys.stderr)
            if isinstance(datasets, Exception):
                print(
                    f"[huggingface] datasets search failed: {datasets}",
                    file=sys.stderr,
                )

        # Interleave models and datasets
        merged: list[dict] = []
        limit = max(len(model_list), len(dataset_list))
        for i in range(limit):
            if i < len(model_list):
                merged.append(model_list[i])
            if i < len(dataset_list):
                merged.append(dataset_list[i])
            if len(merged) >= max_results:
                break

        if merged:
            return merged[:max_results]
    except Exception as exc:
        print(f"[huggingface] API failed: {exc}", file=sys.stderr)

    # Fallback: DDGS with huggingface in query (not site: which returns less)
    from channels._engines.ddgs import search_ddgs_web

    return await search_ddgs_web(
        f"huggingface {query}", max_results=max_results, source="huggingface"
    )
