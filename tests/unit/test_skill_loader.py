# Self-written, plan autosearch-0418-channels-and-skills.md § F001
from pathlib import Path

import pytest

import autosearch.skills.loader as loader_module
from autosearch.skills import SkillLoadError, load_all, load_skill


def _fixture_root() -> Path:
    return Path(__file__).resolve().parents[1] / "fixtures" / "skills"


def _fixture_text(name: str) -> str:
    return (_fixture_root() / name / "SKILL.md").read_text(encoding="utf-8")


def _write_skill(tmp_path: Path, directory_name: str, content: str) -> Path:
    skill_dir = tmp_path / directory_name
    skill_dir.mkdir(parents=True, exist_ok=True)
    (skill_dir / "SKILL.md").write_text(content, encoding="utf-8")
    return skill_dir


def test_load_valid_channel_skill() -> None:
    spec = load_skill(_fixture_root() / "valid_channel")

    assert spec.name == "valid_channel"
    assert spec.languages == ["zh", "en"]
    assert [method.id for method in spec.methods] == ["api_search", "api_detail"]
    assert spec.fallback_chain == ["api_search", "api_detail"]
    assert spec.when_to_use is not None
    assert spec.when_to_use.query_types == ["academic-papers", "literature-review"]
    assert spec.when_to_use.domain_hints == ["citations", "scholarly-search"]
    assert spec.quality_hint is not None
    assert spec.quality_hint.typical_yield == "medium-high"
    assert spec.layer == "leaf"
    assert spec.domains == ["academic"]
    assert spec.scenarios == ["paper-search", "detail-hydration"]
    assert spec.model_tier == "Standard"
    assert spec.tier == 1
    assert spec.fix_hint == "autosearch configure ARXIV_TOKEN <value>"
    assert spec.skill_dir.name == "valid_channel"


def test_load_valid_tool_skill() -> None:
    spec = load_skill(_fixture_root() / "valid_tool")

    assert spec.name == "valid_tool"
    assert spec.languages == []
    assert len(spec.methods) == 1
    assert spec.methods[0].requires == ["binary:curl"]
    assert spec.when_to_use is None
    assert spec.fallback_chain == ["fetch_json"]


def test_load_missing_required_raises() -> None:
    with pytest.raises(SkillLoadError, match="name"):
        load_skill(_fixture_root() / "missing_required")


def test_load_bad_fallback_raises() -> None:
    with pytest.raises(SkillLoadError, match="fallback_chain"):
        load_skill(_fixture_root() / "bad_fallback")


def test_load_bad_requires_token_raises() -> None:
    with pytest.raises(SkillLoadError, match="requires"):
        load_skill(_fixture_root() / "bad_requires_token")


def test_load_all_sorts_by_name(tmp_path: Path) -> None:
    _write_skill(tmp_path, "valid_tool", _fixture_text("valid_tool"))
    _write_skill(tmp_path, "valid_channel", _fixture_text("valid_channel"))

    specs = load_all(tmp_path)

    assert [spec.name for spec in specs] == ["valid_channel", "valid_tool"]


def test_load_all_skips_dirs_without_skill_md(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    _write_skill(tmp_path, "valid_channel", _fixture_text("valid_channel"))
    missing_dir = tmp_path / "no_skill_here"
    missing_dir.mkdir()

    events: list[tuple[str, dict[str, object]]] = []

    class _Logger:
        def info(self, event: str, **kwargs: object) -> None:
            events.append((event, kwargs))

        def debug(self, event: str, **kwargs: object) -> None:
            events.append((event, kwargs))

    monkeypatch.setattr(loader_module, "LOGGER", _Logger())

    specs = load_all(tmp_path)

    assert [spec.name for spec in specs] == ["valid_channel"]
    assert events == [
        (
            "skill_dir_skipped",
            {"reason": "missing_skill_md", "skill_dir": str(missing_dir)},
        )
    ]


def test_load_all_validates_name_matches_dirname(tmp_path: Path) -> None:
    content = _fixture_text("valid_tool").replace("name: valid_tool", "name: bar", 1)
    _write_skill(tmp_path, "foo", content)

    with pytest.raises(SkillLoadError, match="directory name"):
        load_all(tmp_path)
