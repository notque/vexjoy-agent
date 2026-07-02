#!/usr/bin/env python3
"""Composite /do router health check — manual-run only.

MANUAL-RUN ONLY: do not install this script as a cron job, systemd unit or
timer, shell startup entry, or any other scheduled/background job. Persistence
requires explicit owner approval (OWNER-APPROVED-PERSISTENCE); ADR
router-improvement-program ships C3 manual-run only.

One composite report over four checks, exit 0/1:
  1. manifest     — routing-manifest.py output byte size + merged skill/agent
                    entry counts (via the live pre-route.py loader).
  2. merged-index — validate-merged-index.py --strict findings: phantom files,
                    dead agent refs, missing fields, "NOT: " doubling.
  3. replay-suite — pass rate of the route-replay regression corpus
                    (routing-benchmark.json tiers + pre-route corpus pins),
                    run through pytest.
  4. drift        — check-routing-drift.py: every INDEX skill appears in the
                    routing manifest.

Usage:
    python3 scripts/router-self-audit.py

Exit codes:
    0 — all checks passed
    1 — one or more checks failed
"""

from __future__ import annotations

import importlib
import re
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
SCRIPTS = REPO_ROOT / "scripts"

# Replay regression corpus runners: the benchmark-fixture replay
# (test_routing_accuracy.py) plus the pre-route corpus pins.
REPLAY_TEST_FILES = (
    "scripts/tests/test_routing_accuracy.py",
    "scripts/tests/test_pre_route_planning.py",
    "scripts/tests/test_pre_route_pr_workflow.py",
    "scripts/tests/test_pre_route_public_web_deploy.py",
)

_SUBPROCESS_TIMEOUT = 300  # seconds; replay suite shells pytest over ~180 cases


@dataclass
class CheckResult:
    """Outcome of one audit check."""

    name: str
    ok: bool
    summary: str
    detail: str = ""


def _run(cmd: list[str], timeout: int = _SUBPROCESS_TIMEOUT) -> subprocess.CompletedProcess[str]:
    """Run a command, capturing text output. Raises on timeout/missing binary."""
    return subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        cwd=str(REPO_ROOT),
        timeout=timeout,
        check=False,
    )


def parse_pytest_counts(output: str) -> tuple[int, int]:
    """Parse (passed, failed) from pytest terminal output.

    Reads the summary tokens ("2 failed, 146 passed in 12.3s"). Errors count
    as failures. Returns (0, 0) when no summary is found.

    Args:
        output: Full pytest stdout.

    Returns:
        Tuple of (passed count, failed+error count).
    """
    passed = failed = 0
    for count, kind in re.findall(r"(\d+) (passed|failed|error)", output):
        if kind == "passed":
            passed = int(count)
        else:
            failed += int(count)
    return passed, failed


def check_manifest() -> CheckResult:
    """Report routing-manifest byte size and merged index entry counts."""
    proc = _run([sys.executable, str(SCRIPTS / "routing-manifest.py")])
    if proc.returncode != 0:
        return CheckResult("manifest", False, f"routing-manifest.py exited {proc.returncode}", proc.stderr.strip())
    size = len(proc.stdout.encode("utf-8"))

    # Count entries through the live pre-route loader (merged tracked+local,
    # regenerates a missing INDEX) so the audit sees what the router sees.
    if str(SCRIPTS) not in sys.path:
        sys.path.insert(0, str(SCRIPTS))
    pre_route = importlib.import_module("pre-route")
    entries = pre_route.load_entries()
    skills = sum(1 for e in entries if e["type"] == "skill")
    agents = sum(1 for e in entries if e["type"] == "agent")
    return CheckResult(
        "manifest",
        True,
        f"{size} bytes; merged entries: {skills} skills, {agents} agents",
    )


def check_merged_index() -> CheckResult:
    """Run validate-merged-index.py --strict; fail on critical/error findings."""
    proc = _run([sys.executable, str(SCRIPTS / "validate-merged-index.py"), "--strict"])
    tail = proc.stdout.strip().splitlines()
    summary = tail[-1] if tail else "no output"
    ok = proc.returncode == 0
    detail = "" if ok else proc.stdout.strip()
    return CheckResult("merged-index", ok, summary, detail)


def check_replay_suite() -> CheckResult:
    """Run the replay regression corpus through pytest; fail on any failure."""
    cmd = [sys.executable, "-m", "pytest", "-q", "--tb=line", "-p", "no:cacheprovider", *REPLAY_TEST_FILES]
    try:
        proc = _run(cmd)
    except FileNotFoundError:
        return CheckResult("replay-suite", False, "pytest not available")
    passed, failed = parse_pytest_counts(proc.stdout)
    total = passed + failed
    if total == 0:
        return CheckResult("replay-suite", False, "no replay cases collected", proc.stdout.strip()[-2000:])
    rate = 100.0 * passed / total
    ok = failed == 0 and proc.returncode == 0
    detail = "" if ok else proc.stdout.strip()[-2000:]
    return CheckResult("replay-suite", ok, f"{passed}/{total} passed ({rate:.1f}%)", detail)


def check_drift() -> CheckResult:
    """Run check-routing-drift.py; fail when a skill is missing from the manifest."""
    proc = _run([sys.executable, str(SCRIPTS / "check-routing-drift.py")])
    lines = proc.stdout.strip().splitlines()
    ok = proc.returncode == 0
    default = "OK (all INDEX skills present in manifest)" if ok else f"exit {proc.returncode}"
    summary = lines[-1] if lines else default
    detail = "" if ok else (proc.stdout + proc.stderr).strip()
    return CheckResult("drift", ok, summary, detail)


def main() -> int:
    """Run all checks and print the composite report."""
    checks = (check_manifest, check_merged_index, check_replay_suite, check_drift)
    results: list[CheckResult] = []
    for check in checks:
        try:
            results.append(check())
        except (subprocess.TimeoutExpired, OSError) as exc:
            results.append(CheckResult(check.__name__.removeprefix("check_"), False, f"{type(exc).__name__}: {exc}"))

    print("Router Self-Audit")
    print("=================")
    for r in results:
        status = "PASS" if r.ok else "FAIL"
        print(f"[{status}] {r.name:13} {r.summary}")
        if r.detail:
            for line in r.detail.splitlines():
                print(f"       {line}")
    all_ok = all(r.ok for r in results)
    print()
    print(f"RESULT: {'PASS' if all_ok else 'FAIL'}")
    return 0 if all_ok else 1


if __name__ == "__main__":
    sys.exit(main())
