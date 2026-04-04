from __future__ import annotations

import httpx

from lib.search_runner import DEFAULT_TIMEOUT, make_result

HF_PAPERS_API = "https://huggingface.co/api/daily_papers"
USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/135.0.0.0 Safari/537.36"
)


async def search(query: str, max_results: int = 10) -> list[dict]:
    try:
        async with httpx.AsyncClient(
            timeout=DEFAULT_TIMEOUT,
            headers={"User-Agent": USER_AGENT},
        ) as client:
            resp = await client.get(
                HF_PAPERS_API,
                params={"search": query},
            )
            resp.raise_for_status()
            entries = resp.json()
            if not isinstance(entries, list):
                return []

            results: list[dict] = []
            for entry in entries:
                paper = entry.get("paper", entry)
                paper_id = paper.get("id", "")
                title = paper.get("title", "")
                if not paper_id or not title:
                    continue

                metadata: dict = {}
                authors = paper.get("authors", [])
                if authors:
                    metadata["authors"] = ", ".join(
                        a.get("name", "") for a in authors[:3]
                    )
                if paper.get("publishedAt"):
                    metadata["published_at"] = paper["publishedAt"]
                upvotes = entry.get("paper", {}).get("upvotes", 0) or entry.get(
                    "numComments", 0
                )
                if upvotes:
                    metadata["upvotes"] = upvotes

                results.append(
                    make_result(
                        url=f"https://huggingface.co/papers/{paper_id}",
                        title=title,
                        snippet=paper.get("summary", "")[:500] or "",
                        source="papers-with-code",
                        query=query,
                        extra_metadata=metadata,
                    )
                )
                if len(results) >= max_results:
                    break

            return results[:max_results]
    except Exception as exc:
        from lib.search_runner import SearchError

        raise SearchError(
            channel="papers-with-code", error_type="network", message=str(exc)
        ) from exc
