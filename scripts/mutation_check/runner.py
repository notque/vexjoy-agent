"""Orchestrate baseline, redirect probe, and mutant runs across worker sandboxes; persist results for resume."""

from __future__ import annotations

import hashlib
import json
import queue
import threading
import time
from collections import Counter
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from . import engine, mutate
from .scope import Target

DENY_CAP = 150
OTHER_CAP = 40
CACHE_DIR = Path.home() / ".cache" / "mutation-check"


def repo_fingerprint(repo: Path) -> str:
    """Return a hash of the files a mutant could touch (hook sources and validators), to prove the run left them alone.

    The repo is shared with other work in progress, so this covers only the mutation targets, not the whole tree.
    """
    digest = hashlib.sha256()
    files = sorted((repo / "hooks").rglob("*.py")) + sorted((repo / "scripts").glob("validate-*.py"))
    for path in files:
        if "tests" in path.parts or "__pycache__" in path.parts:
            continue
        digest.update(str(path.relative_to(repo)).encode())
        digest.update(path.read_bytes())
    return digest.hexdigest()


def _read_jsonl(path: Path) -> list[dict]:
    if not path.exists():
        return []
    rows = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.strip():
            rows.append(json.loads(line))
    return rows


class Runner:
    """Run baseline, redirect probe, and mutants for a set of targets."""

    def __init__(self, repo: Path, cache: Path = CACHE_DIR, workers: int = 8, seed: int = 0) -> None:
        """Create output dirs and the sandbox pool (sandboxes are built lazily by `start`)."""
        self.repo = repo
        self.cache = cache
        self.workers = workers
        self.seed = seed
        self.lock = threading.Lock()
        for sub in ("baseline", "results"):
            (cache / sub).mkdir(parents=True, exist_ok=True)
        self.sandboxes: queue.Queue[engine.Sandbox] = queue.Queue()
        self.root = engine.make_root()

    def start(self) -> None:
        """Build one sandbox per worker, in parallel."""
        with ThreadPoolExecutor(self.workers) as pool:
            for sb in pool.map(lambda i: engine.Sandbox(self.repo, self.root, i), range(self.workers)):
                self.sandboxes.put(sb)

    def _with_sandbox(self, fn, *args):
        sb = self.sandboxes.get()
        try:
            return fn(sb, *args)
        finally:
            self.sandboxes.put(sb)

    # ------------------------------------------------------------------------------------- baseline + probe
    def _baseline_one(self, sb: engine.Sandbox, target: Target) -> dict:
        path = self.cache / "baseline" / f"{target.name}.json"
        if path.exists():
            return json.loads(path.read_text(encoding="utf-8"))
        base = engine.baseline(sb, target.tests)
        record = {
            "name": target.name,
            "usable": base.usable,
            "reason": base.reason,
            "flaky": base.flaky,
            "broken": base.broken[:10],
            "seconds": round(base.seconds, 2),
            "passed": [r.passed for r in base.runs],
            "returncodes": [r.returncode for r in base.runs],
            "tail": base.runs[-1].tail[-400:] if not base.usable else "",
            "redirect": None,
        }
        if base.usable:
            timeout = min(600.0, max(60.0, base.seconds * 4 + 30))
            record["redirect"] = engine.redirect_proved(sb, target.source, target.tests, base.deselect, timeout)
            if record["redirect"] is None:
                record["usable"] = False
                record["reason"] = "could_not_run: no redirect probe made the tests fail, so the copy is not loaded"
        path.write_text(json.dumps(record, indent=1), encoding="utf-8")
        return record

    def baselines(self, targets: list[Target]) -> dict[str, dict]:
        """Return {target: baseline record} for every target."""
        with ThreadPoolExecutor(self.workers) as pool:
            records = list(pool.map(lambda t: self._with_sandbox(self._baseline_one, t), targets))
        return {r["name"]: r for r in records}

    # ------------------------------------------------------------------------------------------- mutants
    def _mutant_one(self, sb: engine.Sandbox, target: Target, mut: mutate.Mutant, original: str, base: dict) -> dict:
        timeout = min(600.0, max(30.0, base["seconds"] * 6 + 20))
        started = time.monotonic()
        status, kind, res = engine.run_mutant(
            sb, target.source, mut.source, original, target.tests, base["flaky"], timeout
        )
        return {
            "id": mut.id,
            "operator": mut.operator,
            "line": mut.line,
            "function": mut.function,
            "description": mut.description,
            "status": status,
            "kind": kind,
            "failed": res.failed[:3],
            "seconds": round(time.monotonic() - started, 2),
            "diff": mut.diff,
        }

    def mutate_target(self, target: Target, base: dict) -> dict:
        """Generate mutants for *target* and run the ones not already recorded; return the generation summary."""
        source = (self.repo / target.source).read_text(encoding="utf-8")
        cap = DENY_CAP if target.deny else OTHER_CAP
        gen = mutate.generate(source, target.name, cap=cap, seed=self.seed)
        results_path = self.cache / "results" / f"{target.name}.jsonl"
        done = {row["id"] for row in _read_jsonl(results_path)}
        meta = {
            "name": target.name,
            "cap": cap,
            "generated": len(gen.mutants),
            "candidates": gen.candidates,
            "rejected_unparseable": gen.rejected_unparseable,
            "anchor_errors": gen.errors,
            "operators_available": gen.by_operator_candidates,
        }
        (self.cache / "results" / f"{target.name}.meta.json").write_text(json.dumps(meta, indent=1), encoding="utf-8")
        todo = [m for m in gen.mutants if m.id not in done]

        def one(mut: mutate.Mutant) -> None:
            row = self._with_sandbox(self._mutant_one, target, mut, source, base)
            with self.lock, results_path.open("a", encoding="utf-8") as fh:
                fh.write(json.dumps(row) + "\n")

        with ThreadPoolExecutor(self.workers) as pool:
            list(pool.map(one, todo))
        return meta

    def run_all(self, targets: list[Target], bases: dict[str, dict]) -> None:
        """Mutate every usable target, deny hooks first."""
        order = sorted(targets, key=lambda t: (not t.deny, t.name))
        for target in order:
            base = bases[target.name]
            if not base["usable"]:
                continue
            started = time.monotonic()
            meta = self.mutate_target(target, base)
            rows = _read_jsonl(self.cache / "results" / f"{target.name}.jsonl")
            counts = Counter(r["status"] for r in rows)
            print(
                f"{target.name}: {meta['generated']} mutants {dict(counts)} in {time.monotonic() - started:.0f}s",
                flush=True,
            )


def load_results(cache: Path = CACHE_DIR) -> dict[str, dict]:
    """Return {target: {"meta": ..., "baseline": ..., "rows": [...]}} from disk."""
    out: dict[str, dict] = {}
    for bpath in sorted((cache / "baseline").glob("*.json")):
        record = json.loads(bpath.read_text(encoding="utf-8"))
        name = record["name"]
        meta_path = cache / "results" / f"{name}.meta.json"
        out[name] = {
            "baseline": record,
            "meta": json.loads(meta_path.read_text(encoding="utf-8")) if meta_path.exists() else {},
            "rows": _read_jsonl(cache / "results" / f"{name}.jsonl"),
        }
    return out
