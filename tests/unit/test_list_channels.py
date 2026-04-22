"""Tests for list_channels MCP tool (calls core function directly)."""

from __future__ import annotations

import os
from unittest.mock import patch

from autosearch.core.doctor import ChannelStatus


def _make_status(name: str, status: str) -> ChannelStatus:
    return ChannelStatus(channel=name, status=status, message=f"{status} msg", unmet_requires=[])


def _call_list_channels(status_filter: str = "") -> dict:
    """Call list_channels via the MCP server tool function directly."""
    os.environ["AUTOSEARCH_LLM_MODE"] = "dummy"
    from autosearch.mcp.server import create_server  # noqa: PLC0415

    server = create_server()
    fn = server._tool_manager._tools["list_channels"].fn
    return fn(status_filter=status_filter)


def test_list_channels_returns_all():
    statuses = [
        _make_status("arxiv", "ok"),
        _make_status("bilibili", "warn"),
        _make_status("zhihu", "off"),
    ]
    with patch("autosearch.core.doctor.scan_channels", return_value=statuses):
        data = _call_list_channels()

    assert data["total"] == 3
    assert data["ok_count"] == 1
    assert data["warn_count"] == 1
    assert data["off_count"] == 1
    # ok first, then warn, then off
    assert data["channels"][0]["status"] == "ok"
    assert data["channels"][1]["status"] == "warn"
    assert data["channels"][2]["status"] == "off"


def test_list_channels_status_filter():
    statuses = [
        _make_status("arxiv", "ok"),
        _make_status("bilibili", "warn"),
        _make_status("zhihu", "off"),
    ]
    with patch("autosearch.core.doctor.scan_channels", return_value=statuses):
        data = _call_list_channels(status_filter="ok")

    assert data["total"] == 1
    assert data["channels"][0]["name"] == "arxiv"
