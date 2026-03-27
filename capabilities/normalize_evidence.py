"""Normalize raw hit dicts into standard evidence records."""

name = "normalize_evidence"
description = "Convert raw search hits or document dicts into normalized evidence records with consistent fields."
when = "When you have raw hits or documents that need to be standardized into evidence format for judging or reporting."
input_type = "hits"
output_type = "evidence"


def run(input, **context):
    from evidence import coerce_evidence_records

    items = [input] if isinstance(input, dict) else list(input or [])
    items = [d for d in items if isinstance(d, dict)]
    if not items:
        return []
    return coerce_evidence_records(items)


def test():
    from evidence import coerce_evidence_records

    records = coerce_evidence_records(
        [
            {
                "title": "Test Page",
                "url": "https://example.com",
                "body": "Some content here",
                "source": "test",
                "query": "test query",
            }
        ]
    )
    assert len(records) == 1
    assert records[0]["record_type"] == "evidence"
    assert records[0]["title"] == "Test Page"
    return "ok"
