# Source: open_deep_research/src/open_deep_research/prompts.py:L186-L220 (adapted)
import re
from collections import Counter
from collections.abc import Callable, Iterable
from typing import Any

from autosearch.core.models import Evidence, Section

_FENCED_CODE_RE = re.compile(r"```.*?```", re.DOTALL)
_INLINE_CITATION_RE = re.compile(r"\[(\d+)\]")
_INLINE_CODE_RE = re.compile(r"`[^`]+`")


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
        scrubbed_sections = [
            section.model_copy(
                update={
                    "content": scrub_invalid_inline_citations(
                        section.content,
                        valid_ids=section.ref_ids,
                    )
                }
            )
            for section in sections
        ]

        canonical_by_url: dict[str, int] = {}
        for old_ref_id, evidence in enumerate(evidences, start=1):
            canonical_by_url.setdefault(evidence.url, old_ref_id)

        canonical_to_new: dict[int, int] = {}
        old_to_new: dict[int, int] = {}
        remapped_evidences: list[Evidence] = []

        for section in scrubbed_sections:
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
            for section in scrubbed_sections
        ]

        return remapped_sections, remapped_evidences

    def renumber_by_first_appearance(
        self,
        content: str,
        ref_table: dict[int, Any],
    ) -> tuple[str, dict[int, Any]]:
        return renumber_by_first_appearance(content, ref_table)


def apply_to_prose(content: str, fn: Callable[[str], str]) -> str:
    """Apply a text transform while preserving fenced and inline code verbatim."""
    protected_segments: list[str] = []

    def protect(match: re.Match[str]) -> str:
        protected_segments.append(match.group(0))
        return f"\x00AUT_SEARCH_CODE_{len(protected_segments) - 1}\x00"

    masked_content = _FENCED_CODE_RE.sub(protect, content)
    masked_content = _INLINE_CODE_RE.sub(protect, masked_content)
    transformed_content = fn(masked_content)

    for index, segment in enumerate(protected_segments):
        transformed_content = transformed_content.replace(
            f"\x00AUT_SEARCH_CODE_{index}\x00",
            segment,
        )
    return transformed_content


def scrub_invalid_inline_citations(content: str, valid_ids: Iterable[int]) -> str:
    """Remove inline citation markers whose ids are not valid for the section."""
    valid_id_set = set(valid_ids)

    def scrub_plain_text(text: str) -> str:
        scrubbed_text = _INLINE_CITATION_RE.sub(
            lambda match: match.group(0) if int(match.group(1)) in valid_id_set else "",
            text,
        )
        scrubbed_text = re.sub(r"[ \t]{2,}", " ", scrubbed_text)
        scrubbed_text = re.sub(r"[ \t]+([,.])", r"\1", scrubbed_text)
        scrubbed_text = re.sub(r"[ \t]+(?=\n)", "", scrubbed_text)
        scrubbed_text = re.sub(r"[ \t]+$", "", scrubbed_text)
        return scrubbed_text

    scrubbed = apply_to_prose(content, scrub_plain_text)
    return scrubbed


def renumber_by_first_appearance(
    content: str,
    ref_table: dict[int, Any],
) -> tuple[str, dict[int, Any]]:
    """Rewrite citations by first use order and drop uncited references."""
    if not content:
        return content, {}

    old_to_new: dict[int, int] = {}
    reordered_ref_table: dict[int, Any] = {}

    def replacer(match: re.Match[str]) -> str:
        old_ref_id = int(match.group(1))
        reference = ref_table.get(old_ref_id)
        if reference is None:
            return match.group(0)

        new_ref_id = old_to_new.get(old_ref_id)
        if new_ref_id is None:
            new_ref_id = len(old_to_new) + 1
            old_to_new[old_ref_id] = new_ref_id
            reordered_ref_table[new_ref_id] = reference
        return f"[{new_ref_id}]"

    renumbered_content = apply_to_prose(
        content,
        lambda text: _INLINE_CITATION_RE.sub(replacer, text),
    )
    return renumbered_content, reordered_ref_table


def _ordered_ref_ids(section: Section) -> list[int]:
    content_ref_ids = _prose_ref_ids(section.content)
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

    return apply_to_prose(content, lambda text: _INLINE_CITATION_RE.sub(replacer, text))


def _remap_ref_ids(section: Section, old_to_new: dict[int, int]) -> list[int]:
    updated_content = _replace_citations(section.content, old_to_new)
    content_ref_ids = _prose_ref_ids(updated_content)
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


def _prose_ref_ids(content: str) -> list[int]:
    ref_ids: list[int] = []

    def collect_ref_ids(text: str) -> str:
        ref_ids.extend(int(match.group(1)) for match in _INLINE_CITATION_RE.finditer(text))
        return text

    apply_to_prose(content, collect_ref_ids)
    return ref_ids
