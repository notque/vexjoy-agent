#!/usr/bin/env python3
"""Tests for hook-error repeat-offender and matcher-liveness health checks."""

import importlib.util
import json
import os
import shutil
import subprocess
from datetime import datetime, timedelta, timezone
from pathlib import Path

SCRIPT = Path(__file__).resolve().parents[1] / "validate-hook-health.py"
SPEC = importlib.util.spec_from_file_location("validate_hook_health", SCRIPT)
assert SPEC and SPEC.loader
health = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(health)


def _entry(hook: str, ts: datetime) -> str:
    return json.dumps({"ts": ts.isoformat(), "hook": hook, "type": "RuntimeError", "msg": "x"})


def _with_hook_files(monkeypatch, tmp_path, *names: str) -> Path:
    """Point HOOKS_DIR at a tmp dir holding a real file for each hook name.

    The repeat-offender check only fails on hooks that still exist in the repo,
    so a test using synthetic hook names must materialise them.
    """
    hooks_dir = tmp_path / "hooks"
    hooks_dir.mkdir(exist_ok=True)
    for name in names:
        (hooks_dir / f"{name}.py").write_text("# stub\n", encoding="utf-8")
    monkeypatch.setattr(health, "HOOKS_DIR", hooks_dir)
    return hooks_dir


def test_repeat_offenders_ignore_old_and_malformed_entries(tmp_path, monkeypatch):
    now = datetime.now(timezone.utc)
    path = tmp_path / "hook-errors.jsonl"
    lines = [
        *[_entry("old-hook", now - timedelta(hours=169)) for _ in range(6)],
        *[_entry("recent-hook", now - timedelta(hours=1)) for _ in range(5)],
        json.dumps({"hook": "missing-ts"}),
        "not-json",
    ]
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    monkeypatch.setenv("CLAUDE_HOOK_ERRORS_PATH", str(path))
    _with_hook_files(monkeypatch, tmp_path, "old-hook", "recent-hook")

    failures = health.check_hook_error_repeat_offenders(now=now)

    assert len(failures) == 1
    assert "recent-hook" in failures[0]
    assert "old-hook" not in failures[0]


def test_repeat_offenders_honor_runtime_path_override(tmp_path, monkeypatch):
    now = datetime.now(timezone.utc)
    default_path = tmp_path / "default.jsonl"
    override_path = tmp_path / "override.jsonl"
    default_path.write_text("\n".join(_entry("default-hook", now) for _ in range(5)) + "\n", encoding="utf-8")
    override_path.write_text("\n".join(_entry("override-hook", now) for _ in range(5)) + "\n", encoding="utf-8")
    monkeypatch.setattr(health, "DEFAULT_HOOK_ERRORS_JSONL", default_path)
    monkeypatch.setenv("CLAUDE_HOOK_ERRORS_PATH", str(override_path))
    _with_hook_files(monkeypatch, tmp_path, "default-hook", "override-hook")

    failures = health.check_hook_error_repeat_offenders(now=now)

    assert len(failures) == 1
    assert "override-hook" in failures[0]


def test_repeat_offender_lookback_is_configurable(tmp_path, monkeypatch):
    now = datetime.now(timezone.utc)
    path = tmp_path / "hook-errors.jsonl"
    path.write_text(
        "\n".join(_entry("twelve-hour-hook", now - timedelta(hours=12)) for _ in range(5)) + "\n",
        encoding="utf-8",
    )
    monkeypatch.setenv("CLAUDE_HOOK_ERRORS_PATH", str(path))
    _with_hook_files(monkeypatch, tmp_path, "twelve-hour-hook")

    assert health.check_hook_error_repeat_offenders(lookback_hours=6, now=now) == []
    assert "twelve-hour-hook" in health.check_hook_error_repeat_offenders(lookback_hours=24, now=now)[0]


def test_default_lookback_covers_multi_day_crash_streaks(tmp_path, monkeypatch):
    """A sustained crash streak from days ago must still surface by default.

    Regression: adr-enforcement crashed 1,795 times over 8 days but the old
    24-hour default window only ever saw the final day's tail.
    """
    now = datetime.now(timezone.utc)
    path = tmp_path / "hook-errors.jsonl"
    path.write_text(
        "\n".join(_entry("six-day-old-hook", now - timedelta(days=6)) for _ in range(20)) + "\n",
        encoding="utf-8",
    )
    monkeypatch.setenv("CLAUDE_HOOK_ERRORS_PATH", str(path))
    _with_hook_files(monkeypatch, tmp_path, "six-day-old-hook")

    failures = health.check_hook_error_repeat_offenders(now=now)

    assert len(failures) == 1
    assert "six-day-old-hook" in failures[0]


def test_stop_liveness_probe_does_not_audit_the_current_repo():
    stop_payload = health._EVENT_BASE["Stop"]

    assert stop_payload["cwd"] != str(health.REPO_ROOT)
    assert Path(stop_payload["cwd"]).is_dir()


def test_retired_hook_is_reported_as_a_note_not_a_failure(tmp_path, monkeypatch):
    """A deleted hook's historical errors must not fail a maintainer's run.

    Regression: retiring hooks/instruction-compliance.py left 37 errors inside
    the 168-hour window, so the validator failed for a week on a file nobody
    could fix. The errors still surface, as an informational note.
    """
    now = datetime.now(timezone.utc)
    path = tmp_path / "hook-errors.jsonl"
    lines = [
        *[_entry("retired-hook", now - timedelta(hours=2)) for _ in range(37)],
        *[_entry("live-hook", now - timedelta(hours=2)) for _ in range(6)],
    ]
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    monkeypatch.setenv("CLAUDE_HOOK_ERRORS_PATH", str(path))
    _with_hook_files(monkeypatch, tmp_path, "live-hook")  # retired-hook.py absent

    failures = health.check_hook_error_repeat_offenders(now=now)
    notes = health.hook_error_repeat_offender_notes(now=now)

    assert len(failures) == 1
    assert "live-hook" in failures[0]
    assert all("retired-hook" not in f for f in failures)
    assert len(notes) == 1
    assert "retired-hook" in notes[0]
    assert "37" in notes[0]
    assert "No action needed" in notes[0]


def test_live_hook_never_appears_in_the_retired_notes(tmp_path, monkeypatch):
    """Notes are for absent files only; a present hook stays a hard failure."""
    now = datetime.now(timezone.utc)
    path = tmp_path / "hook-errors.jsonl"
    path.write_text("\n".join(_entry("live-hook", now) for _ in range(9)) + "\n", encoding="utf-8")
    monkeypatch.setenv("CLAUDE_HOOK_ERRORS_PATH", str(path))
    _with_hook_files(monkeypatch, tmp_path, "live-hook")

    assert health.hook_error_repeat_offender_notes(now=now) == []
    assert len(health.check_hook_error_repeat_offenders(now=now)) == 1


def test_path_shaped_hook_names_never_escape_the_hooks_dir(tmp_path, monkeypatch):
    """A hook field carrying a path must not be resolved outside hooks/."""
    now = datetime.now(timezone.utc)
    path = tmp_path / "hook-errors.jsonl"
    path.write_text("\n".join(_entry("../../etc/passwd", now) for _ in range(6)) + "\n", encoding="utf-8")
    monkeypatch.setenv("CLAUDE_HOOK_ERRORS_PATH", str(path))
    _with_hook_files(monkeypatch, tmp_path)

    assert health.check_hook_error_repeat_offenders(now=now) == []
    assert len(health.hook_error_repeat_offender_notes(now=now)) == 1


# --------------------------------------------------------------------------- #
# Matcher liveness: the repo's hooks run in a throwaway HOME seeded like CI,
# and a hook that crashes fails the check even when it exits 0.
# --------------------------------------------------------------------------- #

REAL_REPO = Path(__file__).resolve().parents[2]

_SWALLOWED_CRASH = """\
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent / "lib"))
from hook_utils import hook_error
try:
    raise RuntimeError("probe failure")
except Exception as exc:
    hook_error("swallowed", exc)
sys.exit(0)
"""

_PRINTED_TRACEBACK = """\
import sys, traceback
try:
    1 / 0
except ZeroDivisionError:
    traceback.print_exc()
sys.exit(0)
"""


def _liveness_repo(tmp_path, monkeypatch, hooks: dict[str, str]) -> Path:
    """A repo with real hooks/lib, a scripts/lib module, and settings registering *hooks* on PostToolUse:Write."""
    repo = tmp_path / "repo"
    (repo / "hooks" / "lib").mkdir(parents=True)
    for lib in (REAL_REPO / "hooks" / "lib").glob("*.py"):
        shutil.copy2(lib, repo / "hooks" / "lib" / lib.name)
    (repo / "scripts" / "lib").mkdir(parents=True)
    (repo / "scripts" / "lib" / "probe_scripts_lib.py").write_text("VALUE = 'scripts-lib'\n", encoding="utf-8")
    entries = []
    for name, body in hooks.items():
        (repo / "hooks" / name).write_text(body, encoding="utf-8")
        command = f'sh "$HOME/.claude/hooks/lib/pyrun.sh" "$HOME/.claude/hooks/{name}"'
        entries.append({"type": "command", "command": command, "timeout": 5})
    (repo / ".claude").mkdir()
    settings = {"hooks": {"PostToolUse": [{"matcher": "Write|Edit", "hooks": entries}]}}
    (repo / ".claude" / "settings.json").write_text(json.dumps(settings), encoding="utf-8")
    monkeypatch.setattr(health, "REPO_ROOT", repo)
    monkeypatch.setattr(health, "SETTINGS_PATH", repo / ".claude" / "settings.json")
    monkeypatch.setattr(health, "HOOKS_DIR", repo / "hooks")
    return repo


def test_matcher_liveness_fails_a_hook_that_records_a_hook_error_and_exits_zero(tmp_path, monkeypatch):
    """Most hooks catch their own exceptions and exit 0; the error log is the crash signal."""
    _liveness_repo(tmp_path, monkeypatch, {"swallowed.py": _SWALLOWED_CRASH, "fine.py": "import sys\n"})

    failures = health.check_matcher_liveness()

    assert len(failures) == 1, failures
    assert "PostToolUse/swallowed.py" in failures[0]
    assert "hook error" in failures[0] and "RuntimeError" in failures[0]


def test_matcher_liveness_fails_a_hook_that_exits_one(tmp_path, monkeypatch):
    _liveness_repo(tmp_path, monkeypatch, {"crash.py": "raise SystemExit(1)\n"})

    failures = health.check_matcher_liveness()

    assert len(failures) == 1, failures
    assert "PostToolUse/crash.py exited 1" in failures[0]


def test_matcher_liveness_fails_a_hook_that_prints_a_traceback_and_exits_zero(tmp_path, monkeypatch):
    _liveness_repo(tmp_path, monkeypatch, {"tb.py": _PRINTED_TRACEBACK})

    failures = health.check_matcher_liveness()

    assert len(failures) == 1, failures
    assert "PostToolUse/tb.py" in failures[0] and "traceback" in failures[0]


def test_matcher_liveness_runs_in_a_throwaway_home_seeded_like_ci(tmp_path, monkeypatch):
    """Never the real HOME, sync off, and hooks/lib, scripts/ and settings.json installed under it."""
    record = tmp_path / "probe.json"
    probe = (
        "import json, os, sys\n"
        "from pathlib import Path\n"
        "sys.path.insert(0, str(Path(__file__).resolve().parent.parent / 'scripts' / 'lib'))\n"
        "import probe_scripts_lib\n"
        f"Path({str(record)!r}).write_text(json.dumps({{\n"
        "    'home': os.environ['HOME'], 'sync': os.environ.get('VEXJOY_SYNC_DISABLED'),\n"
        "    'lib': probe_scripts_lib.VALUE, 'file': __file__,\n"
        "    'settings': (Path.home() / '.claude' / 'settings.json').is_file(),\n"
        "    'hook_lib': (Path(__file__).parent / 'lib' / 'hook_utils.py').is_file(),\n"
        "    'errors': os.environ.get('CLAUDE_HOOK_ERRORS_PATH'),\n"
        "}))\n"
    )
    _liveness_repo(tmp_path, monkeypatch, {"probe.py": probe})

    assert health.check_matcher_liveness() == []

    seen = json.loads(record.read_text(encoding="utf-8"))
    home = Path(seen["home"])
    assert home != Path.home() and not home.exists(), seen
    assert Path(seen["file"]).is_relative_to(home), seen
    assert seen["sync"] == "1" and seen["lib"] == "scripts-lib", seen
    assert seen["settings"] and seen["hook_lib"], seen
    assert seen["errors"] != os.environ.get("CLAUDE_HOOK_ERRORS_PATH"), "the run keeps its own error log"


def test_matcher_liveness_installs_only_tracked_scripts_in_a_git_checkout(tmp_path, monkeypatch):
    """Like a real install: an ignored or untracked file under scripts/ is not copied."""
    record = tmp_path / "probe.json"
    probe = (
        "import json\n"
        "from pathlib import Path\n"
        "scripts = Path.home() / '.claude' / 'scripts'\n"
        f"Path({str(record)!r}).write_text(json.dumps({{\n"
        "    'tracked': (scripts / 'lib' / 'probe_scripts_lib.py').is_file(),\n"
        "    'untracked': (scripts / 'untracked-output.txt').exists(),\n"
        "}))\n"
    )
    repo = _liveness_repo(tmp_path, monkeypatch, {"probe.py": probe})
    (repo / "scripts" / "untracked-output.txt").write_text("scratch\n", encoding="utf-8")
    git_env = {k: v for k, v in os.environ.items() if not k.startswith("GIT_")}
    git_env.update({"GIT_CONFIG_GLOBAL": os.devnull, "GIT_CONFIG_NOSYSTEM": "1"})
    subprocess.run(["git", "init", "-q"], cwd=repo, env=git_env, check=True, capture_output=True)
    subprocess.run(["git", "add", "scripts/lib"], cwd=repo, env=git_env, check=True, capture_output=True)

    assert health.check_matcher_liveness() == []

    assert json.loads(record.read_text(encoding="utf-8")) == {"tracked": True, "untracked": False}
