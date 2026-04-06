from __future__ import annotations

import asyncio
import os

import httpx

from lib.search_runner import DEFAULT_TIMEOUT, make_result

HF_API = "https://huggingface.co/api"
HF_TOKEN = os.environ.get("HF_TOKEN", "")
USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/135.0.0.0 Safari/537.36"
)


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
                snippet=m.get("pipeline_tag", "") or "",
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
        metadata = {
            "type": "dataset",
            "downloads": d.get("downloads", 0),
            "likes": d.get("likes", 0),
        }
        results.append(
            make_result(
                url=f"https://huggingface.co/datasets/{dataset_id}",
                title=dataset_id,
                snippet=d.get("description", "") or "",
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
            )
        # Interleave models and datasets
        merged: list[dict] = []
        limit = max(len(models), len(datasets))
        for i in range(limit):
            if i < len(models):
                merged.append(models[i])
            if i < len(datasets):
                merged.append(datasets[i])
            if len(merged) >= max_results:
                break
        return merged[:max_results]
    except Exception:
        from channels._engines.ddgs import search_ddgs_site

        return await search_ddgs_site(query, "huggingface.co", max_results=max_results)
