#!/usr/bin/env python3
"""
Tests for the pretool-private-name-leak-gate hook.

All fixtures use SYNTHETIC names (secret-example-skill, hidden-fixture-notes,
translate). The real ~/private-skills tree is never read: every test patches
mod._PRIVATE_DIR to a tmp dir, so no real private name can reach test output.

Run with: python3 -m pytest hooks/tests/test_pretool_private_name_leak_gate.py -v
"""

import importlib.util
import io
import json
import os
import subprocess
import time
from pathlib import Path
from unittest.mock import patch

import pytest

# ---------------------------------------------------------------------------
# Import the module under test
# ---------------------------------------------------------------------------

HOOK_PATH = Path(__file__).parent.parent / "pretool-private-name-leak-gate.py"

spec = importlib.util.spec_from_file_location("pretool_private_name_leak_gate", HOOK_PATH)
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)

SYNTH = "secret-example-skill"  # synthetic private component name
SYNTH_REDACTED = "s…l"

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def private_dir(tmp_path, monkeypatch):
    """Synthetic ~/private-skills tree; patched into the module."""
    root = tmp_path / "private-tree"
    (root / SYNTH).mkdir(parents=True)
    (root / SYNTH / "SKILL.md").write_text("---\nname: x\n---\n")
    (root / "hidden-fixture-notes.md").write_text("notes\n")
    monkeypatch.setattr(mod, "_PRIVATE_DIR", root)
    # Point the user-index fallback at nothing so only the project INDEX counts.
    monkeypatch.setattr(mod, "_USER_INDEX", tmp_path / "no-user-index.json")
    return root


@pytest.fixture()
def toolkit_repo(tmp_path):
    """Toolkit-shaped git repo (agents/ + skills/) with a public INDEX.json."""
    repo = tmp_path / "toolkit"
    (repo / "agents").mkdir(parents=True)
    (repo / "skills").mkdir()
    (repo / "skills" / "INDEX.json").write_text(json.dumps({"version": "2.0", "skills": {"translate": {}}}))
    _git(repo, "init", "-q")
    return repo


def _git(repo: Path, *args: str) -> None:
    subprocess.run(
        ["git", "-c", "user.email=t@example.com", "-c", "user.name=t", *args],
        cwd=repo,
        check=True,
        capture_output=True,
    )


def _event(command: str, cwd: Path | None = None) -> str:
    event: dict = {"tool_input": {"command": command}}
    if cwd:
        event["cwd"] = str(cwd)
    return json.dumps(event)


def _run_main(stdin_payload: str, env: dict | None = None) -> tuple[int, dict | None, str, str]:
    """Invoke mod.main() in-process.

    Returns (logical_exit_code, parsed_stdout_json, raw_stdout, raw_stderr).
    logical_exit_code is 2 if permissionDecision:deny was emitted, 0 otherwise.
    """
    base_env = dict(os.environ)
    for var in ("PRIVATE_NAME_GATE_BYPASS", "CLAUDE_PROJECT_DIR", "CLAUDE_HOOKS_DEBUG"):
        base_env.pop(var, None)
    if env:
        base_env.update(env)

    stdout_capture = io.StringIO()
    stderr_capture = io.StringIO()
    with (
        patch.dict(os.environ, base_env, clear=True),
        patch.object(mod, "read_stdin", return_value=stdin_payload),
        patch.object(mod, "record_governance_event", lambda *_args, **_kwargs: None),
        patch("sys.stdout", stdout_capture),
        patch("sys.stderr", stderr_capture),
    ):
        try:
            mod.main()
        except SystemExit:
            pass

    out = stdout_capture.getvalue()
    parsed = None
    if out.strip():
        try:
            parsed = json.loads(out.strip())
        except json.JSONDecodeError:
            pass

    code = 0
    if parsed and parsed.get("hookSpecificOutput", {}).get("permissionDecision") == "deny":
        code = 2
    return code, parsed, out, stderr_capture.getvalue()


def _reason(parsed: dict) -> str:
    return parsed["hookSpecificOutput"]["permissionDecisionReason"]


# ---------------------------------------------------------------------------
# Blocks — each covered command shape fires on a synthetic name
# ---------------------------------------------------------------------------


class TestBlocks:
    def test_block_on_staged_diff(self, private_dir, toolkit_repo):
        (toolkit_repo / "f.txt").write_text(f"wires {SYNTH} into the router\n")
        _git(toolkit_repo, "add", "f.txt")
        code, parsed, _, _ = _run_main(_event("git commit -m 'clean message'", toolkit_repo))
        assert code == 2
        assert "staged diff" in _reason(parsed)

    def test_block_on_commit_message_arg(self, private_dir, toolkit_repo):
        code, parsed, _, _ = _run_main(_event(f'git commit -m "wire {SYNTH} in"', toolkit_repo))
        assert code == 2
        assert "command text" in _reason(parsed)

    def test_block_on_commit_message_file(self, private_dir, toolkit_repo, tmp_path):
        msg = tmp_path / "msg.txt"
        msg.write_text(f"feat: enable {SYNTH}\n")
        code, parsed, _, _ = _run_main(_event(f"git commit -F {msg}", toolkit_repo))
        assert code == 2
        assert "commit message file" in _reason(parsed)

    def test_block_on_push_with_leaking_commit_message(self, private_dir, toolkit_repo):
        (toolkit_repo / "f.txt").write_text("clean content\n")
        _git(toolkit_repo, "add", "f.txt")
        _git(toolkit_repo, "commit", "-q", "-m", f"add {SYNTH} support")
        code, parsed, _, _ = _run_main(_event("git push origin feat-x", toolkit_repo))
        assert code == 2
        assert "outgoing commit messages" in _reason(parsed)

    def test_block_on_pr_create_body_arg(self, private_dir, toolkit_repo):
        code, parsed, _, _ = _run_main(_event(f'gh pr create --title t --body "uses {SYNTH}"', toolkit_repo))
        assert code == 2

    def test_block_on_pr_create_body_file(self, private_dir, toolkit_repo, tmp_path):
        body = tmp_path / "body.md"
        body.write_text(f"## Summary\nintegrates {SYNTH}\n")
        code, parsed, _, _ = _run_main(_event(f"gh pr create --title t --body-file {body}", toolkit_repo))
        assert code == 2
        assert "PR body file" in _reason(parsed)
        assert str(body) in _reason(parsed)

    def test_block_on_pr_edit(self, private_dir, toolkit_repo):
        code, _, _, _ = _run_main(_event(f'gh pr edit 5 --body "now with {SYNTH}"', toolkit_repo))
        assert code == 2

    def test_block_on_pr_comment(self, private_dir, toolkit_repo):
        code, _, _, _ = _run_main(_event(f'gh pr comment 5 --body "see {SYNTH}"', toolkit_repo))
        assert code == 2

    def test_block_on_pr_merge_body(self, private_dir, toolkit_repo):
        code, _, _, _ = _run_main(_event(f'gh pr merge 5 --squash --body "folds in {SYNTH}"', toolkit_repo))
        assert code == 2

    def test_block_on_md_stem_name(self, private_dir, toolkit_repo):
        """.md basenames (recursive) are part of the name set, not just dirs."""
        code, _, _, _ = _run_main(_event('git commit -m "port hidden-fixture-notes"', toolkit_repo))
        assert code == 2


# ---------------------------------------------------------------------------
# Redaction — the gate never echoes the matched name
# ---------------------------------------------------------------------------


class TestRedaction:
    def test_block_output_never_contains_raw_name(self, private_dir, toolkit_repo):
        (toolkit_repo / "f.txt").write_text(f"{SYNTH}\n")
        _git(toolkit_repo, "add", "f.txt")
        code, parsed, out, err = _run_main(_event("git commit -m 'clean'", toolkit_repo))
        assert code == 2
        assert SYNTH not in out
        assert SYNTH not in err
        assert SYNTH_REDACTED in _reason(parsed)
        assert SYNTH_REDACTED in err

    def test_redact_shape(self):
        assert mod._redact("secret-example-skill") == "s…l"
        assert mod._redact("ab") == "a…b"
        assert mod._redact("x") == "…"


# ---------------------------------------------------------------------------
# Pass-throughs
# ---------------------------------------------------------------------------


class TestPassThrough:
    def test_public_homonym_never_blocks(self, private_dir, toolkit_repo):
        """A private dir name that is also a tracked public skill passes."""
        (private_dir / "translate").mkdir()
        code, _, _, _ = _run_main(_event('git commit -m "improve translate flow"', toolkit_repo))
        assert code == 0

    def test_absent_private_dir_is_noop(self, toolkit_repo, tmp_path, monkeypatch):
        """Public installs and CI have no ~/private-skills: graceful no-op."""
        monkeypatch.setattr(mod, "_PRIVATE_DIR", tmp_path / "does-not-exist")
        code, _, _, _ = _run_main(_event(f'git commit -m "wire {SYNTH} in"', toolkit_repo))
        assert code == 0

    def test_non_toolkit_repo_not_gated(self, private_dir, tmp_path):
        plain = tmp_path / "plain-repo"
        plain.mkdir()
        _git(plain, "init", "-q")
        code, _, _, _ = _run_main(_event(f'git commit -m "wire {SYNTH} in"', plain))
        assert code == 0

    def test_private_repo_itself_not_gated(self, private_dir):
        """Commits inside ~/private-skills always name private components."""
        code, _, _, _ = _run_main(_event(f'git commit -m "update {SYNTH}"', private_dir))  # nosec: fixture string, not SQL
        assert code == 0

    def test_non_matching_command_ignored(self, private_dir, toolkit_repo):
        code, _, _, _ = _run_main(_event(f"grep -rn {SYNTH} .", toolkit_repo))
        assert code == 0

    def test_clean_commit_allowed(self, private_dir, toolkit_repo):
        (toolkit_repo / "f.txt").write_text("clean content\n")
        _git(toolkit_repo, "add", "f.txt")
        code, _, _, _ = _run_main(_event("git commit -m 'feat: clean change'", toolkit_repo))
        assert code == 0

    def test_substring_of_longer_kebab_name_not_matched(self, private_dir, toolkit_repo):
        """Kebab-aware boundaries: name inside a longer identifier passes."""
        code, _, _, _ = _run_main(_event(f'git commit -m "use my-{SYNTH}-fork instead"', toolkit_repo))
        assert code == 0

    def test_bypass_env(self, private_dir, toolkit_repo):
        code, _, _, _ = _run_main(
            _event(f'git commit -m "wire {SYNTH} in"', toolkit_repo),
            env={"PRIVATE_NAME_GATE_BYPASS": "1"},
        )
        assert code == 0

    def test_malformed_stdin_allowed(self, private_dir):
        code, _, _, _ = _run_main("not json{")
        assert code == 0


# ---------------------------------------------------------------------------
# Performance — repo benchmark budget (scripts/benchmark-hooks.py: 200ms)
# ---------------------------------------------------------------------------


class TestPerformance:
    def test_full_scan_under_budget(self, private_dir, toolkit_repo):
        (toolkit_repo / "f.txt").write_text("clean content\n" * 200)
        _git(toolkit_repo, "add", "f.txt")
        payload = _event("git commit -m 'feat: clean change'", toolkit_repo)
        _run_main(payload)  # warm caches
        start = time.perf_counter()
        code, _, _, _ = _run_main(payload)
        elapsed_ms = (time.perf_counter() - start) * 1000
        assert code == 0
        assert elapsed_ms < 200, f"scan took {elapsed_ms:.1f}ms (budget 200ms)"
