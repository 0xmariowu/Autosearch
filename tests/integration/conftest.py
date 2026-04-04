"""Shared fixtures for integration tests."""

from __future__ import annotations

import json
import os
import shutil
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]

TOPICS = [
    {"id": "t1", "topic": "self-evolving AI agents", "lang": "en"},
    {"id": "t2", "topic": "vector databases for RAG", "lang": "en"},
    {"id": "t3", "topic": "smart wearable market 2026", "lang": "en"},
    {"id": "t4", "topic": "中国大模型生态", "lang": "zh"},
    {"id": "t5", "topic": "production RAG systems", "lang": "en"},
]

QUERY_CAPS = {"quick": 8, "standard": 15, "deep": 25}

MODELS = {
    "sonnet": "anthropic/claude-sonnet-4-6",
    "haiku": "anthropic/claude-haiku-4-5",
}


class SessionDir:
    """Isolated session directory for one topic run."""

    def __init__(self, base: Path, topic_id: str, session_id: str) -> None:
        self.root = base / topic_id
        self.id = session_id
        self.topic_id = topic_id

        # Create directory structure
        for d in ("state", "evidence", "delivery"):
            (self.root / d).mkdir(parents=True, exist_ok=True)

        # Copy config.json from project
        src = ROOT / "state" / "config.json"
        if src.exists():
            shutil.copy2(src, self.root / "state" / "config.json")

        # Initialize empty state files
        for f in ("patterns-v2.jsonl", "worklog.jsonl", "rubric-history.jsonl"):
            p = self.root / "state" / f
            if not p.exists():
                p.write_text("")

    @property
    def slug(self) -> str:
        return self.id.split("-", 1)[-1] if "-" in self.id else self.id

    @property
    def queries_path(self) -> Path:
        return self.root / "state" / f"session-{self.id}-queries.json"

    @property
    def knowledge_path(self) -> Path:
        return self.root / "state" / f"session-{self.id}-knowledge.md"

    @property
    def results_path(self) -> Path:
        return self.root / "evidence" / f"{self.id}-results.jsonl"

    @property
    def rubrics_path(self) -> Path:
        return self.root / "evidence" / f"rubrics-{self.slug}.jsonl"

    def write_timing_start(self) -> None:
        ts = datetime.now(timezone.utc).isoformat()
        (self.root / "state" / "timing.json").write_text(json.dumps({"start_ts": ts}))

    def write_timing_end(self) -> None:
        p = self.root / "state" / "timing.json"
        data = json.loads(p.read_text()) if p.exists() else {}
        data["end_ts"] = datetime.now(timezone.utc).isoformat()
        p.write_text(json.dumps(data))

    def read_results(self) -> list[dict]:
        if not self.results_path.exists():
            return []
        lines = self.results_path.read_text().strip().split("\n")
        return [json.loads(line) for line in lines if line.strip()]

    def read_rubrics(self) -> list[dict]:
        if not self.rubrics_path.exists():
            return []
        lines = self.rubrics_path.read_text().strip().split("\n")
        return [json.loads(line) for line in lines if line.strip()]

    def read_knowledge(self) -> str:
        if self.knowledge_path.exists():
            return self.knowledge_path.read_text()
        return ""

    def read_delivery(self) -> str:
        for ext in (".md", ".html"):
            p = self.root / "delivery" / f"{self.id}{ext}"
            if p.exists():
                return p.read_text()
        return ""

    def delivery_path(self) -> Path | None:
        for ext in (".md", ".html"):
            p = self.root / "delivery" / f"{self.id}{ext}"
            if p.exists():
                return p
        return None


def read_skill(name: str) -> str:
    """Read a skill's SKILL.md content."""
    p = ROOT / "skills" / name / "SKILL.md"
    if p.exists():
        return p.read_text()
    return ""


def read_skills(names: list[str]) -> str:
    """Read multiple skills, concatenated."""
    parts = []
    for name in names:
        content = read_skill(name)
        if content:
            parts.append(f"--- SKILL: {name} ---\n{content}")
    return "\n\n".join(parts)


def read_plugin_version() -> str:
    """Read version from plugin.json."""
    p = ROOT / ".claude-plugin" / "plugin.json"
    if p.exists():
        return json.loads(p.read_text()).get("version", "unknown")
    return "unknown"


def get_api_key() -> str | None:
    """Get OpenRouter API key from environment."""
    return os.environ.get("OPENROUTER_API_KEY")


def find_python() -> str:
    """Find the best Python for running search_runner."""
    venv = ROOT / ".venv" / "bin" / "python3"
    if venv.exists():
        return str(venv)
    return "python3"
