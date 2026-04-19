#!/usr/bin/env python3
"""Regenerate the README channels table from autosearch/skills/channels/*/SKILL.md."""

from __future__ import annotations

import argparse
import re
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

from autosearch.init.channel_status import (
    TIER_LABELS,
    infer_tier_from_requires,
    required_env_tokens_from_requires,
)

START_MARKER = "<!-- channels-table-start -->"
END_MARKER = "<!-- channels-table-end -->"
TIER_ORDER = ("t0", "t1", "t2", "scaffold")
REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_CHANNELS_ROOT = REPO_ROOT / "autosearch" / "skills" / "channels"
DEFAULT_README_PATH = REPO_ROOT / "README.md"


@dataclass(frozen=True, slots=True)
class ChannelDocRow:
    name: str
    description: str
    languages: list[str]
    required_env: list[str]
    typical_yield: str
    tier: str


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=__doc__,
        epilog="Run this after adding or changing a channel skill to keep README.md in sync.",
    )
    parser.add_argument(
        "--channels-root",
        type=Path,
        default=DEFAULT_CHANNELS_ROOT,
        help="Path to the channel skills root. Defaults to autosearch/skills/channels.",
    )
    parser.add_argument(
        "--readme",
        type=Path,
        default=DEFAULT_README_PATH,
        help="Path to the README to update. Defaults to this repo's README.md.",
    )
    parser.add_argument(
        "--check",
        action="store_true",
        help="Exit non-zero if README.md differs from the generated channel tables.",
    )
    return parser.parse_args(argv)


def extract_frontmatter(raw_text: str) -> dict[str, Any]:
    lines = raw_text.splitlines()
    try:
        start = next(index for index, line in enumerate(lines) if line.strip() == "---")
        end = next(index for index in range(start + 1, len(lines)) if lines[index].strip() == "---")
    except StopIteration as exc:
        raise ValueError("frontmatter delimiters not found") from exc

    payload = yaml.safe_load("\n".join(lines[start + 1 : end]).strip())
    if not isinstance(payload, dict):
        raise ValueError("frontmatter must be a YAML mapping")
    return payload


def load_channel_rows(channels_root: Path) -> list[ChannelDocRow]:
    rows: list[ChannelDocRow] = []

    for skill_path in sorted(channels_root.glob("*/SKILL.md")):
        payload = extract_frontmatter(skill_path.read_text(encoding="utf-8"))
        name = str(payload["name"])
        quality_hint = payload.get("quality_hint")
        typical_yield = "unknown"
        if isinstance(quality_hint, dict):
            typical_yield = str(quality_hint.get("typical_yield", "unknown"))

        requires_by_method = shipped_method_requires(payload, skill_path.parent)
        rows.append(
            ChannelDocRow(
                name=name,
                description=str(payload.get("description", "")).strip(),
                languages=[str(language) for language in payload.get("languages", [])],
                required_env=required_env_tokens_from_requires(requires_by_method),
                typical_yield=typical_yield,
                tier=infer_tier_from_requires(requires_by_method),
            )
        )

    return rows


def render_supported_channels(channels_root: Path) -> str:
    rows = load_channel_rows(channels_root)
    grouped = {tier: [row for row in rows if row.tier == tier] for tier in TIER_ORDER}

    lines: list[str] = []
    for tier in ("t0", "t1", "t2"):
        lines.extend(_render_tier(grouped[tier], tier=tier))
        lines.append("")

    if grouped["scaffold"]:
        lines.extend(_render_tier(grouped["scaffold"], tier="scaffold"))
        lines.append("")

    return "\n".join(lines).strip()


def replace_marked_section(readme_text: str, generated_section: str) -> str:
    start_index = readme_text.find(START_MARKER)
    end_index = readme_text.find(END_MARKER)
    if start_index == -1 or end_index == -1 or end_index < start_index:
        raise ValueError("markers not found")
    prefix = readme_text[:start_index]
    suffix = readme_text[end_index + len(END_MARKER) :]
    replacement = f"{START_MARKER}\n{generated_section}\n{END_MARKER}"
    return prefix + replacement + suffix


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)

    try:
        readme_text = args.readme.read_text(encoding="utf-8")
    except OSError as exc:
        print(f"ERROR: failed to read README: {exc}", file=sys.stderr)
        return 1

    try:
        generated = render_supported_channels(args.channels_root)
        updated = replace_marked_section(readme_text, generated)
    except ValueError as exc:
        if str(exc) == "markers not found":
            print("ERROR: markers not found", file=sys.stderr)
            return 1
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1

    if args.check:
        if updated != readme_text:
            print("ERROR: README.md is out of date", file=sys.stderr)
            return 1
        return 0

    if updated != readme_text:
        args.readme.write_text(updated, encoding="utf-8")
    return 0


def _render_tier(rows: list[ChannelDocRow], *, tier: str) -> list[str]:
    lines = [f"### {TIER_LABELS[tier]} ({len(rows)})"]
    if tier in {"t1", "t2"}:
        lines.extend(
            [
                "| Channel | Languages | Required env | Description | Typical yield |",
                "|---|---|---|---|---|",
            ]
        )
        for row in rows:
            lines.append(
                "| "
                f"{escape_cell(row.name)} | "
                f"{escape_cell(format_list(row.languages))} | "
                f"{escape_cell(format_list(row.required_env))} | "
                f"{escape_cell(row.description)} | "
                f"{escape_cell(row.typical_yield)} |"
            )
        return lines

    lines.extend(
        [
            "| Channel | Languages | Description | Typical yield |",
            "|---|---|---|---|",
        ]
    )
    for row in rows:
        lines.append(
            "| "
            f"{escape_cell(row.name)} | "
            f"{escape_cell(format_list(row.languages))} | "
            f"{escape_cell(row.description)} | "
            f"{escape_cell(row.typical_yield)} |"
        )
    return lines


def escape_cell(value: str) -> str:
    return re.sub(r"\s+", " ", value.replace("|", "\\|")).strip() or "-"


def format_list(values: list[str]) -> str:
    return ", ".join(values) if values else "-"


def shipped_method_requires(payload: dict[str, Any], skill_dir: Path) -> list[list[str]]:
    methods = payload.get("methods", [])
    if not isinstance(methods, list):
        raise ValueError("methods must be a list")

    requires_by_method: list[list[str]] = []
    for method in methods:
        if not isinstance(method, dict):
            raise ValueError("each method must be a mapping")
        impl = method.get("impl")
        if not isinstance(impl, str):
            raise ValueError("method impl must be a string")
        if not (skill_dir / impl).is_file():
            continue
        requires = method.get("requires", [])
        if not isinstance(requires, list):
            raise ValueError("method requires must be a list")
        requires_by_method.append([str(token) for token in requires])

    return requires_by_method


if __name__ == "__main__":
    raise SystemExit(main())
