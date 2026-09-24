#!/usr/bin/env python3
"""Boundary cases for the deploy force-route guard (ADR deploy).

The full phrasing corpus (positives and idiom negatives) lives in
scripts/routing-benchmark.json as pre_route_only / pre_route_negative rows and is
enforced by scripts/routing-benchmark.py in CI. This file keeps one in-process
case per guard branch so a local run catches a regression fast.

Low-specificity idiom triggers are gated by a POSITIVE companion-word
requirement (a deploy/host term must sit near the trigger), not a blocklist.
The corpus is the contract: if a phrase fails, fix the trigger/guard, do not
drop the case. See `adr/deploy.md`.
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
    "put my website online",  # task-spec true positive
    "set up https on my public nginx site",  # idiom trigger with a deploy companion in-window
    "deploy my site to vercel",  # "deploy site" is unambiguous on its own
    "go live with my website",  # verb-only idiom confirmed by a plain site companion
    "make my website public on github pages",  # "make ... public" deploy family, managed hosting
    "deploy my landing page",  # deploy-target noun
]

NEGATIVE = [
    "use my domain knowledge to design the schema",  # task-spec false case
    "make the repo public",  # visibility op, not a web deploy
    "fix the CSS on my static site",  # static site without deploy intent
    "go live with the launch deck on production",  # generic companion must not satisfy the gate
    "host a website locally for testing",  # local/test intent (skill not_for)
    "compare static site generators for public docs",  # companion overload near a discuss verb
    "deploy sitemap.xml to the repo",  # last-word prefix overmatch
]


@pytest.mark.parametrize("phrase", POSITIVE)
def test_force_routes_to_deploy(route, phrase: str) -> None:
    result = route(phrase)
    assert (result["skill"], result["match_type"]) == ("deploy", "force_route"), result


@pytest.mark.parametrize("phrase", NEGATIVE)
def test_does_not_force_route_to_deploy(route, phrase: str) -> None:
    result = route(phrase)
    assert not (result.get("skill") == "deploy" and result.get("match_type") == "force_route"), result
