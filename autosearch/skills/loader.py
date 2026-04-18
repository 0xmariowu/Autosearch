# Self-written, plan autosearch-0418-channels-and-skills.md § F001
from __future__ import annotations

import re
from pathlib import Path
from typing import Literal

import structlog
import yaml
from pydantic import BaseModel, Field, ValidationError, field_validator, model_validator

SKILL_FILENAME = "SKILL.md"
REQUIRES_TOKEN_PATTERN = re.compile(r"^(cookie|mcp|env|binary):[a-zA-Z_][a-zA-Z0-9_-]*$")
LOGGER = structlog.get_logger(__name__).bind(component="skill_loader")


class SkillLoadError(ValueError):
    """Raised when a skill directory cannot be loaded into a validated spec."""


class MethodSpec(BaseModel):
    id: str
    impl: str
    requires: list[str] = Field(default_factory=list)
    rate_limit: dict[str, object] | None = None

    @field_validator("requires")
    @classmethod
    def validate_requires(cls, value: list[str]) -> list[str]:
        invalid = [token for token in value if not REQUIRES_TOKEN_PATTERN.fullmatch(token)]
        if invalid:
            invalid_tokens = ", ".join(invalid)
            raise ValueError(f"requires contains invalid token(s): {invalid_tokens}")
        return value


class WhenToUse(BaseModel):
    query_languages: list[Literal["zh", "en", "mixed"]] = Field(default_factory=list)
    query_types: list[str] = Field(default_factory=list)
    avoid_for: list[str] = Field(default_factory=list)


class QualityHint(BaseModel):
    typical_yield: Literal["low", "medium", "medium-high", "high", "unknown"] = "unknown"
    chinese_native: bool = False


class SkillSpec(BaseModel):
    name: str
    description: str
    version: int = 1
    languages: list[Literal["zh", "en", "mixed"]] = Field(default_factory=list)
    methods: list[MethodSpec] = Field(default_factory=list)
    fallback_chain: list[str] = Field(default_factory=list)
    when_to_use: WhenToUse | None = None
    quality_hint: QualityHint | None = None
    skill_dir: Path

    @model_validator(mode="after")
    def validate_relationships(self) -> SkillSpec:
        method_ids = {method.id for method in self.methods}
        missing_methods = [
            method_id for method_id in self.fallback_chain if method_id not in method_ids
        ]
        if missing_methods:
            joined = ", ".join(missing_methods)
            raise ValueError(f"fallback_chain references unknown method id(s): {joined}")

        if self.name != self.skill_dir.name:
            raise ValueError(
                f"name '{self.name}' must match directory name '{self.skill_dir.name}'"
            )

        return self


def _extract_frontmatter(raw_text: str, skill_path: Path) -> dict[str, object]:
    lines = raw_text.splitlines()
    start_index = next((index for index, line in enumerate(lines) if line.strip() == "---"), None)
    if start_index is None:
        raise SkillLoadError(f"{skill_path} is missing a YAML frontmatter start delimiter")

    end_index = next(
        (index for index in range(start_index + 1, len(lines)) if lines[index].strip() == "---"),
        None,
    )
    if end_index is None:
        raise SkillLoadError(f"{skill_path} is missing a YAML frontmatter end delimiter")

    frontmatter_text = "\n".join(lines[start_index + 1 : end_index]).strip()
    if not frontmatter_text:
        raise SkillLoadError(f"{skill_path} has empty YAML frontmatter")

    try:
        payload = yaml.safe_load(frontmatter_text)
    except yaml.YAMLError as exc:
        raise SkillLoadError(f"Invalid YAML frontmatter in {skill_path}: {exc}") from exc

    if not isinstance(payload, dict):
        raise SkillLoadError(f"YAML frontmatter in {skill_path} must be a mapping")

    return payload


def load_skill(skill_dir: Path) -> SkillSpec:
    skill_dir = Path(skill_dir)
    skill_path = skill_dir / SKILL_FILENAME
    if not skill_path.is_file():
        raise SkillLoadError(f"Expected {SKILL_FILENAME} in {skill_dir}")

    try:
        raw_text = skill_path.read_text(encoding="utf-8")
    except OSError as exc:
        raise SkillLoadError(f"Failed to read {skill_path}: {exc}") from exc

    payload = _extract_frontmatter(raw_text, skill_path)
    payload["skill_dir"] = skill_dir

    try:
        return SkillSpec.model_validate(payload)
    except ValidationError as exc:
        raise SkillLoadError(f"Invalid skill spec in {skill_path}: {exc}") from exc


def load_all(root: Path) -> list[SkillSpec]:
    root = Path(root)
    if not root.is_dir():
        raise SkillLoadError(f"Skill root does not exist or is not a directory: {root}")

    specs: list[SkillSpec] = []
    for skill_dir in sorted(
        (path for path in root.iterdir() if path.is_dir()), key=lambda path: path.name
    ):
        if not (skill_dir / SKILL_FILENAME).is_file():
            LOGGER.info(
                "skill_dir_skipped",
                skill_dir=str(skill_dir),
                reason="missing_skill_md",
            )
            continue
        specs.append(load_skill(skill_dir))

    return sorted(specs, key=lambda spec: spec.name)
