# Self-written for task F206 Wave G phase 1.
from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from textwrap import dedent


def _load_script_module():
    script_path = Path(__file__).resolve().parents[2] / "scripts" / "generate_channels_table.py"
    spec = importlib.util.spec_from_file_location("generate_channels_table", script_path)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def _write_skill(
    channels_root: Path,
    *,
    name: str,
    description: str,
    languages: list[str],
    methods: list[dict[str, object]],
    typical_yield: str = "medium",
) -> None:
    skill_dir = channels_root / name
    (skill_dir / "methods").mkdir(parents=True, exist_ok=True)

    lines = [
        "---",
        f"name: {name}",
        f'description: "{description}"',
        "version: 1",
        f"languages: [{', '.join(languages)}]",
        "methods:",
    ]
    for method in methods:
        requires = ", ".join(method.get("requires", []))
        lines.extend(
            [
                f"  - id: {method['id']}",
                f"    impl: {method['impl']}",
                f"    requires: [{requires}]",
            ]
        )
    lines.extend(
        [
            f"fallback_chain: [{', '.join(method['id'] for method in methods)}]",
            "quality_hint:",
            f"  typical_yield: {typical_yield}",
            "  chinese_native: false",
            "---",
        ]
    )
    (skill_dir / "SKILL.md").write_text("\n".join(lines) + "\n", encoding="utf-8")

    for method in methods:
        impl = skill_dir / str(method["impl"])
        if method.get("shipped", True):
            impl.write_text(
                dedent(
                    """
                    from autosearch.core.models import Evidence, SubQuery


                    async def search(query: SubQuery) -> list[Evidence]:
                        return []
                    """
                ).lstrip(),
                encoding="utf-8",
            )


def test_generate_replaces_between_markers(tmp_path: Path) -> None:
    module = _load_script_module()
    channels_root = tmp_path / "skills" / "channels"
    _write_skill(
        channels_root,
        name="ddgs",
        description="Free web search",
        languages=["en", "mixed"],
        methods=[{"id": "text_search", "impl": "methods/api.py", "requires": []}],
    )
    readme = tmp_path / "README.md"
    readme.write_text(
        "# Demo\n\n<!-- channels-table-start -->\nold\n<!-- channels-table-end -->\n",
        encoding="utf-8",
    )

    exit_code = module.main(["--channels-root", str(channels_root), "--readme", str(readme)])

    assert exit_code == 0
    rendered = readme.read_text(encoding="utf-8")
    assert "### Tier 0 - always-on (1)" in rendered
    assert "| ddgs | en, mixed | Free web search | medium |" in rendered
    assert "old" not in rendered


def test_generate_errors_when_markers_missing(tmp_path: Path, capsys) -> None:
    module = _load_script_module()
    channels_root = tmp_path / "skills" / "channels"
    _write_skill(
        channels_root,
        name="ddgs",
        description="Free web search",
        languages=["en"],
        methods=[{"id": "text_search", "impl": "methods/api.py", "requires": []}],
    )
    readme = tmp_path / "README.md"
    readme.write_text("# Demo\n", encoding="utf-8")

    exit_code = module.main(["--channels-root", str(channels_root), "--readme", str(readme)])

    assert exit_code == 1
    assert "ERROR: markers not found" in capsys.readouterr().err


def test_generate_check_mode_detects_drift(tmp_path: Path, capsys) -> None:
    module = _load_script_module()
    channels_root = tmp_path / "skills" / "channels"
    _write_skill(
        channels_root,
        name="youtube",
        description="Video search",
        languages=["en"],
        methods=[
            {
                "id": "data_api_search",
                "impl": "methods/data_api.py",
                "requires": ["env:YOUTUBE_API_KEY"],
            }
        ],
    )
    readme = tmp_path / "README.md"
    readme.write_text(
        "# Demo\n\n<!-- channels-table-start -->\nstale\n<!-- channels-table-end -->\n",
        encoding="utf-8",
    )

    exit_code = module.main(
        ["--channels-root", str(channels_root), "--readme", str(readme), "--check"]
    )

    assert exit_code == 1
    assert "ERROR: README.md is out of date" in capsys.readouterr().err


def test_generate_check_mode_passes_when_in_sync(tmp_path: Path) -> None:
    module = _load_script_module()
    channels_root = tmp_path / "skills" / "channels"
    _write_skill(
        channels_root,
        name="ddgs",
        description="Free web search",
        languages=["en", "mixed"],
        methods=[{"id": "text_search", "impl": "methods/api.py", "requires": []}],
    )
    generated = module.render_supported_channels(channels_root)
    readme = tmp_path / "README.md"
    readme.write_text(
        (f"# Demo\n\n{module.START_MARKER}\n{generated}\n{module.END_MARKER}\n"),
        encoding="utf-8",
    )

    exit_code = module.main(
        ["--channels-root", str(channels_root), "--readme", str(readme), "--check"]
    )

    assert exit_code == 0


def test_generate_groups_channels_by_tier(tmp_path: Path) -> None:
    module = _load_script_module()
    channels_root = tmp_path / "skills" / "channels"
    _write_skill(
        channels_root,
        name="ddgs",
        description="Free web search",
        languages=["en"],
        methods=[{"id": "text_search", "impl": "methods/api.py", "requires": []}],
        typical_yield="medium",
    )
    _write_skill(
        channels_root,
        name="youtube",
        description="Video search",
        languages=["en", "mixed"],
        methods=[
            {
                "id": "data_api_search",
                "impl": "methods/data_api.py",
                "requires": ["env:YOUTUBE_API_KEY"],
            }
        ],
        typical_yield="high",
    )
    _write_skill(
        channels_root,
        name="zhihu",
        description="Paid channel",
        languages=["zh", "mixed"],
        methods=[
            {
                "id": "via_tikhub",
                "impl": "methods/via_tikhub.py",
                "requires": ["env:TIKHUB_API_KEY"],
            },
            {
                "id": "api_search",
                "impl": "methods/api_search.py",
                "requires": [],
                "shipped": False,
            },
        ],
        typical_yield="medium-high",
    )

    rendered = module.render_supported_channels(channels_root)

    assert "### Tier 0 - always-on (1)" in rendered
    assert "### Tier 1 - env/API gated (2)" in rendered
    assert "### Tier 2 - login/cookie gated (0)" in rendered
    assert "| youtube | en, mixed | env:YOUTUBE_API_KEY | Video search | high |" in rendered
    assert "| zhihu | zh, mixed | env:TIKHUB_API_KEY | Paid channel | medium-high |" in rendered


def test_generate_prefers_declared_tier_over_requires_inference(tmp_path: Path) -> None:
    module = _load_script_module()
    channels_root = tmp_path / "skills" / "channels"
    skill_dir = channels_root / "xueqiu"
    (skill_dir / "methods").mkdir(parents=True, exist_ok=True)
    (skill_dir / "SKILL.md").write_text(
        "\n".join(
            [
                "---",
                "name: xueqiu",
                'description: "Login-gated finance channel"',
                "version: 1",
                "languages: [zh, mixed]",
                "methods:",
                "  - id: api_search",
                "    impl: methods/api_search.py",
                "    requires: [env:XUEQIU_COOKIES]",
                "fallback_chain: [api_search]",
                "quality_hint:",
                "  typical_yield: medium",
                "  chinese_native: true",
                "tier: 2",
                "---",
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    (skill_dir / "methods" / "api_search.py").write_text(
        "async def search(query):\n    return []\n",
        encoding="utf-8",
    )

    rendered = module.render_supported_channels(channels_root)

    assert "### Tier 2 - login/cookie gated (1)" in rendered
    assert (
        "| xueqiu | zh, mixed | env:XUEQIU_COOKIES | Login-gated finance channel | medium |"
        in rendered
    )
