"""Tests for scripts/generate-skill-index.py symlink-aware behavior."""

from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
from pathlib import Path

import pytest

SCRIPT = Path(__file__).resolve().parent.parent / "generate-skill-index.py"
AGENT_SCRIPT = Path(__file__).resolve().parent.parent / "generate-agent-index.py"


def _load_gsi():
    """Load generate-skill-index.py as a module (hyphenated name requires importlib)."""
    spec = importlib.util.spec_from_file_location("generate_skill_index", SCRIPT)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _load_gai():
    """Load generate-agent-index.py as a module (hyphenated name requires importlib)."""
    spec = importlib.util.spec_from_file_location("generate_agent_index", AGENT_SCRIPT)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


gsi = _load_gsi()
gai = _load_gai()

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


class TestFlattenResolvesNestedThroughSymlink:
    """Regression: in the deployed/synced layout, a flattened entry whose dir is a
    symlink back into the repo must record the real repo-relative NESTED path, not a
    fabricated flat ``skills/<name>/SKILL.md`` that exists in no layout.
    """

    def test_repo_relative_path_recovers_nested(self, tmp_path: Path) -> None:
        repo = tmp_path
        nested = repo / "skills" / "business" / "csuite"
        nested.mkdir(parents=True)
        (nested / "SKILL.md").write_text(_SKILL_FRONTMATTER.format(name="csuite"))
        # Deployed flat symlink pointing back into the nested repo location.
        deployed = repo / "deployed" / "csuite"
        deployed.parent.mkdir(parents=True)
        deployed.symlink_to(nested)

        got = gsi._repo_relative_path(deployed, "skills", repo)
        assert got == "skills/business/csuite/SKILL.md"

    def test_build_entry_flatten_prefers_nested_repo_path(self, tmp_path: Path) -> None:
        repo = tmp_path
        nested = repo / "skills" / "meta" / "do"
        nested.mkdir(parents=True)
        (nested / "SKILL.md").write_text(_SKILL_FRONTMATTER.format(name="do"))
        deployed = repo / "deployed" / "do"
        deployed.parent.mkdir(parents=True)
        deployed.symlink_to(nested)

        entry = gsi.build_entry(
            frontmatter={"name": "do", "description": "Router."},
            skill_dir=deployed,
            dir_prefix="skills",
            flatten=True,
            repo_root=repo,
        )
        # The bug wrote a fabricated flat path (which exists in no layout); the
        # fix records the real nested path under skills/meta/.
        assert entry["file"] == "skills/meta/do/SKILL.md"
        assert (repo / entry["file"]).is_file()

    def test_flatten_keeps_flat_for_external_skill(self, tmp_path: Path) -> None:
        """A genuinely external (outside-repo) skill keeps the flat deployed name."""
        repo = tmp_path / "repo"
        (repo / "skills").mkdir(parents=True)
        external = tmp_path / "private" / "secret-skill"
        external.mkdir(parents=True)
        (external / "SKILL.md").write_text(_SKILL_FRONTMATTER.format(name="secret-skill"))

        entry = gsi.build_entry(
            frontmatter={"name": "secret-skill", "description": "x"},
            skill_dir=external,
            dir_prefix="skills",
            flatten=True,
            repo_root=repo,
        )
        assert entry["file"] == "skills/secret-skill/SKILL.md"

    def test_canonical_entry_not_clobbered_by_symlink_shadow(self, tmp_path: Path) -> None:
        """A skill reached at its canonical nested path AND via a symlinked category
        keeps the on-disk nested path (the shadow must not overwrite it)."""
        repo = tmp_path
        skills = repo / "skills"
        # Canonical copy under a normal category.
        canon = skills / "content" / "voice-writer"
        canon.mkdir(parents=True)
        (canon / "SKILL.md").write_text(_SKILL_FRONTMATTER.format(name="voice-writer"))
        # Shadow copy reached through a symlinked category skills/voice -> external.
        external_voice = repo / "private" / "voice"
        shadow = external_voice / "voice-writer"
        shadow.mkdir(parents=True)
        (shadow / "SKILL.md").write_text(_SKILL_FRONTMATTER.format(name="voice-writer"))
        (skills / "voice").symlink_to(external_voice)

        index, _ = gsi.generate_index(
            source_dir=skills,
            dir_prefix="skills",
            collection_key="skills",
            include_private=True,
            flatten=True,
            repo_root=repo,
        )
        assert index["skills"]["voice-writer"]["file"] == "skills/content/voice-writer/SKILL.md"
        assert (repo / index["skills"]["voice-writer"]["file"]).is_file()


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


class TestPrivateIndexOutput:
    """Private-inclusive generation must never overwrite the public index name."""

    def test_skill_default_output_is_local_when_private_is_included(self, tmp_path: Path) -> None:
        skills_dir = tmp_path / "skills"
        assert gsi.default_output_path(skills_dir, include_private=False) == skills_dir / "INDEX.json"
        assert gsi.default_output_path(skills_dir, include_private=True) == skills_dir / "INDEX.local.json"

    def test_agent_default_output_is_local_when_private_is_included(self, tmp_path: Path) -> None:
        agents_dir = tmp_path / "agents"
        assert gai.default_output_path(agents_dir, include_private=False) == agents_dir / "INDEX.json"
        assert gai.default_output_path(agents_dir, include_private=True) == agents_dir / "INDEX.local.json"


class TestPrunePhantomEntries:
    """Entries advertising files that exist in no layout are pruned (audit defect D1)."""

    def _index(self, file_path: str) -> dict:
        return {
            "skills": {
                "sample-skill": {
                    "file": file_path,
                    "description": "A sample skill.",
                    "triggers": ["sample"],
                }
            }
        }

    def test_existing_file_survives(self, tmp_path: Path) -> None:
        """An entry whose advertised file resolves under a root is kept."""
        skill_md = tmp_path / "skills" / "sample-skill" / "SKILL.md"
        skill_md.parent.mkdir(parents=True)
        skill_md.write_text("---\nname: sample-skill\n---\n")
        index = self._index("skills/sample-skill/SKILL.md")

        pruned = gsi.prune_phantom_entries(index, [tmp_path])

        assert pruned == []
        assert "sample-skill" in index["skills"]

    def test_missing_file_is_pruned(self, tmp_path: Path) -> None:
        """An entry whose advertised file exists under no root is removed."""
        index = self._index("skills/sample-skill/SKILL.md")

        pruned = gsi.prune_phantom_entries(index, [tmp_path, tmp_path / "deployed"])

        assert pruned == ["sample-skill"]
        assert index["skills"] == {}

    def test_nested_layout_flat_path_is_pruned(self, tmp_path: Path) -> None:
        """Reproduces D1: a package with only nested skill/SKILL.md gets a flat
        advertised path that resolves nowhere — it must be pruned."""
        nested = tmp_path / "skills" / "voice-sample" / "skill" / "SKILL.md"
        nested.parent.mkdir(parents=True)
        nested.write_text("---\nname: voice-sample\n---\n")
        index = {
            "skills": {
                "voice-sample": {
                    "file": "skills/voice-sample/SKILL.md",  # flat path; only skill/SKILL.md exists
                    "description": "Nested-layout package.",
                    "triggers": ["voice sample"],
                }
            }
        }

        pruned = gsi.prune_phantom_entries(index, [tmp_path])

        assert pruned == ["voice-sample"]
        assert index["skills"] == {}
