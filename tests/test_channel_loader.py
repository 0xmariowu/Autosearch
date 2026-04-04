import asyncio
import sys
from pathlib import Path
from typing import Optional

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

import channels as channel_loader

SEARCH_IMPL = """async def search(query, max_results=10):
    return []
"""


@pytest.fixture
def channels_dir(tmp_path, monkeypatch):
    base_dir = tmp_path / "channels"
    base_dir.mkdir()
    init_file = base_dir / "__init__.py"
    init_file.write_text("", encoding="utf-8")
    monkeypatch.setattr(channel_loader, "__file__", str(init_file))

    existing_modules = {
        name for name in sys.modules if name.startswith(f"{channel_loader.__name__}.")
    }
    yield base_dir
    for name in list(sys.modules):
        if (
            name.startswith(f"{channel_loader.__name__}.")
            and name not in existing_modules
        ):
            sys.modules.pop(name, None)


def make_channel(
    base_dir: Path,
    name: str,
    *,
    search_source: Optional[str] = SEARCH_IMPL,
    skill_md: Optional[str] = None,
) -> Path:
    channel_dir = base_dir / name
    channel_dir.mkdir()

    if search_source is not None:
        (channel_dir / "search.py").write_text(search_source, encoding="utf-8")

    if skill_md is not None:
        (channel_dir / "SKILL.md").write_text(skill_md, encoding="utf-8")

    return channel_dir


def test_load_empty(channels_dir):
    assert channel_loader.load_channels() == {}


def test_load_valid_channel(channels_dir):
    make_channel(channels_dir, "reddit")

    channels = channel_loader.load_channels()

    assert list(channels) == ["reddit"]
    assert callable(channels["reddit"])


def test_skip_underscore_prefix(channels_dir):
    make_channel(channels_dir, "_engines")

    assert channel_loader.load_channels() == {}


def test_skip_pycache(channels_dir):
    make_channel(channels_dir, "__pycache__")

    assert channel_loader.load_channels() == {}


def test_skip_missing_search_py(channels_dir):
    make_channel(channels_dir, "github", search_source=None)

    assert channel_loader.load_channels() == {}


def test_skip_no_search_function(channels_dir):
    make_channel(
        channels_dir,
        "hackernews",
        search_source="VALUE = 1\n",
    )

    assert channel_loader.load_channels() == {}


def test_aliases_inline(channels_dir):
    make_channel(
        channels_dir,
        "paperswithcode",
        skill_md="---\naliases: [alt-name]\n---\n",
    )

    channels = channel_loader.load_channels()

    assert set(channels) == {"alt-name", "paperswithcode"}
    assert channels["paperswithcode"] is channels["alt-name"]


def test_aliases_list(channels_dir):
    make_channel(
        channels_dir,
        "arxiv",
        skill_md='---\naliases:\n  - alt-one\n  - "alt-two"\n---\n',
    )

    channels = channel_loader.load_channels()

    assert set(channels) == {"alt-one", "alt-two", "arxiv"}
    assert channels["arxiv"] is channels["alt-one"]
    assert channels["arxiv"] is channels["alt-two"]


def test_duplicate_name_skipped(channels_dir):
    make_channel(
        channels_dir,
        "alpha",
        skill_md="---\naliases: [dup]\n---\n",
    )
    make_channel(
        channels_dir,
        "dup",
        search_source="""async def search(query, max_results=10):
    return [{"source": "dup"}]
""",
    )

    channels = channel_loader.load_channels()

    assert set(channels) == {"alpha", "dup"}
    results = asyncio.run(channels["dup"]("test"))
    assert results == []
