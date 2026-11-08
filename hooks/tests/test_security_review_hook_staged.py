"""security-review-hook commit gate: staged plumbing and visible fail-open (D-02, D-03).

- The gate scans what the index holds, from whatever directory the commit runs in.
- A scan that did not finish, crashed or timed out still allows the commit when
  nothing blocking was found, but says so in the model's context, not only on stderr.

Fixture code is assembled from fragments so this file holds no scanner pattern.
"""

from __future__ import annotations

import importlib.util
import io
import json
import os
import subprocess
import sys
from contextlib import ExitStack, redirect_stderr, redirect_stdout
from pathlib import Path
from unittest.mock import patch

HOOK = Path(__file__).resolve().parents[1] / "security-review-hook.py"
HIGH_LINE = "os." + "system(cmd)\n"

_spec = importlib.util.spec_from_file_location("security_review_hook_staged", HOOK)
mod = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(mod)


def _env(home: Path) -> dict[str, str]:
    env = {
        k: v
        for k, v in os.environ.items()
        if not k.startswith(("GIT_", "VEXJOY_SECURITY_REVIEW"))
        and k not in ("CLAUDE_PROJECT_DIR", "CLAUDE_HOOKS_DEBUG")
    }
    env.update({"HOME": str(home), "GIT_CONFIG_GLOBAL": os.devnull, "GIT_CONFIG_NOSYSTEM": "1"})
    return env


def _git(repo: Path, *args: str) -> None:
    subprocess.run(["git", *args], cwd=repo, env=_env(repo.parent), capture_output=True, text=True, check=True)


def _repo(root: Path) -> Path:
    repo = root / "repo"
    repo.mkdir()
    _git(repo, "init", "--quiet", "-b", "main")
    return repo


def _commit_event(cwd: Path, command: str = "git commit -m x") -> dict:
    return {"hook_event_name": "PreToolUse", "tool_name": "Bash", "tool_input": {"command": command}, "cwd": str(cwd)}


def _hook(event: dict, home: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(HOOK)],
        input=json.dumps(event),
        capture_output=True,
        text=True,
        cwd="/",
        env=_env(home),
        timeout=90,
        check=False,
    )


def _output(stdout: str) -> dict:
    return json.loads(stdout).get("hookSpecificOutput", {}) if stdout.strip() else {}


def _run_in_process(event: dict, report) -> tuple[int, dict, str]:
    out, err = io.StringIO(), io.StringIO()
    code = 0
    with ExitStack() as stack:
        stack.enter_context(patch.dict(os.environ, {}, clear=False))
        for key in ("VEXJOY_SECURITY_REVIEW_SKIP", "VEXJOY_SECURITY_REVIEW_DISABLE"):
            os.environ.pop(key, None)
        stack.enter_context(patch.object(mod, "read_stdin", return_value=json.dumps(event)))
        stack.enter_context(patch.object(mod, "_run_scanner", return_value=report))
        stack.enter_context(redirect_stdout(out))
        stack.enter_context(redirect_stderr(err))
        try:
            mod.main()
        except SystemExit as exc:
            code = int(exc.code or 0)
    return code, _output(out.getvalue()), err.getvalue()


def _report(findings: list[dict], incomplete: list[str]) -> dict:
    return {
        "findings": findings,
        "summary": {
            "critical": 0,
            "high": len(findings),
            "medium": 0,
            "total": len(findings),
            "files_scanned": 1,
            "files_skipped": 0,
            "incomplete": incomplete,
        },
    }


_HIGH = {"file": "app.py", "line": 2, "severity": "HIGH", "rule": "shell-injection", "match": "os." + "system("}


# --- D-03: the gate scans the index, from any directory in the repo ------------


def test_commit_from_a_subdirectory_is_blocked_on_a_staged_finding(tmp_path):
    repo = _repo(tmp_path)
    (repo / "pkg").mkdir()
    (repo / "pkg" / "app.py").write_text("import os\n" + HIGH_LINE, encoding="utf-8")
    _git(repo, "add", "-A")
    proc = _hook(_commit_event(repo / "pkg"), tmp_path)
    out = _output(proc.stdout)
    assert out.get("permissionDecision") == "deny", proc.stdout + proc.stderr
    assert "pkg/app.py:2" in out["permissionDecisionReason"]


def test_staged_finding_blocks_even_when_the_working_tree_is_clean(tmp_path):
    repo = _repo(tmp_path)
    (repo / "app.py").write_text("import os\n" + HIGH_LINE, encoding="utf-8")
    _git(repo, "add", "app.py")
    (repo / "app.py").write_text("x = 1\n", encoding="utf-8")
    proc = _hook(_commit_event(repo), tmp_path)
    assert _output(proc.stdout).get("permissionDecision") == "deny", proc.stdout + proc.stderr


def test_unstaged_finding_does_not_block(tmp_path):
    repo = _repo(tmp_path)
    (repo / "app.py").write_text("x = 1\n", encoding="utf-8")
    _git(repo, "add", "app.py")
    (repo / "app.py").write_text("import os\n" + HIGH_LINE, encoding="utf-8")
    proc = _hook(_commit_event(repo), tmp_path)
    assert proc.returncode == 0
    assert _output(proc.stdout).get("permissionDecision") is None, proc.stdout


# --- D-02: a scan that did not finish is visible, never a silent pass ----------


def test_long_generated_line_beside_a_finding_still_blocks(tmp_path):
    # Lane D's repro: a long line stalled the old SQL rules past the hook's
    # timeout (this 45 KB one took over 90 s), and the commit went through.
    repo = _repo(tmp_path)
    (repo / "gen.py").write_text(('"' + ("sel" + "ect %s ") * 45 + '" ') * 100 + "\n", encoding="utf-8")
    (repo / "app.py").write_text("import os\n" + HIGH_LINE, encoding="utf-8")
    _git(repo, "add", "-A")
    proc = _hook(_commit_event(repo), tmp_path)
    out = _output(proc.stdout)
    assert out.get("permissionDecision") == "deny", proc.stdout + proc.stderr
    assert "app.py:2" in out["permissionDecisionReason"]


def test_scanner_is_given_a_time_budget_inside_the_subprocess_timeout():
    seen = {}

    def fake_run(args, **kwargs):
        seen["args"], seen["timeout"] = args, kwargs.get("timeout")
        return subprocess.CompletedProcess(args, 0, stdout=json.dumps(_report([], [])), stderr="")

    with patch.object(mod.subprocess, "run", side_effect=fake_run):
        assert mod._run_scanner("/tmp", staged=True) == _report([], [])
    args = seen["args"]
    budget = float(args[args.index("--time-budget") + 1])
    assert "--staged" in args
    assert 0 < budget < seen["timeout"]


def test_scanner_timeout_returns_none():
    with patch.object(mod.subprocess, "run", side_effect=subprocess.TimeoutExpired(["x"], 30)):
        assert mod._run_scanner("/tmp", staged=True) is None


def test_unavailable_scanner_allows_with_a_visible_warning():
    code, out, err = _run_in_process(_commit_event(Path("/tmp")), None)
    assert code == 0
    assert out.get("permissionDecision") is None
    assert "NOT scanned" in out.get("additionalContext", "")
    assert "fail-open" in err


def test_incomplete_scan_without_findings_allows_with_a_visible_warning():
    reason = "big.min.js: 20,000,000 bytes is over the 16,777,216-byte scan limit; not scanned"
    code, out, _ = _run_in_process(_commit_event(Path("/tmp")), _report([], [reason]))
    assert code == 0
    assert out.get("permissionDecision") is None
    assert "did not finish" in out["additionalContext"]
    assert reason in out["additionalContext"]


def test_incomplete_scan_with_a_blocking_finding_still_denies_and_says_so():
    code, out, _ = _run_in_process(_commit_event(Path("/tmp")), _report([_HIGH], ["the time budget ran out"]))
    assert code == 0
    assert out.get("permissionDecision") == "deny"
    assert "did not finish" in out["permissionDecisionReason"]
    assert "the time budget ran out" in out["permissionDecisionReason"]


def test_complete_clean_scan_stays_silent():
    code, out, err = _run_in_process(_commit_event(Path("/tmp")), _report([], []))
    assert code == 0
    assert out == {}
    assert err == ""


def test_many_incomplete_reasons_are_capped():
    reasons = [f"f{i}.txt: cannot read" for i in range(12)]
    _, out, _ = _run_in_process(_commit_event(Path("/tmp")), _report([], reasons))
    context = out["additionalContext"]
    assert "f4.txt" in context and "f5.txt" not in context
    assert "and 7 more" in context
