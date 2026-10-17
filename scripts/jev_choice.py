"""Read a Jev Choice's probabilities: top, margin over the runner-up, and a consequence-gated escalation test.

A flat Choice over many near-equal options is normal, not a failure (references/field-learnings.md).
Two reads matter: ``margin`` (``p_max / p_second``) says whether the argmax is stable, and whether
the split options differ in outcome cost says whether a stronger model is worth paying for.
``classes`` sums the probability of options that are the same thing (duplicate cards, one action
reachable two ways) before the margin is read, so identical options do not look like a split.

Thresholds are provisional: measured 2026-10-16 on jev-1.14.0, synthetic nav Choices (n=50). Re-measure.
"""

from __future__ import annotations

import math
from collections import defaultdict
from collections.abc import Mapping
from dataclasses import dataclass

MARGIN_MIN = 2.0  # at or above this p_max / p_second the pick agreed under reversed option order 29/29


@dataclass(frozen=True)
class ChoiceRead:
    """The top class of a Choice, its probability, and how far it leads the runner-up."""

    choice: str
    p_max: float
    p_second: float
    margin: float
    n: int


def choice_margin(probabilities: Mapping[str, float], classes: Mapping[str, str] | None = None) -> ChoiceRead:
    """Return the top option (or class), ``p_max``, ``p_second``, and ``margin = p_max / p_second``.

    ``classes`` maps an option to the class it belongs to; probabilities of one class are summed.
    An option missing from ``classes`` is its own class. ``margin`` is ``math.inf`` when the runner-up has
    no mass. Raises ValueError on an empty mapping or a negative probability.
    """
    if not probabilities:
        raise ValueError("probabilities is empty")
    mass: dict[str, float] = defaultdict(float)
    for option, p in probabilities.items():
        if p < 0:
            raise ValueError(f"negative probability for {option!r}")
        mass[classes.get(option, option) if classes else option] += p
    ranked = sorted(mass.items(), key=lambda kv: kv[1], reverse=True)
    top, p_max = ranked[0]
    p_second = ranked[1][1] if len(ranked) > 1 else 0.0
    margin = p_max / p_second if p_second > 0 else math.inf
    return ChoiceRead(choice=top, p_max=p_max, p_second=p_second, margin=margin, n=len(ranked))


def should_escalate(read: ChoiceRead, *, consequences_differ: bool, margin_min: float = MARGIN_MIN) -> bool:
    """True only when the pick is unstable AND the leading options differ in outcome cost.

    A flat Choice over interchangeable options needs no stronger model: take the argmax, or let code break the tie.
    The caller decides ``consequences_differ`` from state (lethal possible, irreversible, money, owner-visible).
    """
    return consequences_differ and read.margin < margin_min
