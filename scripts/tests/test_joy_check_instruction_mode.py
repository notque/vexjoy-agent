"""Deterministic joy-check tests for instruction-mode patterns.

Two scopes:
1. Golden fixture tests -- small .md snippets that exercise each of the 7
   primary patterns from skills/code-quality/joy-check/references/
   instruction-rubric.md, plus contextual exceptions that must pass.
2. Fleet gate -- the fleet scan over agents/*.md and skills/**/SKILL.md
   lives in `validate_positive_instruction_docs.py --fleet` (a CI step);
   these tests prove that mode fails on a bad fixture.

Run with:
    python3 -m pytest scripts/tests/test_joy_check_instruction_mode.py -v
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest

# ---------------------------------------------------------------------------
# Module loading
# ---------------------------------------------------------------------------

_SCRIPTS_DIR = Path(__file__).resolve().parent.parent
_REPO_ROOT = _SCRIPTS_DIR.parent

_spec = importlib.util.spec_from_file_location(
    "validate_positive_instruction_docs",
    _SCRIPTS_DIR / "validate_positive_instruction_docs.py",
)
assert _spec is not None and _spec.loader is not None
_mod = importlib.util.module_from_spec(_spec)
sys.modules["validate_positive_instruction_docs"] = _mod
_spec.loader.exec_module(_mod)  # type: ignore[attr-defined]

scan_file = _mod.scan_file

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _write(tmp_path: Path, content: str, name: str = "sample.md") -> Path:
    """Write content to a temp file and return its path."""
    p = tmp_path / name
    p.write_text(content, encoding="utf-8")
    return p


# ---------------------------------------------------------------------------
# Golden fixture tests -- each primary pattern
# ---------------------------------------------------------------------------


class TestPrimaryPatterns:
    """Each of the 7 primary patterns from the instruction rubric must be flagged."""

    def test_anti_pattern_heading_fails(self, tmp_path: Path) -> None:
        """Heading containing 'Anti-Pattern' is flagged."""
        p = _write(tmp_path, "## Anti-Patterns\n\nSome description.\n")
        violations = scan_file(p)
        assert any(v.pattern == "Anti-Pattern" for v in violations), (
            f"Expected Anti-Pattern violation, got: {violations}"
        )

    def test_forbidden_caps_fails(self, tmp_path: Path) -> None:
        """FORBIDDEN in instruction context is flagged."""
        p = _write(tmp_path, "- FORBIDDEN: Do not commit credentials.\n")
        violations = scan_file(p)
        assert any(v.pattern == "FORBIDDEN" for v in violations), f"Expected FORBIDDEN violation, got: {violations}"

    def test_never_caps_fails(self, tmp_path: Path) -> None:
        """NEVER in instruction context is flagged."""
        p = _write(tmp_path, "NEVER edit code directly.\n")
        violations = scan_file(p)
        assert any(v.pattern == "NEVER" for v in violations), f"Expected NEVER violation, got: {violations}"

    def test_do_not_fails(self, tmp_path: Path) -> None:
        """'do NOT' (lowercase d) is flagged."""
        p = _write(tmp_path, "do NOT use git add -A.\n")
        violations = scan_file(p)
        assert any(v.pattern == "do NOT" for v in violations), f"Expected 'do NOT' violation, got: {violations}"

    def test_do_not_caps_fails(self, tmp_path: Path) -> None:
        """'Do NOT' (capital D) is flagged."""
        p = _write(tmp_path, "Do NOT skip tests.\n")
        violations = scan_file(p)
        assert any(v.pattern == "do NOT" for v in violations), (
            f"Expected 'do NOT' violation for 'Do NOT', got: {violations}"
        )

    def test_must_not_fails(self, tmp_path: Path) -> None:
        """'must NOT' is flagged."""
        p = _write(tmp_path, "Hooks must NOT block tools.\n")
        violations = scan_file(p)
        assert any(v.pattern == "must NOT" for v in violations), f"Expected 'must NOT' violation, got: {violations}"

    def test_dont_instruction_start_fails(self, tmp_path: Path) -> None:
        """Line starting with Don't is flagged."""
        p = _write(tmp_path, "- Don't mock the database.\n")
        violations = scan_file(p)
        assert any(v.pattern == "Don't" for v in violations), f"Expected Don't violation, got: {violations}"

    def test_avoid_heading_fails(self, tmp_path: Path) -> None:
        """Heading containing 'Avoid' is flagged."""
        p = _write(tmp_path, "### Patterns to Avoid\n\nSome content.\n")
        violations = scan_file(p)
        assert any(v.pattern == "Avoid" for v in violations), f"Expected Avoid violation, got: {violations}"

    def test_avoid_as_bullet_start_fails(self, tmp_path: Path) -> None:
        """Bullet starting with 'Avoid' is flagged."""
        p = _write(tmp_path, "- Avoid using global state.\n")
        violations = scan_file(p)
        assert any(v.pattern == "Avoid" for v in violations), f"Expected Avoid violation for bullet, got: {violations}"


# ---------------------------------------------------------------------------
# Contextual exceptions -- must PASS (no violations)
# ---------------------------------------------------------------------------


class TestContextualExceptions:
    """Patterns inside fenced code blocks and subordinate positions must not be flagged."""

    def test_never_in_fenced_code_block_passes(self, tmp_path: Path) -> None:
        """NEVER inside a fenced code block is skipped."""
        content = "```python\n# NEVER do this\nrm -rf /\n```\n"
        p = _write(tmp_path, content)
        violations = scan_file(p)
        assert violations == [], f"Expected no violations for fenced NEVER, got: {violations}"

    def test_do_not_in_fenced_code_block_passes(self, tmp_path: Path) -> None:
        """do NOT inside a fenced block is skipped."""
        content = "```bash\n# do NOT run as root\nsudo command\n```\n"
        p = _write(tmp_path, content)
        violations = scan_file(p)
        assert violations == [], f"Expected no violations for fenced 'do NOT', got: {violations}"

    def test_anti_pattern_in_fenced_block_passes(self, tmp_path: Path) -> None:
        """Anti-Pattern heading inside fenced code is skipped."""
        content = "```md\n## Anti-Patterns\nBad thing.\n```\n"
        p = _write(tmp_path, content)
        violations = scan_file(p)
        assert violations == [], f"Expected no violations for fenced Anti-Pattern, got: {violations}"

    def test_clean_file_passes(self, tmp_path: Path) -> None:
        """A file with positive-only framing produces zero violations."""
        content = (
            "# My Skill\n\n"
            "## Preferred Patterns\n\n"
            "Route code modifications to domain agents.\n\n"
            "Create feature branches for all commits.\n\n"
            "Use `git add specific-file.py` to stage by name.\n"
        )
        p = _write(tmp_path, content)
        violations = scan_file(p)
        assert violations == [], f"Expected no violations for clean file, got: {violations}"

    def test_subordinate_never_in_positive_instruction_passes(self, tmp_path: Path) -> None:
        """'never in code' subordinate to positive instruction does not trigger NEVER pattern.

        The regex matches \\bNEVER\\b (uppercase). Lowercase 'never' is not
        flagged -- this is the intended behaviour for subordinate negatives
        like 'Credentials stay in .env files, never in code.'
        """
        content = "Credentials stay in .env files, never in code or logs.\n"
        p = _write(tmp_path, content)
        violations = scan_file(p)
        assert violations == [], f"Expected no violations for subordinate lowercase 'never', got: {violations}"

    def test_blockquote_line_passes(self, tmp_path: Path) -> None:
        """Lines starting with > (blockquote) are skipped."""
        content = "> Do NOT copy this pattern.\n> NEVER do this in production.\n"
        p = _write(tmp_path, content)
        violations = scan_file(p)
        assert violations == [], f"Expected no violations for blockquote lines, got: {violations}"


# ---------------------------------------------------------------------------
# Positive rewrite examples -- positive framing must not be flagged
# ---------------------------------------------------------------------------


class TestPositiveRewrites:
    """Positive rewrites from the rubric must produce zero violations."""

    def test_route_to_agents_positive(self, tmp_path: Path) -> None:
        p = _write(tmp_path, "Route all code modifications to domain agents.\n")
        assert scan_file(p) == []

    def test_feature_branch_positive(self, tmp_path: Path) -> None:
        p = _write(tmp_path, "Create feature branches for all commits.\n")
        assert scan_file(p) == []

    def test_preferred_heading_positive(self, tmp_path: Path) -> None:
        p = _write(tmp_path, "## Preferred Patterns\n\nUse this approach.\n")
        assert scan_file(p) == []

    def test_hard_gate_heading_positive(self, tmp_path: Path) -> None:
        p = _write(tmp_path, "### Hard Gate Patterns\n\nEnforced by hooks.\n")
        assert scan_file(p) == []


# ---------------------------------------------------------------------------
# Fleet gate -- the CI step runs `validate_positive_instruction_docs.py --fleet`
# ---------------------------------------------------------------------------


class TestFleetGate:
    """--fleet scans agents/*.md and skills/**/SKILL.md and fails on any violation."""

    @staticmethod
    def _fleet(tmp_path: Path, skill_body: str) -> Path:
        (tmp_path / "agents").mkdir()
        (tmp_path / "agents" / "demo.md").write_text("# Demo\n\nRoute work to agents.\n", encoding="utf-8")
        skill = tmp_path / "skills" / "cat" / "demo" / "SKILL.md"
        skill.parent.mkdir(parents=True)
        skill.write_text(skill_body, encoding="utf-8")
        # Reference docs are outside the fleet; a violation there must not fail --fleet.
        (skill.parent / "references").mkdir()
        (skill.parent / "references" / "notes.md").write_text("NEVER do this.\n", encoding="utf-8")
        return tmp_path

    def test_fleet_catches_bad_skill(self, tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
        root = self._fleet(tmp_path, "# Demo\n\nDo NOT skip tests.\n")
        assert _mod.main(["--fleet", "--root", str(root)]) == 1
        assert "skills/cat/demo/SKILL.md:3 [do NOT]" in capsys.readouterr().out

    def test_fleet_passes_clean_fleet(self, tmp_path: Path) -> None:
        root = self._fleet(tmp_path, "# Demo\n\nRun the tests.\n")
        assert _mod.main(["--fleet", "--root", str(root)]) == 0
