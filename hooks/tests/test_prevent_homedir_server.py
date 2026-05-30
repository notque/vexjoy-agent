#!/usr/bin/env python3
"""
Tests for the prevent-homedir-server hook.

Covers the documented BLOCKED cases (python http.server from the bare home
directory) and SAFE cases (--directory to a project path, `cd ~/project`
first, non-home CWD, commands without http.server), plus the non-blocking
contract (exit 0 on every path, including empty/malformed stdin).

The hook reads the protected home from Path.home() at import time, so each
subprocess run sets HOME explicitly and passes a matching `cwd` in the event
envelope.

Run with: python3 -m pytest hooks/tests/test_prevent_homedir_server.py -v
Or standalone: python3 hooks/tests/test_prevent_homedir_server.py
"""

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

HOOK_PATH = Path(__file__).parent.parent / "prevent-homedir-server.py"

FAKE_HOME = "/home/testuser"


def _event(command, *, cwd=None, omit_cwd=False):
    ev = {"tool_name": "Bash", "tool_input": {"command": command}}
    if not omit_cwd:
        ev["cwd"] = cwd
    return json.dumps(ev)


def _run(stdin_payload, *, home=FAKE_HOME):
    """Run the hook as a subprocess. Return (exit_code, decision_or_None)."""
    env = dict(os.environ)
    env["HOME"] = home
    # Ensure the hook's CWD fallback (os.getcwd) cannot accidentally equal home.
    proc = subprocess.run(
        [sys.executable, str(HOOK_PATH)],
        input=stdin_payload,
        capture_output=True,
        text=True,
        env=env,
        cwd="/tmp",
    )
    decision = None
    out = proc.stdout.strip()
    if out:
        try:
            parsed = json.loads(out)
            decision = parsed.get("hookSpecificOutput", {}).get("permissionDecision")
        except json.JSONDecodeError:
            decision = "INVALID_JSON"
    return proc.returncode, decision


# ---------------------------------------------------------------------------
# BLOCKED cases
# ---------------------------------------------------------------------------


def test_http_server_from_bare_home_is_blocked():
    code, decision = _run(_event("python3 -m http.server 8080", cwd=FAKE_HOME))
    assert code == 0
    assert decision == "deny"


def test_simplehttpserver_from_bare_home_is_blocked():
    code, decision = _run(_event("python -m SimpleHTTPServer 8000", cwd=FAKE_HOME))
    assert code == 0
    assert decision == "deny"


def test_http_server_no_3_from_bare_home_is_blocked():
    # `python -m http.server` (no 3) must also be blocked.
    code, decision = _run(_event("python -m http.server", cwd=FAKE_HOME))
    assert code == 0
    assert decision == "deny"


def test_directory_flag_pointing_at_home_is_blocked():
    code, decision = _run(_event(f"python3 -m http.server --directory {FAKE_HOME} 8080", cwd="/tmp"))
    assert code == 0
    assert decision == "deny"


def test_home_cwd_via_envelope_even_when_process_cwd_differs():
    # Process runs in /tmp but the session envelope reports home as CWD.
    code, decision = _run(_event("python3 -m http.server", cwd=FAKE_HOME))
    assert code == 0
    assert decision == "deny"


def test_no_space_dash_m_form_is_blocked():
    # Bypass regression: Python accepts `-mhttp.server` (no space); must block.
    code, decision = _run(_event("python3 -mhttp.server 8080", cwd=FAKE_HOME))
    assert code == 0
    assert decision == "deny"


def test_no_space_dash_m_simplehttpserver_is_blocked():
    code, decision = _run(_event("python -mSimpleHTTPServer 8000", cwd=FAKE_HOME))
    assert code == 0
    assert decision == "deny"


def test_symlinked_cwd_to_home_is_blocked(tmp_path):
    # Bypass regression: a cwd that is a symlink pointing at home must block.
    link = tmp_path / "homelink"
    link.symlink_to(FAKE_HOME)
    code, decision = _run(_event("python3 -m http.server 8080", cwd=str(link)))
    assert code == 0
    assert decision == "deny"


def test_directory_dot_from_home_is_blocked():
    # Bypass regression: relative `--directory .` resolves against the session
    # cwd (home here), not the hook process cwd, so it must block.
    code, decision = _run(_event("python3 -m http.server --directory . 8080", cwd=FAKE_HOME))
    assert code == 0
    assert decision == "deny"


# ---------------------------------------------------------------------------
# SAFE cases
# ---------------------------------------------------------------------------


def test_directory_flag_to_project_path_is_allowed():
    code, decision = _run(_event(f"python3 -m http.server --directory {FAKE_HOME}/myproject 8080", cwd=FAKE_HOME))
    assert code == 0
    assert decision is None


def test_cd_into_subdir_first_is_allowed():
    code, decision = _run(_event("cd ~/myproject && python3 -m http.server 8080", cwd=FAKE_HOME))
    assert code == 0
    assert decision is None


def test_non_home_cwd_is_allowed():
    code, decision = _run(_event("python3 -m http.server 8080", cwd=f"{FAKE_HOME}/myproject"))
    assert code == 0
    assert decision is None


def test_command_without_http_server_is_allowed():
    code, decision = _run(_event("ls -la && grep http.server notes.txt", cwd=FAKE_HOME))
    assert code == 0
    assert decision is None


def test_unrelated_command_from_home_is_allowed():
    code, decision = _run(_event("git status", cwd=FAKE_HOME))
    assert code == 0
    assert decision is None


def test_directory_flag_outside_home_is_allowed():
    code, decision = _run(_event("python3 -m http.server --directory /srv/www 8080", cwd=FAKE_HOME))
    assert code == 0
    assert decision is None


def test_relative_directory_subdir_from_home_is_allowed():
    # `--directory ./proj` from home resolves to a subdir of home -> safe.
    code, decision = _run(_event("python3 -m http.server --directory ./proj 8080", cwd=FAKE_HOME))
    assert code == 0
    assert decision is None


# ---------------------------------------------------------------------------
# Non-blocking contract: exit 0 on every input shape
# ---------------------------------------------------------------------------


def test_empty_stdin_exits_zero_and_allows():
    code, decision = _run("")
    assert code == 0
    assert decision is None


def test_whitespace_stdin_exits_zero_and_allows():
    code, decision = _run("   \n  ")
    assert code == 0
    assert decision is None


def test_malformed_json_exits_zero_and_allows():
    code, decision = _run("{not valid json")
    assert code == 0
    assert decision is None


def test_missing_cwd_in_envelope_does_not_crash():
    # No cwd key at all -> falls back to env/os.getcwd (/tmp), so allowed.
    code, decision = _run(_event("python3 -m http.server 8080", omit_cwd=True))
    assert code == 0
    assert decision is None


if __name__ == "__main__":
    sys.exit(pytest.main([__file__, "-v"]))
