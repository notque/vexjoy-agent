"""Tests for the shadow replay (scripts/route-replay.py).

The replay runs `health_adjust()` over a corpus in two arms:
  - REAL: gold pick, no alternates, supplied weights. With healthy weights
    (>=0.5 conf, 0 failures) it must change 0 routes.
  - SYNTHETIC: a seeded temp DB with failure-bearing rows. Non-force-route
    picks demote toward the healthy gold alternate (help>0, harm=0); force-route
    picks are kept (exemption holds under the same failure load).

Tests run on a tiny fixture corpus + a temp DB; the live DB is never touched.
"""

from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

import pytest

_REPO_ROOT = Path(__file__).resolve().parent.parent.parent
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))


def _load_replay():
    """Import scripts/route-replay.py as a module (hyphenated filename)."""
    spec = importlib.util.spec_from_file_location("route_replay", _REPO_ROOT / "scripts" / "route-replay.py")
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture
def tiny_corpora(tmp_path: Path) -> tuple[Path, Path]:
    """Write two tiny corpus files: one force-route case, two normal cases."""
    ab = {
        "version": "test",
        "test_cases": [
            {"request": "send commits", "expected_agent": None, "expected_skill": "pr-workflow"},
            {
                "request": "write a function",
                "expected_agent": "python-general-engineer",
                "expected_skill": "test-driven-development",
            },
        ],
    }
    bm = {
        "version": "test",
        "test_cases": [
            {"request": "scan for vulns", "expected_agent": None, "expected_skill": "security-review"},
            {"request": "explore the repo", "expected_agent": "explore", "expected_skill": "codebase-overview"},
            {"request": "no skill case", "expected_agent": None, "expected_skill": None},
        ],
    }
    ab_path = tmp_path / "ab.json"
    bm_path = tmp_path / "bm.json"
    ab_path.write_text(json.dumps(ab), encoding="utf-8")
    bm_path.write_text(json.dumps(bm), encoding="utf-8")
    return ab_path, bm_path


def test_real_arm_zero_changes_on_healthy_weights(tiny_corpora: tuple[Path, Path], tmp_path: Path) -> None:
    """With healthy weights and gold picks the real arm changes 0 routes."""
    rr = _load_replay()
    ab_path, bm_path = tiny_corpora
    # Healthy weights for every gold key (>=0.5 conf, 0 failures).
    weights = {
        "direct:pr-workflow": {"confidence": 0.7, "n": 5, "success": 5, "failure": 0, "last_seen": "x"},
        "python-general-engineer:test-driven-development": {
            "confidence": 0.7,
            "n": 5,
            "success": 5,
            "failure": 0,
            "last_seen": "x",
        },
        "direct:security-review": {"confidence": 0.7, "n": 5, "success": 5, "failure": 0, "last_seen": "x"},
        "explore:codebase-overview": {"confidence": 0.7, "n": 5, "success": 5, "failure": 0, "last_seen": "x"},
    }
    db_dir = tmp_path / "syn-learning"
    result = rr.run_replay(ab_path, bm_path, db_dir=db_dir, real_weights=weights)

    real = result["real"]
    # 4 cases have a gold skill (the 5th has none and is skipped).
    assert real["evaluated"] == 4
    assert real["changed"] == 0
    assert real["help"] == 0
    assert real["harm"] == 0
    assert real["unchanged"] == 4


def test_synthetic_arm_help_positive_harm_zero(tiny_corpora: tuple[Path, Path], tmp_path: Path) -> None:
    """Synthetic arm demotes failing non-force picks toward gold; force-route held."""
    rr = _load_replay()
    ab_path, bm_path = tiny_corpora
    db_dir = tmp_path / "syn-learning"
    result = rr.run_replay(ab_path, bm_path, db_dir=db_dir, real_weights={})

    syn = result["synthetic"]
    assert syn["harm"] == 0, syn["changes"]
    # Two non-force-route cases (tdd, codebase-overview) demote toward gold.
    assert syn["help"] == 2
    # Two force-route cases (pr-workflow, security-review) held by exemption.
    assert syn["force_route_held"] == 2


def test_force_route_never_demoted_under_failure(tiny_corpora: tuple[Path, Path], tmp_path: Path) -> None:
    """A force-route pair seeded into the floor is still kept (exemption)."""
    rr = _load_replay()
    ab_path, bm_path = tiny_corpora
    db_dir = tmp_path / "syn-learning"
    result = rr.run_replay(ab_path, bm_path, db_dir=db_dir, real_weights={})
    syn = result["synthetic"]
    # No change ever lands a force-route pair on a non-gold pick.
    for change in syn["changes"]:
        assert "pr-workflow" not in str(change["from"])
        assert "security-review" not in str(change["from"])


def test_tiebreak_arm_help_positive_harm_zero(tiny_corpora: tuple[Path, Path], tmp_path: Path) -> None:
    """Tie-break arm moves low-confidence non-force picks toward gold; force held.

    Proves the honest counter to "Step 1.5 cannot change a live route on healthy
    data": tie-break keys on semantic confidence, so it fires with zero failures.
    """
    rr = _load_replay()
    ab_path, bm_path = tiny_corpora
    db_dir = tmp_path / "learning"
    result = rr.run_replay(ab_path, bm_path, db_dir=db_dir, real_weights={})

    tb = result["tiebreak"]
    assert tb["harm"] == 0, tb["changes"]
    # Two non-force-route cases (tdd, codebase-overview) tie-break toward gold.
    assert tb["help"] == 2
    # Two force-route cases (pr-workflow, security-review) held by exemption.
    assert tb["force_route_held"] == 2


def test_render_markdown_reports_real_zero_finding(tiny_corpora: tuple[Path, Path], tmp_path: Path) -> None:
    """Markdown renders the honest 0-change finding when the real arm is inert."""
    rr = _load_replay()
    ab_path, bm_path = tiny_corpora
    weights = {
        "direct:pr-workflow": {"confidence": 0.7, "n": 5, "success": 5, "failure": 0, "last_seen": "x"},
        "python-general-engineer:test-driven-development": {
            "confidence": 0.7,
            "n": 5,
            "success": 5,
            "failure": 0,
            "last_seen": "x",
        },
        "direct:security-review": {"confidence": 0.7, "n": 5, "success": 5, "failure": 0, "last_seen": "x"},
        "explore:codebase-overview": {"confidence": 0.7, "n": 5, "success": 5, "failure": 0, "last_seen": "x"},
    }
    db_dir = tmp_path / "syn-learning"
    result = rr.run_replay(ab_path, bm_path, db_dir=db_dir, real_weights=weights)
    md = rr.render_markdown(result)
    assert "changes **0** routes" in md
    assert "harm=0" in md or "harm (away from gold): **0**" in md
