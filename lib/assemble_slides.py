#!/usr/bin/env python3
"""Assemble AutoSearch presentation slides from body HTML + template.

Usage:
    python3 lib/assemble_slides.py --body delivery/ID-slides-body.html \
        --meta '{"topic":"...","version":"..."}' \
        --output delivery/ID-slides.html

Body HTML should contain <section> elements (one per slide), using the
template's CSS classes. reveal.js wraps each <section> as a slide.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TEMPLATE_PATH = ROOT / "lib" / "templates" / "slides.html"


def detect_lang(body: str) -> str:
    chinese_chars = len(re.findall(r"[\u4e00-\u9fff]", body[:2000]))
    return "zh-CN" if chinese_chars > 50 else "en"


def assemble(body_path: Path, meta: dict, output_path: Path) -> None:
    if not TEMPLATE_PATH.exists():
        print(f"ERROR: Template not found at {TEMPLATE_PATH}", file=sys.stderr)
        sys.exit(1)

    template = TEMPLATE_PATH.read_text(encoding="utf-8")
    body = body_path.read_text(encoding="utf-8")

    title = meta.get("topic", "AutoSearch Presentation")
    lang = detect_lang(body)

    html = template
    html = html.replace("{{LANG}}", lang)
    html = html.replace("{{TITLE}}", title)
    html = html.replace("{{BODY}}", body)

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(html, encoding="utf-8")
    print(f"Assembled: {output_path} ({len(html):,} bytes)")


def main() -> int:
    parser = argparse.ArgumentParser(description="Assemble AutoSearch slides")
    parser.add_argument("--body", required=True, help="Path to slides body HTML")
    parser.add_argument("--meta", help="JSON string with metadata")
    parser.add_argument("--meta-file", help="Path to JSON metadata file")
    parser.add_argument("--output", required=True, help="Output HTML path")
    args = parser.parse_args()

    if args.meta_file:
        meta = json.loads(Path(args.meta_file).read_text())
    elif args.meta:
        meta = json.loads(args.meta)
    else:
        meta = {}

    body_path = Path(args.body)
    if not body_path.exists():
        print(f"ERROR: Body file not found: {body_path}", file=sys.stderr)
        return 1

    assemble(body_path, meta, Path(args.output))
    return 0


if __name__ == "__main__":
    sys.exit(main())
