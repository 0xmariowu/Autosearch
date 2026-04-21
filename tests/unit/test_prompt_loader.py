import re
from pathlib import Path

import pytest

import autosearch.skills.prompts as prompt_loader_module
from autosearch.skills.prompts import PromptNotFoundError, load_prompt

# W3.3 PR C: m3_* and m7_* prompts (m3_gap_reflection, m3_follow_up_query,
# m7_outline, m7_section_write) removed from disk; the pipeline they served is
# env-gated behind AUTOSEARCH_LEGACY_RESEARCH and will be deleted in PR D/E.
PROMPT_NAMES = [
    "m2_search_query",
    "m4_draft_outline",
    "m4_refine_outline",
    "m8_section_grader",
]
PLACEHOLDER_RE = re.compile(r"(?<!\{)\{[a-zA-Z0-9_]+\}(?!\})")


@pytest.fixture(autouse=True)
def clear_prompt_cache() -> None:
    load_prompt.cache_clear()
    yield
    load_prompt.cache_clear()


def _write_prompt(tmp_path: Path, name: str, body: str) -> None:
    (tmp_path / f"{name}.md").write_text(
        "\n".join(
            [
                "---",
                f"name: {name}",
                "phase: M0",
                "description: Test prompt.",
                "---",
                body,
                "",
            ]
        ),
        encoding="utf-8",
    )


def test_load_prompt_returns_body_without_frontmatter(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    _write_prompt(tmp_path, "example", "Line one\n\nLine two")
    monkeypatch.setattr(prompt_loader_module, "_PROMPTS_DIR", tmp_path)

    assert load_prompt("example") == "Line one\n\nLine two"


def test_load_prompt_raises_when_missing(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    monkeypatch.setattr(prompt_loader_module, "_PROMPTS_DIR", tmp_path)

    with pytest.raises(PromptNotFoundError, match="does_not_exist"):
        load_prompt("does_not_exist")


def test_load_prompt_handles_placeholders(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    _write_prompt(
        tmp_path,
        "placeholder_example",
        '{{\n  "value": "{x}"\n}}',
    )
    monkeypatch.setattr(prompt_loader_module, "_PROMPTS_DIR", tmp_path)

    prompt = load_prompt("placeholder_example")

    assert prompt == '{{\n  "value": "{x}"\n}}'
    assert prompt.format(x=1) == '{\n  "value": "1"\n}'


def test_all_six_prompts_load_and_contain_placeholders() -> None:
    for name in PROMPT_NAMES:
        prompt = load_prompt(name)

        assert prompt
        assert PLACEHOLDER_RE.search(prompt)
