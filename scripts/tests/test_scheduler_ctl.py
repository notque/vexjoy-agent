"""Tests for scheduler-ctl.py — CLI subcommands and output formatting."""

from __future__ import annotations

import importlib
import json
import sqlite3
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
scheduler_ctl = importlib.import_module("scheduler-ctl")


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def sample_config(tmp_path: Path) -> Path:
    """Create a sample config and return its path."""
    config = {
        "version": 1,
        "defaults": {"model": "haiku", "timeout_seconds": 60, "enabled": True},
        "daily_budget_usd": 5.0,
        "jobs": [
            {
                "name": "test-job",
                "description": "Test job",
                "trigger": {"type": "cron", "schedule": "*/5 * * * *"},
                "prompt": "echo test",
                "model": "haiku",
                "timeout_seconds": 30,
                "cost_limit_usd": 0.01,
            },
            {
                "name": "webhook-job",
                "description": "Webhook test",
                "trigger": {"type": "webhook", "path": "/webhook/test"},
                "prompt": "handle webhook",
                "model": "sonnet",
                "timeout_seconds": 60,
                "cost_limit_usd": 0.05,
            },
        ],
    }
    path = tmp_path / "schedules.json"
    path.write_text(json.dumps(config))
    return path


@pytest.fixture
def temp_db(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Create a temporary database with some test data."""
    db_path = tmp_path / "scheduler-results.db"
    conn = sqlite3.connect(str(db_path))
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS job_results (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            job_name TEXT NOT NULL,
            trigger_type TEXT NOT NULL,
            started_at TEXT NOT NULL,
            finished_at TEXT NOT NULL,
            exit_code INTEGER NOT NULL,
            stdout TEXT,
            stderr TEXT,
            model TEXT NOT NULL,
            duration_seconds REAL NOT NULL,
            cost_estimate_usd REAL,
            trigger_detail TEXT
        );

        INSERT INTO job_results
            (job_name, trigger_type, started_at, finished_at, exit_code,
             stdout, stderr, model, duration_seconds, cost_estimate_usd, trigger_detail)
        VALUES
            ('test-job', 'cron', '2026-03-14T10:00:00+00:00', '2026-03-14T10:00:05+00:00',
             0, 'Success output', '', 'haiku', 5.0, 0.001, '*/5 * * * *');

        INSERT INTO job_results
            (job_name, trigger_type, started_at, finished_at, exit_code,
             stdout, stderr, model, duration_seconds, cost_estimate_usd, trigger_detail)
        VALUES
            ('test-job', 'cron', '2026-03-14T10:05:00+00:00', '2026-03-14T10:05:10+00:00',
             1, '', 'Error occurred', 'haiku', 10.0, 0.002, '*/5 * * * *');

    """)
    conn.commit()
    conn.close()

    monkeypatch.setattr(scheduler_ctl, "_DB_PATH", db_path)
    return db_path


def _args(**kwargs: object) -> SimpleNamespace:
    """Build a SimpleNamespace with json_output defaulting to False."""
    kwargs.setdefault("json_output", False)
    return SimpleNamespace(**kwargs)


# ---------------------------------------------------------------------------
# Config operations
# ---------------------------------------------------------------------------


class TestConfigOperations:
    def test_load_config(self, sample_config: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr(scheduler_ctl, "_DEFAULT_CONFIG", sample_config)
        config = scheduler_ctl.load_config()
        assert len(config["jobs"]) == 2

    def test_save_config_roundtrip(self, sample_config: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr(scheduler_ctl, "_DEFAULT_CONFIG", sample_config)
        config = scheduler_ctl.load_config()
        config["jobs"][0]["enabled"] = False
        scheduler_ctl.save_config(config)
        reloaded = scheduler_ctl.load_config()
        assert reloaded["jobs"][0]["enabled"] is False


# ---------------------------------------------------------------------------
# cmd_list
# ---------------------------------------------------------------------------


class TestCmdList:
    def test_list_jobs(
        self, sample_config: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
    ) -> None:
        monkeypatch.setattr(scheduler_ctl, "_DEFAULT_CONFIG", sample_config)
        result = scheduler_ctl.cmd_list(_args())
        assert result == 0
        output = capsys.readouterr().out
        assert "test-job" in output
        assert "webhook-job" in output

    def test_list_jobs_json(
        self, sample_config: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
    ) -> None:
        monkeypatch.setattr(scheduler_ctl, "_DEFAULT_CONFIG", sample_config)
        result = scheduler_ctl.cmd_list(_args(json_output=True))
        assert result == 0
        data = json.loads(capsys.readouterr().out)
        assert isinstance(data, list)
        assert len(data) == 2


# ---------------------------------------------------------------------------
# cmd_history
# ---------------------------------------------------------------------------


class TestCmdHistory:
    def test_history_all(self, temp_db: Path, capsys: pytest.CaptureFixture[str]) -> None:
        result = scheduler_ctl.cmd_history(_args(job_name=None))
        assert result == 0
        output = capsys.readouterr().out
        assert "test-job" in output

    def test_history_specific_job(self, temp_db: Path) -> None:
        result = scheduler_ctl.cmd_history(_args(job_name="test-job"))
        assert result == 0

    def test_history_json(self, temp_db: Path, capsys: pytest.CaptureFixture[str]) -> None:
        result = scheduler_ctl.cmd_history(_args(json_output=True, job_name=None))
        assert result == 0
        data = json.loads(capsys.readouterr().out)
        assert isinstance(data, list)
        assert len(data) == 2


# ---------------------------------------------------------------------------
# cmd_last
# ---------------------------------------------------------------------------


class TestCmdLast:
    def test_last_result(self, temp_db: Path, capsys: pytest.CaptureFixture[str]) -> None:
        result = scheduler_ctl.cmd_last(_args(job_name="test-job"))
        assert result == 0
        output = capsys.readouterr().out
        assert "test-job" in output

    def test_last_not_found(self, temp_db: Path) -> None:
        result = scheduler_ctl.cmd_last(_args(job_name="nonexistent"))
        assert result == 1


# ---------------------------------------------------------------------------
# cmd_status
# ---------------------------------------------------------------------------


class TestCmdStatus:
    def test_status_not_running(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
    ) -> None:
        monkeypatch.setattr(scheduler_ctl, "_PID_FILE", tmp_path / "nonexistent.pid")
        result = scheduler_ctl.cmd_status(_args())
        assert result == 1
        assert "NOT RUNNING" in capsys.readouterr().out

    def test_status_json_not_running(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
    ) -> None:
        monkeypatch.setattr(scheduler_ctl, "_PID_FILE", tmp_path / "nonexistent.pid")
        result = scheduler_ctl.cmd_status(_args(json_output=True))
        assert result == 1
        data = json.loads(capsys.readouterr().out)
        assert data["running"] is False


# ---------------------------------------------------------------------------
# cmd_enable / cmd_disable
# ---------------------------------------------------------------------------


class TestEnableDisable:
    def test_disable_job(self, sample_config: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr(scheduler_ctl, "_DEFAULT_CONFIG", sample_config)
        result = scheduler_ctl.cmd_disable(_args(job_name="test-job"))
        assert result == 0
        config = scheduler_ctl.load_config()
        job = next(j for j in config["jobs"] if j["name"] == "test-job")
        assert job["enabled"] is False

    def test_enable_job(self, sample_config: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr(scheduler_ctl, "_DEFAULT_CONFIG", sample_config)
        scheduler_ctl.cmd_disable(_args(job_name="test-job"))
        result = scheduler_ctl.cmd_enable(_args(job_name="test-job"))
        assert result == 0
        config = scheduler_ctl.load_config()
        job = next(j for j in config["jobs"] if j["name"] == "test-job")
        assert job["enabled"] is True

    def test_enable_nonexistent_job(self, sample_config: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr(scheduler_ctl, "_DEFAULT_CONFIG", sample_config)
        result = scheduler_ctl.cmd_enable(_args(job_name="nonexistent"))
        assert result == 1
