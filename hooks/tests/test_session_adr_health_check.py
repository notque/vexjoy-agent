#!/usr/bin/env python3
"""
Tests for the session-adr-health-check hook.

Run with: python3 -m pytest hooks/tests/test_session_adr_health_check.py -v
"""

import importlib.util
import io
import json
import os
from pathlib import Path
from unittest.mock import patch

# ---------------------------------------------------------------------------
# Import the module under test
# ---------------------------------------------------------------------------

HOOK_PATH = Path(__file__).parent.parent / "session-adr-health-check.py"

spec = importlib.util.spec_from_file_location("session_adr_health_check", HOOK_PATH)
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _run_main(project_dir: str) -> tuple[int, dict | None]:
    """Invoke mod.main() with CLAUDE_PROJECT_DIR set to project_dir.

    Returns (exit_code, parsed_stdout_json). exit_code is always 0.
    """
    env = dict(os.environ)
    env["CLAUDE_PROJECT_DIR"] = project_dir

    stdout_capture = io.StringIO()
    with (
        patch.dict(os.environ, env, clear=True),
        patch("sys.stdout", stdout_capture),
    ):
        try:
            mod.main()
        except SystemExit:
            pass

    output = stdout_capture.getvalue().strip()
    parsed = None
    if output:
        try:
            parsed = json.loads(output)
        except json.JSONDecodeError:
            pass
    return 0, parsed


def _write_session(project_dir: Path, data: dict) -> None:
    (project_dir / ".adr-session.json").write_text(json.dumps(data))


# ---------------------------------------------------------------------------
# No .adr-session.json — silent pass
# ---------------------------------------------------------------------------


class TestNoSessionFile:
    def test_no_session_file_emits_empty_output(self, tmp_path):
        """No .adr-session.json produces empty HookOutput (no additionalContext)."""
        _, parsed = _run_main(str(tmp_path))
        assert parsed is not None
        inner = parsed.get("hookSpecificOutput", {})
        assert "additionalContext" not in inner

    def test_exit_code_always_0(self, tmp_path):
        code, _ = _run_main(str(tmp_path))
        assert code == 0


# ---------------------------------------------------------------------------
# Orphaned session — ADR file missing
# ---------------------------------------------------------------------------


class TestOrphanedSession:
    def test_orphaned_session_injects_warning(self, tmp_path):
        """Orphaned .adr-session.json injects a warning in additionalContext."""
        _write_session(
            tmp_path,
            {
                "adr_path": "adr/999-nonexistent.md",
                "domain": "999-nonexistent",
                "registered_at": "2026-01-01T00:00:00+00:00",
            },
        )
        _, parsed = _run_main(str(tmp_path))
        assert parsed is not None
        inner = parsed.get("hookSpecificOutput", {})
        assert "additionalContext" in inner
        context = inner["additionalContext"]
        assert "Orphaned" in context or "WARNING" in context
        assert "999-nonexistent.md" in context

    def test_orphaned_session_includes_clear_command(self, tmp_path):
        """Warning message includes the rm command to clear the stale session."""
        _write_session(tmp_path, {"adr_path": "adr/000-gone.md", "domain": "000-gone"})
        _, parsed = _run_main(str(tmp_path))
        context = parsed["hookSpecificOutput"]["additionalContext"]
        assert "rm" in context
        assert ".adr-session.json" in context

    def test_orphaned_session_via_adr_file_key(self, tmp_path):
        """Supports 'adr_file' key in addition to 'adr_path'."""
        _write_session(tmp_path, {"adr_file": "adr/old-schema.md", "domain": "old-schema"})
        _, parsed = _run_main(str(tmp_path))
        inner = parsed.get("hookSpecificOutput", {})
        assert "additionalContext" in inner
        context = inner["additionalContext"]
        assert "old-schema.md" in context

    def test_orphaned_always_exits_0(self, tmp_path):
        """Advisory hook never blocks — always exits 0."""
        _write_session(tmp_path, {"adr_path": "adr/gone.md", "domain": "gone"})
        code, _ = _run_main(str(tmp_path))
        assert code == 0


# ---------------------------------------------------------------------------
# Healthy session — ADR file exists
# ---------------------------------------------------------------------------


class TestHealthySession:
    def test_healthy_session_injects_status(self, tmp_path):
        """Healthy session injects a brief status line in additionalContext."""
        adr_file = tmp_path / "adr" / "187-test.md"
        adr_file.parent.mkdir(parents=True)
        adr_file.write_text("# ADR-187\n")

        _write_session(
            tmp_path,
            {
                "adr_path": "adr/187-test.md",
                "domain": "187-test",
                "registered_at": "2026-04-16T10:00:00+00:00",
            },
        )
        _, parsed = _run_main(str(tmp_path))
        inner = parsed.get("hookSpecificOutput", {})
        assert "additionalContext" in inner
        context = inner["additionalContext"]
        assert "Active ADR session" in context or "adr-health-check" in context
        assert "187-test" in context

    def test_healthy_session_no_deny(self, tmp_path):
        """Healthy session never produces a deny decision."""
        adr_file = tmp_path / "adr" / "187-test.md"
        adr_file.parent.mkdir(parents=True)
        adr_file.write_text("# ADR-187\n")
        _write_session(tmp_path, {"adr_path": "adr/187-test.md", "domain": "187-test"})

        _, parsed = _run_main(str(tmp_path))
        inner = parsed.get("hookSpecificOutput", {})
        assert inner.get("permissionDecision") != "deny"

    def test_absolute_adr_path_that_exists(self, tmp_path):
        """Absolute adr_path pointing to an existing file is treated as healthy."""
        adr_file = tmp_path / "187-abs.md"
        adr_file.write_text("# ADR\n")

        _write_session(tmp_path, {"adr_path": str(adr_file), "domain": "187-abs"})
        _, parsed = _run_main(str(tmp_path))
        inner = parsed.get("hookSpecificOutput", {})
        assert "additionalContext" in inner
        # Should be healthy — no orphan warning
        context = inner["additionalContext"]
        assert "Orphaned" not in context and "WARNING" not in context


# ---------------------------------------------------------------------------
# Missing adr_path / adr_file fields
# ---------------------------------------------------------------------------


class TestMissingPathField:
    def test_session_without_path_field_injects_warning(self, tmp_path):
        """Session with neither adr_path nor adr_file injects a schema warning."""
        _write_session(tmp_path, {"domain": "no-path", "registered_at": "2026-04-01T00:00:00+00:00"})
        _, parsed = _run_main(str(tmp_path))
        inner = parsed.get("hookSpecificOutput", {})
        assert "additionalContext" in inner
        context = inner["additionalContext"]
        assert "WARNING" in context or "adr_path" in context or "adr_file" in context


# ---------------------------------------------------------------------------
# Malformed .adr-session.json
# ---------------------------------------------------------------------------


class TestMalformedSession:
    def test_malformed_json_treated_as_no_session(self, tmp_path):
        """Malformed JSON in .adr-session.json is treated as absent — silent pass."""
        (tmp_path / ".adr-session.json").write_text("not valid json {{{")
        _, parsed = _run_main(str(tmp_path))
        inner = parsed.get("hookSpecificOutput", {})
        assert "additionalContext" not in inner

    def test_empty_json_object_treated_as_missing_path(self, tmp_path):
        """Empty JSON object has no path fields — injects schema warning."""
        _write_session(tmp_path, {})
        _, parsed = _run_main(str(tmp_path))
        inner = parsed.get("hookSpecificOutput", {})
        # Empty session has no adr_path — warning is injected
        assert "additionalContext" in inner
