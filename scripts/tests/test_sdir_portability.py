"""$SDIR portability (`validate-doc-commands.py --check-sdir`).

The /do SKILL.md must invoke its scripts as "$SDIR/name.py"; a repo-relative
`python3 scripts/name.py` fails silently from a non-repo cwd. The repo check is
a CI step; these tests prove it catches each bad fixture.
"""

from __future__ import annotations

import importlib
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT / "scripts"))
doc_commands = importlib.import_module("validate-doc-commands")


def _fixture(tmp_path: Path, skill_text: str, broken_script: bool = False) -> tuple[Path, Path]:
    scripts = tmp_path / "scripts"
    scripts.mkdir()
    ok = "import argparse\nargparse.ArgumentParser().parse_args()\n"
    (scripts / "a.py").write_text(ok, encoding="utf-8")
    (scripts / "b.py").write_text("raise SystemExit(3)\n" if broken_script else ok, encoding="utf-8")
    skill = tmp_path / "SKILL.md"
    skill.write_text(skill_text, encoding="utf-8")
    return skill, scripts


def test_real_do_skill_is_portable() -> None:
    assert doc_commands.check_sdir() == []


def test_portable_fixture_passes(tmp_path: Path) -> None:
    skill, scripts = _fixture(tmp_path, 'python3 "$SDIR/a.py"\npython3 "$SDIR/b.py"\n')
    assert doc_commands.check_sdir(skill, scripts) == []


def test_bad_fixture_is_caught(tmp_path: Path) -> None:
    text = 'python3 scripts/a.py\npython3 "$SDIR/b.py"\npython3 "$SDIR/gone.py"\n'
    skill, scripts = _fixture(tmp_path, text, broken_script=True)
    failures = "\n".join(doc_commands.check_sdir(skill, scripts))
    assert "bare repo-relative invocation (use $SDIR): python3 scripts/a.py" in failures
    assert "$SDIR/b.py: exit 3 from a non-repo cwd" in failures
    assert "$SDIR/gone.py: missing" in failures


def test_regex_matching_nothing_is_caught(tmp_path: Path) -> None:
    skill, scripts = _fixture(tmp_path, "no scripts here\n")
    assert doc_commands.check_sdir(skill, scripts) == ["expected at least 2 $SDIR scripts, found []"]
