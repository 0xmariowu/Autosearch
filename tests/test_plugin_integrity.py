"""Plugin integrity tests.

Validates that AutoSearch is correctly structured for distribution:
- Command file has valid orchestrated blocks
- Agent definitions have valid frontmatter
- All referenced paths exist
- Inter-block data contract is consistent
- No hardcoded absolute paths in source files
- .gitignore covers all runtime files
- Install script is valid
- Directory structure is complete
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]


# ---------------------------------------------------------------------------
# Directory structure
# ---------------------------------------------------------------------------

REQUIRED_DIRS = [
    "agents",
    "channels",
    "commands",
    "delivery",
    "evidence",
    "lib",
    "scripts",
    "skills",
    "state",
    "tests",
]


@pytest.mark.parametrize("dirname", REQUIRED_DIRS)
def test_required_directory_exists(dirname: str) -> None:
    assert (ROOT / dirname).is_dir(), f"Missing required directory: {dirname}/"


REQUIRED_FILES = [
    "commands/autosearch.md",
    "agents/researcher.md",
    "PROTOCOL.md",
    "CLAUDE.md",
    "lib/judge.py",
    "lib/search_runner.py",
    "scripts/install.sh",
    ".gitignore",
    "state/config.json",
    "state/channels.json",
    "evidence/.gitkeep",
    "delivery/.gitkeep",
]


@pytest.mark.parametrize("filepath", REQUIRED_FILES)
def test_required_file_exists(filepath: str) -> None:
    assert (ROOT / filepath).exists(), f"Missing required file: {filepath}"


# ---------------------------------------------------------------------------
# Command file structure (orchestrated blocks)
# ---------------------------------------------------------------------------


class TestCommandFile:
    """Validate commands/autosearch.md has correct orchestrated structure."""

    @pytest.fixture(autouse=True)
    def _load(self) -> None:
        self.text = (ROOT / "commands/autosearch.md").read_text(encoding="utf-8")

    def test_has_frontmatter(self) -> None:
        assert self.text.startswith("---")
        assert "user-invocable: true" in self.text

    def test_has_phase_a(self) -> None:
        assert "Phase A:" in self.text or "### Phase A" in self.text

    def test_has_orchestrated_phase_b(self) -> None:
        assert "Orchestrated Research" in self.text, (
            "Phase B should use orchestrated blocks, not single researcher agent"
        )

    def test_has_four_blocks(self) -> None:
        blocks = re.findall(r"#### Block \d", self.text)
        assert len(blocks) == 4, f"Expected 4 blocks, found {len(blocks)}"

    def test_all_blocks_specify_sonnet(self) -> None:
        # Each block section should mention model: "sonnet"
        block_sections = re.split(r"#### Block \d", self.text)[1:]
        for i, section in enumerate(block_sections, 1):
            assert "sonnet" in section.lower(), (
                f"Block {i} does not specify Sonnet model"
            )

    def test_has_all_six_phases_in_progress(self) -> None:
        for n in range(1, 7):
            assert f"Phase {n}/6" in self.text, f"Missing [Phase {n}/6] progress output"

    def test_has_error_handling(self) -> None:
        assert "Error Handling" in self.text

    def test_has_session_id_generation(self) -> None:
        assert "session_id" in self.text.lower() or "session ID" in self.text

    def test_has_zero_query_guard(self) -> None:
        assert "zero-query" in self.text.lower() or "queries == 0" in self.text

    def test_no_bypass_permissions(self) -> None:
        assert "bypassPermissions" not in self.text or "Do NOT" in self.text


# ---------------------------------------------------------------------------
# Inter-block data contract
# ---------------------------------------------------------------------------


class TestDataContract:
    """Verify file paths are consistent between blocks."""

    @pytest.fixture(autouse=True)
    def _load(self) -> None:
        self.text = (ROOT / "commands/autosearch.md").read_text(encoding="utf-8")

    def test_block1_writes_knowledge_file(self) -> None:
        assert "session-{id}-knowledge.md" in self.text

    def test_block1_writes_queries_file(self) -> None:
        assert "session-{id}-queries.json" in self.text

    def test_block2_reads_queries_file(self) -> None:
        # Block 2 should reference the same queries file Block 1 writes
        block2_start = self.text.index("Block 2")
        block2_text = self.text[block2_start:]
        assert "session-{id}-queries.json" in block2_text

    def test_block3_reads_knowledge_file(self) -> None:
        block3_start = self.text.index("Block 3")
        block3_text = self.text[block3_start:]
        assert "session-{id}-knowledge.md" in block3_text

    def test_block3_reads_results_file(self) -> None:
        block3_start = self.text.index("Block 3")
        block3_text = self.text[block3_start:]
        assert "results.jsonl" in block3_text

    def test_delivery_path_is_delivery_not_state(self) -> None:
        # Delivery should go to delivery/, not state/delivery/
        block3_start = self.text.index("Block 3")
        block3_end = self.text.index("Block 4")
        block3_text = self.text[block3_start:block3_end]
        assert "state/delivery/" not in block3_text, (
            "Delivery should write to delivery/, not state/delivery/"
        )

    def test_block4_reads_delivery_from_correct_path(self) -> None:
        block4_start = self.text.index("Block 4")
        block4_text = self.text[block4_start:]
        assert "delivery/{session_id}" in block4_text or "delivery/" in block4_text

    def test_patterns_file_is_v2(self) -> None:
        # Should reference patterns-v2.jsonl, not patterns.jsonl
        assert "patterns-v2.jsonl" in self.text
        # The only mention of patterns.jsonl should be patterns-v2.jsonl
        non_v2_pattern = re.findall(r"patterns\.jsonl", self.text)
        v2_pattern = re.findall(r"patterns-v2\.jsonl", self.text)
        assert len(non_v2_pattern) == 0, (
            f"Found {len(non_v2_pattern)} references to legacy patterns.jsonl "
            f"(should all be patterns-v2.jsonl)"
        )


# ---------------------------------------------------------------------------
# Agent definition
# ---------------------------------------------------------------------------


class TestAgentDefinition:
    """Validate agents/researcher.md."""

    @pytest.fixture(autouse=True)
    def _load(self) -> None:
        self.text = (ROOT / "agents/researcher.md").read_text(encoding="utf-8")

    def test_has_frontmatter(self) -> None:
        assert self.text.startswith("---")

    def test_model_is_sonnet(self) -> None:
        assert "model: sonnet" in self.text

    def test_has_required_tools(self) -> None:
        for tool in ("Bash", "Read", "Write"):
            assert tool in self.text, f"Agent missing tool: {tool}"

    def test_has_name(self) -> None:
        assert "name: researcher" in self.text


# ---------------------------------------------------------------------------
# Cross-platform safety
# ---------------------------------------------------------------------------


SCAN_GLOBS = [
    "commands/*.md",
    "agents/*.md",
    "skills/*/SKILL.md",
    "lib/*.py",
    "scripts/*.sh",
    "PROTOCOL.md",
]

# Patterns that indicate hardcoded absolute paths
HARDCODED_PATH_PATTERNS = [
    r"/Users/\w+",  # macOS home
    r"C:\\",  # Windows drive
    r"D:\\",  # Windows drive
    r"/home/\w+",  # Linux home
]


def _source_files() -> list[Path]:
    files = []
    for glob in SCAN_GLOBS:
        files.extend(ROOT.glob(glob))
    return sorted(files)


@pytest.mark.parametrize(
    "path", _source_files(), ids=lambda p: str(p.relative_to(ROOT))
)
def test_no_hardcoded_absolute_paths(path: Path) -> None:
    text = path.read_text(encoding="utf-8")
    for pattern in HARDCODED_PATH_PATTERNS:
        matches = re.findall(pattern, text)
        assert not matches, (
            f"{path.relative_to(ROOT)} contains hardcoded path: {matches[0]}"
        )


# ---------------------------------------------------------------------------
# .gitignore coverage
# ---------------------------------------------------------------------------


class TestGitignore:
    """Verify .gitignore covers runtime files."""

    @pytest.fixture(autouse=True)
    def _load(self) -> None:
        self.text = (ROOT / ".gitignore").read_text(encoding="utf-8")

    def test_evidence_ignored(self) -> None:
        assert "evidence/*.jsonl" in self.text

    def test_delivery_ignored(self) -> None:
        assert "delivery/*.md" in self.text or "delivery/" in self.text

    def test_state_jsonl_ignored(self) -> None:
        assert "state/*.jsonl" in self.text

    def test_exec_plans_ignored(self) -> None:
        assert "docs/exec-plans/" in self.text

    def test_handoff_ignored(self) -> None:
        assert "HANDOFF.md" in self.text

    def test_experience_ignored(self) -> None:
        assert "experience/" in self.text

    def test_config_not_ignored(self) -> None:
        assert "!state/config.json" in self.text

    def test_channels_not_ignored(self) -> None:
        assert "!state/channels.json" in self.text

    def test_env_ignored(self) -> None:
        assert ".env" in self.text

    def test_venv_ignored(self) -> None:
        assert ".venv" in self.text


# ---------------------------------------------------------------------------
# Install script
# ---------------------------------------------------------------------------


class TestInstallScript:
    """Validate scripts/install.sh."""

    @pytest.fixture(autouse=True)
    def _load(self) -> None:
        self.path = ROOT / "scripts/install.sh"
        self.text = self.path.read_text(encoding="utf-8")

    def test_is_executable(self) -> None:
        import os

        assert os.access(self.path, os.X_OK), "install.sh is not executable"

    def test_has_shebang(self) -> None:
        assert self.text.startswith("#!/bin/bash") or self.text.startswith(
            "#!/usr/bin/env bash"
        )

    def test_checks_claude_available(self) -> None:
        assert "claude" in self.text

    def test_copies_command_file(self) -> None:
        assert ".claude/commands" in self.text

    def test_no_hardcoded_paths(self) -> None:
        for pattern in HARDCODED_PATH_PATTERNS:
            assert not re.search(pattern, self.text), (
                f"install.sh contains hardcoded path matching {pattern}"
            )


# ---------------------------------------------------------------------------
# Skill files reference existing paths
# ---------------------------------------------------------------------------


class TestSkillReferences:
    """Verify that pipeline-flow references real skills and state files."""

    @pytest.fixture(autouse=True)
    def _load(self) -> None:
        self.text = (ROOT / "skills/pipeline-flow/SKILL.md").read_text(encoding="utf-8")

    def test_references_existing_skills(self) -> None:
        # Extract all skills/{name}/SKILL.md references
        refs = re.findall(r"(\w[\w-]+)\.md", self.text)
        skill_dirs = {d.name for d in (ROOT / "skills").iterdir() if d.is_dir()}
        # pipeline-flow references skills by short name (e.g., "systematic-recall.md")
        skill_refs = re.findall(r"([\w-]+)\.md`", self.text)
        for ref in skill_refs:
            # Skip non-skill references
            if ref in ("SKILL", "PROTOCOL", "CLAUDE", "CHANGELOG", "README"):
                continue
            if ref.startswith("state/") or ref.startswith("evidence/"):
                continue
            assert ref in skill_dirs, (
                f"pipeline-flow references skill '{ref}' but skills/{ref}/ does not exist"
            )


# ---------------------------------------------------------------------------
# Protocol immutability markers
# ---------------------------------------------------------------------------


class TestProtocol:
    """Verify PROTOCOL.md contract markers."""

    @pytest.fixture(autouse=True)
    def _load(self) -> None:
        self.text = (ROOT / "PROTOCOL.md").read_text(encoding="utf-8")

    def test_judge_is_fixed(self) -> None:
        assert "judge.py" in self.text
        assert "fixed" in self.text.lower()

    def test_has_constraints_section(self) -> None:
        assert "Constraints" in self.text

    def test_meta_skills_listed(self) -> None:
        for skill in ("create-skill", "observe-user", "interact-user"):
            assert skill in self.text


# ---------------------------------------------------------------------------
# State config files are valid JSON
# ---------------------------------------------------------------------------


class TestStateConfig:
    """Verify shipped state files are valid."""

    def test_config_json_valid(self) -> None:
        import json

        path = ROOT / "state/config.json"
        data = json.loads(path.read_text(encoding="utf-8"))
        assert isinstance(data, dict)

    def test_channels_json_valid(self) -> None:
        import json

        path = ROOT / "state/channels.json"
        data = json.loads(path.read_text(encoding="utf-8"))
        assert isinstance(data, (dict, list))


# ---------------------------------------------------------------------------
# Version consistency
# ---------------------------------------------------------------------------


class TestVersionConsistency:
    """Verify version is consistent across all manifest files."""

    @pytest.fixture(autouse=True)
    def _load(self) -> None:
        import json

        self.plugin = json.loads(
            (ROOT / ".claude-plugin/plugin.json").read_text(encoding="utf-8")
        )
        self.marketplace = json.loads(
            (ROOT / ".claude-plugin/marketplace.json").read_text(encoding="utf-8")
        )
        self.changelog = (ROOT / "CHANGELOG.md").read_text(encoding="utf-8")

    def test_plugin_json_has_version(self) -> None:
        assert "version" in self.plugin
        assert self.plugin["version"]

    def test_version_is_calver(self) -> None:
        version = self.plugin["version"]
        assert re.match(r"^\d{4}\.\d{1,2}\.\d{1,2}(-\d+)?$", version), (
            f"Version '{version}' is not CalVer YYYY.M.D format"
        )

    def test_marketplace_metadata_matches_plugin(self) -> None:
        assert self.marketplace["metadata"]["version"] == self.plugin["version"]

    def test_marketplace_plugin_entry_matches(self) -> None:
        for plugin in self.marketplace.get("plugins", []):
            assert plugin["version"] == self.plugin["version"], (
                f"marketplace plugins[].version ({plugin['version']}) "
                f"!= plugin.json ({self.plugin['version']})"
            )

    def test_changelog_has_version_section(self) -> None:
        version = self.plugin["version"]
        assert f"## {version}" in self.changelog, (
            f"CHANGELOG.md missing section for current version {version}"
        )

    def test_bump_script_exists_and_executable(self) -> None:
        import os

        path = ROOT / "scripts/bump-version.sh"
        assert path.exists(), "scripts/bump-version.sh missing"
        assert os.access(path, os.X_OK), "scripts/bump-version.sh not executable"
