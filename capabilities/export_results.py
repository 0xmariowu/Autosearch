"""Export search results to structured formats."""

name = "export_results"
description = "Export search results to CSV, JSONL, or Markdown format. Produces a clean, shareable output from collected evidence."
when = "At the end of a search session to produce a deliverable output."
input_type = "hits"
output_type = "report"
input_schema = {
    "type": "object",
    "properties": {
        "input": {
            "type": "array",
            "items": {"type": "object"},
            "description": "List of hit dicts to export",
        },
        "context": {
            "type": "object",
            "properties": {
                "format": {"type": "string", "enum": ["markdown", "csv", "jsonl"], "default": "markdown"},
                "output_path": {"type": "string", "description": "Optional file path to write output"},
            },
        },
    },
    "required": ["input"],
}

import json
from pathlib import Path


def run(hits, **context):
    fmt = context.get("format", "markdown")
    output_path = context.get("output_path", "")
    hits = [h for h in (hits or []) if isinstance(h, dict)]

    if fmt == "csv":
        lines = ["title,url,source,score,domain"]
        for h in hits:
            title = str(h.get("title", "")).replace(",", " ").replace('"', "'")
            url = h.get("url", "")
            source = h.get("provider", h.get("source", ""))
            score = h.get("score_hint", 0)
            domain = h.get("domain", "")
            lines.append(f'"{title}",{url},{source},{score},{domain}')
        content = "\n".join(lines)

    elif fmt == "jsonl":
        content = "\n".join(json.dumps(h, default=str, ensure_ascii=False) for h in hits)

    else:  # markdown
        lines = [f"# Search Results ({len(hits)} items)", ""]
        # Group by quality tier if available
        high = [h for h in hits if h.get("quality_tier") == "high"]
        medium = [h for h in hits if h.get("quality_tier") != "high"]

        if high:
            lines.append(f"## High Quality ({len(high)})")
            lines.append("")
            for i, h in enumerate(high, 1):
                title = h.get("title", "Untitled")
                url = h.get("url", "")
                source = h.get("provider", h.get("source", ""))
                lines.append(f"{i}. [{title}]({url}) — {source}")
            lines.append("")

        if medium:
            lines.append(f"## Other ({len(medium)})")
            lines.append("")
            for i, h in enumerate(medium, 1):
                title = h.get("title", "Untitled")
                url = h.get("url", "")
                source = h.get("provider", h.get("source", ""))
                lines.append(f"{i}. [{title}]({url}) — {source}")

        content = "\n".join(lines)

    # Write to file if path given
    if output_path:
        Path(output_path).parent.mkdir(parents=True, exist_ok=True)
        Path(output_path).write_text(content, encoding="utf-8")

    return {"format": fmt, "content": content, "count": len(hits), "output_path": output_path or ""}


def test():
    sample = [
        {"title": "Repo A", "url": "https://github.com/a", "provider": "github", "score_hint": 100, "quality_tier": "high"},
        {"title": "Article B", "url": "https://blog.com/b", "provider": "web", "score_hint": 50, "quality_tier": "medium"},
    ]
    # Test markdown
    md = run(sample, format="markdown")
    assert md["count"] == 2
    assert "High Quality" in md["content"]

    # Test CSV
    csv = run(sample, format="csv")
    assert "title,url" in csv["content"]

    # Test JSONL
    jl = run(sample, format="jsonl")
    assert jl["count"] == 2
    return "ok"
