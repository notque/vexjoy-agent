"""Choice margin and consequence-gated escalation."""

from __future__ import annotations

import math
import sys
from pathlib import Path

import pytest

SCRIPTS = Path(__file__).resolve().parents[1]
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

import jev_choice


def test_margin_is_top_over_second() -> None:
    read = jev_choice.choice_margin({"a": 0.6, "b": 0.3, "c": 0.1})
    assert read.choice == "a"
    assert read.margin == pytest.approx(2.0)
    assert read.n == 3


def test_classes_sum_equivalent_options() -> None:
    probs = {"strike_1": 0.3, "strike_2": 0.3, "defend": 0.4}
    assert jev_choice.choice_margin(probs).choice == "defend"
    read = jev_choice.choice_margin(probs, {"strike_1": "strike", "strike_2": "strike"})
    assert read.choice == "strike"
    assert read.p_max == pytest.approx(0.6)
    assert read.margin == pytest.approx(1.5)


def test_single_option_has_infinite_margin() -> None:
    assert jev_choice.choice_margin({"only": 1.0}).margin == math.inf


@pytest.mark.parametrize("bad", [{}, {"a": -0.1, "b": 1.1}])
def test_bad_input_raises(bad: dict[str, float]) -> None:
    with pytest.raises(ValueError):
        jev_choice.choice_margin(bad)


def test_escalation_needs_both_a_split_and_a_consequence() -> None:
    flat = jev_choice.choice_margin({"a": 0.26, "b": 0.25, "c": 0.49})
    clear = jev_choice.choice_margin({"a": 0.8, "b": 0.1, "c": 0.1})
    assert jev_choice.should_escalate(flat, consequences_differ=True)
    assert not jev_choice.should_escalate(flat, consequences_differ=False)
    assert not jev_choice.should_escalate(clear, consequences_differ=True)


def test_order_averaged_margin_cancels_first_option_lean() -> None:
    fwd = {"a": 0.5, "b": 0.3, "c": 0.2}
    rev = {"a": 0.2, "b": 0.5, "c": 0.3}
    assert jev_choice.order_averaged_margin(fwd, rev) == pytest.approx(0.4 / 0.35)
    with pytest.raises(ValueError):
        jev_choice.order_averaged_margin(fwd, {"a": 1.0})
