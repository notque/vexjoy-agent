"""Tests pinning the planning force-route trigger corpus (audit defect D7).

`planning` is force_route: true. Its former bare unigram triggers
(`continue`, `resume`, `pause`, `handoff`, `unsure`) force-routed ordinary
English requests ("continue fixing the login bug") to planning at high
confidence. The fix replaced them with phrases at the trigger source
(skills/process/planning/SKILL.md frontmatter).

Negative corpus: 6 idiomatic requests that MUST NOT force-route to planning.
Positive corpus: 4 genuine planning requests that MUST still force-route.

The corpus is the contract — if a phrase fails, fix the trigger, do not
drop the test case. See adr/router-improvement-program.md (C1).
"""

import json
import subprocess
import sys
from pathlib import Path

import pytest

SCRIPT = Path(__file__).resolve().parents[1] / "pre-route.py"


def _route(phrase: str) -> dict:
    """Invoke pre-route.py CLI and parse JSON output."""
    proc = subprocess.run(
        [sys.executable, str(SCRIPT), "--request", phrase, "--json-compact"],
        capture_output=True,
        text=True,
        check=False,
    )
    assert proc.returncode == 0, f"pre-route.py exited {proc.returncode}: {proc.stderr}"
    return json.loads(proc.stdout)


# Ordinary English requests that share a word with old planning unigram
# triggers. None of them is a plan-lifecycle request.
NEGATIVE_CORPUS = [
    "continue fixing the login bug",
    "resume the download",
    "pause the music player script",
    "unsure if this test is flaky",
    "continue reviewing PR 12",
    "hand off the ball to the receiver",
]

# Genuine plan-lifecycle requests that must keep their force-route.
POSITIVE_CORPUS = [
    "resume the plan we paused yesterday",
    "pause this plan and hand off to the next session",
    "create a plan for the database migration",
    "resume where we left off with the migration plan",
]


@pytest.mark.parametrize("phrase", NEGATIVE_CORPUS)
def test_idiom_does_not_force_route_planning(phrase: str) -> None:
    """Ordinary requests never force-route to planning."""
    result = _route(phrase)
    is_planning_force = result.get("skill") == "planning" and result.get("match_type") == "force_route"
    assert not is_planning_force, f"'{phrase}' force-routed to planning: {result}"


@pytest.mark.parametrize("phrase", POSITIVE_CORPUS)
def test_genuine_planning_request_force_routes(phrase: str) -> None:
    """Plan-lifecycle requests force-route to planning at high confidence."""
    result = _route(phrase)
    assert result["matched"] is True, f"'{phrase}' did not match: {result}"
    assert result["skill"] == "planning", f"'{phrase}' routed to {result['skill']}: {result}"
    assert result["match_type"] == "force_route", f"'{phrase}' lost force-route: {result}"
    assert result["confidence"] == "high", f"'{phrase}' lost high confidence: {result}"
