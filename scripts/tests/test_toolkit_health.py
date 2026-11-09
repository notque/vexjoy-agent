"""Tests for scripts/toolkit-health.py."""

from __future__ import annotations

import importlib
import json
import os
import sqlite3
import sys
import time
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
    """Insert governance events stamped the way the hooks stamp them: naive local time."""
    conn = sqlite3.connect(str(db_path))
    ts = (datetime.now() - timedelta(days=age_days)).isoformat()
    for i in range(total):
        conn.execute(
            "INSERT INTO governance_events (blocked, created_at) VALUES (?, ?)",
            (1 if i < blocked else 0, ts),
        )
    conn.commit()
    conn.close()


def _write_crashes(path: Path, crashes: list[tuple[str, float]], extra_lines: list[str] | None = None) -> None:
    """Write hook-errors.jsonl entries as hook_error() does: one (hook, age in days) per line, UTC ``ts``."""
    now = datetime.now(tz=timezone.utc)
    lines = [
        json.dumps({"ts": (now - timedelta(days=age)).isoformat(), "hook": hook, "type": "ValueError", "msg": "x"})
        for hook, age in crashes
    ]
    path.write_text("\n".join(lines + (extra_lines or [])) + "\n", encoding="utf-8")


@pytest.fixture
def crash_log(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    path = tmp_path / "crashes" / "hook-errors.jsonl"
    path.parent.mkdir()
    monkeypatch.setenv("CLAUDE_HOOK_ERRORS_PATH", str(path))
    return path


# ---------------------------------------------------------------------------
# check_hook_errors (crashes, from hook-errors.jsonl)
# ---------------------------------------------------------------------------


class TestCheckHookErrors:
    def test_log_missing_is_ok(self, default_config: th.HealthConfig, crash_log: Path) -> None:
        result = th.check_hook_errors(default_config)
        assert result.status == "OK"
        assert result.log_missing is True
        assert result.flag_message() is None

    def test_default_path_is_the_learning_dir_log(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.delenv("CLAUDE_HOOK_ERRORS_PATH")
        assert th.hook_errors_path() == th.CLAUDE_DIR / "learning" / "hook-errors.jsonl"

    def test_counts_crashes_per_hook_inside_the_window(self, default_config: th.HealthConfig, crash_log: Path) -> None:
        _write_crashes(crash_log, [("a", 1), ("a", 2), ("b", 6.9), ("old", 7.1), ("old", 30)])
        result = th.check_hook_errors(default_config)
        assert result.log_missing is False
        assert result.crash_count == 3
        assert result.by_hook == [("a", 2), ("b", 1)]
        assert result.status == "OK"

    def test_at_threshold_is_ok_and_above_warns(self, default_config: th.HealthConfig, crash_log: Path) -> None:
        _write_crashes(crash_log, [("a", 1)] * th.HOOK_CRASH_WARN_COUNT)
        assert th.check_hook_errors(default_config).status == "OK"

        _write_crashes(crash_log, [("a", 1)] * (th.HOOK_CRASH_WARN_COUNT + 1) + [("b", 1)])
        result = th.check_hook_errors(default_config)
        assert result.status == "WARN"
        message = result.flag_message()
        assert message is not None
        assert "a (6)" in message and "b (" not in message

    def test_threshold_is_per_hook_not_total(self, default_config: th.HealthConfig, crash_log: Path) -> None:
        _write_crashes(crash_log, [(f"hook-{i}", 1) for i in range(th.HOOK_CRASH_WARN_COUNT * 3)])
        result = th.check_hook_errors(default_config)
        assert result.crash_count == th.HOOK_CRASH_WARN_COUNT * 3
        assert result.status == "OK"

    def test_threshold_comes_from_config(self, crash_log: Path) -> None:
        _write_crashes(crash_log, [("a", 1), ("a", 1)])
        assert th.check_hook_errors(th.HealthConfig(hook_crash_warn_count=1)).status == "WARN"

    def test_trend(self, default_config: th.HealthConfig, crash_log: Path) -> None:
        _write_crashes(crash_log, [("a", 1)] * 4 + [("a", 5)])
        assert th.check_hook_errors(default_config).trend == "INCREASING"
        _write_crashes(crash_log, [("a", 1)] + [("a", 5)] * 4)
        assert th.check_hook_errors(default_config).trend == "DECREASING"
        _write_crashes(crash_log, [("a", 1), ("a", 5)])
        assert th.check_hook_errors(default_config).trend == "STABLE"

    def test_unreadable_lines_are_skipped(self, default_config: th.HealthConfig, crash_log: Path) -> None:
        _write_crashes(
            crash_log,
            [("a", 1)],
            extra_lines=[
                "not json",
                "[1, 2]",
                "null",
                json.dumps({"hook": "no-ts"}),
                json.dumps({"ts": "yesterday", "hook": "bad-ts"}),
                json.dumps({"ts": 5, "hook": "int-ts"}),
                "",
            ],
        )
        result = th.check_hook_errors(default_config)
        assert result.by_hook == [("a", 1)]

    def test_missing_hook_name_counts_as_unknown(self, default_config: th.HealthConfig, crash_log: Path) -> None:
        now = datetime.now(tz=timezone.utc).isoformat()
        crash_log.write_text(json.dumps({"ts": now}) + "\n" + json.dumps({"ts": now, "hook": 3}) + "\n")
        assert th.check_hook_errors(default_config).by_hook == [("unknown", 2)]

    def test_naive_timestamp_is_read_as_utc(self, default_config: th.HealthConfig, crash_log: Path) -> None:
        naive = datetime.now(tz=timezone.utc).replace(tzinfo=None) - timedelta(hours=1)
        crash_log.write_text(json.dumps({"ts": naive.isoformat(), "hook": "a"}) + "\n")
        assert th.check_hook_errors(default_config).crash_count == 1

    def test_does_not_read_the_database(self, default_config: th.HealthConfig, crash_log: Path, tmp_path: Path) -> None:
        """Denials never reach the crash count: 100 denials and no crash log entries is 0 crashes."""
        db = tmp_path / "learning.db"
        conn = sqlite3.connect(str(db))
        conn.execute("CREATE TABLE governance_events (id INTEGER PRIMARY KEY, blocked INTEGER, created_at TEXT)")
        conn.commit()
        conn.close()
        _insert_events(db, blocked=100, total=100)
        _write_crashes(crash_log, [])
        with patch.object(th, "LEARNING_DB", db):
            result = th.check_hook_errors(default_config)
        assert (result.crash_count, result.status) == (0, "OK")


# ---------------------------------------------------------------------------
# check_hook_denials (count, from governance_events)
# ---------------------------------------------------------------------------


class TestCheckHookDenials:
    def test_db_missing_returns_ok(self, default_config: th.HealthConfig, tmp_path: Path) -> None:
        with patch.object(th, "LEARNING_DB", tmp_path / "nonexistent.db"):
            result = th.check_hook_denials(default_config)
        assert result.status == "OK"
        assert result.db_missing is True

    def test_all_blocked_is_ok_not_an_alarm(self, default_config: th.HealthConfig, learning_db: Path) -> None:
        """Every recorded governance event is a denial, so 100% blocked is the normal reading."""
        _insert_events(learning_db, blocked=500, total=500, age_days=1.0)
        with patch.object(th, "LEARNING_DB", learning_db):
            result = th.check_hook_denials(default_config)
        assert (result.denial_count, result.event_count) == (500, 500)
        assert result.trend == "INCREASING"
        assert result.status == "OK"
        assert result.flag_message() is None

    def test_counts_only_the_window(self, default_config: th.HealthConfig, learning_db: Path) -> None:
        _insert_events(learning_db, blocked=2, total=3, age_days=1.0)
        _insert_events(learning_db, blocked=4, total=4, age_days=5.0)
        _insert_events(learning_db, blocked=9, total=9, age_days=8.0)
        with patch.object(th, "LEARNING_DB", learning_db):
            result = th.check_hook_denials(default_config)
        assert (result.denial_count, result.event_count) == (6, 7)
        assert result.trend == "STABLE"

    def test_zero_events_is_ok(self, default_config: th.HealthConfig, learning_db: Path) -> None:
        with patch.object(th, "LEARNING_DB", learning_db):
            result = th.check_hook_denials(default_config)
        assert (result.denial_count, result.status, result.db_missing) == (0, "OK", False)

    def test_missing_table_handled(self, default_config: th.HealthConfig, tmp_path: Path) -> None:
        db_path = tmp_path / "empty.db"
        conn = sqlite3.connect(str(db_path))
        conn.close()
        with patch.object(th, "LEARNING_DB", db_path):
            result = th.check_hook_denials(default_config)
        assert result.db_missing is True
        assert result.status == "OK"

    @pytest.mark.parametrize("tz", ["America/Los_Angeles", "UTC", "Asia/Tokyo"])
    def test_window_edge_is_right_in_any_time_zone(
        self, tz: str, default_config: th.HealthConfig, learning_db: Path
    ) -> None:
        """created_at is naive local time. A UTC cutoff moved the window edge by the UTC offset (8 h in Los Angeles)."""
        saved = os.environ.get("TZ")
        os.environ["TZ"] = tz
        time.tzset()
        try:
            _insert_events(learning_db, blocked=1, total=1, age_days=7 - 2 / 24)  # 2 h inside the window
            _insert_events(learning_db, blocked=1, total=1, age_days=7 + 2 / 24)  # 2 h outside it
            _insert_events(learning_db, blocked=1, total=1, age_days=3.5 - 2 / 24)  # 2 h inside the recent half
            with patch.object(th, "LEARNING_DB", learning_db):
                result = th.check_hook_denials(default_config)
        finally:
            if saved is None:
                del os.environ["TZ"]
            else:
                os.environ["TZ"] = saved
            time.tzset()
        assert result.denial_count == 2
        assert result.trend == "STABLE", "one denial in each half"

    def test_opens_the_database_read_only(
        self, default_config: th.HealthConfig, learning_db: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        _insert_events(learning_db, blocked=1, total=2)
        calls: list[tuple[tuple, dict]] = []
        real_connect = sqlite3.connect

        def spy(*args, **kwargs):
            calls.append((args, kwargs))
            return real_connect(*args, **kwargs)

        monkeypatch.setattr(sqlite3, "connect", spy)
        with patch.object(th, "LEARNING_DB", learning_db):
            result = th.check_hook_denials(default_config)
        assert result.event_count == 2
        assert calls and all(kw.get("uri") is True and str(a[0]).endswith("?mode=ro") for a, kw in calls), calls


def _load_fresh_module(monkeypatch: pytest.MonkeyPatch):
    """toolkit-health loaded under a new name, so its module-level DB path resolves against the patched env."""
    spec = importlib.util.spec_from_file_location("toolkit_health_fresh", REPO_ROOT / "scripts" / "toolkit-health.py")
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    monkeypatch.setitem(sys.modules, spec.name, module)  # dataclasses look their module up while it loads
    spec.loader.exec_module(module)
    return module


def _real_store(db_path: Path) -> Path:
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(db_path))
    conn.execute("CREATE TABLE governance_events (id INTEGER PRIMARY KEY, blocked INTEGER, created_at TEXT)")
    conn.commit()
    conn.close()
    _insert_events(db_path, blocked=10, total=20)
    return db_path


class TestLearningDbLocation:
    """The check reads the store the hooks write (hooks/lib/learning_db_v2.get_db_dir), not ~/.claude/state."""

    def test_default_is_the_learning_dir_not_the_stray_state_file(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv("HOME", str(tmp_path))
        monkeypatch.delenv("CLAUDE_LEARNING_DIR", raising=False)
        _real_store(tmp_path / ".claude" / "learning" / "learning.db")
        stray = tmp_path / ".claude" / "state" / "learning.db"
        stray.parent.mkdir(parents=True)
        stray.touch()  # the empty file the old path read, which made the check always say OK
        mod = _load_fresh_module(monkeypatch)
        assert tmp_path / ".claude" / "learning" / "learning.db" == mod.LEARNING_DB
        result = mod.check_hook_denials(mod.HealthConfig())
        assert result.db_missing is False
        assert (result.denial_count, result.event_count, result.status) == (10, 20, "OK")
        assert stray.stat().st_size == 0

    def test_claude_learning_dir_overrides_the_default(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("HOME", str(tmp_path / "home"))
        monkeypatch.setenv("CLAUDE_LEARNING_DIR", str(tmp_path / "alt"))
        _real_store(tmp_path / "alt" / "learning.db")
        mod = _load_fresh_module(monkeypatch)
        assert tmp_path / "alt" / "learning.db" == mod.LEARNING_DB
        assert mod.check_hook_denials(mod.HealthConfig()).event_count == 20
        assert not (tmp_path / "home" / ".claude").exists(), "the check must not create anything under HOME"


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
        assert report.hook_denials is not None
        assert report.stale_memory is not None
        assert report.state_files is not None
        assert report.adr_backlog is not None

    def test_subset_of_checks(self, default_config: th.HealthConfig, tmp_path: Path) -> None:
        with patch.object(th, "ADR_DIR", tmp_path / "adr"):
            report = th.check_toolkit_health(default_config, checks=("adr-backlog",))
        assert report.hook_errors is None
        assert report.hook_denials is None
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
                        "hook_crash_warn_count": 2,
                        "hook_error_rate_threshold": 99.0,  # retired key: ignored, not an error
                    }
                }
            )
        )
        config = th.load_config(cfg)
        assert config.hook_crash_warn_count == 2
        assert not hasattr(config, "hook_error_rate_threshold")
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
        assert set(d["checks"]["hook_errors"]) == {
            "status",
            "log_missing",
            "crash_count",
            "threshold",
            "trend",
            "by_hook",
        }
        assert set(d["checks"]["hook_denials"]) == {"status", "db_missing", "denial_count", "event_count", "trend"}
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


class TestHookLinesInReports:
    def test_crashes_warn_and_denials_do_not(
        self, tmp_path: Path, default_config: th.HealthConfig, learning_db: Path, crash_log: Path
    ) -> None:
        _insert_events(learning_db, blocked=50, total=50)
        _write_crashes(crash_log, [("pretool-unified-gate", 1)] * 6)
        with (
            patch.object(th, "LEARNING_DB", learning_db),
            patch.object(th, "MEMORY_PROJECTS_DIR", tmp_path / "projects"),
            patch.object(th, "STATE_DIR", tmp_path / "state"),
            patch.object(th, "ADR_DIR", tmp_path / "adr"),
        ):
            report = th.check_toolkit_health(default_config)
        text = th.format_human_report(report)
        d = th.report_to_dict(report)

        assert len(report.flags) == 1 and "pretool-unified-gate (6)" in report.flags[0]
        assert "[WARN] hook-errors: 6 crashes" in text
        assert "[ OK ] hook-denials: 50 denials of 50 governance events" in text
        assert d["checks"]["hook_errors"]["by_hook"] == [{"hook": "pretool-unified-gate", "count": 6}]
        assert d["checks"]["hook_denials"]["status"] == "OK"

    def test_denials_alone_leave_the_report_nominal(
        self, tmp_path: Path, default_config: th.HealthConfig, learning_db: Path, crash_log: Path
    ) -> None:
        _insert_events(learning_db, blocked=50, total=50)
        with (
            patch.object(th, "LEARNING_DB", learning_db),
            patch.object(th, "MEMORY_PROJECTS_DIR", tmp_path / "projects"),
            patch.object(th, "STATE_DIR", tmp_path / "state"),
            patch.object(th, "ADR_DIR", tmp_path / "adr"),
        ):
            report = th.check_toolkit_health(default_config)

        assert not report.has_warnings()
        assert "All systems nominal." in th.format_human_report(report)
