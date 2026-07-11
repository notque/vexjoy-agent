"""Target-root CLI behavior for validate-doc-counts.py."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

SCRIPT = Path(__file__).resolve().parent.parent / "validate-doc-counts.py"


def test_repo_root_option_counts_target_as_data(tmp_path: Path) -> None:
    (tmp_path / "agents").mkdir()
    (tmp_path / "scripts").mkdir()
    (tmp_path / "hooks").mkdir()
    (tmp_path / "skills").mkdir()
    (tmp_path / "agents" / "one.md").write_text("# Agent\n", encoding="utf-8")
    (tmp_path / "scripts" / "one.py").write_text("# data\n", encoding="utf-8")
    (tmp_path / "hooks" / "one.py").write_text("# data\n", encoding="utf-8")

    result = subprocess.run(
        [sys.executable, str(SCRIPT), "--json", "--repo-root", str(tmp_path)],
        capture_output=True,
        text=True,
        timeout=10,
    )

    assert result.returncode == 0, result.stderr
    report = json.loads(result.stdout)
    assert report["truth"]["agents"] == 1
    assert report["truth"]["scripts"] == 1
    assert report["truth"]["hooks"] == 1
