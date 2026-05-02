"""Tests for scripts/toolkit-health.py."""

from __future__ import annotations

import importlib
import json
import sqlite3
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import patch

import pytest

# ---------------------------------------------------------------------------
# Imports under test — resolve relative to repo root
# ---------------------------------------------------------------------------

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
_SCRIPTS_DIR = str(REPO_ROOT / "scripts")
if _SCRIPTS_DIR not in sys.path:
    sys.path.insert(0, _SCRIPTS_DIR)

th = importlib.import_module("toolkit-health")


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def default_config() -> th.HealthConfig:
    return th.HealthConfig()


@pytest.fixture
def fresh_state_dir(tmp_path: Path) -> Path:
    state = tmp_path / "state"
    state.mkdir()
    return state


@pytest.fixture
def learning_db(tmp_path: Path) -> Path:
    db_path = tmp_path / "learning.db"
    conn = sqlite3.connect(str(db_path))
    conn.execute("CREATE TABLE governance_events (id INTEGER PRIMARY KEY, blocked INTEGER, created_at TEXT)")
    conn.commit()
    conn.close()
    return db_path


def _insert_events(db_path: Path, *, blocked: int, total: int, age_days: float = 1.0) -> None:
    """Insert test governance events into a learning.db fixture."""
    conn = sqlite3.connect(str(db_path))
    ts = (datetime.now(tz=timezone.utc) - timedelta(days=age_days)).isoformat()
    for i in range(total):
        conn.execute(
            "INSERT INTO governance_events (blocked, created_at) VALUES (?, ?)",
            (1 if i < blocked else 0, ts),
        )
    conn.commit()
    conn.close()


# ---------------------------------------------------------------------------
# check_hook_errors
# ---------------------------------------------------------------------------


class TestCheckHookErrors:
    def test_db_missing_returns_ok(self, default_config: th.HealthConfig, tmp_path: Path) -> None:
        with patch.object(th, "LEARNING_DB", tmp_path / "nonexistent.db"):
            result = th.check_hook_errors(default_config)
        assert result.status == "OK"
        assert result.db_missing is True

    def test_low_error_rate_is_ok(self, default_config: th.HealthConfig, learning_db: Path) -> None:
        # Spread events evenly across both halves of the 7-day window so trend is STABLE
        _insert_events(learning_db, blocked=1, total=10, age_days=1.0)  # recent half
        _insert_events(learning_db, blocked=1, total=10, age_days=5.0)  # older half
        with patch.object(th, "LEARNING_DB", learning_db):
            result = th.check_hook_errors(default_config)
        assert result.status == "OK"
        assert result.error_rate == pytest.approx(10.0)

    def test_high_error_rate_warns(self, default_config: th.HealthConfig, learning_db: Path) -> None:
        _insert_events(learning_db, blocked=10, total=20)  # 50%
        with patch.object(th, "LEARNING_DB", learning_db):
            result = th.check_hook_errors(default_config)
        assert result.status == "WARN"
        assert result.error_rate == pytest.approx(50.0)

    def test_zero_events_is_ok(self, default_config: th.HealthConfig, learning_db: Path) -> None:
        with patch.object(th, "LEARNING_DB", learning_db):
            result = th.check_hook_errors(default_config)
        assert result.status == "OK"
        assert result.error_rate == 0.0

    def test_trend_increasing(self, default_config: th.HealthConfig, learning_db: Path) -> None:
        # Recent (last 3.5 days): many blocks
        _insert_events(learning_db, blocked=10, total=10, age_days=1.0)
        # Older (3.5-7 days ago): few blocks
        _insert_events(learning_db, blocked=1, total=10, age_days=5.0)
        with patch.object(th, "LEARNING_DB", learning_db):
            result = th.check_hook_errors(default_config)
        assert result.trend == "INCREASING"

    def test_missing_table_handled(self, default_config: th.HealthConfig, tmp_path: Path) -> None:
        db_path = tmp_path / "empty.db"
        conn = sqlite3.connect(str(db_path))
        conn.close()
        with patch.object(th, "LEARNING_DB", db_path):
            result = th.check_hook_errors(default_config)
        assert result.db_missing is True
        assert result.status == "OK"

    def test_flag_message_none_when_ok(self, default_config: th.HealthConfig, learning_db: Path) -> None:
        # Spread events evenly so trend is STABLE and rate is below threshold
        _insert_events(learning_db, blocked=1, total=10, age_days=1.0)
        _insert_events(learning_db, blocked=1, total=10, age_days=5.0)
        with patch.object(th, "LEARNING_DB", learning_db):
            result = th.check_hook_errors(default_config)
        assert result.flag_message() is None

    def test_flag_message_present_when_warn(self, default_config: th.HealthConfig, learning_db: Path) -> None:
        _insert_events(learning_db, blocked=10, total=20)
        with patch.object(th, "LEARNING_DB", learning_db):
            result = th.check_hook_errors(default_config)
        assert result.flag_message() is not None
        assert "50.0%" in result.flag_message()  # type: ignore[operator]


# ---------------------------------------------------------------------------
# check_stale_memory
# ---------------------------------------------------------------------------


class TestCheckStaleMemory:
    def _make_memory_dir(self, tmp_path: Path, project: str = "test-proj") -> Path:
        memory_dir = tmp_path / "projects" / project / "memory"
        memory_dir.mkdir(parents=True)
        return memory_dir

    def test_no_projects_dir_is_ok(self, default_config: th.HealthConfig, tmp_path: Path) -> None:
        with patch.object(th, "MEMORY_PROJECTS_DIR", tmp_path / "projects"):
            result = th.check_stale_memory(default_config)
        assert result.status == "OK"
        assert result.stale_files == []

    def test_fresh_files_not_flagged(self, default_config: th.HealthConfig, tmp_path: Path) -> None:
        memory_dir = self._make_memory_dir(tmp_path)
        (memory_dir / "user_role.md").write_text("content")
        with patch.object(th, "MEMORY_PROJECTS_DIR", tmp_path / "projects"):
            result = th.check_stale_memory(default_config)
        assert result.status == "OK"

    def test_stale_files_detected(self, default_config: th.HealthConfig, tmp_path: Path) -> None:
        memory_dir = self._make_memory_dir(tmp_path)
        for i in range(6):
            md = memory_dir / f"file_{i}.md"
            md.write_text("x")
            # Back-date mtime to 30 days ago
            old_time = (datetime.now(tz=timezone.utc) - timedelta(days=30)).timestamp()
            import os

            os.utime(md, (old_time, old_time))
        with patch.object(th, "MEMORY_PROJECTS_DIR", tmp_path / "projects"):
            result = th.check_stale_memory(default_config)
        assert result.status == "WARN"
        assert len(result.stale_files) == 6

    def test_memory_md_skipped(self, default_config: th.HealthConfig, tmp_path: Path) -> None:
        memory_dir = self._make_memory_dir(tmp_path)
        md = memory_dir / "MEMORY.md"
        md.write_text("index")
        old_time = (datetime.now(tz=timezone.utc) - timedelta(days=60)).timestamp()
        import os

        os.utime(md, (old_time, old_time))
        with patch.object(th, "MEMORY_PROJECTS_DIR", tmp_path / "projects"):
            result = th.check_stale_memory(default_config)
        assert result.stale_files == []


# ---------------------------------------------------------------------------
# check_state_files
# ---------------------------------------------------------------------------


class TestCheckStateFiles:
    def test_missing_state_dir_is_ok(self, default_config: th.HealthConfig, tmp_path: Path) -> None:
        with patch.object(th, "STATE_DIR", tmp_path / "nonexistent"):
            result = th.check_state_files(default_config)
        assert result.status == "OK"
        assert result.file_count == 0

    def test_below_threshold_is_ok(self, default_config: th.HealthConfig, tmp_path: Path) -> None:
        state = tmp_path / "state"
        state.mkdir()
        for i in range(10):
            (state / f"file{i}.txt").write_text("x")
        with patch.object(th, "STATE_DIR", state):
            result = th.check_state_files(default_config)
        assert result.status == "OK"
        assert result.file_count == 10

    def test_above_threshold_warns(self, default_config: th.HealthConfig, tmp_path: Path) -> None:
        state = tmp_path / "state"
        state.mkdir()
        for i in range(55):
            (state / f"file{i}.txt").write_text("x")
        with patch.object(th, "STATE_DIR", state):
            result = th.check_state_files(default_config)
        assert result.status == "WARN"
        assert result.file_count == 55

    def test_exact_threshold_is_ok(self, default_config: th.HealthConfig, tmp_path: Path) -> None:
        state = tmp_path / "state"
        state.mkdir()
        for i in range(50):
            (state / f"file{i}.txt").write_text("x")
        with patch.object(th, "STATE_DIR", state):
            result = th.check_state_files(default_config)
        assert result.status == "OK"


# ---------------------------------------------------------------------------
# check_adr_backlog
# ---------------------------------------------------------------------------


class TestCheckAdrBacklog:
    def test_missing_dir_is_ok(self, default_config: th.HealthConfig, tmp_path: Path) -> None:
        with patch.object(th, "ADR_DIR", tmp_path / "nonexistent"):
            result = th.check_adr_backlog(default_config)
        assert result.status == "OK"
        assert result.adr_count == 0

    def test_below_threshold_is_ok(self, default_config: th.HealthConfig, tmp_path: Path) -> None:
        adr_dir = tmp_path / "adr"
        adr_dir.mkdir()
        for i in range(5):
            (adr_dir / f"00{i}-test.md").write_text("# ADR")
        with patch.object(th, "ADR_DIR", adr_dir):
            result = th.check_adr_backlog(default_config)
        assert result.status == "OK"
        assert result.adr_count == 5

    def test_above_threshold_warns(self, default_config: th.HealthConfig, tmp_path: Path) -> None:
        adr_dir = tmp_path / "adr"
        adr_dir.mkdir()
        for i in range(25):
            (adr_dir / f"{i:03d}-test.md").write_text("# ADR")
        with patch.object(th, "ADR_DIR", adr_dir):
            result = th.check_adr_backlog(default_config)
        assert result.status == "WARN"
        assert result.adr_count == 25

    def test_non_md_files_not_counted(self, default_config: th.HealthConfig, tmp_path: Path) -> None:
        adr_dir = tmp_path / "adr"
        adr_dir.mkdir()
        (adr_dir / "001-test.md").write_text("# ADR")
        (adr_dir / "README.txt").write_text("ignored")
        with patch.object(th, "ADR_DIR", adr_dir):
            result = th.check_adr_backlog(default_config)
        assert result.adr_count == 1


# ---------------------------------------------------------------------------
# check_toolkit_health (orchestration)
# ---------------------------------------------------------------------------


class TestCheckToolkitHealth:
    def test_all_checks_run_by_default(self, default_config: th.HealthConfig, tmp_path: Path) -> None:
        with (
            patch.object(th, "LEARNING_DB", tmp_path / "x.db"),
            patch.object(th, "MEMORY_PROJECTS_DIR", tmp_path / "projects"),
            patch.object(th, "STATE_DIR", tmp_path / "state"),
            patch.object(th, "ADR_DIR", tmp_path / "adr"),
        ):
            report = th.check_toolkit_health(default_config)
        assert report.hook_errors is not None
        assert report.stale_memory is not None
        assert report.state_files is not None
        assert report.adr_backlog is not None

    def test_subset_of_checks(self, default_config: th.HealthConfig, tmp_path: Path) -> None:
        with patch.object(th, "ADR_DIR", tmp_path / "adr"):
            report = th.check_toolkit_health(default_config, checks=("adr-backlog",))
        assert report.hook_errors is None
        assert report.stale_memory is None
        assert report.state_files is None
        assert report.adr_backlog is not None

    def test_flags_aggregated(self, default_config: th.HealthConfig, tmp_path: Path) -> None:
        # Plant 25 ADR files to trigger a WARN
        adr_dir = tmp_path / "adr"
        adr_dir.mkdir()
        for i in range(25):
            (adr_dir / f"{i:03d}-test.md").write_text("# ADR")
        with (
            patch.object(th, "LEARNING_DB", tmp_path / "x.db"),
            patch.object(th, "MEMORY_PROJECTS_DIR", tmp_path / "projects"),
            patch.object(th, "STATE_DIR", tmp_path / "state"),
            patch.object(th, "ADR_DIR", adr_dir),
        ):
            report = th.check_toolkit_health(default_config)
        assert report.has_warnings()
        assert any("ADR" in flag for flag in report.flags)


# ---------------------------------------------------------------------------
# load_config
# ---------------------------------------------------------------------------


class TestLoadConfig:
    def test_none_path_returns_defaults(self) -> None:
        config = th.load_config(None)
        assert config.stale_memory_days == 14
        assert config.state_file_warn_count == 50
        assert config.adr_backlog_warn_count == 20

    def test_missing_file_returns_defaults(self, tmp_path: Path) -> None:
        config = th.load_config(tmp_path / "nonexistent.json")
        assert config.stale_memory_days == 14

    def test_loads_thresholds_from_file(self, tmp_path: Path) -> None:
        cfg = tmp_path / "kairos.json"
        cfg.write_text(
            json.dumps(
                {
                    "thresholds": {
                        "stale_memory_days": 7,
                        "state_file_warn_count": 30,
                        "adr_backlog_warn_count": 10,
                    }
                }
            )
        )
        config = th.load_config(cfg)
        assert config.stale_memory_days == 7
        assert config.state_file_warn_count == 30
        assert config.adr_backlog_warn_count == 10

    def test_invalid_json_exits_2(self, tmp_path: Path) -> None:
        cfg = tmp_path / "bad.json"
        cfg.write_text("{not valid json")
        with pytest.raises(SystemExit) as exc_info:
            th.load_config(cfg)
        assert exc_info.value.code == 2


# ---------------------------------------------------------------------------
# report_to_dict (JSON serialisation)
# ---------------------------------------------------------------------------


class TestReportToDict:
    def test_structure(self, tmp_path: Path, default_config: th.HealthConfig) -> None:
        with (
            patch.object(th, "LEARNING_DB", tmp_path / "x.db"),
            patch.object(th, "MEMORY_PROJECTS_DIR", tmp_path / "projects"),
            patch.object(th, "STATE_DIR", tmp_path / "state"),
            patch.object(th, "ADR_DIR", tmp_path / "adr"),
        ):
            report = th.check_toolkit_health(default_config)
        d = th.report_to_dict(report)

        assert "scan_timestamp" in d
        assert "has_warnings" in d
        assert "flags" in d
        assert "checks" in d
        assert "hook_errors" in d["checks"]
        assert "stale_memory" in d["checks"]
        assert "state_files" in d["checks"]
        assert "adr_backlog" in d["checks"]

    def test_json_serialisable(self, tmp_path: Path, default_config: th.HealthConfig) -> None:
        with (
            patch.object(th, "LEARNING_DB", tmp_path / "x.db"),
            patch.object(th, "MEMORY_PROJECTS_DIR", tmp_path / "projects"),
            patch.object(th, "STATE_DIR", tmp_path / "state"),
            patch.object(th, "ADR_DIR", tmp_path / "adr"),
        ):
            report = th.check_toolkit_health(default_config)
        d = th.report_to_dict(report)
        # Must not raise
        serialised = json.dumps(d)
        assert len(serialised) > 0


# ---------------------------------------------------------------------------
# format_human_report
# ---------------------------------------------------------------------------


class TestFormatHumanReport:
    def test_all_ok_shows_nominal(self, tmp_path: Path, default_config: th.HealthConfig) -> None:
        with (
            patch.object(th, "LEARNING_DB", tmp_path / "x.db"),
            patch.object(th, "MEMORY_PROJECTS_DIR", tmp_path / "projects"),
            patch.object(th, "STATE_DIR", tmp_path / "state"),
            patch.object(th, "ADR_DIR", tmp_path / "adr"),
        ):
            report = th.check_toolkit_health(default_config)
        text = th.format_human_report(report)
        assert "All systems nominal." in text

    def test_warn_present_in_output(self, tmp_path: Path, default_config: th.HealthConfig) -> None:
        adr_dir = tmp_path / "adr"
        adr_dir.mkdir()
        for i in range(25):
            (adr_dir / f"{i:03d}-test.md").write_text("# ADR")
        with (
            patch.object(th, "LEARNING_DB", tmp_path / "x.db"),
            patch.object(th, "MEMORY_PROJECTS_DIR", tmp_path / "projects"),
            patch.object(th, "STATE_DIR", tmp_path / "state"),
            patch.object(th, "ADR_DIR", adr_dir),
        ):
            report = th.check_toolkit_health(default_config)
        text = th.format_human_report(report)
        assert "[WARN]" in text
        assert "adr-backlog" in text
