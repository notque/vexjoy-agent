#!/usr/bin/env python3
"""Mutation-kill tests for pretool-adr-creation-gate.

Covers what the base suite never pinned: the hook always exits 0 (deny is a
stdout JSON, not an exit code), debug output only appears when
CLAUDE_HOOKS_DEBUG is set, and the helper fallbacks (unreadable dir, odd git
output) fail the safe way.
"""

import importlib.util
import json
import os
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import pytest

HOOK_PATH = Path(__file__).parent.parent / "pretool-adr-creation-gate.py"
spec = importlib.util.spec_from_file_location("pretool_adr_creation_gate_mut", HOOK_PATH)
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)


def _run(payload, capsys, *, debug=False, env=None):
    """Run main() in-process; return (exit_code, denied, stderr)."""
    base = {k: v for k, v in os.environ.items() if k not in ("ADR_CREATION_GATE_BYPASS", "CLAUDE_HOOKS_DEBUG")}
    if debug:
        base["CLAUDE_HOOKS_DEBUG"] = "1"
    base.update(env or {})
    raw = payload if isinstance(payload, str) else json.dumps(payload)
    code = None
    with patch.dict(os.environ, base, clear=True), patch.object(mod, "read_stdin", return_value=raw):
        try:
            mod.main()
        except SystemExit as exc:
            code = exc.code
    out = capsys.readouterr()
    denied = False
    if out.out.strip():
        denied = json.loads(out.out)["hookSpecificOutput"]["permissionDecision"] == "deny"
    return code, denied, out.err


def _write(path, cwd=None):
    event = {"tool_name": "Write", "tool_input": {"file_path": str(path)}}
    if cwd is not None:
        event["cwd"] = str(cwd)
    return event


@pytest.fixture
def state(tmp_path):
    """Point the centralized ADR dir at an empty tmp dir."""
    with patch.object(mod, "_VEXJOY_STATE_DIR", tmp_path / "state"):
        yield tmp_path / "state"


def _allow_scenarios(tmp_path, state):
    """Every path through main() that ends in allow, as (name, payload, env)."""
    proj = tmp_path / "proj"
    (proj / "adr").mkdir(parents=True)
    (proj / "adr" / "has-adr.md").write_text("# adr\n")
    existing = proj / "skills" / "old" / "SKILL.md"
    existing.parent.mkdir(parents=True)
    existing.write_text("x\n")
    central = state / proj.name / "adrs"
    central.mkdir(parents=True)
    (central / "central-adr.md").write_text("# adr\n")
    return [
        ("bypass", _write(proj / "skills" / "new" / "SKILL.md", proj), {"ADR_CREATION_GATE_BYPASS": "1"}),
        ("non-component", _write(proj / "src" / "a.py", proj), {}),
        ("existing-file", _write(existing, proj), {}),
        ("voice-allowlist", _write(proj / "skills" / "voice-x" / "SKILL.md", proj), {}),
        ("project-adr", _write(proj / "skills" / "has-adr" / "SKILL.md", proj), {}),
        ("central-adr", _write(proj / "skills" / "central-adr" / "SKILL.md", proj), {}),
    ]


class TestExitCodes:
    def test_every_allow_path_exits_zero(self, tmp_path, state, capsys):
        for name, payload, env in _allow_scenarios(tmp_path, state):
            code, denied, _ = _run(payload, capsys, env=env)
            assert code == 0 and not denied, name

    def test_malformed_json_exits_zero(self, capsys):
        code, denied, _ = _run("{not json", capsys)
        assert code == 0 and not denied

    def test_missing_file_path_exits_zero(self, capsys):
        code, denied, _ = _run({"tool_input": {}}, capsys)
        assert code == 0 and not denied

    def test_deny_still_exits_zero(self, tmp_path, state, capsys):
        code, denied, _ = _run(_write(tmp_path / "skills" / "brand-new" / "SKILL.md", tmp_path), capsys)
        assert code == 0 and denied


class TestDebugOutput:
    def test_allow_paths_are_silent_without_debug(self, tmp_path, state, capsys):
        for name, payload, env in _allow_scenarios(tmp_path, state):
            _, _, err = _run(payload, capsys, env=env)
            assert err == "", name

    def test_allow_paths_explain_themselves_with_debug(self, tmp_path, state, capsys):
        for name, payload, env in _allow_scenarios(tmp_path, state):
            _, _, err = _run(payload, capsys, debug=True, env=env)
            assert err.strip(), name

    def test_debug_shows_where_a_missing_adr_was_looked_for(self, tmp_path, state, capsys):
        _, denied, err = _run(_write(tmp_path / "skills" / "brand-new" / "SKILL.md", tmp_path), capsys, debug=True)
        assert denied
        assert str(state) in err
        assert str(tmp_path / "adr" / "brand-new.md") in err

    def test_missing_adr_without_debug_only_prints_the_block_notice(self, tmp_path, state, capsys):
        _, denied, err = _run(_write(tmp_path / "skills" / "brand-new" / "SKILL.md", tmp_path), capsys)
        assert denied
        assert "BLOCKED" in err
        assert "ADR not found in" not in err

    def test_find_adr_is_quiet_by_default(self, tmp_path, state, capsys):
        assert mod._find_adr("nothing", tmp_path) is None
        assert capsys.readouterr().err == ""


class TestHelpers:
    def test_unreadable_repo_root_is_not_a_toolkit(self):
        class Boom:
            def __truediv__(self, _):
                return self

            def is_dir(self):
                raise OSError("denied")

        assert mod._is_toolkit_repo(Boom()) is False

    def test_failed_git_remote_falls_back_to_dir_name(self, tmp_path):
        failed = SimpleNamespace(returncode=1, stdout="https://example.com/other/wrong.git\n", stderr="")
        with patch.object(mod.subprocess, "run", return_value=failed):
            assert mod._derive_repo_name(tmp_path / "myrepo") == "myrepo"

    def test_remote_name_is_taken_from_git_url(self, tmp_path):
        ok = SimpleNamespace(returncode=0, stdout="git@example.com:team/cool-repo.git\n", stderr="")
        with patch.object(mod.subprocess, "run", return_value=ok):
            assert mod._derive_repo_name(tmp_path) == "cool-repo"
