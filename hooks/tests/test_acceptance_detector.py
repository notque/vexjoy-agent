#!/usr/bin/env python3
"""Golden-fixture tests for the finalizer's acceptance detector + basis label.

Mirror of the rejection detector's precision contract (asymmetric costs):
a MISSED acceptance stays NEUTRAL (the T4 floor — no harm); a FALSE
acceptance boosts a route on a new-task prompt, inflating exactly the
silent-success share this detector exists to shrink. So acceptance fires
ONLY on strong, unambiguous markers that LEAD the prompt (first clause)
or stand alone, with negation / task-verb / instructional-cue vetoes.

Covers:
- every curated marker fires (positive goldens)
- every negation / buried-in-task / instructional case stays neutral
- outcome_basis grows the acceptance_detected label (errors > rejection >
  acceptance > default ordering preserved)

Run with: python3 -m pytest hooks/tests/test_acceptance_detector.py -v
"""

import importlib.util
import sys
from pathlib import Path
from unittest.mock import patch

import pytest

HOOKS_DIR = Path(__file__).parent.parent
sys.path.insert(0, str(HOOKS_DIR / "lib"))

spec = importlib.util.spec_from_file_location("routing_outcome_finalizer", HOOKS_DIR / "routing-outcome-finalizer.py")
mod = importlib.util.module_from_spec(spec)
with patch("sys.exit"):
    spec.loader.exec_module(mod)


# --- positive goldens: every marker fires ------------------------------------

ACCEPTS = [
    "thanks",
    "thank you",
    "thx",
    "great job",
    "perfect",
    "looks good",
    "lgtm",
    "nice work",
    "well done",
    "that worked",
    "works now",
    "that fixed it",
    "that did it",
    "good job",
    "merge it",
    "ship it",
    "approved",
    "thanks, works",  # acceptance clause leads; comma splits it clean
    "perfect, now add tests to the other module",  # leading acceptance, new work later
    "great job. one more thing: update the docs",
    "lgtm, merge it",
    "ok that worked",
]


@pytest.mark.parametrize("prompt", ACCEPTS)
def test_acceptance_fires(prompt):
    assert mod.is_acceptance(prompt) is True, prompt


# --- negative goldens: negation / buried / instructional stay neutral --------

NEUTRALS = [
    # negation
    "not perfect",
    "that's not perfect",
    "this doesn't work, thanks anyway",
    "it still isn't perfect",
    "no thanks",
    "it didn't work",
    # marker buried in NEW task text (first clause is a task, not a reaction)
    "make a great landing page",
    "write the perfect README for this repo",
    "add a thanks page to the site",
    "build something that works now and later",
    "create a looks good badge for the CI",
    # instructional / conditional cues
    "can you make it perfect",
    "try to get it perfect this time",
    "explain why lgtm reviews are risky",
    "document when ship it applies",
    "if it looks good then merge",
    # long task-shaped first clause (not a terse reaction)
    "refactor the parser so the output is perfect for downstream consumers and then rerun the suite",
    # plain new-topic prompts
    "now refactor the auth module",
    "what does route-health report",
    # empty / junk
    "",
    None,
    123,
]


@pytest.mark.parametrize("prompt", NEUTRALS)
def test_neutral_stays_neutral(prompt):
    assert mod.is_acceptance(prompt) is False, prompt


# --- acceptance never flips a genuine rejection -------------------------------


def test_rejection_still_wins_its_own_goldens():
    assert mod.is_rejection("that's wrong, redo it") is True
    assert mod.is_rejection("thanks, that worked") is False


# --- outcome_basis: acceptance_detected label ---------------------------------


def test_outcome_basis_acceptance_detected():
    from routing_outcome_score import outcome_basis

    assert outcome_basis(errors=False, reaction_failure=False, reaction_success=True) == "acceptance_detected"


def test_outcome_basis_ordering_errors_and_rejection_beat_acceptance():
    from routing_outcome_score import outcome_basis

    assert outcome_basis(errors=True, reaction_failure=False, reaction_success=True) == "tool_errors_only"
    assert outcome_basis(errors=False, reaction_failure=True, reaction_success=True) == "rejection_detected"


def test_outcome_basis_default_unchanged():
    from routing_outcome_score import outcome_basis

    assert outcome_basis(errors=False, reaction_failure=False) == "default_no_complaint"
    assert outcome_basis(errors=False, reaction_failure=False, reaction_success=False) == "default_no_complaint"
