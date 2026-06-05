#!/usr/bin/env python3
"""
Tests for scripts/skill-eval-ablation.py (local before/after eval runner).

ADR: skill-eval-pr-ablation, Decision section 3 + Validation Requirements 3-5.

Covers the parts that do NOT need the `claude` CLI:
- delta line formatting (base% -> head% (+delta));
- --record degradation when the PR-A envelope is absent: WARN string + one
  JSON line appended to the log file, exit 0, no DB row dropped;
- --record promotion when the envelope is present: named columns written,
  readable back by learning-db query (git_commit_sha == head);
- the CI workflow YAML guarantees the coverage job can never become a failing
  required check (continue-on-error: true, no required: true);
- --install-hook writes an idempotent, advisory .git/hooks/pre-push.

Run with: python3 -m pytest scripts/tests/test_skill_eval_ablation.py -v
"""

import importlib.util
import json
import subprocess
import sys
from pathlib import Path

import pytest

SCRIPT = Path(__file__).resolve().parent.parent / "skill-eval-ablation.py"
REPO_ROOT = Path(__file__).resolve().parents[2]
LEARNING_DB_CLI = REPO_ROOT / "scripts" / "learning-db.py"
WORKFLOW = REPO_ROOT / ".github" / "workflows" / "test.yml"
LIB_DIR = REPO_ROOT / "hooks" / "lib"


def _load_module():
    spec = importlib.util.spec_from_file_location("skill_eval_ablation", SCRIPT)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


# ---------------------------------------------------------------------------
# Delta formatting.
# ---------------------------------------------------------------------------


def test_format_delta_line():
    mod = _load_module()
    line = mod.format_delta(
        skill="planning", base_rate=0.58, head_rate=0.67, eval_dir="evals/new-skills-ab-test", runs=3
    )
    assert "planning" in line
    assert "58%" in line
    assert "67%" in line
    assert "+9" in line
    assert "eval=evals/new-skills-ab-test" in line
    assert "runs=3" in line


def test_format_delta_negative():
    mod = _load_module()
    line = mod.format_delta(skill="x", base_rate=0.70, head_rate=0.60, eval_dir="evals/x", runs=2)
    assert "70%" in line
    assert "60%" in line
    assert "-10" in line


def test_format_uncovered_line():
    mod = _load_module()
    line = mod.format_uncovered(["a", "b"])
    assert "no eval coverage for changed skill(s)" in line
    assert "a" in line
    assert "b" in line


# ---------------------------------------------------------------------------
# --record degradation (no PR-A envelope) -- Validation Requirement 3.
# ---------------------------------------------------------------------------


def test_record_no_envelope_degrades_to_log(temp_db_no_envelope, tmp_path, capsys, monkeypatch):
    mod = _load_module()
    log = tmp_path / "eval-ablations.log"
    monkeypatch.setattr(mod, "ABLATION_LOG", log, raising=False)

    rc = mod.record_run(
        eval_dir="evals/new-skills-ab-test",
        skill="planning",
        arm="head",
        pass_rate=0.67,
        runs=3,
        base_sha="b" * 40,
        head_sha="h" * 40,
        model_id="claude-x",
        skill_version="1.1.0",
    )
    out = capsys.readouterr().out
    assert rc == 0
    assert "WARN: telemetry envelope not present (PR-A); wrote to ~/.claude/eval-ablations.log" in out

    # One JSON line appended, with the envelope schema + a UTC timestamp.
    lines = [ln for ln in log.read_text(encoding="utf-8").splitlines() if ln.strip()]
    assert len(lines) == 1
    rec = json.loads(lines[0])
    assert rec["eval_dir"] == "evals/new-skills-ab-test"
    assert rec["skill"] == "planning"
    assert rec["arm"] == "head"
    assert rec["pass_rate"] == 0.67
    assert rec["git_commit_sha"] == "h" * 40
    assert rec["model_id"] == "claude-x"
    assert rec["skill_version"] == "1.1.0"
    assert "timestamp" in rec


def test_record_no_envelope_still_writes_db_row(temp_db_no_envelope, tmp_path, monkeypatch):
    """Degraded record is NOT dropped: it lands in the DB via the value column."""
    mod = _load_module()
    monkeypatch.setattr(mod, "ABLATION_LOG", tmp_path / "log.jsonl", raising=False)
    mod.record_run(
        eval_dir="evals/x",
        skill="quick",
        arm="base",
        pass_rate=0.5,
        runs=2,
        base_sha="b" * 40,
        head_sha="h" * 40,
        model_id="m",
        skill_version="1.0.0",
    )
    sys.path.insert(0, str(LIB_DIR))
    import learning_db_v2 as ldb

    monkeypatch.setattr(ldb, "_initialized", False, raising=False)
    rows = ldb.query_learnings(topic="eval:evals/x", exclude_test_sources=False)
    assert len(rows) == 1
    # Envelope packed into value (no named columns pre-PR-A).
    assert "git_commit_sha=" + "h" * 40 in rows[0]["value"]


# ---------------------------------------------------------------------------
# --record promotion (PR-A envelope present) -- Validation Requirement 5.
# ---------------------------------------------------------------------------


def test_record_with_envelope_writes_named_columns(temp_db_with_envelope, tmp_path, monkeypatch):
    mod = _load_module()
    monkeypatch.setattr(mod, "ABLATION_LOG", tmp_path / "log.jsonl", raising=False)
    head = "a" * 40
    rc = mod.record_run(
        eval_dir="evals/new-skills-ab-test",
        skill="planning",
        arm="head",
        pass_rate=0.67,
        runs=3,
        base_sha="b" * 40,
        head_sha=head,
        model_id="claude-x",
        skill_version="1.1.0",
    )
    assert rc == 0

    # Read it back via the learning-db CLI query (Validation Requirement 5).
    res = subprocess.run(
        [
            sys.executable,
            str(LEARNING_DB_CLI),
            "query",
            "--topic",
            "eval:evals/new-skills-ab-test",
            "--format",
            "json",
        ],
        capture_output=True,
        text=True,
        env={**_clean_env(), "CLAUDE_LEARNING_DIR": str(temp_db_with_envelope.parent)},
    )
    assert res.returncode == 0, res.stderr
    rows = json.loads(res.stdout)
    assert rows, "expected at least one row"
    assert any(r.get("git_commit_sha") == head for r in rows)


def _clean_env() -> dict:
    import os

    return {k: v for k, v in os.environ.items()}


# ---------------------------------------------------------------------------
# CI workflow guarantee -- Validation Requirement 4.
# ---------------------------------------------------------------------------


def test_ci_job_is_report_only():
    """skill-eval-coverage job: continue-on-error true, never a required check."""
    import yaml

    data = yaml.safe_load(WORKFLOW.read_text(encoding="utf-8"))
    jobs = data["jobs"]
    assert "skill-eval-coverage" in jobs, "skill-eval-coverage job missing"
    job = jobs["skill-eval-coverage"]
    assert job.get("continue-on-error") is True
    # No 'required: true' anywhere in the job definition.
    assert "required: true" not in yaml.safe_dump(job)


# ---------------------------------------------------------------------------
# --install-hook: writes an idempotent, advisory pre-push hook.
# ---------------------------------------------------------------------------


def test_install_hook_writes_advisory_idempotent(tmp_path):
    repo = tmp_path / "repo"
    (repo / ".git" / "hooks").mkdir(parents=True)
    res1 = subprocess.run(
        [sys.executable, str(SCRIPT), "--install-hook"],
        cwd=str(repo),
        capture_output=True,
        text=True,
    )
    assert res1.returncode == 0, res1.stderr
    hook = repo / ".git" / "hooks" / "pre-push"
    assert hook.exists()
    body = hook.read_text(encoding="utf-8")
    assert "# vexjoy-skill-eval-prepush" in body
    assert "VEXJOY_SKILL_EVAL_PREPUSH" in body
    assert "exit 0" in body

    # Re-run: idempotent, does not duplicate the marker.
    res2 = subprocess.run(
        [sys.executable, str(SCRIPT), "--install-hook"],
        cwd=str(repo),
        capture_output=True,
        text=True,
    )
    assert res2.returncode == 0
    body2 = hook.read_text(encoding="utf-8")
    assert body2.count("# vexjoy-skill-eval-prepush") == 1


def test_install_hook_preserves_foreign_hook(tmp_path):
    """A pre-existing non-vexjoy hook is not clobbered."""
    repo = tmp_path / "repo"
    (repo / ".git" / "hooks").mkdir(parents=True)
    hook = repo / ".git" / "hooks" / "pre-push"
    hook.write_text("#!/usr/bin/env bash\necho foreign\nexit 0\n", encoding="utf-8")
    res = subprocess.run(
        [sys.executable, str(SCRIPT), "--install-hook"],
        cwd=str(repo),
        capture_output=True,
        text=True,
    )
    # Refuses to clobber a foreign hook; exits 0, prints a notice.
    assert res.returncode == 0
    assert "foreign" in hook.read_text(encoding="utf-8")


@pytest.mark.parametrize("arm", ["base", "head"])
def test_record_arm_keying(temp_db_no_envelope, tmp_path, monkeypatch, arm):
    """base and head arms write distinct keys (skill@head:arm)."""
    mod = _load_module()
    monkeypatch.setattr(mod, "ABLATION_LOG", tmp_path / f"log-{arm}.jsonl", raising=False)
    head = "c" * 40
    mod.record_run(
        eval_dir="evals/k",
        skill="planning",
        arm=arm,
        pass_rate=0.5,
        runs=1,
        base_sha="b" * 40,
        head_sha=head,
        model_id="m",
        skill_version="1.0.0",
    )
    sys.path.insert(0, str(LIB_DIR))
    import learning_db_v2 as ldb

    monkeypatch.setattr(ldb, "_initialized", False, raising=False)
    rows = ldb.query_learnings(topic="eval:evals/k", exclude_test_sources=False)
    assert any(r["key"] == f"planning@{head}:{arm}" for r in rows)
