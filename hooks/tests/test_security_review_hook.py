#!/usr/bin/env python3
"""
Tests for the security-review-hook.

Run with: python3 -m pytest hooks/tests/test_security_review_hook.py -v

Covers (ADR acceptance criteria):
- PreToolUse blocks git commit on a HIGH/CRITICAL staged finding (JSON deny).
- PreToolUse allows a clean commit.
- VEXJOY_SECURITY_REVIEW_SKIP=1 overrides the block.
- VEXJOY_SECURITY_REVIEW_DISABLE=1 disables the hook entirely.
- Stop emits a valid asyncRewake payload (exit 2 + rewakeSummary + diff on stderr).
- Fail-open on malformed stdin and on scanner failure.
"""

import importlib.util
import io
import json
import os
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path
from unittest.mock import patch

# ---------------------------------------------------------------------------
# Import the module under test
# ---------------------------------------------------------------------------

HOOK_PATH = Path(__file__).parent.parent / "security-review-hook.py"

spec = importlib.util.spec_from_file_location("security_review_hook", HOOK_PATH)
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _pre_event(command: str, cwd: str | None = None) -> str:
    event = {"hook_event_name": "PreToolUse", "tool_name": "Bash", "tool_input": {"command": command}}
    if cwd:
        event["cwd"] = cwd
    return json.dumps(event)


def _stop_event(cwd: str | None = None, stop_hook_active: bool = False) -> str:
    event = {"hook_event_name": "Stop", "stop_hook_active": stop_hook_active}
    if cwd:
        event["cwd"] = cwd
    return json.dumps(event)


def _post_event(tool_name: str, file_path: str, cwd: str | None = None) -> str:
    event = {
        "hook_event_name": "PostToolUse",
        "tool_name": tool_name,
        "tool_input": {"file_path": file_path},
    }
    if cwd:
        event["cwd"] = cwd
    return json.dumps(event)


def _advisory_context(stdout_str: str) -> str | None:
    """Return the additionalContext string from a PostToolUse output, or None."""
    for line in stdout_str.strip().splitlines():
        try:
            data = json.loads(line)
        except json.JSONDecodeError:
            continue
        return data.get("hookSpecificOutput", {}).get("additionalContext")
    return None


def _clean_env(extra: dict | None = None) -> dict:
    base = {
        k: v
        for k, v in os.environ.items()
        if k
        not in (
            "VEXJOY_SECURITY_REVIEW_SKIP",
            "VEXJOY_SECURITY_REVIEW_DISABLE",
            "VEXJOY_SECURITY_REVIEW_DEDUP_TTL_SECONDS",
        )
    }
    if extra:
        base.update(extra)
    return base


def _run(stdin_payload: str, env: dict | None = None, scanner_report=None, diff=None):
    """Invoke mod.main() in-process.

    Returns (exit_code, stdout_str, stderr_str). exit_code is the SystemExit code.
    scanner_report: if provided, patches _run_scanner to return it.
    diff: if provided, patches _working_tree_diff to return it.
    """
    out, err = io.StringIO(), io.StringIO()
    patches = [
        patch.dict(os.environ, _clean_env(env), clear=True),
        patch.object(mod, "read_stdin", return_value=stdin_payload),
        redirect_stdout(out),
        redirect_stderr(err),
    ]
    if scanner_report is not None:
        patches.append(patch.object(mod, "_run_scanner", return_value=scanner_report))
    if diff is not None:
        patches.append(patch.object(mod, "_working_tree_diff", return_value=diff))

    from contextlib import ExitStack

    code = 0
    with ExitStack() as stack:
        for p in patches:
            stack.enter_context(p)
        try:
            mod.main()
        except SystemExit as e:
            code = int(e.code) if e.code is not None else 0
    return code, out.getvalue(), err.getvalue()


def _is_deny(stdout_str: str) -> bool:
    if not stdout_str.strip():
        return False
    # The deny JSON is the last JSON line printed.
    for line in stdout_str.strip().splitlines():
        try:
            data = json.loads(line)
        except json.JSONDecodeError:
            continue
        hook_out = data.get("hookSpecificOutput", {})
        if hook_out.get("permissionDecision") == "deny":
            return True
    return False


# Sample scanner reports
_HIGH_REPORT = {
    "findings": [{"file": "app.py", "line": 12, "severity": "HIGH", "rule": "shell-injection", "match": "os.system("}],
    "summary": {"critical": 0, "high": 1, "medium": 0, "total": 1, "files_scanned": 1, "files_skipped": 0},
}
_CRITICAL_REPORT = {
    "findings": [
        {"file": "c.py", "line": 3, "severity": "CRITICAL", "rule": "hardcoded-secret", "match": "password=[REDACTED]"}
    ],
    "summary": {"critical": 1, "high": 0, "medium": 0, "total": 1, "files_scanned": 1, "files_skipped": 0},
}
_CLEAN_REPORT = {
    "findings": [],
    "summary": {"critical": 0, "high": 0, "medium": 0, "total": 0, "files_scanned": 2, "files_skipped": 0},
}
_MEDIUM_ONLY_REPORT = {
    "findings": [{"file": "m.py", "line": 1, "severity": "MEDIUM", "rule": "security-todo", "match": "TODO security"}],
    "summary": {"critical": 0, "high": 0, "medium": 1, "total": 1, "files_scanned": 1, "files_skipped": 0},
}


# ---------------------------------------------------------------------------
# PreToolUse — blocking
# ---------------------------------------------------------------------------


class TestPreToolUseBlocking:
    def test_high_finding_blocks_commit(self):
        code, out, _ = _run(_pre_event("git commit -m 'x'"), scanner_report=_HIGH_REPORT)
        assert code == 0
        assert _is_deny(out)

    def test_critical_finding_blocks_commit(self):
        code, out, _ = _run(_pre_event("git commit -m 'x'"), scanner_report=_CRITICAL_REPORT)
        assert code == 0
        assert _is_deny(out)

    def test_deny_reason_mentions_findings(self):
        code, out, _ = _run(_pre_event("git commit -m 'x'"), scanner_report=_HIGH_REPORT)
        data = json.loads([ln for ln in out.strip().splitlines() if ln.startswith("{")][-1])
        reason = data["hookSpecificOutput"]["permissionDecisionReason"]
        assert "app.py:12" in reason
        assert "VEXJOY_SECURITY_REVIEW_SKIP" in reason


class TestPreToolUseAllow:
    def test_clean_commit_allowed(self):
        code, out, _ = _run(_pre_event("git commit -m 'x'"), scanner_report=_CLEAN_REPORT)
        assert code == 0
        assert not _is_deny(out)

    def test_medium_only_allowed(self):
        """MEDIUM findings are advisory — they do not block a commit."""
        code, out, _ = _run(_pre_event("git commit -m 'x'"), scanner_report=_MEDIUM_ONLY_REPORT)
        assert code == 0
        assert not _is_deny(out)

    def test_non_commit_bash_ignored(self):
        """A Bash command that is not a git commit passes through without scanning."""
        code, out, _ = _run(_pre_event("git status"), scanner_report=_HIGH_REPORT)
        assert code == 0
        assert not _is_deny(out)

    def test_git_commit_substring_in_path_does_not_match(self):
        """`git status` style commands without a commit verb are ignored."""
        code, out, _ = _run(_pre_event("ls git-commit-helper.sh"), scanner_report=_HIGH_REPORT)
        assert code == 0
        assert not _is_deny(out)


# ---------------------------------------------------------------------------
# Bypass / kill switches
# ---------------------------------------------------------------------------


class TestBypass:
    def test_skip_env_allows_commit_despite_findings(self):
        code, out, _ = _run(
            _pre_event("git commit -m 'x'"),
            env={"VEXJOY_SECURITY_REVIEW_SKIP": "1"},
            scanner_report=_HIGH_REPORT,
        )
        assert code == 0
        assert not _is_deny(out)

    def test_skip_value_zero_does_not_bypass(self):
        code, out, _ = _run(
            _pre_event("git commit -m 'x'"),
            env={"VEXJOY_SECURITY_REVIEW_SKIP": "0"},
            scanner_report=_HIGH_REPORT,
        )
        assert _is_deny(out)

    def test_disable_env_disables_pre_tool_use(self):
        code, out, _ = _run(
            _pre_event("git commit -m 'x'"),
            env={"VEXJOY_SECURITY_REVIEW_DISABLE": "1"},
            scanner_report=_HIGH_REPORT,
        )
        assert code == 0
        assert not _is_deny(out)

    def test_disable_env_disables_stop(self):
        code, out, err = _run(
            _stop_event(cwd="/repo"),
            env={"VEXJOY_SECURITY_REVIEW_DISABLE": "1"},
            diff="diff --git a/x b/x\n+secret",
        )
        assert code == 0
        assert "rewakeSummary" not in out


# ---------------------------------------------------------------------------
# Stop — asyncRewake
# ---------------------------------------------------------------------------


class TestStopAsyncRewake:
    def test_stop_emits_rewake_on_diff(self):
        code, out, err = _run(_stop_event(cwd="/repo"), diff="diff --git a/x b/x\n+os.system(cmd)\n")
        # exit 2 is the asyncRewake signal
        assert code == 2
        # stdout carries a valid JSON line with rewakeSummary
        data = json.loads(out.strip().splitlines()[0])
        assert "rewakeSummary" in data
        # stderr carries the diff + instruction (the rewake context)
        assert "security-review" in err
        assert "working-tree diff" in err
        assert "os.system(cmd)" in err

    def test_stop_instruction_states_no_sdk_no_api_key(self):
        code, out, err = _run(_stop_event(cwd="/repo"), diff="diff --git a/x b/x\n+x\n")
        assert "no API key" in err
        assert "no SDK" in err

    def test_stop_no_diff_no_rewake(self):
        code, out, err = _run(_stop_event(cwd="/repo"), diff="")
        assert code == 0
        assert "rewakeSummary" not in out

    def test_stop_mode_only_diff_no_rewake(self):
        """A diff with only mode changes (no +/- content lines) must not trigger a rewake."""
        mode_only = "diff --git a/foo.py b/foo.py\nold mode 100644\nnew mode 100755\n"
        code, out, err = _run(_stop_event(cwd="/repo"), diff=mode_only)
        assert code == 0
        assert "rewakeSummary" not in out

    def test_stop_dedup_short_circuits_identical_diff(self, tmp_path):
        """A byte-identical diff re-fired must short-circuit (exit 0). Permanent by default."""
        state_file = tmp_path / "last-diff-hash.json"
        diff = "diff --git a/x b/x\n+payload\n"
        with patch.object(mod, "_STATE_DIR", tmp_path), patch.object(mod, "_STATE_FILE", state_file):
            code1, _, _ = _run(_stop_event(cwd="/repo"), diff=diff)
            assert code1 == 2
            assert state_file.exists()
            code2, out2, err2 = _run(_stop_event(cwd="/repo"), diff=diff)
            assert code2 == 0
            assert "rewakeSummary" not in out2
            assert "diff unchanged" in err2

    def test_stop_dedup_does_not_block_changed_diff(self, tmp_path):
        """A different diff after a recorded one must still trigger a rewake."""
        state_file = tmp_path / "last-diff-hash.json"
        with patch.object(mod, "_STATE_DIR", tmp_path), patch.object(mod, "_STATE_FILE", state_file):
            code1, _, _ = _run(_stop_event(cwd="/repo"), diff="diff --git a/x b/x\n+a\n")
            assert code1 == 2
            code2, out2, _ = _run(_stop_event(cwd="/repo"), diff="diff --git a/x b/x\n+b\n")
            assert code2 == 2
            assert "rewakeSummary" in out2

    def test_no_ttl_means_forever(self, tmp_path):
        """Default behavior: no TTL. An ancient ts (e.g. ts=0) still suppresses if hash matches."""
        state_file = tmp_path / "last-diff-hash.json"
        diff = "diff --git a/x b/x\n+payload\n"
        with patch.object(mod, "_STATE_DIR", tmp_path), patch.object(mod, "_STATE_FILE", state_file):
            state_file.write_text(
                json.dumps(
                    {
                        "hash": mod._diff_signature("/repo", diff),
                        "ts": 0,
                        "ts_iso": "1970-01-01T00:00:00+00:00",
                        "cwd": "/repo",
                    }
                )
            )
            code, out, err = _run(_stop_event(cwd="/repo"), diff=diff)
            assert code == 0
            assert "rewakeSummary" not in out
            assert "diff unchanged" in err

    def test_explicit_ttl_env_still_works(self, tmp_path):
        """Setting VEXJOY_SECURITY_REVIEW_DEDUP_TTL_SECONDS to a positive int re-enables TTL expiry."""
        state_file = tmp_path / "last-diff-hash.json"
        diff = "diff --git a/x b/x\n+payload\n"
        with patch.object(mod, "_STATE_DIR", tmp_path), patch.object(mod, "_STATE_FILE", state_file):
            # Pre-seed state with a record older than the explicit TTL.
            stale_ts = __import__("time").time() - 10_000
            state_file.write_text(
                json.dumps(
                    {
                        "hash": mod._diff_signature("/repo", diff),
                        "ts": stale_ts,
                        "ts_iso": "2020-01-01T00:00:00+00:00",
                        "cwd": "/repo",
                    }
                )
            )
            env = {"VEXJOY_SECURITY_REVIEW_DEDUP_TTL_SECONDS": "300"}
            code, out, _ = _run(_stop_event(cwd="/repo"), env=env, diff=diff)
            assert code == 2
            assert "rewakeSummary" in out

    def test_stop_dedup_distinguishes_by_cwd(self, tmp_path):
        """Same diff under different cwds must not collide — each cwd dedups independently."""
        state_file = tmp_path / "last-diff-hash.json"
        diff = "diff --git a/x b/x\n+payload\n"
        with patch.object(mod, "_STATE_DIR", tmp_path), patch.object(mod, "_STATE_FILE", state_file):
            code1, _, _ = _run(_stop_event(cwd="/repo-a"), diff=diff)
            code2, out2, _ = _run(_stop_event(cwd="/repo-b"), diff=diff)
            assert code1 == 2
            assert code2 == 2
            assert "rewakeSummary" in out2

    def test_stop_hook_active_skips(self):
        """The asyncRewake recursion guard prevents re-firing while a rewake is in flight."""
        code, out, err = _run(
            _stop_event(cwd="/repo", stop_hook_active=True),
            diff="diff --git a/x b/x\n+x\n",
        )
        assert code == 0
        assert "rewakeSummary" not in out


# ---------------------------------------------------------------------------
# PostToolUse — advisory edit-time scan (matches Anthropic edit-time firing)
# ---------------------------------------------------------------------------


class TestPostToolUseAdvisory:
    def test_vulnerable_edit_injects_advisory_context(self, tmp_path):
        f = tmp_path / "app.py"
        f.write_text("import os\nos.system(cmd)\n")
        code, out, _ = _run(_post_event("Write", str(f), cwd=str(tmp_path)))
        assert code == 0
        ctx = _advisory_context(out)
        assert ctx is not None
        assert "shell-injection" in ctx
        assert "app.py:2" in ctx

    def test_advisory_never_emits_permission_decision(self, tmp_path):
        """PostToolUse runs after the edit — it must never block."""
        f = tmp_path / "app.py"
        f.write_text("os.system(cmd)\n")
        code, out, _ = _run(_post_event("Edit", str(f), cwd=str(tmp_path)))
        assert code == 0
        assert not _is_deny(out)

    def test_clean_edit_emits_no_advisory(self, tmp_path):
        f = tmp_path / "ok.py"
        f.write_text("x = 1 + 1\n")
        code, out, _ = _run(_post_event("Edit", str(f), cwd=str(tmp_path)))
        assert code == 0
        assert _advisory_context(out) is None

    def test_non_source_file_skipped(self, tmp_path):
        f = tmp_path / "notes.md"
        f.write_text("Call eval(x) to run.\n")
        code, out, _ = _run(_post_event("Write", str(f), cwd=str(tmp_path)))
        assert code == 0
        assert _advisory_context(out) is None

    def test_non_edit_tool_skipped(self, tmp_path):
        f = tmp_path / "app.py"
        f.write_text("os.system(cmd)\n")
        code, out, _ = _run(_post_event("Bash", str(f), cwd=str(tmp_path)))
        assert code == 0
        assert _advisory_context(out) is None

    def test_disable_env_disables_post_tool_use(self, tmp_path):
        f = tmp_path / "app.py"
        f.write_text("os.system(cmd)\n")
        code, out, _ = _run(
            _post_event("Write", str(f), cwd=str(tmp_path)),
            env={"VEXJOY_SECURITY_REVIEW_DISABLE": "1"},
        )
        assert code == 0
        assert _advisory_context(out) is None

    def test_missing_file_fails_open(self, tmp_path):
        code, out, _ = _run(_post_event("Write", str(tmp_path / "gone.py"), cwd=str(tmp_path)))
        assert code == 0
        assert _advisory_context(out) is None


# ---------------------------------------------------------------------------
# Fail-open
# ---------------------------------------------------------------------------


class TestFailOpen:
    def test_malformed_stdin_exits_0(self):
        code, out, _ = _run("not valid json {{{")
        assert code == 0
        assert not _is_deny(out)

    def test_empty_stdin_exits_0(self):
        code, out, _ = _run("")
        assert code == 0
        assert not _is_deny(out)

    def test_non_dict_json_exits_0(self):
        code, out, _ = _run("[1, 2, 3]")
        assert code == 0
        assert not _is_deny(out)

    def test_scanner_failure_allows_commit(self):
        """When the scanner is unavailable (returns None), the commit is allowed."""
        code, out, err = _run(_pre_event("git commit -m 'x'"), scanner_report=None)
        # scanner_report=None means _run_scanner is NOT patched, so the real
        # scanner runs against the real (clean) index — assert no deny either way.
        assert code == 0

    def test_scanner_returns_none_fail_open(self):
        """Explicitly patch _run_scanner to None to exercise the fail-open path."""
        with patch.object(mod, "_run_scanner", return_value=None):
            code, out, err = _run(_pre_event("git commit -m 'x'"))
        assert code == 0
        assert not _is_deny(out)
        assert "fail-open" in err

    def test_unknown_event_exits_0(self):
        code, out, _ = _run(json.dumps({"hook_event_name": "PostToolUse", "tool_name": "Bash"}))
        assert code == 0
        assert not _is_deny(out)


# ---------------------------------------------------------------------------
# CWD extraction
# ---------------------------------------------------------------------------


class TestCwdExtraction:
    def test_cd_prefix_extracted(self):
        assert mod._extract_effective_cwd("cd /repo && git commit -m x", None) == "/repo"

    def test_git_C_flag_extracted(self):
        assert mod._extract_effective_cwd("git -C /work commit -m x", None) == "/work"

    def test_default_cwd_used(self):
        assert mod._extract_effective_cwd("git commit -m x", "/fallback") == "/fallback"
