"""Tests for the resume agent-output cache helpers in feature-state.py.

Covers opportunity #1 from the token-efficiency backlog: caching per-agent
outputs in the resume artifact (HANDOFF.json) keyed by a deterministic input
hash, so an interrupted parallel agent wave can be resumed without re-dispatching
agents whose inputs are unchanged.

Helpers under test (all pure Python, no wall-clock/randomness in the hash):
- agent_input_hash(prompt, inputs=None) -> stable SHA256 hex digest
- load_agent_outputs(handoff) -> dict cache (backwards-compatible)
- store_agent_output(handoff, input_hash, output, label, timestamp) -> handoff
- lookup_agent_output(handoff, input_hash) -> cached entry or None
"""

from __future__ import annotations

import importlib
import sys
from pathlib import Path

# ─── Path setup ─────────────────────────────────────────────────────────────

_REPO_ROOT = Path(__file__).resolve().parent.parent.parent
_SCRIPTS_DIR = _REPO_ROOT / "scripts"
if str(_SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS_DIR))

feature_state = importlib.import_module("feature-state")


# ─── Hash determinism ───────────────────────────────────────────────────────


def test_hash_same_input_same_hash() -> None:
    """Same input twice produces the same hash (stable across runs)."""
    h1 = feature_state.agent_input_hash("review the diff", {"files": ["a.py", "b.py"]})
    h2 = feature_state.agent_input_hash("review the diff", {"files": ["a.py", "b.py"]})
    assert h1 == h2


def test_hash_is_sha256_hex() -> None:
    """Hash is a 64-char lowercase hex SHA256 digest."""
    h = feature_state.agent_input_hash("anything")
    assert len(h) == 64
    assert all(c in "0123456789abcdef" for c in h)


def test_hash_different_prompt_different_hash() -> None:
    """Different prompt text produces a different hash."""
    h1 = feature_state.agent_input_hash("review the diff")
    h2 = feature_state.agent_input_hash("review the tests")
    assert h1 != h2


def test_hash_different_inputs_different_hash() -> None:
    """Different inputs (same prompt) produce a different hash."""
    h1 = feature_state.agent_input_hash("review", {"files": ["a.py"]})
    h2 = feature_state.agent_input_hash("review", {"files": ["b.py"]})
    assert h1 != h2


def test_hash_input_order_independent() -> None:
    """Dict input ordering does not change the hash (normalized representation)."""
    h1 = feature_state.agent_input_hash("review", {"x": 1, "y": 2})
    h2 = feature_state.agent_input_hash("review", {"y": 2, "x": 1})
    assert h1 == h2


def test_hash_no_inputs_matches_empty_inputs() -> None:
    """Omitting inputs is equivalent to passing an empty/None inputs value."""
    assert feature_state.agent_input_hash("p") == feature_state.agent_input_hash("p", None)


# ─── Cache round-trip: miss → store → hit ────────────────────────────────────


def test_cache_miss_then_store_then_hit() -> None:
    """A fresh handoff misses, store records the output, lookup then hits."""
    handoff: dict = {"task_summary": "x"}
    h = feature_state.agent_input_hash("dispatch agent A", {"scope": "pkg/foo"})

    # Miss before store.
    assert feature_state.lookup_agent_output(handoff, h) is None

    feature_state.store_agent_output(
        handoff,
        input_hash=h,
        output="Agent A findings: looks good.",
        label="security-reviewer",
        timestamp="2026-05-28T00:00:00Z",
    )

    # Hit after store.
    entry = feature_state.lookup_agent_output(handoff, h)
    assert entry is not None
    assert entry["output"] == "Agent A findings: looks good."
    assert entry["label"] == "security-reviewer"
    assert entry["timestamp"] == "2026-05-28T00:00:00Z"


def test_store_persists_through_json_roundtrip(tmp_path: Path) -> None:
    """Stored cache survives a write/read of HANDOFF.json (real resume path)."""
    import json

    handoff: dict = {"task_summary": "x"}
    h = feature_state.agent_input_hash("dispatch agent B")
    feature_state.store_agent_output(handoff, input_hash=h, output="B done", label="arch-reviewer", timestamp="t")

    path = tmp_path / "HANDOFF.json"
    path.write_text(json.dumps(handoff))
    reloaded = json.loads(path.read_text())

    assert feature_state.lookup_agent_output(reloaded, h)["output"] == "B done"


def test_store_returns_handoff_for_chaining() -> None:
    """store_agent_output returns the handoff so callers can chain/store-back."""
    handoff: dict = {}
    result = feature_state.store_agent_output(handoff, input_hash="abc", output="o", label="l", timestamp="t")
    assert result is handoff


# ─── Backwards compatibility ─────────────────────────────────────────────────


def test_load_missing_field_is_empty_cache() -> None:
    """A handoff lacking agent_outputs loads as an empty cache, no error."""
    legacy_handoff = {
        "created_at": "2026-01-01T00:00:00Z",
        "task_summary": "old session",
        "completed_tasks": ["a"],
        "remaining_tasks": ["b"],
    }
    cache = feature_state.load_agent_outputs(legacy_handoff)
    assert cache == {}


def test_lookup_on_legacy_handoff_is_miss() -> None:
    """Lookup against a legacy handoff (no agent_outputs) is a clean miss."""
    legacy_handoff = {"task_summary": "old"}
    assert feature_state.lookup_agent_output(legacy_handoff, "anyhash") is None


def test_store_into_legacy_handoff_creates_field() -> None:
    """Storing into a legacy handoff creates agent_outputs without dropping data."""
    legacy_handoff = {"task_summary": "old", "completed_tasks": ["a"]}
    feature_state.store_agent_output(legacy_handoff, input_hash="h1", output="o", label="l", timestamp="t")
    assert legacy_handoff["task_summary"] == "old"
    assert legacy_handoff["completed_tasks"] == ["a"]
    assert "agent_outputs" in legacy_handoff
    assert legacy_handoff["agent_outputs"]["h1"]["output"] == "o"
