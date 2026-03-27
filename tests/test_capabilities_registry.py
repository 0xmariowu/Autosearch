"""Tests for the capabilities registry."""

import pytest
from capabilities import load_manifest, dispatch, manifest_text, manifest_json, run_all_tests, available_capabilities


def test_load_manifest_returns_list():
    m = load_manifest(force=True)
    assert isinstance(m, list)
    assert len(m) >= 27  # 17 wrappers + 10+ new


def test_manifest_entries_have_required_fields():
    for cap in load_manifest():
        assert "name" in cap
        assert "description" in cap
        assert "when" in cap
        assert "input_type" in cap
        assert "output_type" in cap
        assert cap["name"], f"Empty name in capability"
        assert cap["description"], f"Empty description for {cap['name']}"


def test_manifest_text_not_empty():
    text = manifest_text()
    assert len(text) > 100
    assert "search_web" in text


def test_manifest_json_valid_tool_format():
    tools = manifest_json()
    assert isinstance(tools, list)
    for tool in tools:
        assert "name" in tool
        assert "description" in tool
        assert "input_schema" in tool


def test_dispatch_consensus_score():
    hits = [
        {"url": "a.com", "score_hint": 10, "provider": "x"},
        {"url": "a.com", "score_hint": 10, "provider": "y"},
    ]
    result = dispatch("consensus_score", hits)
    assert result[0]["consensus_count"] == 2


def test_dispatch_unknown_raises():
    with pytest.raises(Exception):
        dispatch("nonexistent_capability_xyz", {})


def test_run_all_tests_all_pass():
    results = run_all_tests()
    failures = {k: v for k, v in results.items() if isinstance(v, str) and v.startswith("FAIL")}
    assert not failures, f"Failed tests: {failures}"


def test_available_capabilities_filters():
    available = available_capabilities()
    assert isinstance(available, list)
    # All available should have no LOAD ERROR
    for cap in available:
        assert "LOAD ERROR" not in cap.get("description", "")
