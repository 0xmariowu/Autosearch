from __future__ import annotations

import json
import os
from functools import reduce
from urllib.parse import quote_plus

import httpx

from lib.search_runner import DEFAULT_TIMEOUT, make_result

_INNERTUBE_KEY = os.environ.get("YOUTUBE_INNERTUBE_KEY", "")
BASE_URL = "https://www.youtube.com/results"
NEXT_PAGE_URL = f"https://www.youtube.com/youtubei/v1/search?key={_INNERTUBE_KEY}"
BASE_YOUTUBE_URL = "https://www.youtube.com/watch?v="
CONSENT_COOKIE = {"CONSENT": "YES+"}
USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/135.0.0.0 Safari/537.36"
)


def _extract_json_after_marker(text: str, marker: str) -> dict:
    start = text.find(marker)
    if start == -1:
        return {}
    start = text.find("{", start)
    if start == -1:
        return {}

    depth = 0
    in_string = False
    escape = False
    for index in range(start, len(text)):
        char = text[index]
        if in_string:
            if escape:
                escape = False
            elif char == "\\":
                escape = True
            elif char == '"':
                in_string = False
            continue

        if char == '"':
            in_string = True
            continue
        if char == "{":
            depth += 1
        elif char == "}":
            depth -= 1
            if depth == 0:
                try:
                    return json.loads(text[start : index + 1])
                except json.JSONDecodeError:
                    return {}
    return {}


def _get_text_from_json(element: dict) -> str:
    if not isinstance(element, dict):
        return ""
    if "runs" in element:
        return reduce(lambda a, b: a + b.get("text", ""), element.get("runs", []), "")
    return element.get("simpleText", "") or ""


def _parse_video_renderer(video: dict) -> dict | None:
    video_id = video.get("videoId")
    if not video_id:
        return None

    title = _get_text_from_json(video.get("title", {}))
    if not title:
        return None

    author = _get_text_from_json(video.get("ownerText", {}))
    length = _get_text_from_json(video.get("lengthText", {}))
    description = _get_text_from_json(video.get("descriptionSnippet", {}))
    if not description:
        parts = [p for p in (author, length) if p]
        description = " · ".join(parts) if parts else title

    return {
        "url": BASE_YOUTUBE_URL + video_id,
        "title": title,
        "content": description,
        "author": author,
        "length": length,
        "iframe_src": "https://www.youtube-nocookie.com/embed/" + video_id,
        "thumbnail": "https://i.ytimg.com/vi/" + video_id + "/hqdefault.jpg",
        "video_id": video_id,
    }


def _parse_first_page_response(response_text: str) -> tuple[list[dict], str | None]:
    results: list[dict] = []
    next_page_token: str | None = None
    data = _extract_json_after_marker(response_text, "ytInitialData = ")
    sections = (
        data.get("contents", {})
        .get("twoColumnSearchResultsRenderer", {})
        .get("primaryContents", {})
        .get("sectionListRenderer", {})
        .get("contents", [])
    )

    for section in sections:
        continuation = section.get("continuationItemRenderer", {})
        token = (
            continuation.get("continuationEndpoint", {})
            .get("continuationCommand", {})
            .get("token", "")
        )
        if token:
            next_page_token = token

        for container in section.get("itemSectionRenderer", {}).get("contents", []):
            parsed = _parse_video_renderer(container.get("videoRenderer", {}))
            if parsed:
                results.append(parsed)

    return results, next_page_token


def _parse_next_page_response(response_text: str) -> tuple[list[dict], str | None]:
    results: list[dict] = []
    next_page_token: str | None = None
    data = json.loads(response_text)
    commands = data.get("onResponseReceivedCommands", [])
    if not commands:
        return results, next_page_token

    continuation_items = (
        commands[0]
        .get("appendContinuationItemsAction", {})
        .get("continuationItems", [])
    )
    for item in continuation_items:
        for section in item.get("itemSectionRenderer", {}).get("contents", []):
            parsed = _parse_video_renderer(section.get("videoRenderer", {}))
            if parsed:
                results.append(parsed)

        token = (
            item.get("continuationItemRenderer", {})
            .get("continuationEndpoint", {})
            .get("continuationCommand", {})
            .get("token", "")
        )
        if token:
            next_page_token = token

    return results, next_page_token


async def search(query: str, max_results: int = 10) -> list[dict]:
    results: list[dict] = []

    try:
        async with httpx.AsyncClient(
            timeout=DEFAULT_TIMEOUT,
            headers={"User-Agent": USER_AGENT},
            cookies=CONSENT_COOKIE,
        ) as client:
            response = await client.get(
                f"{BASE_URL}?search_query={quote_plus(query)}&page=1"
            )
            response.raise_for_status()
            batch, next_page_token = _parse_first_page_response(response.text)

            while True:
                for item in batch:
                    results.append(
                        make_result(
                            url=item["url"],
                            title=item["title"],
                            snippet=item["content"],
                            source="youtube",
                            query=query,
                            extra_metadata={
                                "author": item["author"],
                                "length": item["length"],
                                "iframe_src": item["iframe_src"],
                                "thumbnail": item["thumbnail"],
                                "video_id": item["video_id"],
                            },
                        )
                    )
                    if len(results) >= max_results:
                        return results[:max_results]

                if not next_page_token:
                    break

                next_response = await client.post(
                    NEXT_PAGE_URL,
                    json={
                        "context": {
                            "client": {
                                "clientName": "WEB",
                                "clientVersion": "2.20210310.12.01",
                            }
                        },
                        "continuation": next_page_token,
                    },
                    headers={
                        "Content-Type": "application/json",
                        "User-Agent": USER_AGENT,
                    },
                )
                next_response.raise_for_status()
                batch, next_page_token = _parse_next_page_response(next_response.text)
                if not batch:
                    break

        return results[:max_results]
    except Exception as exc:
        from lib.search_runner import SearchError

        raise SearchError(
            channel="youtube", error_type="network", message=str(exc)
        ) from exc
