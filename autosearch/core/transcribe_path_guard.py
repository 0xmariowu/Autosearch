"""Default-deny local path guard for transcription inputs.

Local transcription can expose arbitrary files to downstream tooling. This guard
only permits resolved paths that live under an explicit
``AUTOSEARCH_TRANSCRIBE_ALLOWED_DIRS`` entry, and denies all local files by
default when no allowlist is configured.
"""

from __future__ import annotations

import fnmatch
import os
from pathlib import Path

_DENIED_GLOBS = (
    ".env",
    ".env.*",
    "*.env",
    "*.key",
    "*.pem",
    "*/.ssh/*",
    "*/.config/*",
    "/etc/*",
)

_AUDIO_VIDEO_EXTS = {
    ".mp3",
    ".m4a",
    ".wav",
    ".aac",
    ".ogg",
    ".opus",
    ".flac",
    ".wma",
    ".aif",
    ".aiff",
    ".mp4",
    ".mov",
    ".mkv",
    ".avi",
    ".webm",
    ".flv",
    ".m4v",
    ".mpg",
    ".mpeg",
    ".3gp",
    ".wmv",
}

_AUDIO_VIDEO_MAGIC_BYTES = (
    (b"ID3", "mp3-id3"),
    (b"\xff\xfb", "mp3"),
    (b"\xff\xf3", "mp3"),
    (b"\xff\xf2", "mp3"),
    (b"OggS", "ogg"),
    (b"fLaC", "flac"),
    (b"RIFF", "wav-or-avi"),
    (b"\x00\x00\x00\x18ftyp", "mp4-isobmff-18"),
    (b"\x00\x00\x00\x20ftyp", "mp4-isobmff-20"),
    (b"\x1a\x45\xdf\xa3", "matroska-webm"),
)


def _is_denied(resolved_path: Path) -> bool:
    path_text = str(resolved_path)
    path_name = resolved_path.name
    for pattern in _DENIED_GLOBS:
        if fnmatch.fnmatch(path_text, pattern):
            return True
        if "/" not in pattern and fnmatch.fnmatch(path_name, pattern):
            return True
    return False


def validate_local_path(path: str | Path) -> Path:
    """Return a resolved path only when it is inside the configured allowlist."""
    allowed_dirs = os.environ.get("AUTOSEARCH_TRANSCRIBE_ALLOWED_DIRS")
    if not allowed_dirs:
        raise PermissionError(
            "transcribe path guard: AUTOSEARCH_TRANSCRIBE_ALLOWED_DIRS not set; "
            "no local files allowed"
        )

    resolved_path = Path(path).expanduser().resolve()
    if _is_denied(resolved_path):
        raise PermissionError(f"transcribe path guard: {path} matches a hard-deny pattern")

    for allowed_dir in allowed_dirs.split(os.pathsep):
        if not allowed_dir:
            continue
        resolved_allowed_dir = Path(allowed_dir).expanduser().resolve()
        if resolved_path.is_relative_to(resolved_allowed_dir):
            suffix = resolved_path.suffix.lower()
            if suffix not in _AUDIO_VIDEO_EXTS:
                raise PermissionError(
                    f"transcribe path guard: extension {suffix} is not an allowed audio/video type"
                )
            with resolved_path.open("rb") as file:
                head_bytes = file.read(16)
            has_audio_video_magic = any(
                head_bytes.startswith(prefix) for prefix, _label in _AUDIO_VIDEO_MAGIC_BYTES
            )
            if not has_audio_video_magic and b"ftyp" not in head_bytes:
                raise PermissionError(
                    "transcribe path guard: file does not look like audio/video "
                    "(magic bytes mismatch)"
                )
            return resolved_path

    raise PermissionError(
        f"transcribe path guard: {path} is not inside any AUTOSEARCH_TRANSCRIBE_ALLOWED_DIRS entry"
    )
