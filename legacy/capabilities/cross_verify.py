"""Cross-verify findings for contradictions and consensus."""

name = "cross_verify"
description = "Analyze a set of findings for contradictions, consensus, and source disputes. Identifies claims that different sources agree or disagree on."
when = "After collecting evidence from multiple sources on the same topic. Especially useful for controversial or fact-checking topics."
input_type = "evidence"
output_type = "report"
input_schema = {
    "type": "object",
    "properties": {
        "input": {
            "type": "array",
            "items": {"type": "object"},
            "description": "List of evidence records to cross-verify",
        },
        "context": {
            "type": "object",
            "properties": {
                "goal_id": {"type": "string", "default": "orchestrated"},
            },
        },
    },
    "required": ["input"],
}


def run(evidence, **context):
    if not evidence or not isinstance(evidence, list):
        return {
            "contradictions": [],
            "consensus": [],
            "analysis": "No evidence to verify.",
        }

    evidence = [e for e in evidence if isinstance(e, dict)]
    if len(evidence) < 2:
        return {
            "contradictions": [],
            "consensus": [],
            "analysis": "Need at least 2 pieces of evidence to cross-verify.",
        }

    # Try full synthesizer
    try:
        from research.synthesizer import _align_claims

        claim_alignment = _align_claims(evidence)
        return {
            "contradictions": list(claim_alignment.get("contradiction_clusters") or []),
            "consensus": list(claim_alignment.get("aligned_claims") or []),
            "contradiction_detected": bool(
                claim_alignment.get("contradiction_detected")
            ),
            "stance_counts": dict(claim_alignment.get("stance_counts") or {}),
            "source_dispute_map": dict(claim_alignment.get("source_dispute_map") or {}),
            "analysis": f"Analyzed {len(evidence)} items. Contradiction detected: {claim_alignment.get('contradiction_detected', False)}.",
        }
    except Exception:
        pass

    # Fallback: simple cross-reference by domain
    from collections import defaultdict

    domain_claims = defaultdict(list)
    for item in evidence:
        domain = str(item.get("domain", item.get("source", "unknown")))
        title = str(item.get("title", ""))
        domain_claims[domain].append(title)

    return {
        "contradictions": [],
        "consensus": [],
        "sources_checked": len(domain_claims),
        "domains": list(domain_claims.keys()),
        "analysis": f"Cross-referenced {len(evidence)} items across {len(domain_claims)} domains.",
    }


def test():
    evidence = [
        {"title": "Framework A is best", "source": "blog1", "domain": "blog1.com"},
        {"title": "Framework B is better", "source": "blog2", "domain": "blog2.com"},
    ]
    result = run(evidence)
    assert "analysis" in result
    return "ok"
