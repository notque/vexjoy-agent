"""Tests for scripts/route-signal-check.py (the cheap actuator re-propose gate).

Exit 0 = NO-SIGNAL; exit 3 = SIGNAL (>=1 routing-relevant failure outcome OR
>=1 would-demote/would-tiebreak decision). Read-only: the script must never
write to the learning dir. Tests isolate via CLAUDE_LEARNING_DIR.
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

_repo_root = Path(__file__).resolve().parent.parent.parent
_SCRIPT = _repo_root / "scripts" / "route-signal-check.py"


def _run(learning_dir: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(_SCRIPT)],
        capture_output=True,
        text=True,
        env={"CLAUDE_LEARNING_DIR": str(learning_dir), "PATH": "/usr/bin:/bin"},
    )


def _write_events(learning_dir: Path, events: list[dict[str, object]], *, raw_suffix: str = "") -> None:
    learning_dir.mkdir(parents=True, exist_ok=True)
    lines = "".join(json.dumps(e) + "\n" for e in events) + raw_suffix
    (learning_dir / "route-events.jsonl").write_text(lines, encoding="utf-8")


def _decision(health: float | None, action: str | None) -> dict[str, object]:
    return {"type": "decision", "health_at_decision": health, "action": action}


def test_missing_log_is_no_signal(tmp_path: Path) -> None:
    """No route-events.jsonl at all: counts 0, exit 0."""
    result = _run(tmp_path / "learning")
    assert result.returncode == 0
    assert "routing-relevant failures: 0" in result.stdout
    assert "NO-SIGNAL" in result.stdout


def test_keep_decisions_are_no_signal(tmp_path: Path) -> None:
    """Scored keep-only decisions count as instrumented but carry no signal."""
    learning = tmp_path / "learning"
    _write_events(learning, [_decision(0.72, "keep"), _decision(None, None)])
    result = _run(learning)
    assert result.returncode == 0
    assert "decisions with health_at_decision: 1" in result.stdout


def test_routing_relevant_failure_signals(tmp_path: Path) -> None:
    """One routing-relevant failure outcome => exit 3."""
    learning = tmp_path / "learning"
    _write_events(
        learning,
        [{"type": "outcome", "outcome": "failure", "routing_relevant": True}],
    )
    result = _run(learning)
    assert result.returncode == 3
    assert "routing-relevant failures: 1" in result.stdout
    assert "SIGNAL" in result.stdout


def test_non_relevant_failure_is_no_signal(tmp_path: Path) -> None:
    """A failure without routing_relevant=true never signals."""
    learning = tmp_path / "learning"
    _write_events(
        learning,
        [
            {"type": "outcome", "outcome": "failure"},
            {"type": "outcome", "outcome": "failure", "routing_relevant": False},
            {"type": "outcome", "outcome": "neutral", "routing_relevant": True},
        ],
    )
    result = _run(learning)
    assert result.returncode == 0


def test_would_demote_signals(tmp_path: Path) -> None:
    """One would-demote decision => exit 3."""
    learning = tmp_path / "learning"
    _write_events(learning, [_decision(0.2, "demote")])
    result = _run(learning)
    assert result.returncode == 3
    assert "would-demote/would-tiebreak decisions: 1" in result.stdout


def test_would_tiebreak_signals(tmp_path: Path) -> None:
    """One would-tiebreak decision => exit 3."""
    learning = tmp_path / "learning"
    _write_events(learning, [_decision(0.9, "tiebreak")])
    result = _run(learning)
    assert result.returncode == 3


def test_malformed_lines_tolerated(tmp_path: Path) -> None:
    """Partial/garbage lines in the append-only log are skipped, not fatal."""
    learning = tmp_path / "learning"
    _write_events(learning, [_decision(0.5, "keep")], raw_suffix='{"type": "deci\nnot json\n')
    result = _run(learning)
    assert result.returncode == 0
    assert "decisions with health_at_decision: 1" in result.stdout


def test_read_only(tmp_path: Path) -> None:
    """The script never writes to the learning dir."""
    learning = tmp_path / "learning"
    _write_events(learning, [_decision(0.5, "keep")])
    before = sorted(p.name for p in learning.iterdir())
    mtime = (learning / "route-events.jsonl").stat().st_mtime_ns
    _run(learning)
    assert sorted(p.name for p in learning.iterdir()) == before
    assert (learning / "route-events.jsonl").stat().st_mtime_ns == mtime
