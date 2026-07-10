"""Regression tests for bundled skill self-validation commands."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]


@pytest.mark.parametrize(
    "validator",
    [
        "skills/meta/docs-sync-checker/scripts/validate.py",
        "skills/testing/test-driven-development/scripts/validate.py",
    ],
)
def test_self_validator_accepts_its_current_skill_contract(validator: str) -> None:
    """A bundled validator must pass the skill it is shipped with."""
    result = subprocess.run(
        [sys.executable, str(REPO_ROOT / validator)],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        timeout=30,
    )

    assert result.returncode == 0, f"{validator} failed:\nstdout:\n{result.stdout}\nstderr:\n{result.stderr}"
