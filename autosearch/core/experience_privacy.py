from __future__ import annotations

from typing import Any


def _is_cjk(char: str) -> bool:
    codepoint = ord(char)
    return (
        0x3400 <= codepoint <= 0x4DBF
        or 0x4E00 <= codepoint <= 0x9FFF
        or 0xF900 <= codepoint <= 0xFAFF
        or 0x3040 <= codepoint <= 0x30FF
        or 0xAC00 <= codepoint <= 0xD7AF
    )


def _is_latin(char: str) -> bool:
    return ("A" <= char <= "Z") or ("a" <= char <= "z") or (0x00C0 <= ord(char) <= 0x00FF)


def detect_query_language(query: str) -> str:
    """Return a coarse language class without storing query content."""

    has_latin = False
    has_other_alpha = False
    for char in query:
        if _is_cjk(char):
            return "cjk"
        if _is_latin(char):
            has_latin = True
        elif char.isalpha():
            has_other_alpha = True

    if has_latin and not has_other_alpha:
        return "latin"
    if has_latin and has_other_alpha:
        return "mixed"
    return "other"


def query_shape(query: str, *, channel: str, outcome: str) -> dict[str, str]:
    length = len(query)
    if length < 20:
        length_bucket = "short"
    elif length < 60:
        length_bucket = "medium"
    else:
        length_bucket = "long"

    return {
        "length_bucket": length_bucket,
        "language": detect_query_language(query),
        "channel": channel,
        "outcome": outcome,
    }


def shape_from_legacy_query(value: Any, *, channel: str, outcome: str) -> dict[str, str] | None:
    if not isinstance(value, str):
        return None
    return query_shape(value, channel=channel, outcome=outcome)


def query_shape_label(shape: Any) -> str | None:
    if not isinstance(shape, dict):
        return None
    length_bucket = shape.get("length_bucket")
    language = shape.get("language")
    channel = shape.get("channel")
    outcome = shape.get("outcome")
    if not all(isinstance(v, str) and v for v in (length_bucket, language, channel, outcome)):
        return None
    return f"{channel}:{outcome}:{length_bucket}:{language}"
