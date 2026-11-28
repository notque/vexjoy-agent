"""Unit and CLI tests for scripts/prompt-diagnostics.py."""

from __future__ import annotations

import json
import sqlite3
import subprocess
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "scripts" / "prompt-diagnostics.py"
HOOKS_LIB = ROOT / "hooks" / "lib"
if str(HOOKS_LIB) not in sys.path:
    sys.path.insert(0, str(HOOKS_LIB))

import learning_db_v2 as ldb


def _run_cli(*args: str, env_override: dict[str, str] | None = None) -> subprocess.CompletedProcess[str]:
    env = None
    if env_override is not None:
        import os

        env = {**os.environ, **env_override}
    return subprocess.run(
        [sys.executable, str(SCRIPT), *args],
        capture_output=True,
        text=True,
        env=env,
        timeout=15,
        check=False,
    )


def _init_temp_db(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> Path:
    learning_dir = tmp_path / "learning"
    learning_dir.mkdir(parents=True, exist_ok=True)
    monkeypatch.setenv("CLAUDE_LEARNING_DIR", str(learning_dir))
    monkeypatch.setattr(ldb, "_initialized", False)
    ldb.init_db()
    return learning_dir / "learning.db"


def _iso_days_ago(days_ago: float) -> str:
    dt = datetime.now(timezone.utc) - timedelta(days=days_ago)
    return dt.strftime("%Y-%m-%d %H:%M:%S")


def test_missing_db_exits_zero_without_creating_file(tmp_path: Path) -> None:
    missing = tmp_path / "does-not-exist" / "learning.db"
    res = _run_cli("--db", str(missing))
    assert res.returncode == 0
    assert "No learning database found" in res.stdout
    assert not missing.exists()
    assert not missing.parent.exists()

    res_json = _run_cli("--db", str(missing), "--json")
    assert res_json.returncode == 0
    payload = json.loads(res_json.stdout)
    assert payload["db_exists"] is False
    assert payload["cohorts"] == []
    assert payload["recommendations"] == []
    assert payload["alignment_summary"]["total_judgments"] == 0
    assert payload["handoff_health"]["scored_dispatches"] == 0


def test_empty_initialized_db_exits_zero_with_empty_message(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    db_path = _init_temp_db(monkeypatch, tmp_path)
    res = _run_cli("--db", str(db_path))
    assert res.returncode == 0
    assert "No prompt alignment or handoff telemetry recorded" in res.stdout

    res_json = _run_cli("--db", str(db_path), "--json")
    assert res_json.returncode == 0
    payload = json.loads(res_json.stdout)
    assert payload["db_exists"] is True
    assert payload["cohorts"] == []
    assert payload["recommendations"] == []


def test_empty_sqlite_without_tables_exits_zero(tmp_path: Path) -> None:
    db_path = tmp_path / "blank.db"
    sqlite3.connect(db_path).close()
    res = _run_cli("--db", str(db_path), "--json")
    assert res.returncode == 0
    payload = json.loads(res.stdout)
    assert payload["db_exists"] is True
    assert payload["alignment_summary"]["total_judgments"] == 0
    assert payload["handoff_health"]["scored_dispatches"] == 0


def test_drift_aggregation_issues_handoff_and_recommendations(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    db_path = _init_temp_db(monkeypatch, tmp_path)

    # Cohort 1: claude / opus / low -> 6 proposed judgments, 3 drift (50% >= 20%), 2 clarifications
    for idx in range(6):
        differs = idx < 3
        clarify = idx in (3, 4)
        route_mis = idx == 0
        issues = []
        if differs:
            issues.append("proposed intent adds unrequested work")
        if clarify:
            issues.append("essential clarification is needed")
        if route_mis:
            issues.append("selected route omits material scope")
        assert ldb.record_jev_intent_alignment(
            phase="proposed",
            transport="vercel",
            model="typesafe-ai/jev-1.14.0",
            agent_model="claude-opus-5",
            agent_effort="low",
            agent_runtime="claude",
            alignment="review" if (differs or clarify or route_mis) else "aligned",
            materially_differs=differs,
            route_mismatch=route_mis,
            clarification_needed=clarify,
            issues=issues,
            ts=_iso_days_ago(1),
        )

    # Cohort 2: codex / gpt-test / medium -> 5 proposed judgments, 0 drift, 1 clarification
    for idx in range(5):
        clarify = idx == 0
        assert ldb.record_jev_intent_alignment(
            phase="proposed",
            transport="direct",
            model="typesafe-ai/jev-1.14.0",
            agent_model="gpt-test",
            agent_effort="medium",
            agent_runtime="codex",
            alignment="review" if clarify else "aligned",
            materially_differs=False,
            route_mismatch=False,
            clarification_needed=clarify,
            issues=["essential clarification is needed"] if clarify else [],
            ts=_iso_days_ago(2),
        )

    # Small cohort (< 5 measured) with 100% drift should NOT trigger high_drift_cohort
    for _ in range(3):
        assert ldb.record_jev_intent_alignment(
            phase="proposed",
            transport="vercel",
            agent_model="claude-sonnet-5",
            agent_effort="low",
            agent_runtime="claude",
            alignment="review",
            materially_differs=True,
            route_mismatch=False,
            clarification_needed=True,
            issues=["proposed intent drops explicit constraints"],
            ts=_iso_days_ago(1),
        )

    # Error row with NULL materially_differs should increment judgments but not measured
    assert ldb.record_jev_intent_alignment(
        phase="proposed",
        transport="vercel",
        agent_model="claude-opus-5",
        agent_effort="low",
        agent_runtime="claude",
        alignment="error",
        materially_differs=None,
        route_mismatch=None,
        clarification_needed=False,
        issues=[],
        ts=_iso_days_ago(1),
    )

    # Baseline phase row must be excluded from proposed-intent diagnostics
    assert ldb.record_jev_intent_alignment(
        phase="baseline",
        transport="vercel",
        agent_model="baseline-model",
        agent_effort="low",
        agent_runtime="antigravity",
        alignment="review",
        materially_differs=True,
        ts=_iso_days_ago(1),
    )

    # Handoff spec telemetry: 2 low-spec dispatches, 1 complete dispatch, 1 main-thread route (excluded)
    ldb.record_evidence_route_decision(
        session_id="s1",
        agent="general-purpose",
        skill="testing",
        complexity="medium",
        spec_score=3,
        spec_missing="Request (verbatim),## Repo state,Acceptance criteria",
        prompt_chars=500,
        outcome_basis="route_fit:underspecified",
    )
    ldb.record_evidence_route_decision(
        session_id="s1",
        agent="general-purpose",
        skill="testing",
        complexity="complex",
        spec_score=4,
        spec_missing="## Repo state,Prior results",
        prompt_chars=800,
        outcome_basis="default_no_complaint",
    )
    ldb.record_evidence_route_decision(
        session_id="s1",
        agent="general-purpose",
        skill="testing",
        complexity="medium",
        spec_score=7,
        spec_missing="",
        prompt_chars=2400,
        outcome_basis="default_no_complaint",
    )
    ldb.record_evidence_route_decision(
        session_id="s1",
        agent="main",
        skill="testing",
        complexity="simple",
        spec_score=0,
        spec_missing="Request (verbatim),## Repo state",
        prompt_chars=40,
    )

    res = _run_cli("--db", str(db_path), "--days", "30", "--json")
    assert res.returncode == 0
    payload = json.loads(res.stdout)

    # Verify JSON schema top-level keys
    assert set(payload) >= {
        "db_path",
        "db_exists",
        "window_days",
        "drift_threshold",
        "cohorts",
        "alignment_summary",
        "handoff_health",
        "recommendations",
    }

    cohorts_by_key = {(c["runtime"], c["agent_model"], c["agent_effort"]): c for c in payload["cohorts"]}
    assert ("antigravity", "baseline-model", "low") not in cohorts_by_key

    c_opus = cohorts_by_key[("claude", "claude-opus-5", "low")]
    assert c_opus["judgments"] == 7  # 6 measured + 1 error
    assert c_opus["measured"] == 6
    assert c_opus["material_differences"] == 3
    assert c_opus["drift_rate"] == pytest.approx(0.5)
    assert c_opus["route_mismatches"] == 1
    assert c_opus["clarifications"] == 2

    c_codex = cohorts_by_key[("codex", "gpt-test", "medium")]
    assert c_codex["judgments"] == 5
    assert c_codex["measured"] == 5
    assert c_codex["material_differences"] == 0
    assert c_codex["drift_rate"] == 0.0

    # Total proposed judgments = 7 + 5 + 3 = 15; clarifications = 2 + 1 + 3 = 6 (40% >= 25%)
    summary = payload["alignment_summary"]
    assert summary["total_judgments"] == 15
    assert summary["measured_judgments"] == 14
    assert summary["signals"]["materially_differs"] == 6
    assert summary["signals"]["route_mismatch"] == 1
    assert summary["signals"]["clarification_needed"] == 6
    assert summary["signals"]["clarification_rate"] == pytest.approx(6 / 15, abs=1e-4)
    assert summary["alignment_statuses"]["error"] == 1
    issue_counts = {item["issue"]: item["count"] for item in summary["top_issues"]}
    assert issue_counts["proposed intent adds unrequested work"] == 3
    assert issue_counts["essential clarification is needed"] == 3
    assert issue_counts["proposed intent drops explicit constraints"] == 3

    # Handoff health (main excluded -> 3 scored, 2 low_spec < 5)
    handoff = payload["handoff_health"]
    assert handoff["scored_dispatches"] == 3
    assert handoff["low_spec_count"] == 2
    assert handoff["low_spec_rate"] == pytest.approx(2 / 3, abs=1e-4)
    missing_counts = {item["label"]: item["count"] for item in handoff["top_missing_labels"]}
    assert missing_counts["## Repo state"] == 2
    assert missing_counts["Request (verbatim)"] == 1
    assert missing_counts["Acceptance criteria"] == 1
    assert missing_counts["Prior results"] == 1
    assert handoff["outcome_basis_counts"] == {
        "default_no_complaint": 2,
        "route_fit:underspecified": 1,
    }

    # Recommendations: high_drift_cohort (only claude/opus/low), missing_runtime_coverage (antigravity),
    # high_clarification_rate, and low_handoff_spec
    rec_by_code = {}
    for rec in payload["recommendations"]:
        rec_by_code.setdefault(rec["code"], []).append(rec["message"])

    assert len(rec_by_code["high_drift_cohort"]) == 1
    assert "claude-opus-5" in rec_by_code["high_drift_cohort"][0]
    assert "--strict-scope" in rec_by_code["high_drift_cohort"][0]
    assert "claude-sonnet-5" not in rec_by_code["high_drift_cohort"][0]

    assert len(rec_by_code["missing_runtime_coverage"]) == 1
    assert "antigravity" in rec_by_code["missing_runtime_coverage"][0]
    assert "claude" not in rec_by_code["missing_runtime_coverage"][0]
    assert "codex" not in rec_by_code["missing_runtime_coverage"][0]

    assert len(rec_by_code["high_clarification_rate"]) == 1
    assert "/prompt" in rec_by_code["high_clarification_rate"][0]

    assert len(rec_by_code["low_handoff_spec"]) == 1
    assert "pretool-dispatch-spec-gate" in rec_by_code["low_handoff_spec"][0]

    # Human report renders cleanly without crashing
    res_human = _run_cli("--db", str(db_path), "--days", "30")
    assert res_human.returncode == 0
    assert "Prompt diagnostics" in res_human.stdout
    assert "claude-opus-5" in res_human.stdout
    assert "## Handoff spec health" in res_human.stdout
    assert "## Recommendations" in res_human.stdout


def test_days_window_and_custom_drift_threshold(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    db_path = _init_temp_db(monkeypatch, tmp_path)

    # 5 recent judgments with 1 drift (20%)
    for idx in range(5):
        assert ldb.record_jev_intent_alignment(
            phase="proposed",
            transport="vercel",
            agent_model="gemini-4",
            agent_effort="medium",
            agent_runtime="antigravity",
            alignment="review" if idx == 0 else "aligned",
            materially_differs=(idx == 0),
            route_mismatch=False,
            clarification_needed=False,
            ts=_iso_days_ago(2),
        )

    # 10 old judgments outside a 7-day window
    for _ in range(10):
        assert ldb.record_jev_intent_alignment(
            phase="proposed",
            transport="vercel",
            agent_model="old-model",
            agent_effort="low",
            agent_runtime="claude",
            alignment="review",
            materially_differs=True,
            ts=_iso_days_ago(45),
        )

    # Insert an old evidence_route_decisions row directly to test created_at windowing
    with sqlite3.connect(db_path) as conn:
        conn.execute(
            "INSERT INTO evidence_route_decisions "
            "(decision_id, route_key, agent, spec_score, spec_missing, created_at, updated_at) "
            "VALUES (?, ?, ?, ?, ?, ?, ?)",
            (
                "old-dec-1",
                "general-purpose:testing",
                "general-purpose",
                1,
                "## Repo state",
                _iso_days_ago(45),
                _iso_days_ago(45),
            ),
        )
        conn.commit()

    # 7-day window excludes the 45-day-old rows; threshold 0.25 excludes 20% drift
    res = _run_cli("--db", str(db_path), "--days", "7", "--drift-threshold", "0.25", "--json")
    assert res.returncode == 0
    payload = json.loads(res.stdout)
    assert payload["alignment_summary"]["total_judgments"] == 5
    assert payload["handoff_health"]["scored_dispatches"] == 0
    rec_codes = [r["code"] for r in payload["recommendations"]]
    assert "high_drift_cohort" not in rec_codes
    assert "low_handoff_spec" not in rec_codes

    # Raising window to 60 days includes the old rows and flags old-model
    res_wide = _run_cli("--db", str(db_path), "--days", "60", "--drift-threshold", "0.25", "--json")
    assert res_wide.returncode == 0
    wide = json.loads(res_wide.stdout)
    assert wide["alignment_summary"]["total_judgments"] == 15
    assert wide["handoff_health"]["scored_dispatches"] == 1
    assert any(r["code"] == "high_drift_cohort" and "old-model" in r["message"] for r in wide["recommendations"])


def test_corrupt_non_sqlite_file_exits_zero_cleanly(tmp_path: Path) -> None:
    corrupt = tmp_path / "corrupt.db"
    corrupt.write_bytes(b"not a valid sqlite database header\x00\xff\xfe")

    res_json = _run_cli("--db", str(corrupt), "--json")
    assert res_json.returncode == 0
    payload = json.loads(res_json.stdout)
    assert payload["db_exists"] is False
    assert payload["cohorts"] == []
    assert payload["alignment_summary"]["total_judgments"] == 0
    assert payload["handoff_health"]["scored_dispatches"] == 0
    assert payload["recommendations"] == []

    res_human = _run_cli("--db", str(corrupt))
    assert res_human.returncode == 0
    assert "No learning database found" in res_human.stdout


def test_pre_v16_alignment_table_without_agent_profile_columns_exits_zero(tmp_path: Path) -> None:
    db_path = tmp_path / "legacy.db"
    with sqlite3.connect(db_path) as conn:
        conn.execute(
            "CREATE TABLE jev_intent_alignments ("
            "id INTEGER PRIMARY KEY AUTOINCREMENT, "
            "ts TEXT NOT NULL, "
            "phase TEXT NOT NULL, "
            "alignment TEXT NOT NULL, "
            "materially_differs INTEGER, "
            "route_mismatch INTEGER, "
            "clarification_needed INTEGER, "
            "issues_json TEXT"
            ")"
        )
        conn.execute(
            "INSERT INTO jev_intent_alignments "
            "(ts, phase, alignment, materially_differs, route_mismatch, clarification_needed, issues_json) "
            "VALUES (?, 'proposed', 'review', 1, 0, 0, ?)",
            (_iso_days_ago(1), json.dumps(["proposed intent adds unrequested work"])),
        )
        conn.commit()

    res = _run_cli("--db", str(db_path), "--json")
    assert res.returncode == 0
    payload = json.loads(res.stdout)
    assert payload["db_exists"] is True
    assert payload["alignment_summary"]["total_judgments"] == 1
    assert payload["alignment_summary"]["signals"]["materially_differs"] == 1
    assert len(payload["cohorts"]) == 1
    assert payload["cohorts"][0]["runtime"] is None
    assert payload["cohorts"][0]["agent_model"] is None
    assert payload["cohorts"][0]["agent_effort"] is None
    assert payload["cohorts"][0]["judgments"] == 1
