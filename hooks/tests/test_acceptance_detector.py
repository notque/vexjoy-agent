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
    "ok that worked",
    # v1.2.0: leading filler is stripped before the first clause is taken
    "okay, that worked",
    "oh great that worked",
    "alright thanks",
    "well, looks good",
    "okay great that looks good now move on to the next one",  # dictated, no punctuation
    # v1.2.0: wider markers that judge the work
    "awesome",
    "excellent work",
    "looks great",
    "seems fine",
    "works really well",
    "that's right",
    "that's exactly what i wanted",
    "exactly what i asked for",
    "it works",
    "yeah that works great",
    "much better",
    "love it",
    "commit it",
    # v1.2.0: a terse verdict is the whole clause
    "nice",
    "cool, next one",
    "good.",
]


@pytest.mark.parametrize("prompt", ACCEPTS)
def test_acceptance_fires(prompt):
    assert mod.is_acceptance(prompt) is True, prompt


# --- negative goldens: negation / buried / instructional stay neutral --------

NEUTRALS = [
    # negation
    "not perfect",
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
    "what does route-health report",
    # v1.2.0: an answer or a plan approval, not a verdict on finished work
    "yes",
    "yeah",
    "okay",
    "sure",
    "yes do that",
    "sounds good",
    "okay",
    # v1.2.0: contrast leads into a complaint
    "great, but the tests fail",
    "looks good but fix the header",
    "it works but it is slow",
    "that's right, however the count is off",
    "great, that's wrong",
    "nice, although the footer moved",
    # v1.2.0: request cues
    "i want a great header",
    "please make sure it works",
    "let's merge it",
    "could you check it looks good",
    "we need a much better parser",
    # v1.2.0: marker deep in the clause is task text
    "put the logo where the banner sits so it looks good",
    "the footer on the pricing page looks good",
    # v1.2.0: terse words are verdicts only as a whole clause
    "nice to have would be a dark mode",
    "good question",
    "the cool thing about this parser is speed",
    # v1.2.0: a complaint never boosts
    "that isn't working well",
    "it still doesn't work",
    # empty / junk
    "",
    None,
]


@pytest.mark.parametrize("prompt", NEUTRALS)
def test_neutral_stays_neutral(prompt):
    assert mod.is_acceptance(prompt) is False, prompt


# --- acceptance never flips a genuine rejection -------------------------------


def test_rejection_still_wins_its_own_goldens():
    assert mod.is_rejection("that's wrong, redo it") is True
    assert mod.is_rejection("thanks, that worked") is False


# --- v1.2.0 rejection goldens, both directions --------------------------------

REJECTS = [
    "that's wrong",
    "okay that's wrong",  # leading filler stripped
    "oh, that's not what i asked for",
    "it's still broken",
    "this is wrong",
    "this isn't working",
    "it doesn't work",
    "that still doesn't work",
    "still broken",
    "still not fixed, the header overlaps",
    "not what i wanted",
    "you misunderstood",
    "you broke the build",
    "no, it still doesn't work",  # leading no + complaint in the next clause
    "nope, still broken",
    "thanks but that's wrong",  # a complaint in the same clause beats the marker
]

NOT_REJECTS = [
    "that isn't wrong",  # negated complaint
    "the CI is still failing on main, take a look",  # new task, not the prior work
    "no, go ahead and ship it",  # leading no without a complaint
    "no",
    "if it doesn't work, roll back",  # conditional
    "explain why it's broken",  # instructional
    "should we revert that",
    "thanks. redo it for the other file",  # acceptance leads; rework is new work
    "there is no cache and it is wrong to assume one",  # marker deep in the clause
    "it is wrong to assume a cache here",  # dummy-it statement, not a verdict
    "okay next task",
    "yes",
    "",
    None,
]


@pytest.mark.parametrize("prompt", REJECTS)
def test_rejection_fires(prompt):
    assert mod.is_rejection(prompt) is True, prompt
    assert mod.is_acceptance(prompt) is False, prompt


@pytest.mark.parametrize("prompt", NOT_REJECTS)
def test_non_rejection_stays_clear(prompt):
    assert mod.is_rejection(prompt) is False, prompt


def test_filler_only_prompt_is_neutral():
    assert mod.is_acceptance("okay") is False
    assert mod.is_rejection("okay") is False
    assert mod._first_clause("okay, so, that worked") == "that worked"
    assert mod._first_clause("well done") == "well done"


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
