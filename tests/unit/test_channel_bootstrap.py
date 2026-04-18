# Self-written, plan autosearch-0418-channels-and-skills.md § F003
from pathlib import Path

from autosearch.channels.base import Environment
from autosearch.channels.demo import DemoChannel
from autosearch.core.channel_bootstrap import _build_channels


def _skills_root() -> Path:
    return Path(__file__).resolve().parents[2] / "skills" / "channels"


def test_build_channels_falls_back_to_demo_for_empty_skills_dir(tmp_path: Path) -> None:
    channels = _build_channels(channels_root=tmp_path, env=Environment())

    assert len(channels) == 1
    assert isinstance(channels[0], DemoChannel)


def test_build_channels_includes_youtube_when_key_available() -> None:
    channels = _build_channels(
        channels_root=_skills_root(),
        env=Environment(env_keys={"YOUTUBE_API_KEY"}),
    )
    names = {channel.name for channel in channels}

    assert {"arxiv", "ddgs", "hackernews", "youtube"} <= names


def test_build_channels_excludes_youtube_without_key() -> None:
    channels = _build_channels(channels_root=_skills_root(), env=Environment())
    names = {channel.name for channel in channels}

    assert {"arxiv", "ddgs", "hackernews"} <= names
    assert "youtube" not in names
