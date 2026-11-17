"""Tests for validate-threat-model.py — runs the CLI as a subprocess on tmp_path fixtures."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

SCRIPT = Path(__file__).resolve().parents[1] / "validate-threat-model.py"

VALID_THREAT_MODEL = """\
# Threat Model

## Run Metadata
run_id: abc-123

## Attack Surface Inventory
Some inventory text that makes the file longer than 100 characters overall.

## Active Threats
Threat one.

## Mitigations In Place
Mitigation one.

## Gaps and Recommended Next Controls
Gap one.

## Deny-List Status
Clean.

## Supply-Chain Audit Summary
All clear.

## Learning DB Sanitization Summary
Sanitized.
"""

VALID_BADGE = json.dumps(
    {
        "status": "pass",
        "timestamp": "2026-01-01T00:00:00Z",
        "run_id": "abc-123",
        "critical_count": 0,
        "warning_count": 1,
        "phases_completed": 5,
    }
)


def _run(
    *extra_args: str,
    threat_model: Path | None = None,
    badge: Path | None = None,
) -> subprocess.CompletedProcess[str]:
    """Run the validator script and return the completed process."""
    cmd = [sys.executable, str(SCRIPT)]
    if threat_model is not None:
        cmd += ["--threat-model", str(threat_model)]
    if badge is not None:
        cmd += ["--badge", str(badge)]
    cmd += list(extra_args)
    return subprocess.run(cmd, capture_output=True, text=True, timeout=30)


def test_passing_input(tmp_path: Path) -> None:
    """Both files valid: exit 0."""
    tm = tmp_path / "threat-model.md"
    tm.write_text(VALID_THREAT_MODEL, encoding="utf-8")
    badge = tmp_path / "audit-badge.json"
    badge.write_text(VALID_BADGE, encoding="utf-8")

    result = _run(threat_model=tm, badge=badge)
    assert result.returncode == 0
    assert "PASS" in result.stdout


def test_missing_section_fails(tmp_path: Path) -> None:
    """A threat model missing a required section: exit 1, names the missing section."""
    tm = tmp_path / "threat-model.md"
    # Remove "## Deny-List Status" section
    content = VALID_THREAT_MODEL.replace("## Deny-List Status\nClean.\n", "")
    tm.write_text(content, encoding="utf-8")
    badge = tmp_path / "audit-badge.json"
    badge.write_text(VALID_BADGE, encoding="utf-8")

    result = _run(threat_model=tm, badge=badge)
    assert result.returncode == 1
    assert "Deny-List Status" in result.stdout


def test_invalid_badge_status_fails(tmp_path: Path) -> None:
    """Badge with an invalid status value: exit 1, names the failure."""
    tm = tmp_path / "threat-model.md"
    tm.write_text(VALID_THREAT_MODEL, encoding="utf-8")
    badge_data = json.loads(VALID_BADGE)
    badge_data["status"] = "unknown"
    badge = tmp_path / "audit-badge.json"
    badge.write_text(json.dumps(badge_data), encoding="utf-8")

    result = _run(threat_model=tm, badge=badge)
    assert result.returncode == 1
    assert "status" in result.stdout


@pytest.mark.parametrize("missing_field", ["run_id", "critical_count"])
def test_badge_missing_field_fails(tmp_path: Path, missing_field: str) -> None:
    """Badge missing a required field: exit 1, names the field."""
    tm = tmp_path / "threat-model.md"
    tm.write_text(VALID_THREAT_MODEL, encoding="utf-8")
    badge_data = json.loads(VALID_BADGE)
    del badge_data[missing_field]
    badge = tmp_path / "audit-badge.json"
    badge.write_text(json.dumps(badge_data), encoding="utf-8")

    result = _run(threat_model=tm, badge=badge)
    assert result.returncode == 1
    assert missing_field in result.stdout
