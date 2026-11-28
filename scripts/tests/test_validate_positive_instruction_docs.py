"""CLI tests for scripts/validate_positive_instruction_docs.py."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

SCRIPT = Path(__file__).resolve().parent.parent / "validate_positive_instruction_docs.py"


def test_cli_fleet_exits_zero_on_clean_skill(tmp_path: Path) -> None:
    skill = tmp_path / "skills" / "demo" / "clean" / "SKILL.md"
    skill.parent.mkdir(parents=True)
    skill.write_text("# Clean Skill\n\nUse positive, direct instructions.\n", encoding="utf-8")

    result = subprocess.run(
        [sys.executable, str(SCRIPT), "--fleet", "--root", str(tmp_path)],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stdout + result.stderr


def test_cli_fleet_exits_one_on_prohibition_led_violation(tmp_path: Path) -> None:
    """CLI negative control: prohibition-led framing in a skill exits 1."""
    skill = tmp_path / "skills" / "demo" / "bad" / "SKILL.md"
    skill.parent.mkdir(parents=True)
    skill.write_text("# Bad Skill\n\nNEVER skip verification steps.\n", encoding="utf-8")

    result = subprocess.run(
        [sys.executable, str(SCRIPT), "--fleet", "--root", str(tmp_path), "--json"],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 1, result.stdout + result.stderr
    data = json.loads(result.stdout)
    assert data["count"] == 1
    assert data["violations"][0]["pattern"] == "NEVER"
