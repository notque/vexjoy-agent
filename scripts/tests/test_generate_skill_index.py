"""Tests for scripts/generate-skill-index.py.

Covers:
- Private-path symlink exclusion (default public-only mode)
- Private-path symlink inclusion with --include-private
- Non-symlink public skills are always included
- Output JSON structure matches the expected format
"""

from __future__ import annotations

import importlib
import importlib.util
import json
import subprocess
import sys
from pathlib import Path

import pytest

# ---------------------------------------------------------------------------
# Module import helpers
# ---------------------------------------------------------------------------

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
SCRIPT = REPO_ROOT / "scripts" / "generate-skill-index.py"


def _load_module():
    """Load generate-skill-index.py as a module despite the hyphenated filename."""
    spec = importlib.util.spec_from_file_location("generate_skill_index", SCRIPT)
    assert spec is not None and spec.loader is not None, f"Cannot load {SCRIPT}"
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)  # type: ignore[union-attr]
    return module


_mod = _load_module()
generate_index = _mod.generate_index
is_private_path = _mod.is_private_path


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_MINIMAL_SKILL_MD = """\
---
name: {name}
description: "A test skill: {name}."
version: 1.0.0
user-invocable: false
routing:
  category: testing
  triggers:
    - {name}
---

# {name}

Test skill body.
"""


def _write_skill(skill_dir: Path, name: str) -> Path:
    """Create a minimal SKILL.md inside *skill_dir/<name>/* and return its path."""
    entry = skill_dir / name
    entry.mkdir(parents=True, exist_ok=True)
    skill_file = entry / "SKILL.md"
    skill_file.write_text(_MINIMAL_SKILL_MD.format(name=name), encoding="utf-8")
    return skill_file


# ---------------------------------------------------------------------------
# is_private_path unit tests
# ---------------------------------------------------------------------------


class TestIsPrivatePath:
    """Unit tests for the is_private_path() guard function."""

    def test_regular_path_is_not_private(self, tmp_path: Path) -> None:
        """A file inside a normal directory is not private."""
        regular_file = tmp_path / "skills" / "my-skill" / "SKILL.md"
        regular_file.parent.mkdir(parents=True)
        regular_file.touch()
        assert is_private_path(regular_file) is False

    def test_path_inside_private_skills_is_private(self, tmp_path: Path) -> None:
        """A file directly inside private-skills/ is private."""
        private_file = tmp_path / "private-skills" / "secret-skill" / "SKILL.md"
        private_file.parent.mkdir(parents=True)
        private_file.touch()
        assert is_private_path(private_file) is True

    def test_path_inside_private_voices_is_private(self, tmp_path: Path) -> None:
        """A file resolved into private-voices/ is private."""
        private_file = tmp_path / "private-voices" / "voice-x" / "SKILL.md"
        private_file.parent.mkdir(parents=True)
        private_file.touch()
        assert is_private_path(private_file) is True

    def test_symlink_into_private_voices_is_private(self, tmp_path: Path) -> None:
        """A symlink whose resolved target lives in private-voices/ is private."""
        private_target = tmp_path / "private-voices" / "voice-secret" / "SKILL.md"
        private_target.parent.mkdir(parents=True)
        private_target.write_text("---\nname: voice-secret\n---\n", encoding="utf-8")

        skills_dir = tmp_path / "skills"
        skills_dir.mkdir()
        link_dir = skills_dir / "voice-secret"
        link_dir.symlink_to(private_target.parent)

        symlinked_skill = link_dir / "SKILL.md"
        assert is_private_path(symlinked_skill) is True

    def test_broken_symlink_pointing_into_private_dir_is_private(self, tmp_path: Path) -> None:
        """A broken symlink whose target path contains a private directory name is private.

        Even though the target does not exist, the path components are checked so that
        someone cannot work around the guard by pointing at a not-yet-created private path.
        """
        broken = tmp_path / "skills" / "broken-skill"
        broken.parent.mkdir(parents=True)
        broken.symlink_to(tmp_path / "private-skills" / "nonexistent" / "SKILL.md")
        # The unresolvable symlink still has "private-skills" in the target path,
        # so is_private_path returns True (conservative -- better safe than leaky).
        assert is_private_path(broken) is True


# ---------------------------------------------------------------------------
# generate_index integration tests
# ---------------------------------------------------------------------------


class TestGenerateIndexPrivateFilter:
    """Integration tests for the private-skill exclusion in generate_index()."""

    def _make_private_symlink_skill(
        self,
        tmp_path: Path,
        skills_dir: Path,
        skill_name: str,
        private_category: str = "private-voices",
    ) -> None:
        """Create a private skill directory and symlink it into skills_dir."""
        private_dir = tmp_path / private_category / skill_name
        private_dir.mkdir(parents=True)
        skill_content = _MINIMAL_SKILL_MD.format(name=skill_name)
        (private_dir / "SKILL.md").write_text(skill_content, encoding="utf-8")
        link = skills_dir / skill_name
        link.symlink_to(private_dir)

    def test_symlink_into_private_voices_excluded_by_default(self, tmp_path: Path) -> None:
        """A symlink into private-voices/ is excluded from the public index by default."""
        skills_dir = tmp_path / "skills"
        skills_dir.mkdir()

        _write_skill(skills_dir, "public-skill-a")
        self._make_private_symlink_skill(tmp_path, skills_dir, "voice-private", "private-voices")

        index, warnings = generate_index(
            source_dir=skills_dir,
            dir_prefix="skills",
            collection_key="skills",
            is_pipeline=False,
            include_private=False,
        )

        assert "public-skill-a" in index["skills"], "Public skill should be included"
        assert "voice-private" not in index["skills"], "Private voice skill should be excluded"

    def test_symlink_into_private_skills_excluded_by_default(self, tmp_path: Path) -> None:
        """A symlink into private-skills/ is excluded from the public index by default."""
        skills_dir = tmp_path / "skills"
        skills_dir.mkdir()

        _write_skill(skills_dir, "public-skill-b")
        self._make_private_symlink_skill(tmp_path, skills_dir, "private-secret", "private-skills")

        index, _ = generate_index(
            source_dir=skills_dir,
            dir_prefix="skills",
            collection_key="skills",
            is_pipeline=False,
            include_private=False,
        )

        assert "public-skill-b" in index["skills"]
        assert "private-secret" not in index["skills"]

    def test_symlink_into_private_voices_included_with_flag(self, tmp_path: Path) -> None:
        """With include_private=True, private symlinks are included in the index."""
        skills_dir = tmp_path / "skills"
        skills_dir.mkdir()

        _write_skill(skills_dir, "public-skill-c")
        self._make_private_symlink_skill(tmp_path, skills_dir, "voice-private", "private-voices")

        index, _ = generate_index(
            source_dir=skills_dir,
            dir_prefix="skills",
            collection_key="skills",
            is_pipeline=False,
            include_private=True,
        )

        assert "public-skill-c" in index["skills"]
        assert "voice-private" in index["skills"], "Private skill should be included with include_private=True"

    def test_non_symlink_skills_always_included(self, tmp_path: Path) -> None:
        """Regular (non-symlink) directories in skills/ are always included regardless of flag."""
        skills_dir = tmp_path / "skills"
        skills_dir.mkdir()

        _write_skill(skills_dir, "always-public-1")
        _write_skill(skills_dir, "always-public-2")

        for include_private in (False, True):
            index, _ = generate_index(
                source_dir=skills_dir,
                dir_prefix="skills",
                collection_key="skills",
                is_pipeline=False,
                include_private=include_private,
            )
            assert "always-public-1" in index["skills"]
            assert "always-public-2" in index["skills"]


class TestGenerateIndexOutputStructure:
    """Tests that the output JSON structure matches the required format."""

    def test_index_has_required_top_level_fields(self, tmp_path: Path) -> None:
        """Index output must include version, generated, generated_by, and skills keys."""
        skills_dir = tmp_path / "skills"
        skills_dir.mkdir()
        _write_skill(skills_dir, "struct-test-skill")

        index, _ = generate_index(
            source_dir=skills_dir,
            dir_prefix="skills",
            collection_key="skills",
            is_pipeline=False,
        )

        assert index["version"] == "2.0"
        assert "generated" in index
        assert index["generated_by"] == "scripts/generate-skill-index.py"
        assert "skills" in index
        assert isinstance(index["skills"], dict)

    def test_skill_entry_has_required_fields(self, tmp_path: Path) -> None:
        """Each skill entry must have file, description, triggers, user_invocable, and version."""
        skills_dir = tmp_path / "skills"
        skills_dir.mkdir()
        _write_skill(skills_dir, "entry-format-skill")

        index, _ = generate_index(
            source_dir=skills_dir,
            dir_prefix="skills",
            collection_key="skills",
            is_pipeline=False,
        )

        entry = index["skills"]["entry-format-skill"]
        assert "file" in entry
        assert "description" in entry
        assert "triggers" in entry
        assert isinstance(entry["triggers"], list)
        assert "user_invocable" in entry
        assert "version" in entry

    def test_output_is_valid_json(self, tmp_path: Path) -> None:
        """The index dict must round-trip through JSON without error."""
        skills_dir = tmp_path / "skills"
        skills_dir.mkdir()
        _write_skill(skills_dir, "json-round-trip-skill")

        index, _ = generate_index(
            source_dir=skills_dir,
            dir_prefix="skills",
            collection_key="skills",
            is_pipeline=False,
        )

        serialized = json.dumps(index, indent=2)
        parsed = json.loads(serialized)
        assert parsed["skills"]["json-round-trip-skill"]["version"] == "1.0.0"


# ---------------------------------------------------------------------------
# CLI integration tests (subprocess)
# ---------------------------------------------------------------------------


class TestCLIFlags:
    """Test the --include-private and --output CLI flags via subprocess."""

    def _make_private_symlink_skill(
        self,
        tmp_path: Path,
        skills_dir: Path,
        skill_name: str,
        private_category: str = "private-voices",
    ) -> None:
        private_dir = tmp_path / private_category / skill_name
        private_dir.mkdir(parents=True)
        (private_dir / "SKILL.md").write_text(_MINIMAL_SKILL_MD.format(name=skill_name), encoding="utf-8")
        (skills_dir / skill_name).symlink_to(private_dir)

    def test_default_excludes_private_symlink(self, tmp_path: Path) -> None:
        """Running the script with no flags excludes private symlink skills."""
        skills_dir = tmp_path / "skills"
        skills_dir.mkdir()
        _write_skill(skills_dir, "public-only")
        self._make_private_symlink_skill(tmp_path, skills_dir, "voice-secret")
        output_path = tmp_path / "INDEX.json"

        result = subprocess.run(
            [
                sys.executable,
                str(SCRIPT),
                "--skills-dir",
                str(skills_dir),
                "--output",
                str(output_path),
            ],
            capture_output=True,
            text=True,
        )
        assert result.returncode == 0, f"Script failed:\nstdout: {result.stdout}\nstderr: {result.stderr}"
        index = json.loads(output_path.read_text())
        assert "public-only" in index["skills"], "Public skill must be present"
        assert "voice-secret" not in index["skills"], "Private symlink must be excluded by default"

    def test_include_private_includes_symlink(self, tmp_path: Path) -> None:
        """Running the script with --include-private includes private symlink skills."""
        skills_dir = tmp_path / "skills"
        skills_dir.mkdir()
        _write_skill(skills_dir, "public-only")
        self._make_private_symlink_skill(tmp_path, skills_dir, "voice-secret")
        output_path = tmp_path / "INDEX.local.json"

        result = subprocess.run(
            [
                sys.executable,
                str(SCRIPT),
                "--include-private",
                "--skills-dir",
                str(skills_dir),
                "--output",
                str(output_path),
            ],
            capture_output=True,
            text=True,
        )
        assert result.returncode == 0, f"Script failed:\nstdout: {result.stdout}\nstderr: {result.stderr}"
        index = json.loads(output_path.read_text())
        assert "public-only" in index["skills"], "Public skill must be present"
        assert "voice-secret" in index["skills"], "Private skill must be included with --include-private"
