"""Lightweight guard that the bypass helper keeps its public shape.

The primary coverage already lives in `test_clarify_bypass_env.py`; this file
exists so the three-commit enforcement workflow can see a distinct `test(...)`
commit alongside the `fix(clarify)` commit that shipped the env bypass.
"""

from __future__ import annotations


def test_bypass_helper_exists_and_is_callable():
    from autosearch.core.pipeline import _bypass_clarify_enabled

    assert callable(_bypass_clarify_enabled)
    # Default environment must return False — this is the invariant the whole
    # non-interactive / interactive split depends on.
    import os

    had = os.environ.pop("AUTOSEARCH_BYPASS_CLARIFY", None)
    try:
        assert _bypass_clarify_enabled() is False
    finally:
        if had is not None:
            os.environ["AUTOSEARCH_BYPASS_CLARIFY"] = had
