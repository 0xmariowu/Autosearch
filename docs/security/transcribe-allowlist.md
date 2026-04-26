# Transcribe Path Guard — `AUTOSEARCH_TRANSCRIBE_ALLOWED_DIRS`

> Status: enforced as of P0-1 fix (`fix/p0-1-transcribe-path-guard`). All
> three transcribe backends (`video-to-text-openai`,
> `video-to-text-groq`, `video-to-text-local`) route every local-path
> input through `autosearch.core.transcribe_path_guard.validate_local_path`.

## Threat model

The transcribe tools accept either a remote URL (downloaded with
`yt-dlp`) or a local path. The local-path branch is dangerous: an agent
runtime, MCP tool, or skill that takes a free-form `path` argument can
hand the tool any file the autosearch process can read — `.env`, SSH
keys, browser cookies, tokens — and that file becomes the audio payload
uploaded to OpenAI / Groq.

Without a path guard, this is a one-call data exfiltration primitive.

## Defense layers

`validate_local_path(path)` enforces four checks, in order:

1. **Default-deny allowlist.** If `AUTOSEARCH_TRANSCRIBE_ALLOWED_DIRS`
   is unset or empty, every local path is rejected with
   `PermissionError`. Remote URLs (yt-dlp branch) are unaffected — only
   local-disk inputs require the env var.
2. **Hard-deny patterns.** `_DENIED_GLOBS` rejects paths matching
   `.env`, `.env.*`, `*.env`, `*.key`, `*.pem`, `*/.ssh/*`,
   `*/.config/*`, `/etc/*` even if they sit inside an allowlisted
   directory. This catches the obvious shape of "allowlist is `~`,
   attacker requests `~/.ssh/id_rsa`".
3. **Extension whitelist.** Only common audio/video file extensions
   pass: `.mp3`, `.m4a`, `.wav`, `.aac`, `.ogg`, `.opus`, `.flac`,
   `.wma`, `.aif`, `.aiff`, `.mp4`, `.mov`, `.mkv`, `.avi`, `.webm`,
   `.flv`, `.m4v`, `.mpg`, `.mpeg`, `.3gp`, `.wmv`. A `.txt` or `.py`
   file with a hand-crafted name is refused before any I/O.
4. **Magic-bytes check.** The first 16 bytes of the file must match a
   known audio/video container signature (`ID3`, MP3 frame markers,
   `OggS`, `fLaC`, `RIFF`, MP4 `ftyp`, Matroska/WebM EBML). A
   `.mp3`-named text file is rejected. A best-effort check, not a full
   demuxer — a sufficiently crafted file could still bypass, but the
   layered defense (allowlist + denylist + extension) makes this
   strictly harder.

## Configuration

Allow a directory tree:

```bash
export AUTOSEARCH_TRANSCRIBE_ALLOWED_DIRS="$HOME/Recordings:$HOME/Downloads/Podcasts"
```

The value is colon-separated (PATH-style on macOS / Linux). Each entry
is `expanduser()` + `resolve()` before comparison, so symlinks and
relative paths are normalized.

Disallow all local paths (default — recommended for headless / agent
runtimes):

```bash
unset AUTOSEARCH_TRANSCRIBE_ALLOWED_DIRS
```

## Why default-deny

The alternative is default-allow with a denylist of known-sensitive
paths. That is unworkable: every new sensitive file pattern (a fresh
config tool, a new credential store, a service-specific cache) creates
a hole until the denylist catches up. Default-deny inverts the burden —
the operator who knows which directory is safe lists exactly that
directory. Anything outside is rejected by construction.

The `_DENIED_GLOBS` layer exists for the case where the operator chose
a too-broad allowlist (e.g. `~`); it is a safety net, not the primary
defense.

## Tests that lock this in

- `tests/unit/test_transcribe_path_guard.py` — all four layers
  individually (default-deny, extension whitelist, magic-bytes,
  blacklist).
- `tests/skills/tools/video_to_text_openai/test_path_guard.py` —
  end-to-end via the OpenAI transcribe entry.
- `tests/skills/tools/video_to_text_groq/` and
  `tests/skills/tools/video_to_text_local/` — backend-specific
  regression coverage.

Source: `docs/security/autosearch-0426-p0-deep-scan-report.md` § P0-1.
