"""Packaged prompt library shipped with autosearch."""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path

_PROMPTS_DIR = Path(__file__).resolve().parent


class PromptNotFoundError(FileNotFoundError):
    """Raised when a packaged prompt file cannot be found."""

    def __init__(self, name: str) -> None:
        super().__init__(f"Prompt '{name}' not found at {_PROMPTS_DIR / f'{name}.md'}")
        self.name = name


@lru_cache(maxsize=None)
def load_prompt(name: str) -> str:
    """Load prompt body from autosearch/skills/prompts/<name>.md, stripping frontmatter."""

    prompt_path = _PROMPTS_DIR / f"{name}.md"
    if not prompt_path.is_file():
        raise PromptNotFoundError(name)

    raw_text = prompt_path.read_text(encoding="utf-8")
    lines = raw_text.splitlines(keepends=True)
    delimiters = [index for index, line in enumerate(lines) if line.strip() == "---"]
    if len(delimiters) < 2:
        raise ValueError(f"{prompt_path} is missing frontmatter delimiters")

    body = "".join(lines[delimiters[1] + 1 :])
    if body.endswith("\n"):
        body = body[:-1]
    return body


__all__ = ["PromptNotFoundError", "load_prompt"]
