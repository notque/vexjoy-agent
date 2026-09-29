#!/usr/bin/env python3
"""Boundary cases for the deploy force-route guard (ADR deploy).

The full phrasing corpus (positives and idiom negatives) lives in
scripts/routing-benchmark.json as pre_route_only / pre_route_negative rows and is
enforced by scripts/routing-benchmark.py in CI, which owns the negatives. This
file keeps in-process positives so a local run catches a regression fast.

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


@pytest.mark.parametrize("phrase", POSITIVE)
def test_force_routes_to_deploy(route, phrase: str) -> None:
    result = route(phrase)
    assert (result["skill"], result["match_type"]) == ("deploy", "force_route"), result
