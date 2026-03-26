"""Tests for ADR-105: pass@k metrics.

Covers:
- run_vector emission from run_eval.run_eval()
- pass@k and pass^k computation in aggregate_benchmark
- baseline write and diff via baseline.py CLI
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path
from unittest.mock import patch

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
BASELINE_SCRIPT = REPO_ROOT / "scripts" / "skill_eval" / "baseline.py"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _run_baseline(*args: str, expect_rc: int = 0) -> subprocess.CompletedProcess[str]:
    """Run baseline.py with the given arguments."""
    result = subprocess.run(
        [sys.executable, str(BASELINE_SCRIPT), *args],
        capture_output=True,
        text=True,
        cwd=str(REPO_ROOT),
    )
    assert result.returncode == expect_rc, (
        f"Expected rc={expect_rc}, got {result.returncode}\nstdout: {result.stdout}\nstderr: {result.stderr}"
    )
    return result


def _pop(trigger_map: dict[str, list[bool]], query: str, call_count: dict[str, int]) -> bool:
    """Return next value from trigger_map[query], cycling if needed."""
    idx = call_count.get(query, 0)
    call_count[query] = idx + 1
    values = trigger_map.get(query, [False])
    return values[idx % len(values)]


# ---------------------------------------------------------------------------
# run_vector emission from the routing evaluator
# ---------------------------------------------------------------------------


class TestRunVector:
    """run_eval() must emit run_vector in each query result."""

    def _invoke(self, trigger_map: dict, queries: list[dict], runs_per_query: int) -> dict:
        """Invoke run_eval with run_single_query patched to return deterministic results.

        ProcessPoolExecutor pickles work to subprocesses, so mocks don't cross the
        process boundary.  We patch the executor class itself to use threads instead,
        which share the patched module namespace.
        """
        from concurrent.futures import ThreadPoolExecutor

        from scripts.skill_eval.run_eval import run_eval

        call_count: dict[str, int] = {}

        with (
            patch(
                "scripts.skill_eval.run_eval.run_single_query",
                side_effect=lambda q, *a, **kw: _pop(trigger_map, q, call_count),  # noqa: ARG005
            ),
            patch("scripts.skill_eval.run_eval.ProcessPoolExecutor", ThreadPoolExecutor),
        ):
            return run_eval(
                eval_set=queries,
                skill_name="test-skill",
                description="desc",
                num_workers=1,
                timeout=10,
                project_root=Path("/tmp"),
                runs_per_query=runs_per_query,
            )

    def test_run_vector_present(self):
        output = self._invoke(
            {"q-a": [True, False, True]},
            [{"query": "q-a", "should_trigger": True}],
            3,
        )
        result = output["results"][0]
        assert "run_vector" in result
        assert isinstance(result["run_vector"], list)
        assert len(result["run_vector"]) == 3

    def test_run_vector_values_correct(self):
        output = self._invoke(
            {"q-b": [True, False, True]},
            [{"query": "q-b", "should_trigger": True}],
            3,
        )
        result = output["results"][0]
        assert result["triggers"] == 2
        assert result["run_vector"].count(True) == 2
        assert result["run_vector"].count(False) == 1

    def test_single_run_vector(self):
        output = self._invoke(
            {"q-c": [True]},
            [{"query": "q-c", "should_trigger": True}],
            1,
        )
        assert output["results"][0]["run_vector"] == [True]

    def test_all_false_vector(self):
        output = self._invoke(
            {"q-d": [False, False]},
            [{"query": "q-d", "should_trigger": True}],
            2,
        )
        assert output["results"][0]["run_vector"] == [False, False]


# ---------------------------------------------------------------------------
# pass@k and pass^k computation
# ---------------------------------------------------------------------------


class TestPassKStats:
    """compute_passk_stats() unit tests."""

    def _stats(self, vectors):
        from scripts.skill_eval.aggregate_benchmark import compute_passk_stats

        return compute_passk_stats(vectors)

    def test_empty(self):
        s = self._stats([])
        assert s == {"pass_at_k": 0.0, "pass_all_k": 0.0, "k": 0}

    def test_all_pass_k1(self):
        s = self._stats([[True], [True], [True]])
        assert s["pass_at_k"] == 1.0
        assert s["pass_all_k"] == 1.0
        assert s["k"] == 1

    def test_all_fail_k1(self):
        s = self._stats([[False], [False]])
        assert s["pass_at_k"] == 0.0
        assert s["pass_all_k"] == 0.0

    def test_pass_at_k_any_semantics(self):
        # 2 of 3 queries have at least one True
        vectors = [[True, False, False], [False, False, False], [False, True, True]]
        s = self._stats(vectors)
        assert s["pass_at_k"] == pytest.approx(2 / 3, abs=1e-4)

    def test_pass_all_k_all_semantics(self):
        # Only first query has all True
        vectors = [[True, True, True], [True, False, True], [False, False, False]]
        s = self._stats(vectors)
        assert s["pass_all_k"] == pytest.approx(1 / 3, abs=1e-4)

    def test_k_is_max_length(self):
        vectors = [[True, True], [True, True, False]]
        assert self._stats(vectors)["k"] == 3

    def test_empty_vector_treated_as_false(self):
        # [] → [False], so pass_at = 1/2
        s = self._stats([[], [True]])
        assert s["pass_at_k"] == pytest.approx(0.5, abs=1e-4)
        assert s["pass_all_k"] == pytest.approx(0.5, abs=1e-4)

    def test_mixed_k3(self):
        # 2 queries pass@k, 1 passes^k
        vectors = [[True, False], [True, True], [False, False]]
        s = self._stats(vectors)
        assert s["pass_at_k"] == pytest.approx(2 / 3, abs=1e-4)
        assert s["pass_all_k"] == pytest.approx(1 / 3, abs=1e-4)


class TestAggregatePassK:
    """aggregate_results() surfaces pass_at_k and pass_all_k per config."""

    def _grading(self, pass_rate: float, run_vector=None) -> dict:
        g = {
            "summary": {
                "pass_rate": pass_rate,
                "passed": int(pass_rate * 10),
                "failed": 10 - int(pass_rate * 10),
                "total": 10,
            },
            "timing": {"total_duration_seconds": 1.0},
        }
        if run_vector is not None:
            g["run_vector"] = run_vector
        return g

    def test_pass_at_k_present(self, tmp_path):
        from scripts.skill_eval.aggregate_benchmark import aggregate_results, load_run_results

        bench = tmp_path / "b1"
        rd = bench / "eval-0" / "with_skill" / "run-1"
        rd.mkdir(parents=True)
        (rd / "grading.json").write_text(json.dumps(self._grading(1.0, [True, True])))

        summary = aggregate_results(load_run_results(bench))
        ws = summary["with_skill"]
        assert "pass_at_k" in ws
        assert "pass_all_k" in ws
        assert "k" in ws

    def test_delta_has_pass_at_k(self, tmp_path):
        from scripts.skill_eval.aggregate_benchmark import aggregate_results, load_run_results

        bench = tmp_path / "b2"
        for cfg, rv, pr in [("with_skill", [True], 1.0), ("without_skill", [False], 0.0)]:
            rd = bench / "eval-0" / cfg / "run-1"
            rd.mkdir(parents=True)
            (rd / "grading.json").write_text(json.dumps(self._grading(pr, rv)))

        delta = aggregate_results(load_run_results(bench))["delta"]
        assert "pass_at_k" in delta
        assert "pass_all_k" in delta

    def test_backward_compat_full_pass(self, tmp_path):
        """pass_rate=1.0 without run_vector → pass_at_k=1.0."""
        from scripts.skill_eval.aggregate_benchmark import aggregate_results, load_run_results

        bench = tmp_path / "b3"
        rd = bench / "eval-0" / "with_skill" / "run-1"
        rd.mkdir(parents=True)
        (rd / "grading.json").write_text(json.dumps(self._grading(1.0)))

        ws = aggregate_results(load_run_results(bench))["with_skill"]
        assert ws["pass_at_k"] == 1.0
        assert ws["pass_all_k"] == 1.0

    def test_backward_compat_partial_pass(self, tmp_path):
        """pass_rate < 1.0 without run_vector → treated as failed run."""
        from scripts.skill_eval.aggregate_benchmark import aggregate_results, load_run_results

        bench = tmp_path / "b4"
        rd = bench / "eval-0" / "with_skill" / "run-1"
        rd.mkdir(parents=True)
        (rd / "grading.json").write_text(json.dumps(self._grading(0.5)))

        ws = aggregate_results(load_run_results(bench))["with_skill"]
        assert ws["pass_at_k"] == 0.0
        assert ws["pass_all_k"] == 0.0


# ---------------------------------------------------------------------------
# baseline.py write and diff
# ---------------------------------------------------------------------------


def _make_run_output(run_vectors: list[list[bool]], skill: str = "sk") -> dict:
    """Build a minimal run output dict with run_vector populated."""
    results = [
        {
            "query": f"q{i}",
            "should_trigger": True,
            "run_vector": rv,
            "pass": any(rv),
            "triggers": sum(rv),
            "runs": len(rv),
            "trigger_rate": sum(rv) / len(rv) if rv else 0.0,
        }
        for i, rv in enumerate(run_vectors)
    ]
    return {
        "skill_name": skill,
        "description": "d",
        "results": results,
        "summary": {
            "total": len(results),
            "passed": sum(1 for r in results if r["pass"]),
            "failed": sum(1 for r in results if not r["pass"]),
        },
    }


class TestBaselineWrite:
    def test_creates_file(self, tmp_path):
        inp = tmp_path / "run.json"
        inp.write_text(json.dumps(_make_run_output([[True, True, True]])))
        bl = tmp_path / "baseline.json"

        _run_baseline("write", "--input", str(inp), "--skill", "sk", "--baseline", str(bl))

        assert bl.exists()
        entry = json.loads(bl.read_text())["sk"]
        assert "pass_at_k" in entry
        assert "pass_all_k" in entry
        assert "k" in entry
        assert "timestamp" in entry

    def test_correct_values(self, tmp_path):
        # q0: all True (passes both), q1: mixed (passes@k only)
        inp = tmp_path / "run.json"
        inp.write_text(json.dumps(_make_run_output([[True, True], [True, False]])))
        bl = tmp_path / "baseline.json"

        _run_baseline("write", "--input", str(inp), "--skill", "sk", "--baseline", str(bl))

        entry = json.loads(bl.read_text())["sk"]
        assert entry["pass_at_k"] == pytest.approx(1.0, abs=1e-4)
        assert entry["pass_all_k"] == pytest.approx(0.5, abs=1e-4)
        assert entry["k"] == 2

    def test_updates_existing_skill(self, tmp_path):
        bl = tmp_path / "baseline.json"
        # First write: passing
        inp1 = tmp_path / "r1.json"
        inp1.write_text(json.dumps(_make_run_output([[True]])))
        _run_baseline("write", "--input", str(inp1), "--skill", "sk", "--baseline", str(bl))
        # Second write: failing
        inp2 = tmp_path / "r2.json"
        inp2.write_text(json.dumps(_make_run_output([[False]])))
        _run_baseline("write", "--input", str(inp2), "--skill", "sk", "--baseline", str(bl))

        assert json.loads(bl.read_text())["sk"]["pass_at_k"] == 0.0

    def test_preserves_other_skills(self, tmp_path):
        bl = tmp_path / "baseline.json"
        bl.write_text(json.dumps({"other": {"pass_at_k": 0.9, "pass_all_k": 0.8, "k": 3}}))

        inp = tmp_path / "run.json"
        inp.write_text(json.dumps(_make_run_output([[True]])))
        _run_baseline("write", "--input", str(inp), "--skill", "new", "--baseline", str(bl))

        data = json.loads(bl.read_text())
        assert "other" in data
        assert "new" in data

    def test_missing_input_exits_2(self, tmp_path):
        _run_baseline(
            "write",
            "--input",
            str(tmp_path / "nope.json"),
            "--skill",
            "sk",
            "--baseline",
            str(tmp_path / "b.json"),
            expect_rc=2,
        )

    def test_backward_compat_no_run_vector(self, tmp_path):
        """Input without run_vector falls back to triggers > 0."""
        data = {
            "skill_name": "sk",
            "description": "d",
            "results": [
                {"query": "q0", "should_trigger": True, "triggers": 3, "runs": 3, "pass": True, "trigger_rate": 1.0},
                {"query": "q1", "should_trigger": True, "triggers": 0, "runs": 3, "pass": False, "trigger_rate": 0.0},
            ],
            "summary": {"total": 2, "passed": 1, "failed": 1},
        }
        inp = tmp_path / "run.json"
        inp.write_text(json.dumps(data))
        bl = tmp_path / "baseline.json"

        _run_baseline("write", "--input", str(inp), "--skill", "compat", "--baseline", str(bl))

        entry = json.loads(bl.read_text())["compat"]
        assert entry["pass_at_k"] == pytest.approx(0.5, abs=1e-4)


class TestBaselineDiff:
    def _bl_file(self, tmp_path: Path, entries: dict) -> Path:
        p = tmp_path / "baseline.json"
        p.write_text(json.dumps(entries))
        return p

    def _inp(self, tmp_path: Path, run_vectors: list[list[bool]], name: str = "run.json") -> Path:
        p = tmp_path / name
        p.write_text(json.dumps(_make_run_output(run_vectors)))
        return p

    def test_no_regression_exits_0(self, tmp_path):
        bl = self._bl_file(tmp_path, {"sk": {"pass_at_k": 1.0, "pass_all_k": 1.0, "k": 1}})
        inp = self._inp(tmp_path, [[True]])
        _run_baseline("diff", "--input", str(inp), "--skill", "sk", "--baseline", str(bl), expect_rc=0)

    def test_regression_exits_1(self, tmp_path):
        bl = self._bl_file(tmp_path, {"sk": {"pass_at_k": 0.9, "pass_all_k": 0.9, "k": 3}})
        inp = self._inp(tmp_path, [[False]])
        _run_baseline("diff", "--input", str(inp), "--skill", "sk", "--baseline", str(bl), expect_rc=1)

    def test_small_drop_within_threshold_exits_0(self, tmp_path):
        # Baseline=0.9, current=0.857 (6/7), drop=0.043 < 0.05
        bl = self._bl_file(tmp_path, {"sk": {"pass_at_k": 0.9, "pass_all_k": 0.9, "k": 1}})
        vectors = [[i < 6] for i in range(7)]  # 6 True, 1 False
        inp = self._inp(tmp_path, vectors)
        _run_baseline(
            "diff",
            "--input",
            str(inp),
            "--skill",
            "sk",
            "--baseline",
            str(bl),
            "--threshold",
            "0.05",
            expect_rc=0,
        )

    def test_custom_threshold_absorbs_large_drop(self, tmp_path):
        bl = self._bl_file(tmp_path, {"sk": {"pass_at_k": 0.9, "pass_all_k": 0.9, "k": 1}})
        inp = self._inp(tmp_path, [[False]])  # drop=0.9
        # threshold=0.95 → drop=0.9 < 0.95 → no regression
        _run_baseline(
            "diff",
            "--input",
            str(inp),
            "--skill",
            "sk",
            "--baseline",
            str(bl),
            "--threshold",
            "0.95",
            expect_rc=0,
        )

    def test_missing_skill_in_baseline_exits_0(self, tmp_path):
        bl = self._bl_file(tmp_path, {"other": {"pass_at_k": 1.0, "pass_all_k": 1.0, "k": 1}})
        inp = self._inp(tmp_path, [[True]])
        _run_baseline("diff", "--input", str(inp), "--skill", "unknown", "--baseline", str(bl), expect_rc=0)

    def test_missing_baseline_file_exits_0(self, tmp_path):
        inp = self._inp(tmp_path, [[True]])
        _run_baseline(
            "diff",
            "--input",
            str(inp),
            "--skill",
            "sk",
            "--baseline",
            str(tmp_path / "nope.json"),
            expect_rc=0,
        )

    def test_regression_output_contains_skill_name(self, tmp_path):
        bl = self._bl_file(tmp_path, {"my-skill": {"pass_at_k": 0.9, "pass_all_k": 0.8, "k": 3}})
        inp = self._inp(tmp_path, [[False]])
        result = _run_baseline(
            "diff",
            "--input",
            str(inp),
            "--skill",
            "my-skill",
            "--baseline",
            str(bl),
            expect_rc=1,
        )
        assert "my-skill" in result.stdout
        assert "REGRESSION" in result.stdout
