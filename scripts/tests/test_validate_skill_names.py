"""validate-skill-names.py: flat skill names must be unique across categories."""

from __future__ import annotations

import importlib.util
from pathlib import Path

SCRIPTS_DIR = Path(__file__).resolve().parents[1]
SCRIPT = SCRIPTS_DIR / "validate-skill-names.py"
_SPEC = importlib.util.spec_from_file_location(
    "validate_skill_names", Path(__file__).resolve().parents[1] / "validate-skill-names.py"
)
assert _SPEC and _SPEC.loader
vsn = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(vsn)


def _skill(repo: Path, rel: str) -> None:
    d = repo / "skills" / rel
    d.mkdir(parents=True)
    (d / "SKILL.md").write_text("---\nname: x\n---\n")


def test_unique_names_pass(tmp_path: Path) -> None:
    _skill(tmp_path, "meta/alpha")
    _skill(tmp_path, "content/beta")
    assert vsn.main(["--repo", str(tmp_path)]) == 0


def test_same_name_in_two_categories_fails(tmp_path: Path, capsys) -> None:
    _skill(tmp_path, "meta/alpha")
    _skill(tmp_path, "content/alpha")
    assert vsn.main(["--repo", str(tmp_path)]) == 1
    assert "duplicate skill name 'alpha'" in capsys.readouterr().out


def test_support_dirs_are_ignored(tmp_path: Path) -> None:
    _skill(tmp_path, "shared-patterns/alpha")
    _skill(tmp_path, "meta/alpha")
    assert vsn.main(["--repo", str(tmp_path)]) == 0


def test_cli_exits_nonzero_on_duplicates(tmp_path: Path) -> None:
    import subprocess
    import sys

    _skill(tmp_path, "meta/alpha")
    _skill(tmp_path, "content/alpha")
    result = subprocess.run(
        [sys.executable, str(SCRIPT), "--repo", str(tmp_path)],
        capture_output=True,
        text=True,
    )
    assert result.returncode != 0
