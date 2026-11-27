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


def test_all_flag_covers_routing_and_node_tests() -> None:
    """The --all flag wires up routing checks and Node plugin tests."""
    text = _script_text()
    assert "--all)" in text
    assert "scripts/routing-benchmark.py --verbose" in text
    assert "scripts/check-routing-drift.py --verbose" in text
    assert "scripts/router-self-audit.py" in text
    assert "node --test plugins/jev-auto-compact/tests/*.test.mjs" in text


def test_workflow_permissions_hook_health_and_node_tests() -> None:
    """Workflow pins read-only permissions, deploys pyrun.sh, and runs node-tests."""
    data = yaml.safe_load(_WORKFLOW.read_text(encoding="utf-8"))
    assert data.get("permissions") == {"contents": "read"}

    hook_steps = data["jobs"]["hook-health"]["steps"]
    deploy_runs = "\n".join(s.get("run", "") for s in hook_steps if isinstance(s, dict))
    assert "hooks/lib/pyrun.sh" in deploy_runs

    node_steps = data["jobs"]["node-tests"]["steps"]
    node_runs = "\n".join(s.get("run", "") for s in node_steps if isinstance(s, dict))
    assert "node --test plugins/jev-auto-compact/tests/*.test.mjs" in node_runs


def test_conftest_strips_session_and_token_env_vars() -> None:
    """Root conftest strips live-session, debug, and token env vars."""
    for name in (
        "CLAUDE_AFK_MODE",
        "GH_TOKEN",
        "GITHUB_TOKEN",
        "CLAUDE_HOOKS_DEBUG",
        "CLAUDE_HOOK_DEBUG",
        "PROTECTED_ORGS",
        "CLAUDE_ROUTING_STATE_DIR",
    ):
        assert name not in os.environ, f"{name} leaked into test environment"
