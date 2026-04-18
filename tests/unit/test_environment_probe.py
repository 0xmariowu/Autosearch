# Self-written, plan autosearch-0418-channels-and-skills.md § F003
from pathlib import Path
from textwrap import dedent

import pytest

import autosearch.core.environment_probe as probe_module


def _write_skill(root: Path, *, name: str, requires: list[str]) -> None:
    skill_dir = root / name
    skill_dir.mkdir(parents=True, exist_ok=True)
    requires_yaml = ", ".join(requires)
    (skill_dir / "SKILL.md").write_text(
        dedent(
            f"""
            ---
            name: {name}
            description: "Fixture skill."
            version: 1
            languages: [en]
            methods:
              - id: fixture_method
                impl: methods/fixture.py
                requires: [{requires_yaml}]
            fallback_chain: [fixture_method]
            ---
            """
        ).strip()
        + "\n",
        encoding="utf-8",
    )


def test_probe_environment_empty_when_nothing_present(tmp_path: Path) -> None:
    env = probe_module.probe_environment(
        cookies_dir=tmp_path / "cookies",
        env_keys_to_check=[],
    )

    assert env.cookies == set()
    assert env.mcp_servers == set()
    assert env.env_keys == set()
    assert env.binaries == set()


def test_probe_environment_detects_set_env_var(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    monkeypatch.setenv("EXAMPLE_API_KEY", "present")

    env = probe_module.probe_environment(
        cookies_dir=tmp_path / "cookies",
        env_keys_to_check=["EXAMPLE_API_KEY"],
    )

    assert env.env_keys == {"EXAMPLE_API_KEY"}


def test_probe_environment_ignores_empty_env_var(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    monkeypatch.setenv("EMPTY_API_KEY", "")

    env = probe_module.probe_environment(
        cookies_dir=tmp_path / "cookies",
        env_keys_to_check=["EMPTY_API_KEY"],
    )

    assert env.env_keys == set()


def test_probe_environment_detects_cookie_files(tmp_path: Path) -> None:
    cookies_dir = tmp_path / "cookies"
    cookies_dir.mkdir()
    (cookies_dir / "zhihu.json").write_text("{}", encoding="utf-8")
    (cookies_dir / "weibo.json").write_text("{}", encoding="utf-8")

    env = probe_module.probe_environment(cookies_dir=cookies_dir, env_keys_to_check=[])

    assert env.cookies == {"weibo", "zhihu"}


def test_probe_environment_discovers_env_requires_from_skill_frontmatter(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    channels_root = tmp_path / "channels"
    _write_skill(channels_root, name="fixture", requires=["env:FAKE_VAR"])
    monkeypatch.setattr(probe_module, "KNOWN_ENV_KEYS", set())
    monkeypatch.setattr(probe_module, "_default_channels_root", lambda: channels_root)
    monkeypatch.setenv("FAKE_VAR", "configured")

    env = probe_module.probe_environment(cookies_dir=tmp_path / "cookies")

    assert "FAKE_VAR" in env.env_keys
