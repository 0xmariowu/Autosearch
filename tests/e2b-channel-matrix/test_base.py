from __future__ import annotations

import sys
from pathlib import Path

import pytest
from pydantic import ValidationError

ROOT = Path(__file__).resolve().parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from harness.base import ScrapeResult


def test_scrape_result_accepts_expected_payload() -> None:
    result = ScrapeResult(
        platform="bilibili",
        path_id="bilibili__nemo2011",
        repo="https://github.com/Nemo2011/bilibili-api",
        query="iPhone 16 值得买吗",
        query_category="consumer",
        status="ok",
    )

    assert result.platform == "bilibili"
    assert result.items_returned == 0
    assert result.anti_bot_signals == []


def test_scrape_result_rejects_invalid_status() -> None:
    with pytest.raises(ValidationError):
        ScrapeResult(
            platform="bilibili",
            path_id="bilibili__nemo2011",
            repo="https://github.com/Nemo2011/bilibili-api",
            query="iPhone 16 值得买吗",
            query_category="consumer",
            status="bad-status",
        )
