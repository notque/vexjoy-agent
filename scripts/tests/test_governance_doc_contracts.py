"""Support-dir registration (`validate-skill-names.py`, a CI step).

Pipeline doc targets are checked for every pipeline by
`validate-pipeline-index.py`. This file proves the skills/ support-dir check
catches an unregistered dir that holds no skill.
"""

from __future__ import annotations

import importlib
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT / "scripts"))
skill_names = importlib.import_module("validate-skill-names")


def test_unregistered_support_dir_fails(tmp_path: Path, capsys) -> None:
    skills = tmp_path / "skills"
    (skills / "cat" / "demo").mkdir(parents=True)
    (skills / "cat" / "demo" / "SKILL.md").write_text("# Demo\n", encoding="utf-8")
    (skills / "shared-patterns").mkdir()
    (skills / "loose-notes").mkdir()

    assert skill_names.find_unregistered_dirs(tmp_path) == ["loose-notes"]
    assert skill_names.main(["--repo", str(tmp_path)]) == 1
    assert "skills/loose-notes/ holds no skill" in capsys.readouterr().out
