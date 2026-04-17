# Source: open_deep_research/src/open_deep_research/prompts.py:L186-L220 (adapted)
import re
from collections import Counter

from autosearch.core.models import Evidence, Section

_INLINE_CITATION_RE = re.compile(r"\[(\d+)\]")


class CitationRenderer:
    def render_references(self, evidences: list[Evidence]) -> str:
        lines = ["## References"]
        for index, evidence in enumerate(evidences, start=1):
            title = evidence.title.strip() or "Untitled"
            lines.append(f"[{index}] {title} — {evidence.url}")
        return "\n".join(lines)

    def sources_breakdown(self, evidences: list[Evidence]) -> str:
        counts = Counter(evidence.source_channel for evidence in evidences)
        lines = ["## Sources", "| Platform | Count |", "|---|---|"]
        for platform, count in sorted(counts.items(), key=lambda item: (-item[1], item[0])):
            lines.append(f"| {platform} | {count} |")
        return "\n".join(lines)

    def remap_citations(
        self,
        sections: list[Section],
        evidences: list[Evidence],
    ) -> tuple[list[Section], list[Evidence]]:
        canonical_by_url: dict[str, int] = {}
        for old_ref_id, evidence in enumerate(evidences, start=1):
            canonical_by_url.setdefault(evidence.url, old_ref_id)

        canonical_to_new: dict[int, int] = {}
        old_to_new: dict[int, int] = {}
        remapped_evidences: list[Evidence] = []

        for section in sections:
            for old_ref_id in _ordered_ref_ids(section):
                if old_ref_id < 1 or old_ref_id > len(evidences):
                    continue
                evidence = evidences[old_ref_id - 1]
                canonical_old_ref_id = canonical_by_url[evidence.url]
                new_ref_id = canonical_to_new.get(canonical_old_ref_id)
                if new_ref_id is None:
                    new_ref_id = len(remapped_evidences) + 1
                    canonical_to_new[canonical_old_ref_id] = new_ref_id
                    remapped_evidences.append(evidences[canonical_old_ref_id - 1])
                old_to_new[old_ref_id] = new_ref_id
                old_to_new[canonical_old_ref_id] = new_ref_id

        remapped_sections = [
            section.model_copy(
                update={
                    "content": _replace_citations(section.content, old_to_new),
                    "ref_ids": _remap_ref_ids(section, old_to_new),
                }
            )
            for section in sections
        ]

        return remapped_sections, remapped_evidences


def _ordered_ref_ids(section: Section) -> list[int]:
    content_ref_ids = [
        int(match.group(1)) for match in _INLINE_CITATION_RE.finditer(section.content)
    ]
    ordered_ref_ids = content_ref_ids + section.ref_ids

    seen: set[int] = set()
    deduped: list[int] = []
    for ref_id in ordered_ref_ids:
        if ref_id in seen:
            continue
        seen.add(ref_id)
        deduped.append(ref_id)
    return deduped


def _replace_citations(content: str, old_to_new: dict[int, int]) -> str:
    def replacer(match: re.Match[str]) -> str:
        old_ref_id = int(match.group(1))
        new_ref_id = old_to_new.get(old_ref_id)
        if new_ref_id is None:
            return match.group(0)
        return f"[{new_ref_id}]"

    return _INLINE_CITATION_RE.sub(replacer, content)


def _remap_ref_ids(section: Section, old_to_new: dict[int, int]) -> list[int]:
    updated_content = _replace_citations(section.content, old_to_new)
    content_ref_ids = [
        int(match.group(1)) for match in _INLINE_CITATION_RE.finditer(updated_content)
    ]
    mapped_ref_ids = [old_to_new[ref_id] for ref_id in section.ref_ids if ref_id in old_to_new]
    ordered_ref_ids = content_ref_ids + mapped_ref_ids

    seen: set[int] = set()
    deduped: list[int] = []
    for ref_id in ordered_ref_ids:
        if ref_id in seen:
            continue
        seen.add(ref_id)
        deduped.append(ref_id)
    return deduped
