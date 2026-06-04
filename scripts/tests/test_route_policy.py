"""Tests for the pure `health_adjust()` routing policy (scripts/lib/route_policy.py).

health_adjust is a PURE function: no I/O, no DB, no clock. Given the semantic
pick, its alternates, the T1 weight map, and the set of force-routed pairs, it
returns {final_pick, action, reason}. The policy:

  - Evidence gate: with fewer than MIN_OBSERVATIONS (5) observations on the
    pick, never demote (insufficient evidence). Default = semantic pick stands.
  - Floor demote: demote ONLY if confidence < 0.30 AND failure >= 3 AND n >= 5.
  - Force-route / security pairs are NEVER demoted (hard exempt) — the most
    important guarantee in the build.
  - Tie-break toward higher-health alternate ONLY when the semantic confidence
    is "low"; otherwise the semantic pick stands.
  - High-failure pick loses to a high-success alternate (when demotable + a
    healthier candidate exists).
  - A fresh pick (n < 5) is never demoted.

These tests import the function directly — no subprocess, no DB.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

_repo_root = Path(__file__).resolve().parent.parent.parent
if str(_repo_root) not in sys.path:
    sys.path.insert(0, str(_repo_root))

from scripts.lib.route_policy import (
    MIN_OBSERVATIONS,
    health_adjust,
)


def _w(confidence: float, n: int, success: int, failure: int) -> dict[str, object]:
    """Build one weight-map entry."""
    return {
        "confidence": confidence,
        "n": n,
        "success": success,
        "failure": failure,
        "last_seen": "2026-06-01T00:00:00",
    }


# --- evidence gate ---------------------------------------------------------


def test_gate_noop_below_min_observations() -> None:
    """A pick with n < 5 is never demoted even if confidence is in the floor."""
    pick = {"key": "agent-a:skill-a", "confidence": 0.9}
    weights = {"agent-a:skill-a": _w(0.10, MIN_OBSERVATIONS - 1, 0, MIN_OBSERVATIONS - 1)}
    result = health_adjust(pick, [], weights, set())
    assert result["final_pick"] == "agent-a:skill-a"
    assert result["action"] == "keep"


def test_fresh_pick_never_demoted() -> None:
    """A pick with no weight row at all (brand new) stands unchanged."""
    pick = {"key": "agent-new:skill-new", "confidence": 0.9}
    result = health_adjust(pick, ["agent-b:skill-b"], {}, set())
    assert result["final_pick"] == "agent-new:skill-new"
    assert result["action"] == "keep"


# --- floor demote ----------------------------------------------------------


def test_floor_demote_fires_on_seeded_data() -> None:
    """conf < 0.30 AND failure >= 3 AND n >= 5 demotes the pick."""
    pick = {"key": "agent-bad:skill-bad", "confidence": 0.5}
    weights = {
        "agent-bad:skill-bad": _w(0.20, 8, 2, 6),
        "agent-good:skill-good": _w(0.85, 10, 9, 1),
    }
    result = health_adjust(pick, ["agent-good:skill-good"], weights, set())
    assert result["action"] == "demote"
    assert result["final_pick"] == "agent-good:skill-good"


def test_floor_held_when_failure_below_three() -> None:
    """Low confidence alone (failure < 3) does NOT demote."""
    pick = {"key": "agent-x:skill-x", "confidence": 0.5}
    weights = {"agent-x:skill-x": _w(0.20, 6, 4, 2)}
    result = health_adjust(pick, ["agent-good:skill-good"], weights, set())
    assert result["action"] == "keep"
    assert result["final_pick"] == "agent-x:skill-x"


def test_floor_held_when_confidence_at_or_above_threshold() -> None:
    """confidence == 0.30 is not below the floor; no demote."""
    pick = {"key": "agent-x:skill-x", "confidence": 0.5}
    weights = {"agent-x:skill-x": _w(0.30, 9, 3, 5)}
    result = health_adjust(pick, ["agent-good:skill-good"], weights, set())
    assert result["action"] == "keep"


# --- force-route exemption (THE critical test) -----------------------------


def test_force_route_pair_never_demoted() -> None:
    """A force-routed pair in the floor with a healthier alternate STAYS.

    This is the most important guarantee in the entire build: a force-route /
    security pair can never be re-ranked away, regardless of its health.
    """
    pick = {"key": "security-reviewer:security-review", "confidence": 0.5}
    weights = {
        "security-reviewer:security-review": _w(0.05, 20, 1, 18),
        "agent-good:skill-good": _w(0.99, 50, 50, 0),
    }
    result = health_adjust(
        pick,
        ["agent-good:skill-good"],
        weights,
        {"security-reviewer:security-review"},
    )
    assert result["final_pick"] == "security-reviewer:security-review"
    assert result["action"] == "keep"
    assert "force" in result["reason"].lower() or "exempt" in result["reason"].lower()


def test_force_route_by_skill_name_exempt() -> None:
    """Force-route flag given as bare skill name (not full pair) still exempts."""
    pick = {"key": "security-reviewer:security-review", "confidence": 0.5}
    weights = {
        "security-reviewer:security-review": _w(0.05, 20, 1, 18),
        "agent-good:skill-good": _w(0.99, 50, 50, 0),
    }
    result = health_adjust(pick, ["agent-good:skill-good"], weights, {"security-review"})
    assert result["final_pick"] == "security-reviewer:security-review"
    assert result["action"] == "keep"


def test_force_route_pair_flag_different_agent_still_exempt() -> None:
    """Attack C: flag is a full pair whose AGENT differs from the pick's agent.

    Force-route protection is keyed by SKILL: a security skill must be exempt no
    matter which agent the semantic layer paired it with. A flag
    ``other-agent:security-review`` must still protect a pick
    ``pick-agent:security-review`` (same skill, different agent). Pre-fix this
    returned demote (the skill-name fallback compared against a full-pair flag
    and missed).
    """
    pick = {"key": "pick-agent:security-review", "confidence": 0.5}
    weights = {
        "pick-agent:security-review": _w(0.05, 20, 1, 18),
        "agent-good:skill-good": _w(0.99, 50, 50, 0),
    }
    result = health_adjust(pick, ["agent-good:skill-good"], weights, {"other-agent:security-review"})
    assert result["final_pick"] == "pick-agent:security-review"
    assert result["action"] == "keep"


# --- comparative health ----------------------------------------------------


def test_high_failure_loses_to_high_success() -> None:
    """A demotable high-failure pick yields to the healthiest alternate."""
    pick = {"key": "agent-bad:skill-bad", "confidence": 0.5}
    weights = {
        "agent-bad:skill-bad": _w(0.10, 12, 2, 10),
        "agent-mid:skill-mid": _w(0.55, 10, 6, 4),
        "agent-best:skill-best": _w(0.95, 20, 19, 1),
    }
    result = health_adjust(pick, ["agent-mid:skill-mid", "agent-best:skill-best"], weights, set())
    assert result["action"] == "demote"
    assert result["final_pick"] == "agent-best:skill-best"


def test_demote_keeps_pick_when_no_healthier_alternate() -> None:
    """If every alternate is also unhealthy, the pick stands (nowhere to go)."""
    pick = {"key": "agent-bad:skill-bad", "confidence": 0.5}
    weights = {
        "agent-bad:skill-bad": _w(0.10, 12, 2, 10),
        "agent-worse:skill-worse": _w(0.05, 15, 1, 14),
    }
    result = health_adjust(pick, ["agent-worse:skill-worse"], weights, set())
    assert result["final_pick"] == "agent-bad:skill-bad"
    assert result["action"] == "keep"


# --- low-confidence tie-break ----------------------------------------------


def test_tiebreak_only_when_semantic_low() -> None:
    """With LOW semantic confidence, tie-break toward the higher-health alternate."""
    pick = {"key": "agent-a:skill-a", "confidence": 0.2}
    weights = {
        "agent-a:skill-a": _w(0.50, 8, 4, 4),
        "agent-b:skill-b": _w(0.90, 12, 11, 1),
    }
    result = health_adjust(pick, ["agent-b:skill-b"], weights, set())
    assert result["action"] == "tiebreak"
    assert result["final_pick"] == "agent-b:skill-b"


def test_tiebreak_requires_evidenced_alternate() -> None:
    """Tie-break never moves toward an under-evidenced alternate (n < 5).

    Low semantic confidence alone is not enough: the healthier alternate must
    clear the evidence gate. A flashy but under-observed alternate is ignored,
    and the semantic pick stands. This bounds the tie-break path so it cannot
    reroute toward thin evidence.
    """
    pick = {"key": "agent-a:skill-a", "confidence": 0.2}
    weights = {
        "agent-a:skill-a": _w(0.50, 8, 4, 4),
        "agent-b:skill-b": _w(0.99, MIN_OBSERVATIONS - 1, MIN_OBSERVATIONS - 1, 0),
    }
    result = health_adjust(pick, ["agent-b:skill-b"], weights, set())
    assert result["action"] == "keep"
    assert result["final_pick"] == "agent-a:skill-a"


def test_tiebreak_does_not_fire_with_no_alternates() -> None:
    """Low semantic confidence + no alternates supplied => pick stands.

    The real-DB replay arm offers no alternates, so tie-break cannot fire there
    even though semantic confidence is moot. Documents why the real arm is 0.
    """
    pick = {"key": "agent-a:skill-a", "confidence": 0.1}
    weights = {"agent-a:skill-a": _w(0.50, 8, 4, 4)}
    result = health_adjust(pick, [], weights, set())
    assert result["action"] == "keep"
    assert result["final_pick"] == "agent-a:skill-a"


def test_no_tiebreak_when_semantic_high() -> None:
    """With HIGH semantic confidence, the semantic pick stands despite health gap."""
    pick = {"key": "agent-a:skill-a", "confidence": 0.95}
    weights = {
        "agent-a:skill-a": _w(0.50, 8, 4, 4),
        "agent-b:skill-b": _w(0.90, 12, 11, 1),
    }
    result = health_adjust(pick, ["agent-b:skill-b"], weights, set())
    assert result["action"] == "keep"
    assert result["final_pick"] == "agent-a:skill-a"


def test_default_semantic_pick_stands() -> None:
    """Healthy pick, healthy data, normal confidence => keep, no surprises."""
    pick = {"key": "agent-a:skill-a", "confidence": 0.7}
    weights = {"agent-a:skill-a": _w(0.80, 30, 28, 2)}
    result = health_adjust(pick, ["agent-b:skill-b"], weights, set())
    assert result["action"] == "keep"
    assert result["final_pick"] == "agent-a:skill-a"


# --- output contract -------------------------------------------------------


def test_result_shape_has_required_keys() -> None:
    """Every return carries final_pick, action, reason."""
    pick = {"key": "agent-a:skill-a", "confidence": 0.7}
    result = health_adjust(pick, [], {}, set())
    assert set(result) >= {"final_pick", "action", "reason"}
    assert isinstance(result["reason"], str) and result["reason"]


def test_purity_inputs_not_mutated() -> None:
    """The function mutates none of its inputs (pure)."""
    pick = {"key": "agent-bad:skill-bad", "confidence": 0.5}
    alternates = ["agent-good:skill-good"]
    weights = {
        "agent-bad:skill-bad": _w(0.10, 8, 1, 7),
        "agent-good:skill-good": _w(0.95, 10, 10, 0),
    }
    forced: set[str] = set()
    import copy

    pick_c, alt_c, w_c, f_c = (
        copy.deepcopy(pick),
        copy.deepcopy(alternates),
        copy.deepcopy(weights),
        set(forced),
    )
    health_adjust(pick, alternates, weights, forced)
    assert pick == pick_c
    assert alternates == alt_c
    assert weights == w_c
    assert forced == f_c
