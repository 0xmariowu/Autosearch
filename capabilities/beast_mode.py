"""Force-synthesize best output when budget is exhausted."""

name = "beast_mode"
description = "When search budget is exhausted or max steps reached, force-synthesize the best possible output from all accumulated evidence and learnings. Guarantees an output even when the search couldn't fully complete."
when = "When the orchestrator hits budget limit or max_steps. Always produces output rather than failing silently."
input_type = "evidence"
output_type = "report"

input_schema = {
    "type": "object",
    "properties": {
        "input": {
            "type": "array",
            "items": {"type": "object"},
            "description": "All accumulated evidence records",
        },
        "context": {
            "type": "object",
            "properties": {
                "task_spec": {"type": "string"},
                "learnings": {"type": "array", "items": {"type": "string"}},
            },
        },
    },
    "required": ["input"],
}


def run(evidence, **context):
    learnings = context.get("learnings", [])
    task_spec = context.get("task_spec", "")
    collected_count = len(evidence) if evidence else 0

    # Deduplicate evidence by URL
    seen_urls = set()
    unique_evidence = []
    for item in (evidence or []):
        url = str(item.get("url") or "").strip()
        if url and url in seen_urls:
            continue
        if url:
            seen_urls.add(url)
        unique_evidence.append(item)

    # Sort by score if available
    unique_evidence.sort(
        key=lambda x: int(x.get("score_hint", x.get("score", 0)) or 0),
        reverse=True,
    )

    # Build summary
    top_items = unique_evidence[:20]
    summary_lines = [
        f"## Beast Mode Summary",
        f"",
        f"Task: {task_spec}",
        f"Total evidence collected: {collected_count}",
        f"Unique items: {len(unique_evidence)}",
        f"",
    ]

    if learnings:
        summary_lines.append("### Key Learnings")
        for l in learnings[:10]:
            summary_lines.append(f"- {l}")
        summary_lines.append("")

    summary_lines.append("### Top Results")
    for i, item in enumerate(top_items, 1):
        title = item.get("title", "Untitled")
        url = item.get("url", "")
        score = item.get("score_hint", item.get("score", "?"))
        summary_lines.append(f"{i}. [{title}]({url}) (score: {score})")

    return {
        "status": "beast_mode",
        "summary": "\n".join(summary_lines),
        "unique_count": len(unique_evidence),
        "top_results": top_items,
        "learnings": learnings[:10],
    }


def test():
    evidence = [
        {"title": "A", "url": "https://a.com", "score_hint": 30},
        {"title": "B", "url": "https://b.com", "score_hint": 10},
        {"title": "A dup", "url": "https://a.com", "score_hint": 25},  # duplicate
    ]
    result = run(evidence, learnings=["learning 1"], task_spec="test task")
    assert result["status"] == "beast_mode"
    assert result["unique_count"] == 2, f"Expected 2 unique, got {result['unique_count']}"
    assert "learning 1" in result["learnings"]
    return "ok"
