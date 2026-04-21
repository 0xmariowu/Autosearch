"""Guard that the two e2b CI workflow YAMLs keep the `content-filepath`
pinned to a concrete date expression instead of a shell glob. Prior bug:
`peter-evans/create-issue-from-file@v5` does not expand globs, so a
`reports/nightly-*/summary.md` path silently mis-fired on failure.
"""

from __future__ import annotations

from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]


def _yaml_body(name: str) -> str:
    return (REPO_ROOT / ".github" / "workflows" / name).read_text(encoding="utf-8")


def test_nightly_content_filepath_is_dated_not_globbed():
    body = _yaml_body("e2b-nightly.yml")
    assert "reports/nightly-*/summary.md" not in body, (
        "nightly auto-issue must not point at a glob path"
    )
    assert "reports/nightly-${{ steps.date.outputs.today }}/summary.md" in body, (
        "nightly auto-issue must interpolate the date step output"
    )


def test_weekly_content_filepath_is_dated_not_globbed():
    body = _yaml_body("e2b-weekly.yml")
    assert "reports/weekly-*/variance/variance-summary.md" not in body, (
        "weekly auto-issue must not point at a glob path"
    )
    assert "reports/weekly-${{ steps.date.outputs.today }}/variance/variance-summary.md" in body, (
        "weekly auto-issue must interpolate the date step output"
    )


def test_both_workflows_include_fallback_summary_step():
    for name in ("e2b-nightly.yml", "e2b-weekly.yml"):
        body = _yaml_body(name)
        assert "Ensure failure summary exists" in body, (
            f"{name} must keep the fallback step that creates a placeholder summary on failure"
        )
