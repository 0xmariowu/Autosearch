"""Simple local evidence index abstraction."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any


class LocalEvidenceIndex:
    def __init__(self, path: str | Path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)

    def add(self, records: list[dict[str, Any]]) -> int:
        existing = self.load_all()
        seen = {
            str(item.get("url") or "") or str(item.get("title") or "")
            for item in existing
        }
        added = 0
        with self.path.open("a", encoding="utf-8") as handle:
            for record in list(records or []):
                key = str(record.get("url") or "") or str(record.get("title") or "")
                if not key or key in seen:
                    continue
                handle.write(json.dumps(record, ensure_ascii=False) + "\n")
                seen.add(key)
                added += 1
        return added

    def load_all(self) -> list[dict[str, Any]]:
        if not self.path.exists():
            return []
        rows: list[dict[str, Any]] = []
        for line in self.path.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            try:
                payload = json.loads(line)
            except json.JSONDecodeError:
                continue
            if isinstance(payload, dict):
                rows.append(payload)
        return rows
