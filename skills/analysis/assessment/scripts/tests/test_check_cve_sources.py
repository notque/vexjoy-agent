"""The CVE source audit runs from the installed assessment skill.

The script used to live in the cve-source-check husk, which the installer skips,
so `references/service-health-check/cve-source-check.md` pointed at a script no
install carried. These tests run it from the assessment skill, offline, from a
directory outside the repo, the way an agent runs it.
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

SKILL_DIR = Path(__file__).resolve().parents[2]
SCRIPT = SKILL_DIR / "scripts" / "check-cve-sources.py"
EXAMPLES = SKILL_DIR / "references" / "service-health-check" / "examples"


def _run(cwd: Path, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(SCRIPT), *args, "--out-dir", str(cwd)],
        capture_output=True,
        text=True,
        cwd=str(cwd),
        timeout=60,
    )


def test_default_registry_loads_from_the_assessment_skill(tmp_path: Path) -> None:
    result = _run(tmp_path, "--inline", "go@1.22,nginx@1.25", "--service", "fixture")

    assert result.returncode in (0, 1), result.stderr
    assert "failed to load registry" not in result.stderr
    reports = sorted(tmp_path.glob("cve-source-report-fixture-*.json"))
    assert len(reports) == 1
    summary = json.loads(reports[0].read_text(encoding="utf-8"))["summary"]
    assert summary["mapped"] == 2


def test_quick_start_example_inputs_ship_with_the_skill(tmp_path: Path) -> None:
    result = _run(
        tmp_path,
        "--inventory",
        str(EXAMPLES / "inventory.example.json"),
        "--current-sources",
        str(EXAMPLES / "current-sources.example.txt"),
        "--service",
        "example",
    )

    assert result.returncode in (0, 1), result.stderr
    assert sorted(tmp_path.glob("cve-source-report-example-*.md"))
