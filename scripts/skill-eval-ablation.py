#!/usr/bin/env python3
"""Local before/after skill-eval ablation runner (the real eval).

ADR: skill-eval-pr-ablation (Decision 3). This is the honest fallback: the
actual ablation runs locally, where the `claude` CLI exists. CI cannot run
evals (run_eval.py shells to `claude`), so CI only reports coverage.

For each skill changed in base..head and mapped to an eval by
detect-skill-changes.py:
  1. check out the base content of the skill, run its eval, capture pass rate;
  2. restore head content, run again, capture pass rate;
  3. print: planning  base 58% -> head 67%  (+9, eval=evals/..., runs=3);
  4. restore the working tree to its starting state on every exit path.

Uncovered skills print a no-coverage line and continue.

--record writes one run per arm to learning.db. PR-A shipped the envelope as a
dedicated telemetry_runs table (git_sha/model_id/skill_version per row) with a
record_telemetry_run() API. When that table is present, the run's envelope goes
to telemetry_runs and a human-queryable summary row goes to learnings. When it
is absent (no PR-A), the run still lands in learnings (envelope packed into the
free-text `value` column) AND appends one JSON line to
~/.claude/eval-ablations.log -- never dropped, never a failure.

Usage:
    python3 scripts/skill-eval-ablation.py --base <REF> --head <REF> [--skill NAME] [--record] [--runs N]
    python3 scripts/skill-eval-ablation.py --pre-push          # changed+mapped skills, advisory
    python3 scripts/skill-eval-ablation.py --install-hook      # write the opt-in pre-push hook, then exit
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path

SCRIPTS_DIR = Path(__file__).resolve().parent
REPO_ROOT = SCRIPTS_DIR.parent
DETECTOR = SCRIPTS_DIR / "detect-skill-changes.py"
RUN_EVAL = SCRIPTS_DIR / "skill_eval" / "run_eval.py"


class DirtyTreeError(RuntimeError):
    """Raised when a skill file has uncommitted edits before a base-arm checkout.

    The ablation checks out base content over the working tree, then restores
    head content. That round-trip destroys uncommitted edits. So the runner
    refuses to ablate a skill whose file is dirty and tells the user to commit
    or stash first.
    """


# Degraded-record log (pre-PR-A). Kept as a module global so tests can redirect.
ABLATION_LOG = Path.home() / ".claude" / "eval-ablations.log"

# Marker line written into the generated pre-push hook so a re-install detects
# its own hook and does not clobber a foreign one.
HOOK_MARKER = "# vexjoy-skill-eval-prepush"


# ---------------------------------------------------------------------------
# Formatting.
# ---------------------------------------------------------------------------


def _pct(rate: float) -> int:
    """Render a 0..1 pass rate as an integer percent."""
    return round(rate * 100)


def format_delta(*, skill: str, base_rate: float, head_rate: float, eval_dir: str, runs: int) -> str:
    """One-line delta: 'planning  base 58% -> head 67%  (+9, eval=..., runs=3)'."""
    b, h = _pct(base_rate), _pct(head_rate)
    delta = h - b
    sign = "+" if delta >= 0 else ""
    return f"{skill}  base {b}% -> head {h}%  ({sign}{delta}, eval={eval_dir}, runs={runs})"


def format_uncovered(skills: list[str]) -> str:
    """No-coverage line for changed skills with no eval."""
    return f"no eval coverage for changed skill(s): {', '.join(skills)}"


# ---------------------------------------------------------------------------
# Recording (capture -> store). Probe for PR-A envelope; degrade if absent.
# ---------------------------------------------------------------------------


def _import_learning_db():
    """Import the learning_db_v2 module from hooks/lib."""
    lib = REPO_ROOT / "hooks" / "lib"
    if str(lib) not in sys.path:
        sys.path.insert(0, str(lib))
    import learning_db_v2 as ldb

    return ldb


def _envelope_present(ldb) -> bool:
    """True when learning.db has PR-A's telemetry_runs table (envelope landed).

    PR-A shipped the envelope as a dedicated telemetry_runs table, not as columns
    on learnings. So the probe is the table's existence, not a column on learnings.
    """
    ldb.init_db()
    with ldb.get_connection() as conn:
        row = conn.execute("SELECT name FROM sqlite_master WHERE type = 'table' AND name = 'telemetry_runs'").fetchone()
    return row is not None


def _append_log(record: dict) -> None:
    """Append one JSON line to the degraded-record log."""
    ABLATION_LOG.parent.mkdir(parents=True, exist_ok=True)
    with ABLATION_LOG.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(record) + "\n")


def record_run(
    *,
    eval_dir: str,
    skill: str,
    arm: str,
    pass_rate: float,
    runs: int,
    base_sha: str,
    head_sha: str,
    model_id: str,
    skill_version: str,
) -> int:
    """Record one ablation run to learning.db. Returns 0 always.

    PR-A landed (telemetry_runs table present): write the envelope (git_sha/
    model_id/skill_version) to telemetry_runs via record_telemetry_run, and keep
    a human-queryable summary row in learnings. Otherwise: write the summary row
    with the envelope packed into `value`, AND append a JSON line to
    ~/.claude/eval-ablations.log. The record is never dropped.
    """
    ldb = _import_learning_db()
    topic = f"eval:{eval_dir}"
    key = f"{skill}@{head_sha}:{arm}"
    value = (
        f"pass_rate={pass_rate} runs={runs} base={base_sha} head={head_sha} "
        f"git_commit_sha={head_sha} model_id={model_id} skill_version={skill_version}"
    )

    if _envelope_present(ldb):
        # PR-A present: envelope -> telemetry_runs (the real per-run table);
        # human-queryable summary -> learnings.
        ldb.record_telemetry_run(
            topic=topic,
            key=key,
            run_id=f"{key}:{uuid.uuid4().hex}",
            source="manual:skill-eval-ablation",
            git_sha=head_sha,
            model_id=model_id,
            skill_version=skill_version,
        )
        ldb.record_learning(
            topic=topic,
            key=key,
            value=value,
            category="effectiveness",
            source="manual:skill-eval-ablation",
        )
        return 0

    # No PR-A: write the summary row to learnings (envelope packed into value) so
    # the run is not lost, then append the JSON line and warn.
    ldb.record_learning(
        topic=topic,
        key=key,
        value=value,
        category="effectiveness",
        source="manual:skill-eval-ablation",
    )
    _append_log(
        {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "topic": topic,
            "key": key,
            "eval_dir": eval_dir,
            "skill": skill,
            "arm": arm,
            "pass_rate": pass_rate,
            "runs": runs,
            "base": base_sha,
            "head": head_sha,
            "git_commit_sha": head_sha,
            "model_id": model_id,
            "skill_version": skill_version,
        }
    )
    print("WARN: telemetry envelope not present (PR-A); wrote to ~/.claude/eval-ablations.log")
    return 0


# ---------------------------------------------------------------------------
# Detection + git plumbing.
# ---------------------------------------------------------------------------


def _git(repo: Path, *args: str) -> str:
    res = subprocess.run(["git", *args], cwd=str(repo), capture_output=True, text=True, check=True)
    return res.stdout.strip()


def _is_dirty(repo: Path, rel_path: str) -> bool:
    """True when `rel_path` has uncommitted changes (staged or unstaged).

    `git status --porcelain -- <path>` prints one line per changed path and
    nothing for a clean path. Any output means the file is dirty.
    """
    return bool(_git(repo, "status", "--porcelain", "--", rel_path))


def detect(repo: Path, base: str, head: str) -> dict:
    """Run detect-skill-changes.py and return its JSON report."""
    res = subprocess.run(
        [sys.executable, str(DETECTOR), "--base", base, "--head", head, "--format", "json", "--repo", str(repo)],
        capture_output=True,
        text=True,
    )
    return json.loads(res.stdout)


def _model_id() -> str:
    """Best-effort model id for the envelope (configured or unknown)."""
    return os.environ.get("ANTHROPIC_MODEL") or os.environ.get("CLAUDE_MODEL") or "unknown"


def _skill_version(repo: Path, skill: str) -> str:
    """Read a skill's frontmatter version (best-effort)."""
    for skill_md in (repo / "skills").rglob("SKILL.md"):
        if skill_md.parent.name == skill:
            for line in skill_md.read_text(encoding="utf-8").splitlines():
                if line.strip().startswith("version:"):
                    return line.split(":", 1)[1].strip().strip('"').strip("'")
    return "unknown"


def run_eval_for_content(repo: Path, eval_dir: str, skill: str, runs: int) -> float | None:
    """Run the skill's eval against the current working-tree content.

    Returns the pass rate (0..1) or None when the eval cannot run (no eval set,
    or the `claude` CLI is unavailable). The runner shells to `claude -p`, so
    this only works locally -- never in CI.
    """
    eval_set = None
    for candidate in ("eval-set.json", "eval_set.json", "queries.json"):
        p = repo / eval_dir / candidate
        if p.is_file():
            eval_set = p
            break
    skill_dir = None
    for skill_md in (repo / "skills").rglob("SKILL.md"):
        if skill_md.parent.name == skill:
            skill_dir = skill_md.parent
            break
    if eval_set is None or skill_dir is None:
        return None

    res = subprocess.run(
        [
            sys.executable,
            str(RUN_EVAL),
            "--eval-set",
            str(eval_set),
            "--skill-path",
            str(skill_dir),
            "--runs-per-query",
            str(runs),
        ],
        cwd=str(repo),
        capture_output=True,
        text=True,
    )
    if res.returncode != 0:
        print(f"[skill-eval-ablation] eval run failed for {skill}: {res.stderr.strip()[:200]}", file=sys.stderr)
        return None
    try:
        out = json.loads(res.stdout)
        summ = out["summary"]
        total = summ["total"]
        return (summ["passed"] / total) if total else 0.0
    except (json.JSONDecodeError, KeyError, ZeroDivisionError):
        return None


def ablate_skill(repo: Path, skill: str, eval_dir: str, base_sha: str, head_sha: str, runs: int, record: bool) -> None:
    """Run base vs head eval for one mapped skill; print the delta; restore tree.

    Refuses to run when the skill file has uncommitted edits: the base-arm
    checkout would overwrite them and the head-arm restore would not bring them
    back, so the edits would be lost. When the file is clean, checks out base
    content, runs the eval, restores head content, runs again. The try/finally
    restores head content on every exit path, so a crash never leaves base
    checked out.

    Raises:
        DirtyTreeError: the skill file has uncommitted changes. The caller
            reports it and skips this skill; no checkout has run yet, so the
            working tree is untouched.
    """
    skill_rel = None
    for skill_md in (repo / "skills").rglob("SKILL.md"):
        if skill_md.parent.name == skill:
            skill_rel = skill_md.relative_to(repo).as_posix()
            break
    if skill_rel is None:
        print(f"[skill-eval-ablation] skill dir not found for {skill}", file=sys.stderr)
        return

    # Guard BEFORE any checkout. A dirty skill file would lose its uncommitted
    # edits to the base-arm checkout, so refuse and tell the user to commit or
    # stash. The tree is still pristine here — nothing to restore.
    if _is_dirty(repo, skill_rel):
        raise DirtyTreeError(
            f"{skill}: {skill_rel} has uncommitted changes; commit or stash them before ablating "
            "(the base-arm checkout would overwrite them)."
        )

    model_id = _model_id()
    skill_version = _skill_version(repo, skill)
    base_rate: float | None = None
    head_rate: float | None = None

    try:
        # base arm: check out base content of just this skill file.
        _git(repo, "checkout", base_sha, "--", skill_rel)
        base_rate = run_eval_for_content(repo, eval_dir, skill, runs)
        # head arm: restore head content.
        _git(repo, "checkout", head_sha, "--", skill_rel)
        head_rate = run_eval_for_content(repo, eval_dir, skill, runs)
    finally:
        # Restore the working tree to its starting state no matter what.
        try:
            _git(repo, "checkout", head_sha, "--", skill_rel)
        except subprocess.CalledProcessError:
            pass

    if base_rate is None or head_rate is None:
        # Not SQL — a stderr status line. security-review: ignore (false-positive
        # sql-injection match on the f-string).
        msg = f"{skill}: skipped — needs the claude CLI and an eval set under {eval_dir}"  # security-review: ignore
        print(msg, file=sys.stderr)
        return

    print(format_delta(skill=skill, base_rate=base_rate, head_rate=head_rate, eval_dir=eval_dir, runs=runs))

    if record:
        record_run(
            eval_dir=eval_dir,
            skill=skill,
            arm="base",
            pass_rate=base_rate,
            runs=runs,
            base_sha=base_sha,
            head_sha=head_sha,
            model_id=model_id,
            skill_version=skill_version,
        )
        record_run(
            eval_dir=eval_dir,
            skill=skill,
            arm="head",
            pass_rate=head_rate,
            runs=runs,
            base_sha=base_sha,
            head_sha=head_sha,
            model_id=model_id,
            skill_version=skill_version,
        )


# ---------------------------------------------------------------------------
# Pre-push hook installation.
# ---------------------------------------------------------------------------


def _hook_body() -> str:
    """The advisory, opt-in pre-push hook script."""
    return (
        "#!/usr/bin/env bash\n"
        f"{HOOK_MARKER}\n"
        "# Advisory skill-eval ablation on push. Opt-in: acts only when\n"
        "# VEXJOY_SKILL_EVAL_PREPUSH=1. Never blocks the push (exit 0 always).\n"
        'if [ "${VEXJOY_SKILL_EVAL_PREPUSH:-0}" != "1" ]; then\n'
        "  exit 0\n"
        "fi\n"
        'python3 "$(git rev-parse --show-toplevel)/scripts/skill-eval-ablation.py" --pre-push || true\n'
        "exit 0\n"
    )


def install_hook(repo: Path) -> int:
    """Write .git/hooks/pre-push (advisory, opt-in). Idempotent; never clobbers.

    Returns 0 always. If a hook exists already: re-write only when it is our own
    (carries HOOK_MARKER); leave a foreign hook untouched and print a notice.
    """
    hooks_dir = repo / ".git" / "hooks"
    if not hooks_dir.is_dir():
        print(f"[skill-eval-ablation] no .git/hooks/ under {repo}; not a git repo?", file=sys.stderr)
        return 0
    hook = hooks_dir / "pre-push"
    if hook.exists():
        existing = hook.read_text(encoding="utf-8")
        if HOOK_MARKER not in existing:
            print(
                f"[skill-eval-ablation] {hook} exists and is not ours; left untouched. "
                "Remove it first to install the ablation hook.",
            )
            return 0
    hook.write_text(_hook_body(), encoding="utf-8")
    os.chmod(hook, 0o755)
    print(
        f"[skill-eval-ablation] installed advisory pre-push hook at {hook} "
        "(set VEXJOY_SKILL_EVAL_PREPUSH=1 to activate)"
    )
    return 0


# ---------------------------------------------------------------------------
# Orchestration.
# ---------------------------------------------------------------------------


def run_ablation(repo: Path, base: str, head: str, only_skill: str | None, runs: int, record: bool) -> int:
    """Detect mapped skills and ablate each; print uncovered ones. Exit 0."""
    report = detect(repo, base, head)
    base_sha, head_sha = report["base"], report["head"]
    mapped = report["mapped"]
    uncovered = report["uncovered"]

    if only_skill:
        mapped = [m for m in mapped if m["skill"] == only_skill]
        uncovered = [s for s in uncovered if s == only_skill]

    for m in mapped:
        try:
            ablate_skill(repo, m["skill"], m["eval_dir"], base_sha, head_sha, runs, record)
        except DirtyTreeError as exc:
            # Advisory tool: report the dirty skill and move on. Never abort the
            # run or touch the working tree.
            print(f"[skill-eval-ablation] skipped {exc}", file=sys.stderr)
    if uncovered:
        print(format_uncovered(uncovered))
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Local before/after skill-eval ablation (advisory, never blocks).")
    parser.add_argument("--base", help="Base ref")
    parser.add_argument("--head", help="Head ref")
    parser.add_argument("--skill", help="Limit to one skill name")
    parser.add_argument("--runs", type=int, default=3, help="Runs per query per arm (default 3)")
    parser.add_argument("--record", action="store_true", help="Record runs to learning.db / log file")
    parser.add_argument("--pre-push", action="store_true", help="Pre-push mode: HEAD~1..HEAD, advisory")
    parser.add_argument("--install-hook", action="store_true", help="Write the opt-in pre-push hook, then exit")
    parser.add_argument("--repo", default=".", help="Repo root (default: cwd)")
    args = parser.parse_args()

    repo = Path(args.repo).resolve()

    if args.install_hook:
        return install_hook(repo)

    if args.pre_push:
        base, head = "HEAD~1", "HEAD"
        return run_ablation(repo, base, head, args.skill, args.runs, record=True)

    if not args.base or not args.head:
        parser.error("--base and --head are required (unless --install-hook / --pre-push)")

    return run_ablation(repo, args.base, args.head, args.skill, args.runs, args.record)


if __name__ == "__main__":
    sys.exit(main())
