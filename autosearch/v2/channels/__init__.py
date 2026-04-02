from __future__ import annotations

import importlib.util
import sys
from collections.abc import Awaitable, Callable
from pathlib import Path
from types import ModuleType
from typing import Any

SearchFunction = Callable[[str, int], Awaitable[list[dict[str, Any]]]]


def _warn(message: str) -> None:
    print(f"[channels] {message}", file=sys.stderr)


def _load_search_module(channel_dir: Path) -> ModuleType | None:
    search_file = channel_dir / "search.py"
    module_name = f"{__name__}.{channel_dir.name}.search"
    spec = importlib.util.spec_from_file_location(module_name, search_file)
    if spec is None or spec.loader is None:
        _warn(f"skipping '{channel_dir.name}': could not create import spec")
        return None

    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    try:
        spec.loader.exec_module(module)
    except Exception as exc:
        sys.modules.pop(module_name, None)
        _warn(f"skipping '{channel_dir.name}': import failed: {exc}")
        return None
    return module


def _parse_aliases(frontmatter: str, channel_name: str) -> list[str]:
    aliases: list[str] = []
    lines = frontmatter.splitlines()

    for index, raw_line in enumerate(lines):
        stripped = raw_line.strip()
        if not stripped.startswith("aliases:"):
            continue

        value = stripped[len("aliases:") :].strip()
        if value:
            if value.startswith("[") and value.endswith("]"):
                for item in value[1:-1].split(","):
                    alias = item.strip().strip("'\"")
                    if alias:
                        aliases.append(alias)
            else:
                _warn(
                    f"channel '{channel_name}': unsupported aliases format in SKILL.md"
                )
            break

        for nested_line in lines[index + 1 :]:
            if not nested_line.strip():
                continue
            if not nested_line.startswith((" ", "\t")):
                break

            item = nested_line.strip()
            if not item.startswith("- "):
                continue
            alias = item[2:].strip().strip("'\"")
            if alias:
                aliases.append(alias)
        break

    return aliases


def _read_aliases(channel_dir: Path) -> list[str]:
    skill_file = channel_dir / "SKILL.md"
    if not skill_file.is_file():
        return []

    try:
        content = skill_file.read_text(encoding="utf-8")
    except Exception as exc:
        _warn(f"channel '{channel_dir.name}': could not read SKILL.md: {exc}")
        return []

    content = content.replace("\r\n", "\n")

    if not content.startswith("---"):
        return []

    end = content.find("\n---", 4)
    if end == -1:
        return []

    frontmatter = content[4:end]
    return _parse_aliases(frontmatter, channel_dir.name)


def load_channels() -> dict[str, SearchFunction]:
    channels: dict[str, SearchFunction] = {}
    base_dir = Path(__file__).resolve().parent

    for entry in sorted(base_dir.iterdir(), key=lambda path: path.name):
        if not entry.is_dir():
            continue
        if entry.name == "__pycache__" or entry.name.startswith("_"):
            continue

        search_file = entry / "search.py"
        if not search_file.is_file():
            _warn(f"skipping '{entry.name}': missing search.py")
            continue

        module = _load_search_module(entry)
        if module is None:
            continue

        search = getattr(module, "search", None)
        if not callable(search):
            _warn(f"skipping '{entry.name}': search.py does not export search()")
            continue

        names = [entry.name, *_read_aliases(entry)]
        for name in names:
            if not name:
                continue
            if name in channels:
                _warn(
                    f"channel '{entry.name}': name '{name}' already registered, skipping"
                )
                continue
            channels[name] = search

    return channels
