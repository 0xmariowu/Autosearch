from __future__ import annotations

import pytest

from autosearch.skills.channels import resolve_skill_module


def test_resolve_skill_module_rejects_absolute_paths() -> None:
    """Absolute paths cannot bypass the packaged channel root."""
    with pytest.raises(ValueError, match="relative"):
        resolve_skill_module("/tmp", "methods/api_search.py")

    with pytest.raises(ValueError, match="relative"):
        resolve_skill_module("discourse_forum", "/tmp/api_search.py")


def test_resolve_skill_module_rejects_path_traversal() -> None:
    """Relative traversal cannot escape a channel directory."""
    with pytest.raises(ValueError, match="escapes channel root"):
        resolve_skill_module("discourse_forum", "../ddgs/methods/api.py")
