#!/usr/bin/env python3
"""
Tests for hooks/posttool-security-scan.py — advisory PostToolUse security scan.

Run with: python3 -m pytest hooks/tests/test_posttool_security_scan.py -v

This hook was refactored to delegate ALL detection to the canonical engine
(scripts/security-review-scan.py). These tests prove the consolidation:

- Real insecure code (shell=True, yaml.load, hardcoded secret, SQLi) is still
  flagged — no true positive lost when the inline _build_patterns fork retired.
- The engine's test-skip guard now applies: a test-fixture file (test_*.py)
  with eval()/exec() is SKIPPED (the inline scanner false-positived on these).
- Doc-aware filtering applies: prose in .md is not flagged.
- Non-source files are skipped; missing files / malformed stdin fail open.
- ALWAYS exits 0 (non-blocking — advisory PostToolUse hook).
"""

import importlib.util
import io
import json
import os
from contextlib import ExitStack, redirect_stderr, redirect_stdout
from pathlib import Path
from unittest.mock import patch

HOOK_PATH = Path(__file__).parent.parent / "posttool-security-scan.py"

spec = importlib.util.spec_from_file_location("posttool_security_scan", HOOK_PATH)
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)


def _event(file_path: str, cwd: str | None = None, tool_name: str = "Write") -> str:
    event = {
        "hook_event_name": "PostToolUse",
        "tool_name": tool_name,
        "tool_input": {"file_path": file_path},
    }
    if cwd:
        event["cwd"] = cwd
    return json.dumps(event)


def _run(stdin_payload: str, env: dict | None = None) -> tuple[int, str, str]:
    """Invoke mod.main() in-process. Returns (exit_code, stdout, stderr)."""
    out, err = io.StringIO(), io.StringIO()
    base_env = dict(os.environ)
    if env:
        base_env.update(env)
    code = 0
    with ExitStack() as stack:
        stack.enter_context(patch.dict(os.environ, base_env, clear=True))
        stack.enter_context(patch.object(mod, "read_stdin", return_value=stdin_payload))
        stack.enter_context(redirect_stdout(out))
        stack.enter_context(redirect_stderr(err))
        try:
            mod.main()
        except SystemExit as e:
            code = int(e.code) if e.code is not None else 0
    return code, out.getvalue(), err.getvalue()


# ---------------------------------------------------------------------------
# True positives preserved (parity with the retired inline scanner)
# ---------------------------------------------------------------------------


class TestTruePositivesPreserved:
    def test_shell_true_flagged(self, tmp_path):
        f = tmp_path / "app.py"
        f.write_text("import subprocess\nsubprocess.run(cmd, shell=True)\n")
        code, out, _ = _run(_event(str(f), cwd=str(tmp_path)))
        assert code == 0
        assert "[SECURITY-HINT]" in out
        assert "shell-injection" in out

    def test_yaml_load_flagged(self, tmp_path):
        f = tmp_path / "loader.py"
        f.write_text("import yaml\ndata = yaml.load(stream)\n")
        code, out, _ = _run(_event(str(f), cwd=str(tmp_path)))
        assert code == 0
        assert "unsafe-yaml" in out

    def test_hardcoded_secret_flagged(self, tmp_path):
        f = tmp_path / "conf.py"
        f.write_text('password = "hunter2hunter2"\n')
        code, out, _ = _run(_event(str(f), cwd=str(tmp_path)))
        assert code == 0
        assert "hardcoded-secret" in out

    def test_sql_injection_flagged(self, tmp_path):
        f = tmp_path / "db.py"
        f.write_text('q = f"SELECT * FROM t WHERE id={uid}"\n')
        code, out, _ = _run(_event(str(f), cwd=str(tmp_path)))
        assert code == 0
        assert "sql-injection" in out

    def test_os_system_flagged(self, tmp_path):
        f = tmp_path / "run.py"
        f.write_text('os.system("rm -rf /tmp/x")\n')
        code, out, _ = _run(_event(str(f), cwd=str(tmp_path)))
        assert code == 0
        assert "shell-injection" in out


# ---------------------------------------------------------------------------
# NEW behavior inherited from the canonical engine: test-skip + doc-aware
# ---------------------------------------------------------------------------


class TestTestFixtureSkip:
    def test_test_fixture_eval_skipped(self, tmp_path):
        """A test-fixture file (test_*.py) with eval()/exec() is SKIPPED — the
        engine's skip_test guard suppresses these in test files. The retired
        inline scanner would have false-positived here."""
        f = tmp_path / "test_thing.py"
        f.write_text("def test_x():\n    eval(payload)\n    exec(code)\n")
        code, out, _ = _run(_event(str(f), cwd=str(tmp_path)))
        assert code == 0
        assert "[SECURITY-HINT]" not in out

    def test_test_fixture_public_ip_skipped(self, tmp_path):
        """hardcoded-ip has skip_test=True; a public IP literal in a test file
        is not flagged."""
        f = tmp_path / "conn_test.py"
        f.write_text("HOST = 8.8.8.8\n")
        code, out, _ = _run(_event(str(f), cwd=str(tmp_path)))
        assert code == 0
        assert "hardcoded-ip" not in out

    def test_nontest_eval_still_flagged(self, tmp_path):
        """Control: the SAME eval() in a non-test file IS flagged — proving the
        skip is scoped to test files, not a blanket disable."""
        f = tmp_path / "prod.py"
        f.write_text("eval(payload)\n")
        code, out, _ = _run(_event(str(f), cwd=str(tmp_path)))
        assert code == 0
        assert "dangerous-eval" in out


class TestDocAware:
    def test_markdown_prose_not_flagged(self, tmp_path):
        """Prose in markdown mentioning eval()/os.system() is not code — skipped."""
        f = tmp_path / "notes.md"
        f.write_text("Use eval(x) carefully and avoid os.system(cmd).\n")
        code, out, _ = _run(_event(str(f), cwd=str(tmp_path)))
        assert code == 0
        assert "[SECURITY-HINT]" not in out

    def test_aws_key_in_markdown_still_flagged(self, tmp_path):
        """Anchored secret signatures (AKIA) still fire in docs (scan_docs)."""
        f = tmp_path / "README.md"
        f.write_text("key: AKIAIOSFODNN7EXAMPLE\n")
        code, out, _ = _run(_event(str(f), cwd=str(tmp_path)))
        assert code == 0
        assert "hardcoded-secret" in out


# ---------------------------------------------------------------------------
# Skips and fail-open paths — always exit 0, never block
# ---------------------------------------------------------------------------


class TestSkipsAndFailOpen:
    def test_clean_file_no_hint(self, tmp_path):
        f = tmp_path / "ok.py"
        f.write_text("x = 1 + 1\n")
        code, out, _ = _run(_event(str(f), cwd=str(tmp_path)))
        assert code == 0
        assert out.strip() == ""

    def test_unsupported_extension_skipped(self, tmp_path):
        f = tmp_path / "image.png"
        f.write_text("not really an image\n")
        code, out, _ = _run(_event(str(f), cwd=str(tmp_path)))
        assert code == 0
        assert out.strip() == ""

    def test_missing_file_fails_open(self, tmp_path):
        code, out, _ = _run(_event(str(tmp_path / "gone.py"), cwd=str(tmp_path)))
        assert code == 0
        assert out.strip() == ""

    def test_no_file_path_exits_0(self):
        code, out, _ = _run(json.dumps({"hook_event_name": "PostToolUse", "tool_input": {}}))
        assert code == 0
        assert out.strip() == ""

    def test_malformed_stdin_exits_0(self):
        code, out, _ = _run("not valid json {{{")
        assert code == 0

    def test_empty_stdin_exits_0(self):
        code, out, _ = _run("")
        assert code == 0

    def test_findings_capped_at_five(self, tmp_path):
        f = tmp_path / "many.py"
        # 8 distinct os.system calls -> 8 findings, output collapses after 5.
        f.write_text("\n".join(f'os.system("cmd{i}")' for i in range(8)) + "\n")
        code, out, _ = _run(_event(str(f), cwd=str(tmp_path)))
        assert code == 0
        assert out.count("[SECURITY-HINT]") == 5
        assert "and 3 more" in out

    def test_path_field_alias_supported(self, tmp_path):
        """Some events use tool_input.path instead of file_path."""
        f = tmp_path / "app.py"
        f.write_text("os.system(cmd)\n")
        event = json.dumps(
            {
                "hook_event_name": "PostToolUse",
                "tool_name": "Edit",
                "tool_input": {"path": str(f)},
                "cwd": str(tmp_path),
            }
        )
        code, out, _ = _run(event)
        assert code == 0
        assert "shell-injection" in out
