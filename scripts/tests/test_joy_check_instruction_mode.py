"""Deterministic joy-check tests for instruction-mode patterns.

Two scopes:
1. Golden fixture tests — small .md snippets that exercise each of the 7
   primary patterns from private-skills/voice/skills/joy-check/references/
   instruction-rubric.md, plus contextual exceptions that must pass.
2. Fleet scan — parametrized test across all agents/*.md and
   skills/**/SKILL.md.  Known violations in voice-corpus files are covered
   by the allowlist in validate_positive_instruction_docs.py; any new
   violation in the fleet causes an explicit failure.

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
should_skip = _mod.should_skip

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _write(tmp_path: Path, content: str, name: str = "sample.md") -> Path:
    """Write content to a temp file and return its path."""
    p = tmp_path / name
    p.write_text(content, encoding="utf-8")
    # Override REPO_ROOT so relative-path logic works from tmp_path
    _mod.REPO_ROOT = tmp_path
    return p


# ---------------------------------------------------------------------------
# Golden fixture tests — each primary pattern
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
        """'do NOT' (case-insensitive start) is flagged."""
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
# Contextual exceptions — must PASS (no violations)
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

        The regex matches \bNEVER\b (uppercase). Lowercase 'never' is not
        flagged — this is the intended behaviour for subordinate negatives
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
# Positive rewrite examples — positive framing must not be flagged
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
# Fleet scan — parametrized across agents/*.md and skills/**/SKILL.md
# ---------------------------------------------------------------------------

_AGENT_FILES = sorted(_REPO_ROOT.glob("agents/*.md"))
_SKILL_FILES = sorted(_REPO_ROOT.glob("skills/**/SKILL.md"))
_FLEET = _AGENT_FILES + _SKILL_FILES

# Build fleet parameter list, skipping allowlisted files.
# Use a sentinel so pytest reports "skipped (allowlisted)" rather than collecting 0 params.
_fleet_params = []
for _f in _FLEET:
    _rel = str(_f.relative_to(_REPO_ROOT))
    if should_skip(_f):
        _fleet_params.append(pytest.param(_f, marks=pytest.mark.skip(reason=f"allowlisted: {_rel}")))
    else:
        _fleet_params.append(pytest.param(_f, id=_rel))


@pytest.mark.parametrize("md_file", _fleet_params)
def test_fleet_joy_check(md_file: Path) -> None:
    """Every non-allowlisted agent and skill must pass instruction-mode joy check.

    Failure means the file contains a primary negative-framing pattern that
    should be rewritten to positive framing per instruction-rubric.md.
    Run `python3 scripts/validate_positive_instruction_docs.py` for the full
    violation list with line numbers.
    """
    _mod.REPO_ROOT = _REPO_ROOT
    violations = scan_file(md_file)
    rel = str(md_file.relative_to(_REPO_ROOT))
    assert violations == [], (
        f"Joy-check failure in {rel}: {len(violations)} violation(s).\n"
        + "\n".join(f"  L{v.line} [{v.pattern}] {v.text}" for v in violations[:10])
        + ("\n  ..." if len(violations) > 10 else "")
    )
