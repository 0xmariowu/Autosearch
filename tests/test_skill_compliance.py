from __future__ import annotations

from pathlib import Path

import pytest

CHANNELS_DIR = Path(__file__).resolve().parents[1] / "channels"
REQUIRED_FRONTMATTER = {
    "name",
    "description",
    "categories",
    "platform",
    "api_key_required",
}
REQUIRED_SECTIONS = {
    "Content types",
    "Language",
    "Best for",
    "Blind spots",
    "Quality signals",
}


def _channel_dirs() -> list[Path]:
    dirs = []
    for entry in sorted(CHANNELS_DIR.iterdir(), key=lambda p: p.name):
        if not entry.is_dir():
            continue
        if entry.name == "__pycache__" or entry.name.startswith("_"):
            continue
        dirs.append(entry)
    return dirs


def _parse_frontmatter(text: str) -> dict[str, str]:
    if not text.startswith("---"):
        return {}
    end = text.find("\n---", 4)
    if end == -1:
        return {}
    fields: dict[str, str] = {}
    for line in text[4:end].splitlines():
        if ":" in line:
            key, _, value = line.partition(":")
            fields[key.strip()] = value.strip()
    return fields


def _parse_sections(text: str) -> set[str]:
    sections = set()
    for line in text.splitlines():
        stripped = line.strip()
        if stripped.startswith("## "):
            sections.add(stripped[3:].strip())
    return sections


CHANNEL_NAMES = [d.name for d in _channel_dirs()]


@pytest.mark.parametrize("channel_name", CHANNEL_NAMES)
def test_skill_md_exists(channel_name: str) -> None:
    skill_file = CHANNELS_DIR / channel_name / "SKILL.md"
    assert skill_file.is_file(), f"{channel_name}/SKILL.md missing"


@pytest.mark.parametrize("channel_name", CHANNEL_NAMES)
def test_search_py_exists(channel_name: str) -> None:
    search_file = CHANNELS_DIR / channel_name / "search.py"
    assert search_file.is_file(), f"{channel_name}/search.py missing"


@pytest.mark.parametrize("channel_name", CHANNEL_NAMES)
def test_frontmatter_has_required_fields(channel_name: str) -> None:
    skill_file = CHANNELS_DIR / channel_name / "SKILL.md"
    text = skill_file.read_text(encoding="utf-8")
    fields = _parse_frontmatter(text)
    missing = REQUIRED_FRONTMATTER - set(fields.keys())
    assert not missing, f"{channel_name}/SKILL.md missing frontmatter: {missing}"


@pytest.mark.parametrize("channel_name", CHANNEL_NAMES)
def test_frontmatter_name_matches_directory(channel_name: str) -> None:
    skill_file = CHANNELS_DIR / channel_name / "SKILL.md"
    text = skill_file.read_text(encoding="utf-8")
    fields = _parse_frontmatter(text)
    assert fields.get("name") == channel_name, (
        f"{channel_name}/SKILL.md name={fields.get('name')!r}, expected {channel_name!r}"
    )


@pytest.mark.parametrize("channel_name", CHANNEL_NAMES)
def test_body_has_required_sections(channel_name: str) -> None:
    skill_file = CHANNELS_DIR / channel_name / "SKILL.md"
    text = skill_file.read_text(encoding="utf-8")
    sections = _parse_sections(text)
    missing = REQUIRED_SECTIONS - sections
    assert not missing, f"{channel_name}/SKILL.md missing sections: {missing}"
