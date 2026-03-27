"""Generate structured research report from collected evidence."""

name = "generate_report"
description = "Generate a structured research report from collected evidence. Includes top findings organized by route (implementation/discussion/dataset/reference), plus a summary of what was found."
when = "At the end of a research session, to produce a deliverable output from all collected evidence."
input_type = "evidence"
output_type = "report"
input_schema = {
    "type": "object",
    "properties": {
        "input": {
            "type": "array",
            "items": {"type": "object"},
            "description": "List of evidence records to include in report",
        },
        "context": {
            "type": "object",
            "properties": {
                "goal_id": {"type": "string", "default": "orchestrated"},
                "query": {"type": "string", "default": ""},
            },
        },
    },
    "required": ["input"],
}


def run(evidence, **context):
    if not evidence or not isinstance(evidence, list):
        return {"report": "No evidence to report on.", "sections": []}

    evidence = [e for e in evidence if isinstance(e, dict)]
    goal_id = context.get("goal_id", "orchestrated")
    query = context.get("query", "")

    # Try to use routeable_output
    try:
        from research.routeable_output import build_routeable_output

        routeable = build_routeable_output(
            {"id": goal_id, "title": query},
            bundle=evidence,
            judge_result={"score": 0},
        )
        return routeable
    except Exception:
        pass

    # Fallback: simple report
    sections = {}
    for item in evidence:
        source = str(item.get("source", item.get("provider", "unknown")))
        if source not in sections:
            sections[source] = []
        sections[source].append(item)

    report_lines = [f"# Research Report", f"", f"Query: {query}", f"Total evidence: {len(evidence)}", ""]
    for section_name, items in sections.items():
        report_lines.append(f"## {section_name} ({len(items)} items)")
        for item in items[:10]:
            title = item.get("title", "Untitled")
            url = item.get("url", "")
            report_lines.append(f"- [{title}]({url})")
        report_lines.append("")

    return {"report": "\n".join(report_lines), "sections": list(sections.keys()), "total": len(evidence)}


def test():
    evidence = [
        {"title": "A", "url": "a.com", "source": "github"},
        {"title": "B", "url": "b.com", "source": "web"},
    ]
    result = run(evidence, query="test")
    assert "report" in result or "routes" in result
    return "ok"
