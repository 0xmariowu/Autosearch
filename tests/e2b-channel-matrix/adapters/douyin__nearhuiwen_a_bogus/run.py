from __future__ import annotations

import argparse
import json
import sys
import time
import urllib.parse
import uuid
from pathlib import Path
from typing import Any

REPO = "https://github.com/NearHuiwen/TiktokDouyinCrawler"
PLATFORM = "douyin"
PATH_ID = "douyin__nearhuiwen_a_bogus"
WORKSPACE_REPO = Path("/tmp/as-matrix/TiktokDouyinCrawler")


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


def _status_from_message(message: str) -> str:
    lowered = message.lower()
    if "timeout" in lowered:
        return "timeout"
    if any(
        token in lowered
        for token in (
            "captcha",
            "verify",
            "验证码",
            "anti-bot",
            "antibot",
            "403",
            "461",
            "471",
        )
    ):
        return "anti_bot"
    if any(
        token in lowered
        for token in ("login", "cookie", "token", "unauthorized", "401")
    ):
        return "needs_login"
    return "error"


def _extract_item_text(item: object) -> str:
    if isinstance(item, str):
        return item
    if not isinstance(item, dict):
        return str(item)

    aweme_info = item.get("aweme_info")
    if isinstance(aweme_info, dict):
        for key in ("desc", "title"):
            value = aweme_info.get(key)
            if value:
                return " ".join(str(value).split())[:300]

    for key in ("desc", "title", "content", "text", "snippet", "summary"):
        value = item.get(key)
        if value:
            return " ".join(str(value).split())[:300]

    return json.dumps(item, ensure_ascii=False)[:300]


def _summarize_items(
    items: list[object], max_items: int = 20
) -> tuple[int, int, str | None]:
    limited_items = list(items[:max_items])
    if not limited_items:
        return 0, 0, None

    texts = [_extract_item_text(item) for item in limited_items]
    avg_len = int(sum(len(text) for text in texts) / len(texts))
    sample = texts[0][:200] if texts else None
    return len(limited_items), avg_len, sample


def _extract_items(response_json: Any) -> list[object]:
    if not isinstance(response_json, dict):
        return []

    data = response_json.get("data")
    if not isinstance(data, list):
        return []

    items: list[object] = []
    for item in data:
        if not isinstance(item, dict):
            continue
        aweme_info = item.get("aweme_info")
        if not isinstance(aweme_info, dict):
            continue
        if aweme_info.get("is_ads") or item.get("is_ads"):
            continue
        items.append(item)
    return items


def run(query: str, query_category: str) -> dict[str, object]:
    started = time.perf_counter()

    if not WORKSPACE_REPO.exists():
        elapsed_ms = int((time.perf_counter() - started) * 1000)
        return _result_payload(
            query,
            query_category,
            elapsed_ms,
            status="error",
            error="Repository not found; run setup.sh first",
        )

    if str(WORKSPACE_REPO) not in sys.path:
        sys.path.insert(0, str(WORKSPACE_REPO))

    try:
        import requests
        from utils.common_utils import CommonUtils

        requests.packages.urllib3.disable_warnings()

        common = CommonUtils()
        referer_url = (
            f"https://www.douyin.com/search/{urllib.parse.quote(query)}"
            f"?source=switch_tab&type=video&aid={uuid.uuid4()}"
        )
        ttwid, webid = common.get_ttwid_webid(referer_url)
        if not ttwid or not webid:
            raise RuntimeError("failed to obtain ttwid/webid from upstream helper")

        params = {
            "device_platform": "webapp",
            "aid": "6383",
            "channel": "channel_pc_web",
            "search_channel": "aweme_video_web",
            "enable_history": "1",
            "sort_type": "0",
            "publish_time": "0",
            "filter_duration": "",
            "search_range": "0",
            "keyword": query,
            "search_source": "normal_search",
            "query_correct_type": "1",
            "is_filter_search": "1",
            "from_group_id": "",
            "offset": "0",
            "count": "20",
            "need_filter_settings": "1",
            "list_type": "single",
            "update_version_code": "170400",
            "pc_client_type": "1",
            "version_code": "170400",
            "version_name": "17.4.0",
            "cookie_enabled": "true",
            "screen_width": "1920",
            "screen_height": "1080",
            "browser_language": "zh-CN",
            "browser_platform": "Win32",
            "browser_name": "Chrome",
            "browser_version": "123.0.0.0",
            "browser_online": "true",
            "engine_name": "Blink",
            "engine_version": "123.0.0.0",
            "os_name": "Windows",
            "os_version": "10",
            "cpu_core_num": "16",
            "device_memory": "8",
            "platform": "PC",
            "downlink": "10",
            "effective_type": "4g",
            "round_trip_time": "50",
            "webid": str(webid),
            "msToken": common.get_ms_token(),
        }
        query_string = urllib.parse.urlencode(params)
        unsigned_url = (
            "https://www.douyin.com/aweme/v1/web/search/item/?" + query_string
        )
        params["a_bogus"] = common.get_abogus(unsigned_url, common.user_agent)

        response = requests.get(
            "https://www.douyin.com/aweme/v1/web/search/item/",
            params=params,
            headers={
                "Accept": "application/json, text/plain, */*",
                "Referer": referer_url,
                "User-Agent": common.user_agent,
            },
            cookies={"ttwid": ttwid},
            timeout=10,
            verify=False,
        )
        response.raise_for_status()
        response_json = response.json()
        items = _extract_items(response_json)
        items_returned, avg_content_len, sample = _summarize_items(items)
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
    except Exception as exc:
        elapsed_ms = int((time.perf_counter() - started) * 1000)
        error = f"{type(exc).__name__}: {exc}"
        return _result_payload(
            query,
            query_category,
            elapsed_ms,
            status=_status_from_message(error),
            error=error,
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
