#!/usr/bin/env python3
"""AutoSearch doctor — static source capability checks."""

from __future__ import annotations

import argparse

from source_capability import (
    LATEST_CAPABILITY_PATH,
    format_source_capability_report,
    refresh_source_capability,
    runtime_provider_names,
)


def main() -> None:
    parser = argparse.ArgumentParser(description="AutoSearch source capability doctor")
    parser.add_argument(
        "--runtime-only",
        action="store_true",
        help="Check only runtime providers used by autosearch execution",
    )
    args = parser.parse_args()

    selected = runtime_provider_names() if args.runtime_only else None
    report = refresh_source_capability(selected)
    print(format_source_capability_report(report))
    print(f"\nReport: {LATEST_CAPABILITY_PATH}")


if __name__ == "__main__":
    main()
