"""Tests for scripts/validate-skill-frontmatter.py."""

from __future__ import annotations

import importlib.util
import subprocess
import sys
from pathlib import Path

import pytest

SCRIPT = Path(__file__).resolve().parent.parent / "validate-skill-frontmatter.py"


def _load_module():
    """Load validate-skill-frontmatter.py as a module."""
    spec = importlib.util.spec_from_file_location("validate_skill_frontmatter", SCRIPT)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


vsf = _load_module()


# --- Helpers ---


def _make_skill(tmp_path: Path, name: str, frontmatter: str) -> Path:
    """Create a skill directory with SKILL.md containing the given frontmatter."""
    skill_dir = tmp_path / name
    skill_dir.mkdir(parents=True, exist_ok=True)
    skill_file = skill_dir / "SKILL.md"
    skill_file.write_text(frontmatter)
    return skill_file


_VALID_FM = """\
---
name: test-skill
description: "A test skill for validation."
routing:
  triggers:
    - test
    - validate
  category: testing
---

# Test Skill
"""


# --- Valid frontmatter ---


class TestValidFrontmatter:
    """Tests that valid frontmatter passes validation."""

    def test_minimal_valid(self, tmp_path: Path) -> None:
        skill_file = _make_skill(tmp_path, "test-skill", _VALID_FM)
        errors = vsf.validate_skill(skill_file)
        assert errors == []

    def test_valid_with_optional_fields(self, tmp_path: Path) -> None:
        fm = """\
---
name: my-skill
description: "Full featured skill."
version: "1.0.0"
user-invocable: true
allowed-tools:
  - Read
  - Write
routing:
  triggers:
    - my skill
  pairs_with:
    - other-skill
  complexity: Medium
  category: engineering
  force_route: true
---
"""
        skill_file = _make_skill(tmp_path, "my-skill", fm)
        errors = vsf.validate_skill(skill_file)
        assert errors == []

    def test_valid_with_multiline_description(self, tmp_path: Path) -> None:
        fm = """\
---
name: desc-skill
description: |
  A multiline description that spans
  multiple lines for clarity.
routing:
  triggers:
    - desc test
  category: testing
---
"""
        skill_file = _make_skill(tmp_path, "desc-skill", fm)
        errors = vsf.validate_skill(skill_file)
        assert errors == []


# --- YAML parse errors ---


class TestYAMLParseErrors:
    """Tests that broken YAML is caught."""

    def test_broken_yaml(self, tmp_path: Path) -> None:
        fm = """\
---
name: broken
description: [unclosed bracket
routing:
  triggers:
    - test
---
"""
        skill_file = _make_skill(tmp_path, "broken", fm)
        errors = vsf.validate_skill(skill_file)
        assert len(errors) == 1
        assert "YAML parse error" in errors[0]

    def test_no_frontmatter_delimiters(self, tmp_path: Path) -> None:
        skill_file = _make_skill(tmp_path, "no-fm", "# Just a heading\n\nNo frontmatter here.\n")
        errors = vsf.validate_skill(skill_file)
        assert len(errors) == 1
        assert "No YAML frontmatter" in errors[0]

    def test_frontmatter_not_a_mapping(self, tmp_path: Path) -> None:
        fm = """\
---
- item1
- item2
---
"""
        skill_file = _make_skill(tmp_path, "list-fm", fm)
        errors = vsf.validate_skill(skill_file)
        assert len(errors) == 1
        assert "not a mapping" in errors[0]


# --- Name checks ---


class TestNameValidation:
    """Tests for name field and name-directory matching."""

    def test_missing_name(self, tmp_path: Path) -> None:
        fm = """\
---
description: "No name field."
routing:
  triggers:
    - test
  category: testing
---
"""
        skill_file = _make_skill(tmp_path, "unnamed", fm)
        errors = vsf.validate_skill(skill_file)
        assert any("Missing 'name'" in e for e in errors)

    def test_name_directory_mismatch(self, tmp_path: Path) -> None:
        fm = """\
---
name: wrong-name
description: "Name does not match directory."
routing:
  triggers:
    - test
  category: testing
---
"""
        skill_file = _make_skill(tmp_path, "actual-dir-name", fm)
        errors = vsf.validate_skill(skill_file)
        assert any("Name mismatch" in e for e in errors)
        assert any("wrong-name" in e for e in errors)
        assert any("actual-dir-name" in e for e in errors)


# --- Description checks ---


class TestDescriptionValidation:
    """Tests for description field."""

    def test_missing_description(self, tmp_path: Path) -> None:
        fm = """\
---
name: no-desc
routing:
  triggers:
    - test
  category: testing
---
"""
        skill_file = _make_skill(tmp_path, "no-desc", fm)
        errors = vsf.validate_skill(skill_file)
        assert any("Missing or empty description" in e for e in errors)

    def test_empty_description(self, tmp_path: Path) -> None:
        fm = """\
---
name: empty-desc
description: ""
routing:
  triggers:
    - test
  category: testing
---
"""
        skill_file = _make_skill(tmp_path, "empty-desc", fm)
        errors = vsf.validate_skill(skill_file)
        assert any("Missing or empty description" in e for e in errors)


# --- Routing section checks ---


class TestRoutingValidation:
    """Tests for routing section structure."""

    def test_missing_routing(self, tmp_path: Path) -> None:
        fm = """\
---
name: no-routing
description: "Has no routing section."
---
"""
        skill_file = _make_skill(tmp_path, "no-routing", fm)
        errors = vsf.validate_skill(skill_file)
        assert any("Missing routing section" in e for e in errors)

    def test_routing_not_a_dict(self, tmp_path: Path) -> None:
        fm = """\
---
name: bad-routing
description: "Routing is a string."
routing: "not a dict"
---
"""
        skill_file = _make_skill(tmp_path, "bad-routing", fm)
        errors = vsf.validate_skill(skill_file)
        assert any("routing must be a mapping" in e for e in errors)

    def test_missing_triggers(self, tmp_path: Path) -> None:
        fm = """\
---
name: no-triggers
description: "No triggers."
routing:
  category: testing
---
"""
        skill_file = _make_skill(tmp_path, "no-triggers", fm)
        errors = vsf.validate_skill(skill_file)
        assert any("Missing routing.triggers" in e for e in errors)

    def test_empty_triggers(self, tmp_path: Path) -> None:
        fm = """\
---
name: empty-triggers
description: "Empty triggers list."
routing:
  triggers: []
  category: testing
---
"""
        skill_file = _make_skill(tmp_path, "empty-triggers", fm)
        errors = vsf.validate_skill(skill_file)
        assert any("routing.triggers is empty" in e for e in errors)

    def test_triggers_not_a_list(self, tmp_path: Path) -> None:
        fm = """\
---
name: str-triggers
description: "Triggers is a string."
routing:
  triggers: "just a string"
  category: testing
---
"""
        skill_file = _make_skill(tmp_path, "str-triggers", fm)
        errors = vsf.validate_skill(skill_file)
        assert any("routing.triggers must be a list" in e for e in errors)

    def test_missing_category(self, tmp_path: Path) -> None:
        fm = """\
---
name: no-category
description: "No category."
routing:
  triggers:
    - test
---
"""
        skill_file = _make_skill(tmp_path, "no-category", fm)
        errors = vsf.validate_skill(skill_file)
        assert any("Missing routing.category" in e for e in errors)


# --- Top-level pairs_with ---


class TestTopLevelPairsWith:
    """Tests that pairs_with at top level is caught."""

    def test_top_level_pairs_with(self, tmp_path: Path) -> None:
        fm = """\
---
name: top-pairs
description: "pairs_with wrongly at top level."
pairs_with:
  - other-skill
routing:
  triggers:
    - test
  category: testing
---
"""
        skill_file = _make_skill(tmp_path, "top-pairs", fm)
        errors = vsf.validate_skill(skill_file)
        assert any("pairs_with at top level" in e for e in errors)

    def test_pairs_with_under_routing_is_ok(self, tmp_path: Path) -> None:
        fm = """\
---
name: ok-pairs
description: "pairs_with correctly under routing."
routing:
  triggers:
    - test
  pairs_with:
    - other-skill
  category: testing
---
"""
        skill_file = _make_skill(tmp_path, "ok-pairs", fm)
        errors = vsf.validate_skill(skill_file)
        assert errors == []


# --- force_routing typo ---


class TestForceRoutingTypo:
    """Tests that force_routing (wrong) vs force_route (correct) is caught."""

    def test_force_routing_at_top_level(self, tmp_path: Path) -> None:
        fm = """\
---
name: typo-force
description: "Has force_routing typo."
force_routing: true
routing:
  triggers:
    - test
  category: testing
---
"""
        skill_file = _make_skill(tmp_path, "typo-force", fm)
        errors = vsf.validate_skill(skill_file)
        assert any("force_routing" in e and "force_route" in e for e in errors)

    def test_force_routing_under_routing(self, tmp_path: Path) -> None:
        fm = """\
---
name: typo-nested
description: "Has force_routing typo under routing."
routing:
  triggers:
    - test
  category: testing
  force_routing: true
---
"""
        skill_file = _make_skill(tmp_path, "typo-nested", fm)
        errors = vsf.validate_skill(skill_file)
        assert any("force_routing" in e and "force_route" in e for e in errors)

    def test_force_route_is_ok(self, tmp_path: Path) -> None:
        fm = """\
---
name: correct-force
description: "Uses correct force_route."
routing:
  triggers:
    - test
  category: testing
  force_route: true
---
"""
        skill_file = _make_skill(tmp_path, "correct-force", fm)
        errors = vsf.validate_skill(skill_file)
        assert errors == []


# --- Strict mode ---


class TestStrictMode:
    """Tests for --strict flag checking optional fields."""

    def test_strict_missing_version(self, tmp_path: Path) -> None:
        skill_file = _make_skill(tmp_path, "test-skill", _VALID_FM)
        errors = vsf.validate_skill(skill_file, strict=True)
        assert any("[strict] Missing 'version'" in e for e in errors)

    def test_strict_missing_allowed_tools(self, tmp_path: Path) -> None:
        skill_file = _make_skill(tmp_path, "test-skill", _VALID_FM)
        errors = vsf.validate_skill(skill_file, strict=True)
        assert any("[strict] Missing 'allowed-tools'" in e for e in errors)

    def test_strict_passes_with_all_fields(self, tmp_path: Path) -> None:
        fm = """\
---
name: full-skill
description: "All fields present."
version: "1.0.0"
allowed-tools:
  - Read
routing:
  triggers:
    - test
  category: testing
---
"""
        skill_file = _make_skill(tmp_path, "full-skill", fm)
        errors = vsf.validate_skill(skill_file, strict=True)
        assert errors == []


# --- CLI integration ---


class TestCLI:
    """Tests for command-line interface."""

    def test_cli_all_skills_exit_0(self) -> None:
        """The script exits 0 when run against all real skills."""
        result = subprocess.run(
            [sys.executable, str(SCRIPT)],
            capture_output=True,
            text=True,
        )
        assert result.returncode == 0, f"stdout: {result.stdout}\nstderr: {result.stderr}"

    def test_cli_single_file(self, tmp_path: Path) -> None:
        # Use "test-skill" as dir name to match _VALID_FM's name field
        skill_file = _make_skill(tmp_path, "test-skill", _VALID_FM)
        result = subprocess.run(
            [sys.executable, str(SCRIPT), str(skill_file)],
            capture_output=True,
            text=True,
        )
        assert result.returncode == 0

    def test_cli_bad_file_exit_1(self, tmp_path: Path) -> None:
        fm = """\
---
name: bad
description: "Missing routing."
---
"""
        skill_file = _make_skill(tmp_path, "bad", fm)
        result = subprocess.run(
            [sys.executable, str(SCRIPT), str(skill_file)],
            capture_output=True,
            text=True,
        )
        assert result.returncode == 1

    def test_cli_missing_file_exit_2(self) -> None:
        result = subprocess.run(
            [sys.executable, str(SCRIPT), "/nonexistent/SKILL.md"],
            capture_output=True,
            text=True,
        )
        assert result.returncode == 2

    def test_cli_strict_flag(self, tmp_path: Path) -> None:
        skill_file = _make_skill(tmp_path, "test-skill", _VALID_FM)
        result = subprocess.run(
            [sys.executable, str(SCRIPT), "--strict", str(skill_file)],
            capture_output=True,
            text=True,
        )
        # _VALID_FM lacks version and allowed-tools, so strict should fail
        assert result.returncode == 1


# --- Multiple errors ---


class TestMultipleErrors:
    """Tests that multiple errors are reported for a single file."""

    def test_multiple_errors_reported(self, tmp_path: Path) -> None:
        fm = """\
---
description: ""
pairs_with:
  - some-skill
force_routing: true
---
"""
        skill_file = _make_skill(tmp_path, "multi-bad", fm)
        errors = vsf.validate_skill(skill_file)
        # Should catch: missing name, empty description, missing routing,
        # top-level pairs_with, force_routing typo
        assert len(errors) >= 4
