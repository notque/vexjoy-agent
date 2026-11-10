"""Contract tests: scripts/ci-local.sh mirrors the CI lint job."""

import os
import re
from pathlib import Path

import yaml

_REPO_ROOT = Path(__file__).resolve().parents[1]
_WORKFLOW = _REPO_ROOT / ".github" / "workflows" / "test.yml"
_SCRIPT = _REPO_ROOT / "scripts" / "ci-local.sh"


def _lint_steps() -> list[str]:
    """Return the run strings from the lint job, minus pip-install and multi-line steps."""
    data = yaml.safe_load(_WORKFLOW.read_text(encoding="utf-8"))
    steps = data["jobs"]["lint"]["steps"]
    result: list[str] = []
    for step in steps:
        run = step.get("run")
        if run is None:
            continue
        run = run.strip()
        if run.startswith("pip install"):
            continue
        if "\n" in run:
            continue
        result.append(run)
    return result


def _script_form(cmd: str) -> str:
    """Convert a CI command to the form the script uses."""
    return re.sub(r"\bpython ", '"$PY" ', cmd)


def _script_text() -> str:
    return _SCRIPT.read_text(encoding="utf-8")


def test_every_lint_step_is_mirrored() -> None:
    """Every single-line lint-job step appears in the script."""
    text = _script_text()
    for cmd in _lint_steps():
        form = _script_form(cmd)
        assert form in text, f"CI command not in script: {cmd!r} — add it to scripts/ci-local.sh in workflow order"


def _find_exact(text: str, form: str) -> int:
    """Find form in text, preferring a match that is not a prefix of a longer token.

    When the same command appears with and without trailing flags (e.g.
    ``validate-doc-commands.py`` vs ``validate-doc-commands.py --check-sdir``),
    a plain ``str.find`` can return the wrong hit.  Search for the form
    followed by a quote (closing ``'`` in a ``step '...'`` call) first; fall
    back to the plain substring match.
    """
    exact = text.find(form + "'")
    if exact >= 0:
        return exact
    return text.find(form)


def test_steps_keep_workflow_order() -> None:
    """Mirrored commands appear in the script in the same order as the workflow."""
    text = _script_text()
    positions: list[int] = []
    for cmd in _lint_steps():
        form = _script_form(cmd)
        pos = _find_exact(text, form)
        if pos >= 0:
            positions.append(pos)
    assert positions == sorted(positions), "script commands are not in workflow order"


def test_index_local_guard_is_mirrored() -> None:
    """The multi-line INDEX.local.json guard is present in the script."""
    text = _script_text()
    assert r"INDEX\.local\.json" in text, "the INDEX.local.json guard from the lint job is missing from the script"


def test_lint_job_was_parsed() -> None:
    """Sanity: the lint job has at least 20 single-line steps."""
    assert len(_lint_steps()) >= 20, "fewer than 20 single-line lint steps found — was the job renamed or split?"


def test_script_is_executable_bash() -> None:
    """The script is executable bash with strict mode."""
    text = _script_text()
    assert text.startswith("#!/usr/bin/env bash"), "script must start with #!/usr/bin/env bash"
    assert "set -euo pipefail" in text, "script must use set -euo pipefail"
    assert os.access(_SCRIPT, os.X_OK), "script must be executable (chmod 755)"
