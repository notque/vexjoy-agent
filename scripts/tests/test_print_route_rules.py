"""/d prints /do's Phase 2 rule text instead of copying it.

If /do's SKILL.md moves an anchor or drops a rule, these tests fail, so the two
routers cannot drift apart without CI noticing.
"""

from __future__ import annotations

import importlib.util
import subprocess
import sys
from pathlib import Path

import pytest

SCRIPTS = Path(__file__).resolve().parents[1]
REPO = SCRIPTS.parent
spec = importlib.util.spec_from_file_location("print_route_rules", SCRIPTS / "print-route-rules.py")
rules = importlib.util.module_from_spec(spec)
spec.loader.exec_module(rules)

DO_SKILL = REPO / "skills" / "meta" / "do" / "SKILL.md"

# Every rule /d's pick depends on: Step 0 rules and the Step 0b gates.
REQUIRED_RULES = (
    "SECTION-INTEGRITY RULE",
    "FORCE-ROUTE RULE",
    "PIPELINE-SELECTION RULE",
    "MULTI-AGENT RULE",
    "SPECIFICITY RULES",
    "COMBINATION DOCTRINE",
    "Skill-greediness gate",
    "Agent-greediness gate",
    "Pairing rule",
    "Fallback reason",
)


def test_extracted_span_holds_every_rule() -> None:
    text = rules.extract_rules(DO_SKILL.read_text(encoding="utf-8"))
    for name in REQUIRED_RULES:
        assert name in text, name
    assert text.startswith(rules.START)
    assert rules.END not in text


def test_extracted_span_is_verbatim_do_text() -> None:
    do_text = DO_SKILL.read_text(encoding="utf-8")
    assert rules.extract_rules(do_text).strip() in do_text


def test_cli_prints_the_span() -> None:
    proc = subprocess.run(
        [sys.executable, str(SCRIPTS / "print-route-rules.py")], capture_output=True, text=True, check=False
    )
    assert proc.returncode == 0
    assert proc.stdout == rules.extract_rules(DO_SKILL.read_text(encoding="utf-8"))


@pytest.mark.parametrize("anchor", [rules.START, rules.END])
def test_a_moved_anchor_fails_loudly(anchor: str) -> None:
    text = DO_SKILL.read_text(encoding="utf-8").replace(anchor, "renamed heading")
    with pytest.raises(ValueError, match="not found"):
        rules.extract_rules(text)


def test_anchors_out_of_order_fail() -> None:
    with pytest.raises(ValueError, match="not found"):
        rules.extract_rules(f"{rules.END}\nbody\n{rules.START}\n")


def test_d_skill_loads_the_rules_by_script_not_by_copy() -> None:
    text = (REPO / "skills" / "meta" / "d" / "SKILL.md").read_text(encoding="utf-8")
    assert "print-route-rules.py" in text
    for name in ("SECTION-INTEGRITY RULE", "PIPELINE-SELECTION RULE", "COMBINATION DOCTRINE"):
        assert name not in text, f"{name} is copied into /d; print it from /do instead"
