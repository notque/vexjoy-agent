"""Tests for scripts/generate-skill-index.py symlink-aware behavior."""

from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
from pathlib import Path

import pytest

SCRIPT = Path(__file__).resolve().parent.parent / "generate-skill-index.py"


def _load_gsi():
    """Load generate-skill-index.py as a module (hyphenated name requires importlib)."""
    spec = importlib.util.spec_from_file_location("generate_skill_index", SCRIPT)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


gsi = _load_gsi()

# Minimal valid SKILL.md frontmatter for test fixtures
_SKILL_FRONTMATTER = """\
---
name: {name}
description: A test skill for {name}.
version: "1.0"
user-invocable: false
routing:
  triggers:
    - {name}
  category: testing
---

## Overview

Test skill content.
"""


def _make_skill_dir(base: Path, name: str) -> Path:
    """Create a real (non-symlink) skill directory with a SKILL.md."""
    skill_dir = base / name
    skill_dir.mkdir(parents=True, exist_ok=True)
    (skill_dir / "SKILL.md").write_text(_SKILL_FRONTMATTER.format(name=name))
    return skill_dir


class TestSymlinkExcludedByDefault:
    """Symlinked skill directories are excluded from the index in default mode."""

    def test_symlink_excluded_by_default(self, tmp_path: Path) -> None:
        """A symlinked skill directory should not appear in the index without include_private."""
        # Create the real target outside the skills/ tree
        real_skills = tmp_path / "real-skills"
        _make_skill_dir(real_skills, "real-target-skill")

        # Build a skills/ dir with one real skill and one symlink
        skills_dir = tmp_path / "skills"
        skills_dir.mkdir()
        _make_skill_dir(skills_dir, "public-skill")

        symlink_dir = skills_dir / "private-skill"
        symlink_dir.symlink_to(real_skills / "real-target-skill")

        index, _warnings = gsi.generate_index(
            source_dir=skills_dir,
            dir_prefix="skills",
            collection_key="skills",
            include_private=False,
        )

        assert "public-skill" in index["skills"], "Real skill should be included"
        # The symlinked dir appears as 'private-skill' in the tree
        assert "private-skill" not in index["skills"], "Symlinked directory entry should not appear by default"

    def test_existing_public_skills_preserved(self, tmp_path: Path) -> None:
        """Non-symlinked skills are always included regardless of flag state."""
        skills_dir = tmp_path / "skills"
        for name in ("alpha-skill", "beta-skill", "gamma-skill"):
            _make_skill_dir(skills_dir, name)

        index, _warnings = gsi.generate_index(
            source_dir=skills_dir,
            dir_prefix="skills",
            collection_key="skills",
            include_private=False,
        )

        for name in ("alpha-skill", "beta-skill", "gamma-skill"):
            assert name in index["skills"], f"Expected '{name}' in index"


class TestSymlinkIncludedWithFlag:
    """Symlinked skill directories are included when include_private=True."""

    def test_symlink_included_with_flag(self, tmp_path: Path) -> None:
        """include_private=True causes symlinked directories to appear in the index."""
        real_skills = tmp_path / "real-skills"
        _make_skill_dir(real_skills, "private-target-skill")

        skills_dir = tmp_path / "skills"
        skills_dir.mkdir()
        _make_skill_dir(skills_dir, "public-skill")

        symlink_dir = skills_dir / "private-target-skill"
        symlink_dir.symlink_to(real_skills / "private-target-skill")

        index, _warnings = gsi.generate_index(
            source_dir=skills_dir,
            dir_prefix="skills",
            collection_key="skills",
            include_private=True,
        )

        assert "public-skill" in index["skills"], "Real skill should still be included"
        assert "private-target-skill" in index["skills"], "Symlinked skill should be included when include_private=True"


class TestCustomOutputPath:
    """The --output flag controls where the index file is written."""

    def test_custom_output_path(self, tmp_path: Path) -> None:
        """Generator writes to the path specified by --output."""
        # Build a minimal skills dir next to the output target
        skills_dir = tmp_path / "skills"
        _make_skill_dir(skills_dir, "some-skill")

        custom_output = tmp_path / "custom" / "output.json"
        custom_output.parent.mkdir(parents=True, exist_ok=True)

        index, _warnings = gsi.generate_index(
            source_dir=skills_dir,
            dir_prefix="skills",
            collection_key="skills",
        )
        gsi.write_index(index, custom_output)

        assert custom_output.exists(), f"Expected output at {custom_output}"
        data = json.loads(custom_output.read_text())
        assert "some-skill" in data["skills"]

    def test_output_is_valid_json(self, tmp_path: Path) -> None:
        """The generated file is always valid JSON."""
        skills_dir = tmp_path / "skills"
        _make_skill_dir(skills_dir, "json-test-skill")

        output = tmp_path / "INDEX.json"
        index, _warnings = gsi.generate_index(
            source_dir=skills_dir,
            dir_prefix="skills",
            collection_key="skills",
        )
        gsi.write_index(index, output)

        # json.loads raises if invalid — that is the assertion
        data = json.loads(output.read_text())
        assert isinstance(data, dict)
        assert "version" in data
        assert "skills" in data


class TestCLIFlag:
    """End-to-end CLI tests for --include-private and --output flags."""

    def test_cli_output_flag_creates_file(self, tmp_path: Path) -> None:
        """--output writes to the specified path."""
        custom_output = tmp_path / "out.json"
        result = subprocess.run(
            [sys.executable, str(SCRIPT), "--output", str(custom_output)],
            capture_output=True,
            text=True,
        )
        assert result.returncode == 0, f"CLI failed:\n{result.stderr}"
        assert custom_output.exists(), "Output file not created"
        json.loads(custom_output.read_text())  # must be valid JSON
