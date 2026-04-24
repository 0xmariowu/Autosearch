#!/usr/bin/env python3
"""F012 S3: Experience Layer end-to-end validation.

Simulates 10 run_channel events for a fake channel and verifies:
- patterns.jsonl has 10 entries
- experience.md is auto-generated and <= 120 lines

Usage: python scripts/validate/test_experience_e2e.py
"""

from __future__ import annotations

import json
import sys
import tempfile
from datetime import UTC, datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parents[2]))

from autosearch.core.experience_compact import compact
from autosearch.skills.experience import append_event, should_compact

CHANNEL = "test-experience-channel"
N_EVENTS = 10


def main() -> int:
    with tempfile.TemporaryDirectory() as tmpdir:
        # Bug 4 (fix-plan v8 follow-up): runtime experience writes resolve
        # via AUTOSEARCH_EXPERIENCE_DIR (or ~/.autosearch/experience), NOT
        # via the bundled skills _SKILLS_ROOT. Patching the latter targeted
        # the wrong file path so the test's "verify patterns.jsonl exists"
        # check would later read a stale/missing file in real installs.
        import os

        os.environ["AUTOSEARCH_EXPERIENCE_DIR"] = tmpdir

        tmp_path = Path(tmpdir)
        channel_dir = tmp_path / "channels" / CHANNEL / "experience"
        channel_dir.mkdir(parents=True)
        patterns_file = channel_dir / "patterns.jsonl"

        # Append 10 events with winning_pattern so compact() can promote
        for i in range(N_EVENTS):
            append_event(
                CHANNEL,
                {
                    "skill": CHANNEL,
                    "query": f"query_{i}",
                    "outcome": "success",
                    "count_returned": 5,
                    "count_total": 10,
                    "winning_pattern": "use specific technical terms for better yield",
                    "ts": datetime.now(UTC).isoformat(),
                },
            )

        # Verify patterns.jsonl
        lines = patterns_file.read_text(encoding="utf-8").strip().splitlines()
        if len(lines) != N_EVENTS:
            print(f"FAIL: expected {N_EVENTS} events in patterns.jsonl, got {len(lines)}")
            return 1
        for line in lines:
            json.loads(line)  # must be valid JSON

        print(f"patterns.jsonl: {len(lines)} entries — OK")

        # Trigger compact
        should_compact(CHANNEL)
        compact(CHANNEL)

        # compact() writes to <runtime_root>/<group>/<skill>/experience.md
        # (per the v2 runtime path that resolves via AUTOSEARCH_EXPERIENCE_DIR).
        experience_md = tmp_path / "channels" / CHANNEL / "experience.md"
        if not experience_md.exists():
            print("FAIL: experience.md not created by compact()")
            return 1

        md_lines = experience_md.read_text(encoding="utf-8").splitlines()
        if len(md_lines) > 120:
            print(f"FAIL: experience.md has {len(md_lines)} lines (> 120)")
            return 1

        print(f"experience.md: {len(md_lines)} lines — OK")
        print("PASS")
        return 0


if __name__ == "__main__":
    sys.exit(main())
