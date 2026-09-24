#!/usr/bin/env python3
"""Boundary cases for the PR-creation force-route guard (ADR pr-create-skill-guard).

The full phrasing corpus lives in scripts/routing-benchmark.json as
pre_route_only / pre_route_negative rows and is enforced by
scripts/routing-benchmark.py in CI. This file keeps one in-process case per
trigger family and idiom guard.

The corpus is the contract: if a phrase fails, fix the trigger or guard, do not
drop the case. See `adr/pr-create-skill-guard.md`.
"""

import importlib
import sys
from pathlib import Path

import pytest

pytestmark = pytest.mark.usefixtures("use_public_index")

SCRIPTS_DIR = Path(__file__).resolve().parents[1]


@pytest.fixture(scope="module")
def route():
    """In-process pre-route over the real indexes (entries load once per module)."""
    if str(SCRIPTS_DIR) not in sys.path:
        sys.path.insert(0, str(SCRIPTS_DIR))
    pre_route = importlib.import_module("pre-route")
    entries = pre_route.load_entries()
    return lambda phrase: pre_route.route(phrase, entries=entries)


POSITIVE = [
    "git push",  # bare git verb
    "ship it",  # ship idiom
    "draft a PR for the auth fix",  # PR noun with words between verb and noun
    "wrap this up and merge",  # merge intent
]

NEGATIVE = [
    "push back on this design",  # push idiom
    "ship of Theseus",  # ship idiom
    "publish a paper to arxiv",  # publish, not code
    "merge personalities at the offsite",  # merge idiom
]


@pytest.mark.parametrize("phrase", POSITIVE)
def test_force_routes_to_pr_workflow(route, phrase: str) -> None:
    result = route(phrase)
    assert (result["skill"], result["match_type"]) == ("pr-workflow", "force_route"), result


@pytest.mark.parametrize("phrase", NEGATIVE)
def test_does_not_force_route_to_pr_workflow(route, phrase: str) -> None:
    result = route(phrase)
    assert not (result.get("skill") == "pr-workflow" and result.get("match_type") == "force_route"), result
