"""Show that new tests pass on the real hook and fail on the mutants they were written for.

The spec is a JSON list of entries: {"target": "<hook file name>", "test_file": "<repo-relative path>",
"mutants": ["<mutant id>", ...]}. For each entry the tests run once on an unmutated sandbox copy (must pass), then once
per mutant (must fail). A mutant is regenerated with the same cap and seed as the survey run, and its diff must equal
the diff stored in the survey results, so a test is never credited for killing a different mutant.
"""

from __future__ import annotations

import json
from pathlib import Path

from . import engine, mutate, runner, scope


def _stored_diffs(cache: Path, target: str) -> dict[str, dict]:
    return {row["id"]: row for row in runner._read_jsonl(cache / "results" / f"{target}.jsonl")}


def verify(repo: Path, cache: Path, spec: list[dict], seed: int = 0, timeout: float = 300) -> list[dict]:
    """Return one record per (entry, mutant): passes_on_real, kills_mutant, and the failing test ids."""
    targets = {t.name: t for t in scope.discover(repo)[0]}
    root = engine.make_root(prefix="mutverify-")
    sb = engine.Sandbox(repo, root, 0)
    records: list[dict] = []
    before = runner.repo_fingerprint(repo)
    for entry in spec:
        target = targets[entry["target"]]
        source = (repo / target.source).read_text(encoding="utf-8")
        gen = mutate.generate(source, target.name, cap=runner.DENY_CAP if target.deny else runner.OTHER_CAP, seed=seed)
        by_id = {m.id: m for m in gen.mutants}
        stored = _stored_diffs(cache, target.name)
        real = sb.pytest([entry["test_file"]], timeout=timeout)
        real_ok = real.returncode == 0 and real.passed > 0
        for mid in entry["mutants"]:
            mut = by_id.get(mid)
            row = stored.get(mid)
            record = {
                "target": target.name,
                "mutant": mid,
                "key": f"{target.name}::{mid}",
                "test_file": entry["test_file"],
                "passes_on_real": real_ok,
                "real_passed": real.passed,
                "survived_old_tests": bool(row and row["status"] == "survived"),
                "same_mutant_as_survey": bool(mut and row and mut.diff == row["diff"]),
            }
            if mut is None:
                record.update({"kills_mutant": False, "failed": [], "note": "mutant id not regenerated"})
            else:
                try:
                    sb.write(target.source, mut.source)
                    res = sb.pytest([entry["test_file"]], timeout=timeout)
                finally:
                    sb.write(target.source, source)
                record.update(
                    {
                        "kills_mutant": res.timed_out or res.returncode != 0,
                        "failed": res.failed,
                        "line": mut.line,
                        "operator": mut.operator,
                        "description": mut.description,
                    }
                )
            records.append(record)
    after = runner.repo_fingerprint(repo)
    for rec in records:
        rec["real_repo_unchanged"] = before == after
    return records


def main(cache: Path, repo: Path, spec_path: Path, out: Path) -> int:
    """Verify the spec, write the records to *out*, and print a summary; exit 1 when any record fails."""
    spec = json.loads(spec_path.read_text(encoding="utf-8"))
    records = verify(repo, cache, spec)
    out.write_text(json.dumps(records, indent=1), encoding="utf-8")
    bad = 0
    for rec in records:
        ok = (
            rec["passes_on_real"] and rec["kills_mutant"] and rec["survived_old_tests"] and rec["same_mutant_as_survey"]
        )
        bad += not ok
        print(
            f"{'ok  ' if ok else 'FAIL'} {rec['key']:55} real_pass={rec['passes_on_real']} "
            f"kills={rec['kills_mutant']} by={len(rec['failed'])}"
        )
    print(
        f"{len(records) - bad}/{len(records)} mutants killed with the real hook passing; real repo hooks unchanged: "
        f"{all(r['real_repo_unchanged'] for r in records)}"
    )
    return 1 if bad else 0
