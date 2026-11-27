"""Regression tests for optimize_loop.py, eval_compare.py, and aggregate_benchmark.py."""

from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
from pathlib import Path

SCRIPTS_DIR = Path(__file__).resolve().parents[1]
OPTIMIZE_LOOP = SCRIPTS_DIR / "agent-comparison" / "optimize_loop.py"
EVAL_COMPARE = SCRIPTS_DIR / "skill-creator" / "eval_compare.py"
AGGREGATE_BENCHMARK = SCRIPTS_DIR / "skill-creator" / "aggregate_benchmark.py"


def _load(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec is not None and spec.loader is not None
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_optimize_loop_escapes_script_closing_tag_in_embedded_json() -> None:
    mod = _load("toolkit_optimize_loop", OPTIMIZE_LOOP)
    data = {
        "target": "skills/demo/SKILL.md",
        "goal": "improve pass rate",
        "status": "COMPLETE",
        "baseline_score": {"train": 0.5, "test": 0.5},
        "task_counts": {"train": 2, "test": 1},
        "max_iterations": 5,
        "total_tokens": 1000,
        "iterations": [
            {
                "number": 1,
                "verdict": "ACCEPT",
                "score": {"train": 0.8, "test": 0.75},
                "delta": "+0.30",
                "change_summary": "updated diff",
                "diff": "+</script><script>alert(1)</script>",
            }
        ],
    }
    html = mod.generate_optimization_report(data)
    script_section = html.split("<script>", 1)[1]
    assert "</script><script>alert(1)" not in script_section
    assert r"\u003c/script>" in script_section


def test_eval_compare_escapes_less_than_in_embedded_json(tmp_path: Path) -> None:
    workspace = tmp_path / "ws"
    workspace.mkdir(parents=True)
    (workspace / "compare.html").write_text("<script>const DATA = __DATA_PLACEHOLDER__;</script>", encoding="utf-8")
    evals_dir = workspace / "evals"
    evals_dir.mkdir(parents=True)
    (evals_dir / "evals.json").write_text(
        json.dumps({"evals": [{"name": "e1", "prompt": "</script><script>alert(1)</script>"}]}),
        encoding="utf-8",
    )
    out_a = workspace / "iteration-1" / "e1" / "variant-A" / "outputs"
    out_a.mkdir(parents=True)
    (out_a / "note.txt").write_text("ok", encoding="utf-8")

    proc = subprocess.run(
        [sys.executable, str(EVAL_COMPARE), str(workspace)],
        capture_output=True,
        text=True,
        timeout=30,
    )
    assert proc.returncode == 0, proc.stderr
    report = (workspace / "compare_report.html").read_text(encoding="utf-8")
    assert "</script><script>alert(1)" not in report
    assert r"\u003c/script>" in report


def test_aggregate_benchmark_appends_paired_without_skill_pass_rates(tmp_path: Path) -> None:
    mod = _load("toolkit_aggregate_benchmark", AGGREGATE_BENCHMARK)
    ws = tmp_path / "iteration-1"
    for idx, (ws_rate, wos_rate) in enumerate([(0.9, 0.5), (0.8, 0.4)], start=1):
        d = ws / f"eval-{idx}"
        (d / "with_skill").mkdir(parents=True)
        (d / "without_skill").mkdir(parents=True)
        (d / "grading.json").write_text(
            json.dumps({"configuration": "with_skill", "pass_rate": ws_rate, "pass_count": 9, "fail_count": 1}),
            encoding="utf-8",
        )
        (d / "grading_without.json").write_text(
            json.dumps({"configuration": "without_skill", "pass_rate": wos_rate, "pass_count": 5, "fail_count": 5}),
            encoding="utf-8",
        )
        (d / "with_skill" / "timing.json").write_text(
            json.dumps({"tokens_total": 1000, "duration_seconds": 10.0}),
            encoding="utf-8",
        )
        (d / "without_skill" / "timing.json").write_text(
            json.dumps({"tokens_total": 800, "duration_seconds": 8.0}),
            encoding="utf-8",
        )

    result = mod.aggregate(ws, "demo-skill")
    assert result["with_skill"]["pass_rate"]["mean"] == 0.85
    assert result["without_skill"]["pass_rate"]["mean"] == 0.45
    assert result["delta"]["pass_rate"] == 0.4
    assert result["without_skill"]["tokens"]["mean"] == 800.0
    assert result["without_skill"]["time_seconds"]["mean"] == 8.0
