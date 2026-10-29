"""Sandboxed test runs for mutants.

A mutant never touches the real repo. Each worker owns a copy of the repo (a sandbox) with its own HOME. To test a
mutant, the worker overwrites one file in its copy, runs the target's test files from the copy, and restores the file.
Tests find hooks through paths relative to themselves, so the copied tests load the copied (mutated) hook.
"""

from __future__ import annotations

import ast
import importlib.util
import os
import re
import shutil
import signal
import site
import subprocess
import sys
import tempfile
import time
from dataclasses import dataclass, field
from pathlib import Path

COPY_IGNORE = shutil.ignore_patterns(
    ".git", "node_modules", ".venv", ".cache", ".ruff_cache", ".pytest_cache", "__pycache__", "tmp", ".playwright-mcp"
)
SYMLINKED = (".git", "node_modules")
FAILED_LINE = re.compile(r"^(?:FAILED|ERROR) (\S+)")
SUMMARY = re.compile(r"(\d+) (passed|failed|error|errors|skipped|deselected)")
SCRUB_PREFIXES = ("CLAUDE", "CODEX", "ANTHROPIC", "OPENAI", "PYTEST")
BASELINE_RUNS = 3


@dataclass
class RunResult:
    """Outcome of one pytest invocation."""

    returncode: int
    seconds: float
    failed: list[str] = field(default_factory=list)
    passed: int = 0
    timed_out: bool = False
    tail: str = ""
    collection_error: bool = False


def sandbox_env(home: Path) -> dict[str, str]:
    """Return an environment with agent/session variables removed and HOME pointing at the sandbox."""
    env = {k: v for k, v in os.environ.items() if not k.startswith(SCRUB_PREFIXES)}
    env["HOME"] = str(home)
    # HOME is redirected, so pin the real user site or user-installed pytest vanishes.
    env.setdefault("PYTHONUSERBASE", site.getuserbase())
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    env["MUTATION_CHECK_SANDBOX"] = "1"
    return env


class Sandbox:
    """A throwaway copy of the repo that runs one test invocation at a time."""

    def __init__(self, repo: Path, root: Path, index: int) -> None:
        """Copy *repo* into *root*/ws<index>/repo and create an isolated HOME."""
        self.repo_src = repo
        self.base = root / f"ws{index}"
        self.repo = self.base / "repo"
        self.home = self.base / "home"
        if self.base.exists():
            shutil.rmtree(self.base)
        shutil.copytree(repo, self.repo, ignore=COPY_IGNORE, symlinks=True)
        for name in SYMLINKED:
            if (repo / name).exists():
                (self.repo / name).symlink_to(repo / name)
        self.home.mkdir(parents=True)
        gitconfig = Path.home() / ".gitconfig"
        if gitconfig.exists():
            shutil.copy(gitconfig, self.home / ".gitconfig")
        (self.home / ".claude").mkdir()

    def read(self, rel: str) -> str:
        """Return the sandbox copy of *rel*."""
        return (self.repo / rel).read_text(encoding="utf-8")

    def write(self, rel: str, text: str) -> None:
        """Overwrite the sandbox copy of *rel*."""
        (self.repo / rel).write_text(text, encoding="utf-8")

    def pytest(
        self, tests: list[str], deselect: list[str] | None = None, timeout: float = 300, fail_fast: bool = False
    ) -> RunResult:
        """Run *tests* from the sandbox; kill the whole process group on timeout."""
        cmd = [sys.executable, "-m", "pytest", *tests, "-q", "-p", "no:cacheprovider", "--tb=no", "-rfE"]
        if importlib.util.find_spec("xdist") is not None:
            cmd.append("-n0")  # the repo config asks for -n auto; one process per run keeps timing and kills clean
        cmd += ["--no-header", "-p", "no:randomly"]
        if fail_fast:
            cmd.append("-x")
        for node in deselect or []:
            cmd += ["--deselect", node]
        shutil.rmtree(self.home / ".claude", ignore_errors=True)
        (self.home / ".claude").mkdir(parents=True, exist_ok=True)
        started = time.monotonic()
        proc = subprocess.Popen(
            cmd,
            cwd=self.repo,
            env=sandbox_env(self.home),
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            start_new_session=True,
        )
        timed_out = False
        try:
            out, _ = proc.communicate(timeout=timeout)
        except subprocess.TimeoutExpired:
            timed_out = True
            os.killpg(proc.pid, signal.SIGKILL)
            out, _ = proc.communicate()
        return parse_pytest(out or "", proc.returncode, time.monotonic() - started, timed_out)


def parse_pytest(output: str, returncode: int, seconds: float, timed_out: bool = False) -> RunResult:
    """Parse failing node ids and counts from `pytest -q -rfE` output."""
    failed = []
    for line in output.splitlines():
        match = FAILED_LINE.match(line)
        if match:
            failed.append(match.group(1))
    passed = 0
    for line in reversed(output.splitlines()):
        found = {kind: int(n) for n, kind in SUMMARY.findall(line)}
        if found:
            passed = found.get("passed", 0)
            break
    collection_error = "error collecting" in output.lower() or (returncode in (2, 4) and not failed and not timed_out)
    return RunResult(returncode, seconds, sorted(set(failed)), passed, timed_out, output[-1500:], collection_error)


@dataclass
class Baseline:
    """Result of three unmutated runs."""

    runs: list[RunResult]
    flaky: list[str]
    broken: list[str]
    usable: bool
    reason: str
    seconds: float

    @property
    def deselect(self) -> list[str]:
        """Node ids to drop from every mutant run."""
        return list(self.flaky)


def baseline(sb: Sandbox, tests: list[str], timeout: float = 600) -> Baseline:
    """Run *tests* unmutated three times; tests that fail sometimes are flaky, always are broken."""
    runs = [sb.pytest(tests, timeout=timeout) for _ in range(BASELINE_RUNS)]
    seconds = max(r.seconds for r in runs)
    if any(r.timed_out for r in runs):
        return Baseline(runs, [], [], False, "baseline timed out", seconds)
    if any(r.collection_error for r in runs):
        return Baseline(runs, [], [], False, "collection error in unmutated tests", seconds)
    sets = [set(r.failed) for r in runs]
    always = set.intersection(*sets)
    ever = set.union(*sets)
    flaky = sorted(ever - always)
    broken = sorted(always)
    if broken:
        return Baseline(runs, flaky, broken, False, f"{len(broken)} tests fail unmutated in all 3 runs", seconds)
    if all(r.passed == 0 for r in runs):
        return Baseline(runs, flaky, broken, False, "no tests passed", seconds)
    return Baseline(runs, flaky, broken, True, "ok", seconds)


def probe_sources(source: str) -> list[tuple[str, str]]:
    """Return the redirect probes for a source file: a syntax-valid copy that breaks the hook in an obvious way.

    First probe puts `return` at the top of `main`. Second appends a module-level `raise`. If either makes the tests
    fail, the test file loads the copy we wrote.
    """
    probes = []
    tree = ast.parse(source)
    lines = source.splitlines(keepends=True)
    for node in tree.body:
        if isinstance(node, ast.FunctionDef) and node.name == "main":
            first = node.body[0]
            if isinstance(first, ast.Expr) and isinstance(first.value, ast.Constant) and len(node.body) > 1:
                first = node.body[1]
            indent = " " * first.col_offset
            at = first.lineno - 1
            probes.append(("return at top of main", "".join(lines[:at]) + f"{indent}return\n" + "".join(lines[at:])))
            break
    probes.append(
        ("module-level raise", source.rstrip("\n") + "\n\nraise RuntimeError('mutation-check redirect probe')\n")
    )
    return probes


def redirect_proved(
    sb: Sandbox, target_source: str, tests: list[str], deselect: list[str], timeout: float
) -> str | None:
    """Return the probe name that made the tests fail, or None when no probe did (redirect unproven)."""
    original = sb.read(target_source)
    try:
        for name, text in probe_sources(original):
            sb.write(target_source, text)
            res = sb.pytest(tests, deselect=deselect, timeout=timeout, fail_fast=True)
            if res.timed_out or res.returncode != 0:
                return name
    finally:
        sb.write(target_source, original)
    return None


def run_mutant(
    sb: Sandbox, target_source: str, mutated: str, original: str, tests: list[str], deselect: list[str], timeout: float
) -> tuple[str, str, RunResult]:
    """Run one mutant; return (status, kind, result). Status is killed or survived."""
    try:
        sb.write(target_source, mutated)
        res = sb.pytest(tests, deselect=deselect, timeout=timeout, fail_fast=True)
    finally:
        sb.write(target_source, original)
    if res.timed_out:
        return "killed", "timeout", res
    if res.returncode == 0:
        return "survived", "", res
    if res.returncode == 5:
        return "could_not_run", "no tests collected", res
    if res.failed:
        return "killed", "test_failure", res
    return "killed", "crash", res


def make_root(prefix: str = "mutcheck-") -> Path:
    """Return a fresh temp directory for sandboxes."""
    return Path(tempfile.mkdtemp(prefix=prefix))
