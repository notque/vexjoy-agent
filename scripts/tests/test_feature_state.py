"""Tests for scripts/feature-state.py hardening fixes."""

from __future__ import annotations

import argparse
import importlib.util
import subprocess
import sys
import threading
from datetime import date
from pathlib import Path
from unittest import mock

SCRIPT_PATH = Path(__file__).resolve().parent.parent / "feature-state.py"


def _load_module():
    spec = importlib.util.spec_from_file_location("feature_state_mod", SCRIPT_PATH)
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = mod
    spec.loader.exec_module(mod)
    return mod


fs = _load_module()


def _ns(**kwargs):
    defaults = {"human": False, "feature_name": None, "phase": None, "reason": None, "confidence": "low"}
    defaults.update(kwargs)
    return argparse.Namespace(**defaults)


def _setup_repo(tmp_path: Path, monkeypatch) -> Path:
    (tmp_path / ".git").mkdir()
    monkeypatch.chdir(tmp_path)
    return tmp_path


class TestUtf8AndLanguages:
    def test_init_and_context_read_utf8_arrow(self, tmp_path, monkeypatch, capsys):
        _setup_repo(tmp_path, monkeypatch)
        assert fs.cmd_init(_ns(feature_name="my-feat")) == 0
        l0 = (tmp_path / ".feature" / "FEATURE.md").read_text(encoding="utf-8")
        assert "design → plan" in l0
        capsys.readouterr()
        assert fs.cmd_context_read(_ns(feature="my-feat", level="L0")) == 0
        out = capsys.readouterr().out
        assert "my-feat" in out

    def test_detect_languages_only_globs_target_feature(self, tmp_path):
        feature_dir = tmp_path / ".feature"
        impl_dir = feature_dir / "state" / "implement"
        impl_dir.mkdir(parents=True)
        (impl_dir / "2026-11-28-alpha.md").write_text("edited app.py\n", encoding="utf-8")
        (impl_dir / "2026-11-28-beta.md").write_text("edited server.go and ui.tsx\n", encoding="utf-8")

        assert fs._detect_languages(feature_dir, "alpha") == ["python"]
        assert fs._detect_languages(feature_dir, "beta") == ["go", "typescript"]
        assert fs._detect_languages(feature_dir, "gamma") == ["*"]


class TestCompleteAndAbandonOrdering:
    def test_complete_keeps_state_when_worktree_remove_fails(self, tmp_path, monkeypatch):
        _setup_repo(tmp_path, monkeypatch)
        assert fs.cmd_init(_ns(feature_name="wt-fail")) == 0
        feature_dir = tmp_path / ".feature"
        wt_dir = tmp_path / "fake-wt"
        wt_dir.mkdir()
        state = fs.load_state(feature_dir, "wt-fail")
        assert state is not None
        state.worktree_path = str(wt_dir)
        fs.save_state(feature_dir, state)

        fail_res = subprocess.CompletedProcess(["git"], returncode=1, stdout="", stderr="dirty worktree")
        with mock.patch.object(subprocess, "run", return_value=fail_res):
            rc = fs.cmd_complete(_ns(feature="wt-fail"))

        assert rc == 1
        assert (feature_dir / "state" / "wt-fail.json").exists()
        assert not (feature_dir / "state" / "completed" / f"{date.today().isoformat()}-wt-fail.json").exists()

    def test_abandon_keeps_state_when_worktree_remove_fails(self, tmp_path, monkeypatch):
        _setup_repo(tmp_path, monkeypatch)
        assert fs.cmd_init(_ns(feature_name="ab-fail")) == 0
        feature_dir = tmp_path / ".feature"
        wt_dir = tmp_path / "fake-wt"
        wt_dir.mkdir()
        state = fs.load_state(feature_dir, "ab-fail")
        assert state is not None
        state.worktree_path = str(wt_dir)
        fs.save_state(feature_dir, state)

        fail_res = subprocess.CompletedProcess(["git"], returncode=1, stdout="", stderr="locked worktree")
        with mock.patch.object(subprocess, "run", return_value=fail_res):
            rc = fs.cmd_abandon(_ns(feature="ab-fail", reason="changed mind"))

        assert rc == 1
        assert (feature_dir / "state" / "ab-fail.json").exists()
        assert not (feature_dir / "state" / "abandoned" / f"{date.today().isoformat()}-ab-fail.json").exists()

    def test_complete_and_abandon_overwrite_existing_archive(self, tmp_path, monkeypatch):
        _setup_repo(tmp_path, monkeypatch)
        feature_dir = tmp_path / ".feature"
        today = date.today().isoformat()

        # Pre-create destination in completed/ to verify os.replace does not raise FileExistsError.
        assert fs.cmd_init(_ns(feature_name="dup-done")) == 0
        completed_dir = feature_dir / "state" / "completed"
        completed_dir.mkdir(parents=True, exist_ok=True)
        (completed_dir / f"{today}-dup-done.json").write_text("{}", encoding="utf-8")
        assert fs.cmd_complete(_ns(feature="dup-done")) == 0
        assert not (feature_dir / "state" / "dup-done.json").exists()
        assert (completed_dir / f"{today}-dup-done.json").exists()

        # Same for abandoned/.
        assert fs.cmd_init(_ns(feature_name="dup-ab")) == 0
        abandoned_dir = feature_dir / "state" / "abandoned"
        abandoned_dir.mkdir(parents=True, exist_ok=True)
        (abandoned_dir / f"{today}-dup-ab.json").write_text("{}", encoding="utf-8")
        assert fs.cmd_abandon(_ns(feature="dup-ab", reason="re-abandon")) == 0
        assert not (feature_dir / "state" / "dup-ab.json").exists()
        assert (abandoned_dir / f"{today}-dup-ab.json").exists()


class TestPerFeatureLock:
    def test_concurrent_retro_record_preserves_all_observations(self, tmp_path, monkeypatch):
        _setup_repo(tmp_path, monkeypatch)
        assert fs.cmd_init(_ns(feature_name="race-feat")) == 0
        feature_dir = tmp_path / ".feature"

        errors: list[Exception] = []
        barrier = threading.Barrier(6)

        def worker(i: int):
            try:
                barrier.wait()
                rc = fs.cmd_retro_record(_ns(feature="race-feat", key="obs-key", value=f"val-{i}", confidence="low"))
                assert rc == 0
            except Exception as exc:
                errors.append(exc)

        threads = [threading.Thread(target=worker, args=(i,)) for i in range(6)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert not errors
        state = fs.load_state(feature_dir, "race-feat")
        assert state is not None
        assert state.retro_records["obs-key"]["observations"] == 6
        assert state.retro_records["obs-key"]["confidence"] == "high"
