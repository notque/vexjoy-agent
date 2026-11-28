"""Unit tests for scripts/prompt-eval.py and scripts/data/prompt-eval-golden.json."""

from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
from pathlib import Path
from typing import Any

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPTS_DIR = REPO_ROOT / "scripts"
HARNESS_PATH = SCRIPTS_DIR / "prompt-eval.py"
GOLDEN_PATH = SCRIPTS_DIR / "data" / "prompt-eval-golden.json"

EXPECTED_CATEGORIES = {
    "scope_creep",
    "partial_delivery",
    "constraint_preservation",
    "ambiguity_detection",
    "handoff_spec_completeness",
    "positive_framing",
}


def _load_harness_module():
    spec = importlib.util.spec_from_file_location("prompt_eval_harness", HARNESS_PATH)
    assert spec is not None and spec.loader is not None
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _run_cli(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(HARNESS_PATH), *args],
        cwd=str(REPO_ROOT),
        capture_output=True,
        text=True,
        encoding="utf-8",
        check=False,
    )


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8", newline="\n")


def test_golden_suite_schema_and_coverage() -> None:
    data = json.loads(GOLDEN_PATH.read_text(encoding="utf-8"))
    assert data["schema_version"] == 1
    cases = data["cases"]
    assert isinstance(cases, list)
    assert len(cases) >= 20

    ids = [c["id"] for c in cases]
    assert len(ids) == len(set(ids)), "case IDs must be unique"

    categories = {c["category"] for c in cases}
    assert categories == EXPECTED_CATEGORIES

    expected_flags = {c["expected_pass"] for c in cases}
    assert expected_flags == {True, False}

    for cat in EXPECTED_CATEGORIES:
        cat_cases = [c for c in cases if c["category"] == cat]
        assert len(cat_cases) >= 4, f"category {cat} should have at least 4 cases"
        assert {c["expected_pass"] for c in cat_cases} == {True, False}

    for case in cases:
        for field in ("id", "category", "user_request", "expected_pass", "checks", "notes"):
            assert field in case, f"case {case.get('id')} missing {field}"
        assert any(
            isinstance(case.get(k), str) and case[k].strip()
            for k in ("candidate_text", "proposed_intent", "dispatch_prompt")
        )


def test_offline_golden_suite_exits_zero_with_full_match() -> None:
    proc = _run_cli()
    assert proc.returncode == 0, proc.stdout + proc.stderr
    assert "24/24 matched" in proc.stdout
    assert "accuracy=1.0000" in proc.stdout


def test_negative_control_mutated_expected_pass_fails_and_names_case(tmp_path: Path) -> None:
    suite = json.loads(GOLDEN_PATH.read_text(encoding="utf-8"))
    target_id = suite["cases"][0]["id"]
    suite["cases"][0]["expected_pass"] = not suite["cases"][0]["expected_pass"]
    mutated_path = tmp_path / "mutated-golden.json"
    _write_json(mutated_path, suite)

    proc = _run_cli("--cases", str(mutated_path))
    assert proc.returncode == 1
    assert target_id in proc.stdout


def test_negative_control_mutated_candidate_triggers_failure(tmp_path: Path) -> None:
    suite = json.loads(GOLDEN_PATH.read_text(encoding="utf-8"))
    target_case = next(c for c in suite["cases"] if c["id"] == "cp-01")
    target_case["candidate_text"] = "Fix the date parsing bug in parser.py and push to origin."
    mutated_path = tmp_path / "mutated-candidate.json"
    _write_json(mutated_path, suite)

    proc = _run_cli("--cases", str(mutated_path))
    assert proc.returncode == 1
    assert "cp-01" in proc.stdout


def test_write_baseline_and_compare_unchanged_improved_regressed(tmp_path: Path) -> None:
    baseline_clean = tmp_path / "baseline-clean.json"
    proc_write = _run_cli("--write-baseline", str(baseline_clean))
    assert proc_write.returncode == 0
    assert baseline_clean.is_file()

    # Unchanged: clean vs clean -> exit 0, delta 0.0
    proc_same = _run_cli("--compare", str(baseline_clean), "--json")
    assert proc_same.returncode == 0
    same_payload = json.loads(proc_same.stdout)
    assert same_payload["comparison"]["overall"]["status"] == "unchanged"
    assert same_payload["comparison"]["overall"]["delta"] == 0.0

    # Prepare a degraded suite with one mismatched case.
    suite = json.loads(GOLDEN_PATH.read_text(encoding="utf-8"))
    suite["cases"][0]["expected_pass"] = not suite["cases"][0]["expected_pass"]
    degraded_cases = tmp_path / "degraded.json"
    _write_json(degraded_cases, suite)

    # Regressed: degraded vs clean baseline -> exit 1, negative delta
    proc_regressed = _run_cli(
        "--cases", str(degraded_cases), "--compare", str(baseline_clean), "--min-accuracy", "0.5", "--json"
    )
    assert proc_regressed.returncode == 1
    reg_payload = json.loads(proc_regressed.stdout)
    assert reg_payload["comparison"]["overall"]["status"] == "regressed"
    assert reg_payload["comparison"]["overall"]["delta"] < 0

    # Write degraded baseline (exit 1 because < 1.0, or exit 0 with --min-accuracy 0.5).
    baseline_degraded = tmp_path / "baseline-degraded.json"
    proc_write_deg = _run_cli(
        "--cases",
        str(degraded_cases),
        "--min-accuracy",
        "0.5",
        "--write-baseline",
        str(baseline_degraded),
    )
    assert proc_write_deg.returncode == 0

    # Improved: clean vs degraded baseline -> exit 0, positive delta
    proc_improved = _run_cli("--compare", str(baseline_degraded), "--json")
    assert proc_improved.returncode == 0
    imp_payload = json.loads(proc_improved.stdout)
    assert imp_payload["comparison"]["overall"]["status"] == "improved"
    assert imp_payload["comparison"]["overall"]["delta"] > 0


def test_category_filter_and_json_output_shape() -> None:
    proc = _run_cli("--category", "scope_creep", "--json")
    assert proc.returncode == 0
    payload = json.loads(proc.stdout)
    for key in ("schema_version", "mode", "total", "matched", "accuracy", "by_category", "results"):
        assert key in payload
    assert payload["schema_version"] == 1
    assert payload["mode"] == "offline"
    assert payload["total"] == 4
    assert payload["matched"] == 4
    assert payload["accuracy"] == 1.0
    assert list(payload["by_category"].keys()) == ["scope_creep"]
    assert all(row["category"] == "scope_creep" for row in payload["results"])


def test_unknown_category_exits_two() -> None:
    proc = _run_cli("--category", "does_not_exist")
    assert proc.returncode == 2
    assert "no cases found" in proc.stderr


def test_live_jev_mode_uses_monkeypatched_evaluator_without_network(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    if str(SCRIPTS_DIR) not in sys.path:
        sys.path.insert(0, str(SCRIPTS_DIR))
    import jev_intent_align

    calls: list[dict[str, Any]] = []

    def _fake_evaluate_alignment(
        request: str,
        route: dict[str, Any],
        intent: str | None,
        timeout: float = 8.0,
    ) -> dict[str, Any]:
        calls.append({"request": request, "route": route, "intent": intent, "timeout": timeout})
        return {
            "available": True,
            "source": "mock",
            "alignment": "aligned",
            "aligned": True,
            "clarification_needed": False,
            "issues": [],
            "scores": {"can_proceed_with_proposed_intent": 0.91},
            "reason": None,
        }

    monkeypatch.setattr(jev_intent_align, "evaluate_alignment", _fake_evaluate_alignment)

    harness = _load_harness_module()
    exit_code = harness.main(["--live-jev", "--json", "--timeout", "3.5"])
    assert exit_code == 0

    captured = capsys.readouterr()
    payload = json.loads(captured.out)
    assert payload["mode"] == "live-jev"
    assert payload["total"] == 24
    assert payload["matched"] == 24

    intent_categories = {"scope_creep", "partial_delivery", "constraint_preservation", "ambiguity_detection"}
    expected_live_count = sum(1 for r in payload["results"] if r["category"] in intent_categories)
    assert len(calls) == expected_live_count == 16
    assert all(c["timeout"] == 3.5 for c in calls)

    for row in payload["results"]:
        if row["category"] in intent_categories:
            assert "live_jev" in row
            assert row["live_jev"]["source"] == "mock"
            assert row["live_jev"]["scores"]["can_proceed_with_proposed_intent"] == 0.91
        else:
            assert "live_jev" not in row


def test_handoff_effort_override_and_positive_framing_edge_cases() -> None:
    harness = _load_harness_module()

    override_case = {
        "id": "hs-override",
        "category": "handoff_spec_completeness",
        "user_request": "Deep architectural review",
        "candidate_text": (
            "[do-route] agent=general-purpose skill=architecture complexity=complex model=inherit effort=max health=-\n"
            "[effort-override: owner explicitly approved max effort]\n\n"
            "**Request (verbatim):**\nDeep architectural review\n\n"
            "**Acceptance criteria:**\n- Review written\n\n"
            "## Repo state\nClean"
        ),
        "expected_pass": True,
        "checks": {
            "required_blocks": ["**Request (verbatim):**", "**Acceptance criteria:**", "## Repo state"],
            "gated_complexities": ["medium", "complex"],
            "disallowed_efforts": ["xhigh", "max"],
        },
        "notes": "Explicit override permits effort=max.",
    }
    res_override = harness.evaluate_case(override_case)
    assert res_override["actual_pass"] is True
    assert res_override["matched"] is True

    paired_next_sentence = {
        "id": "pf-next",
        "category": "positive_framing",
        "user_request": "Write a lint rule",
        "candidate_text": "Don't skip formatting checks. Run ruff format --check before committing.",
        "expected_pass": True,
        "checks": {"max_unpaired_negatives": 0, "check_editorial_negative_framing": True},
        "notes": "Negative directive paired with immediate concrete positive sentence.",
    }
    res_paired = harness.evaluate_case(paired_next_sentence)
    assert res_paired["actual_pass"] is True
    assert res_paired["matched"] is True

    clarifying_case = {
        "id": "amb-clarify",
        "category": "ambiguity_detection",
        "user_request": "make it faster",
        "candidate_text": "Before optimizing, please clarify which endpoint and p99 latency target we should measure?",
        "expected_pass": True,
        "checks": {"min_specificity_signals": 3, "requires_clarification": True},
        "notes": "Candidate appropriately asks for clarification on an underspecified prompt.",
    }
    res_clarify = harness.evaluate_case(clarifying_case)
    assert res_clarify["actual_pass"] is True
    assert res_clarify["matched"] is True
