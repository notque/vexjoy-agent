#!/usr/bin/env python3
"""Tests for hook-error repeat-offender and matcher-liveness health checks."""

import contextlib
import importlib.util
import json
import os
import shutil
import signal
import subprocess
import tempfile
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

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
    """Like the CI checkout: an ignored or untracked file under scripts/ is not copied."""
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


# A hook may start work in the background and exit at once, as
# rules-distill-trigger does with rules-distill.py. That work has to finish, or
# be ended, inside the hook's own check: left running, it writes into the
# throwaway HOME while it is deleted (the cleanup then fails with "Directory not
# empty", or the write recreates the deleted tree) and outlives the validator.

_BACKGROUND_CHILD = (
    "import sys, time\n"
    "from pathlib import Path\n"
    "time.sleep(float(sys.argv[1]))\n"
    "late = Path.home() / '.claude' / 'learning'\n"
    "late.mkdir(parents=True, exist_ok=True)\n"
    "(late / 'late-write.json').write_text('{}')\n"
)


def _background_hook(record: Path, delay_s: float) -> str:
    """A hook that starts _BACKGROUND_CHILD, records its pid and HOME, and exits at once."""
    return (
        "import json, os, subprocess, sys\n"
        "from pathlib import Path\n"
        f"child = {_BACKGROUND_CHILD!r}\n"
        f"proc = subprocess.Popen([sys.executable, '-c', child, {str(delay_s)!r}],\n"
        "                        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)\n"
        f"Path({str(record)!r}).write_text(json.dumps({{'pid': proc.pid, 'home': os.environ['HOME']}}))\n"
    )


def _running(pid: int) -> bool:
    """True while *pid* runs; a zombie waiting to be reaped has ended."""
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    try:
        return Path(f"/proc/{pid}/stat").read_text(encoding="utf-8").rsplit(")", 1)[1].split()[0] != "Z"
    except (OSError, IndexError):
        return True


def _wait_until(predicate, timeout_s: float = 10.0) -> bool:
    deadline = time.monotonic() + timeout_s
    while not predicate():
        if time.monotonic() > deadline:
            return False
        time.sleep(0.05)
    return True


def _background_case(tmp_path, monkeypatch, delay_s: float) -> Path:
    """A liveness repo with one background-starting hook; the throwaway HOME is created under tmp_path."""
    record = tmp_path / "child.json"
    _liveness_repo(tmp_path, monkeypatch, {"bg.py": _background_hook(record, delay_s)})
    (tmp_path / "tmp").mkdir()
    monkeypatch.setattr(tempfile, "tempdir", str(tmp_path / "tmp"))
    return record


@pytest.mark.skipif(not hasattr(os, "killpg"), reason="hooks run in their own POSIX session")
def test_matcher_liveness_lets_background_work_finish_before_deleting_its_home(tmp_path, monkeypatch):
    record = _background_case(tmp_path, monkeypatch, delay_s=0.5)

    assert health.check_matcher_liveness() == []

    child = json.loads(record.read_text(encoding="utf-8"))
    assert _wait_until(lambda: not _running(child["pid"])), "the background child never ended"
    assert not Path(child["home"]).exists(), "background work recreated the deleted throwaway HOME"


@pytest.mark.skipif(not hasattr(os, "killpg"), reason="hooks run in their own POSIX session")
def test_matcher_liveness_ends_background_work_that_outlives_the_grace(tmp_path, monkeypatch):
    record = _background_case(tmp_path, monkeypatch, delay_s=60)
    monkeypatch.setattr(health, "_BACKGROUND_GRACE_S", 0.5)
    try:
        assert health.check_matcher_liveness() == []

        child = json.loads(record.read_text(encoding="utf-8"))
        assert not _running(child["pid"]), "a hook's background work outlived the liveness check"
        assert not Path(child["home"]).exists()
    finally:
        if record.is_file():
            with contextlib.suppress(OSError):
                os.kill(json.loads(record.read_text(encoding="utf-8"))["pid"], signal.SIGKILL)


def _orphan_fixture(tmp_path, monkeypatch, allowlist: str) -> dict:
    """A hooks dir with one registered hook and one orphan, plus the given allowlist text."""
    hooks_dir = tmp_path / "hooks"
    hooks_dir.mkdir()
    for name in ("registered.py", "orphan.py"):
        (hooks_dir / name).write_text("# stub\n", encoding="utf-8")
    allow = tmp_path / "allowlist.txt"
    allow.write_text(allowlist, encoding="utf-8")
    monkeypatch.setattr(health, "HOOKS_DIR", hooks_dir)
    monkeypatch.setattr(health, "ALLOWLIST_PATH", allow)
    command = 'sh "$HOME/.claude/hooks/lib/pyrun.sh" "$HOME/.claude/hooks/registered.py"'
    return {"hooks": {"PreToolUse": [{"hooks": [{"type": "command", "command": command}]}]}}


def test_orphan_hook_fails_until_it_is_allowlisted_with_a_reason(tmp_path, monkeypatch):
    settings = _orphan_fixture(tmp_path, monkeypatch, "")

    failures = health.check_no_dormant(settings)

    assert len(failures) == 1
    assert "hooks/orphan.py" in failures[0] and "registered.py" not in failures[0]


def test_allowlisted_orphan_passes(tmp_path, monkeypatch):
    settings = _orphan_fixture(tmp_path, monkeypatch, "orphan.py  # retired stub kept for compatibility\n")

    assert health.check_no_dormant(settings) == []
    assert health.check_allowlist_entries_have_reasons() == []


def test_allowlist_entry_for_a_removed_hook_fails(tmp_path, monkeypatch):
    _orphan_fixture(tmp_path, monkeypatch, "gone.py  # retired stub kept for compatibility\n")

    assert any("hooks/gone.py" in msg for msg in health.check_allowlist_not_stale())
