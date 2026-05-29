#!/usr/bin/env python3
"""Tests pinning the PR-creation force-route corpus from ADR pr-create-skill-guard.

Positive corpus: 19 phrasings of PR-creation intent that MUST force-route to
`pr-workflow`. Negative corpus: 6 idiomatic phrasings that overlap on trigger
words but mean something else, and MUST NOT match `pr-workflow`.

The corpus is the contract — if a phrase fails, fix the trigger or guard,
do not drop the test case. See `adr/pr-create-skill-guard.md` for the spec.
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


# Positive corpus from ADR pr-create-skill-guard Validation Plan table.
# Every phrase MUST force-route to pr-workflow.
POSITIVE_CORPUS = [
    # New phrasings the ADR explicitly added (12)
    "git push",
    "push to origin",
    "push my branch",
    "ship it",
    "ship this work",
    "merge these fixes",
    "make a pull request",
    "draft a PR for the auth fix",
    "publish my changes",
    "let's get this reviewed",
    "send this to GitHub",
    "wrap this up and merge",
    # Existing-passing phrasings the ADR pinned for regression protection (7)
    "open a PR for these changes",
    "create PR",
    "push my changes",
    "open PR",
    "open the PR",
    "submit PR",
    "create pull request",
]


# Negative corpus from ADR pr-create-skill-guard Validation Plan table.
# Every phrase MUST NOT match pr-workflow (idiomatic English overlaps).
NEGATIVE_CORPUS = [
    "push back on this design",
    "merge ideas in your head",
    "ship of Theseus",
    "publish a paper to arxiv",
    "review the menu",
    "merge personalities at the offsite",
]


@pytest.mark.parametrize("phrase", POSITIVE_CORPUS)
def test_positive_corpus_force_routes_to_pr_workflow(phrase: str) -> None:
    """Each PR-creation phrasing must force-route to pr-workflow."""
    result = _route(phrase)
    assert result["skill"] == "pr-workflow", (
        f"phrase {phrase!r} routed to skill={result.get('skill')!r}, expected pr-workflow. full result: {result}"
    )
    assert result["match_type"] == "force_route", (
        f"phrase {phrase!r} matched with match_type={result.get('match_type')!r}, "
        f"expected force_route. full result: {result}"
    )


@pytest.mark.parametrize("phrase", NEGATIVE_CORPUS)
def test_negative_corpus_does_not_match_pr_workflow(phrase: str) -> None:
    """Each idiomatic phrasing must not match pr-workflow as a force_route."""
    result = _route(phrase)
    skill = result.get("skill")
    match_type = result.get("match_type")
    # NOT pr-workflow as the chosen skill, OR if pr-workflow, it must not be a force_route.
    is_pr_force_route = skill == "pr-workflow" and match_type == "force_route"
    assert not is_pr_force_route, f"phrase {phrase!r} incorrectly force-routed to pr-workflow. full result: {result}"
