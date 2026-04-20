# Self-written, plan v2.3 § 13.5 F301
import pytest
from pydantic import ValidationError

from autosearch.core.models import EvidenceSnippet


def test_evidence_snippet_roundtrip() -> None:
    snippet = EvidenceSnippet(
        evidence_id="session-evidence-1",
        text="Chunked evidence body.",
        offset=128,
        source_url="https://example.com/source",
        source_title="Example Source",
    )

    payload = snippet.model_dump_json()
    restored = EvidenceSnippet.model_validate_json(payload)

    assert restored == snippet


def test_evidence_snippet_offset_non_negative() -> None:
    with pytest.raises(ValidationError):
        EvidenceSnippet(
            evidence_id="session-evidence-1",
            text="Chunked evidence body.",
            offset=-1,
            source_url="https://example.com/source",
        )


def test_evidence_snippet_default_source_title_empty() -> None:
    snippet = EvidenceSnippet(
        evidence_id="session-evidence-2",
        text="Chunked evidence body.",
        offset=0,
        source_url="https://example.com/source",
    )

    assert snippet.source_title == ""
