"""Tests pinning the process force-route trigger corpus (audit defect D7).

After skill consolidation, the `planning` skill was absorbed into `process`.
Plan-lifecycle phrases may route to `process` or `workflow` depending on
trigger coverage. The negative corpus remains: ordinary English must not
force-route to process.

Negative corpus: 6 idiomatic requests that MUST NOT force-route to process.
Positive corpus: plan-lifecycle phrases — route to process or workflow,
never fallthrough.

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


# Ordinary English requests that share a word with old process unigram
# triggers. None of them is a plan-lifecycle request.
NEGATIVE_CORPUS = [
    "continue fixing the login bug",
    "resume the download",
    "pause the music player script",
    "unsure if this test is flaky",
    "continue reviewing PR 12",
    "hand off the ball to the receiver",
]

# Genuine plan-lifecycle requests. After consolidation, these route to
# process or workflow (not fallthrough).
POSITIVE_CORPUS = [
    "create a plan for the database migration",
]


@pytest.mark.parametrize("phrase", NEGATIVE_CORPUS)
def test_idiom_does_not_force_route_process(phrase: str) -> None:
    """Ordinary requests never force-route to process."""
    result = _route(phrase)
    is_process_force = result.get("skill") == "process" and result.get("match_type") == "force_route"
    assert not is_process_force, f"'{phrase}' force-routed to process: {result}"


@pytest.mark.parametrize("phrase", POSITIVE_CORPUS)
def test_genuine_plan_request_force_routes(phrase: str) -> None:
    """Plan-lifecycle requests force-route to process or workflow."""
    result = _route(phrase)
    assert result["matched"] is True, f"'{phrase}' did not match: {result}"
    assert result["skill"] in {"process", "workflow"}, f"'{phrase}' routed to {result['skill']}: {result}"
    assert result["match_type"] == "force_route", f"'{phrase}' lost force-route: {result}"
