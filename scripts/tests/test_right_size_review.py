#!/usr/bin/env python3
"""Tests for scripts/right-size-review.py — work-proportional review sizing.

Covers the deterministic tier helper: tier classification by file count and
package count, the max-rule (the larger of file-derived and package-derived
tier wins), boundary cases (5/6, 20/21, 50/51), and the JSON contract.
"""

import json
import subprocess
import sys
from pathlib import Path

import pytest

SCRIPT = Path(__file__).resolve().parents[1] / "right-size-review.py"

# Import the module directly for unit-level tests of the pure helper.
sys.path.insert(0, str(SCRIPT.parent))
import importlib.util

_spec = importlib.util.spec_from_file_location("right_size_review", SCRIPT)
rsr = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(rsr)


# --- Pure helper: tier classification ---------------------------------------


@pytest.mark.parametrize(
    "files,pkgs,expected_tier",
    [
        # Tier 1: 1-5 files, 1 pkg
        (1, 1, 1),
        (5, 1, 1),
        # Tier 2: 6-20 files, 1-2 pkg
        (6, 1, 2),
        (6, 2, 2),
        (20, 2, 2),
        # Tier 3: 21-50 files, 3-5 pkg
        (21, 3, 3),
        (50, 5, 3),
        # Tier 4: 50+ files, 5+ pkg
        (51, 6, 4),
        (200, 12, 4),
    ],
)
def test_tier_classification(files, pkgs, expected_tier):
    assert rsr.compute_tier(files, pkgs) == expected_tier


def test_boundary_5_to_6_files():
    # 5 files stays Tier 1; 6 files crosses into Tier 2.
    assert rsr.compute_tier(5, 1) == 1
    assert rsr.compute_tier(6, 1) == 2


def test_boundary_20_to_21_files():
    assert rsr.compute_tier(20, 2) == 2
    assert rsr.compute_tier(21, 3) == 3


def test_boundary_50_to_51_files():
    assert rsr.compute_tier(50, 5) == 3
    assert rsr.compute_tier(51, 6) == 4


# --- The max-rule: file-tier vs package-tier, larger wins -------------------


def test_max_rule_packages_escalate_above_files():
    # Few files but many packages: package signal escalates the tier.
    # 3 files -> file-tier 1; 6 packages -> package-tier 4. Max wins = 4.
    assert rsr.compute_tier(3, 6) == 4


def test_max_rule_files_escalate_above_packages():
    # Many files but one package: file signal escalates the tier.
    # 60 files -> file-tier 4; 1 package -> package-tier 1. Max wins = 4.
    assert rsr.compute_tier(60, 1) == 4


def test_max_rule_mid_split():
    # 30 files -> file-tier 3; 2 packages -> package-tier 2. Max = 3.
    assert rsr.compute_tier(30, 2) == 3


# --- Composition mapping ----------------------------------------------------


def test_composition_tier1():
    comp = rsr.composition_for_tier(1)
    assert comp["waves"] == []
    assert comp["agent_estimate"] == 3
    assert "parallel-code-review" in comp["recommended"]


def test_composition_tier2():
    comp = rsr.composition_for_tier(2)
    assert comp["waves"] == [1]
    assert comp["agent_estimate"] == 12


def test_composition_tier3():
    comp = rsr.composition_for_tier(3)
    assert comp["waves"] == [1, 2]
    # Wave 1 (12) + Wave 2 subset (5) = 17; Wave 3 conditional on CRITICAL.
    assert comp["agent_estimate"] == 17


def test_composition_tier4():
    comp = rsr.composition_for_tier(4)
    assert comp["waves"] == [1, 2, 3]
    # 12 + 10 + 5 = 27 (Wave 3 upper bound of 4-5).
    assert comp["agent_estimate"] == 27


# --- CLI contract -----------------------------------------------------------


def _run(*args):
    proc = subprocess.run(
        [sys.executable, str(SCRIPT), *args],
        capture_output=True,
        text=True,
    )
    return proc


def test_cli_emits_json_and_exit_zero():
    proc = _run("--files", "3", "--packages", "1")
    assert proc.returncode == 0
    data = json.loads(proc.stdout)
    assert data["tier"] == 1
    assert data["waves"] == []
    assert data["agent_estimate"] == 3


def test_cli_tier4():
    proc = _run("--files", "80", "--packages", "7")
    assert proc.returncode == 0
    data = json.loads(proc.stdout)
    assert data["tier"] == 4
    assert data["agent_estimate"] == 27
    assert data["waves"] == [1, 2, 3]


def test_cli_max_rule_via_packages():
    proc = _run("--files", "3", "--packages", "6")
    data = json.loads(proc.stdout)
    assert data["tier"] == 4


def test_cli_includes_recommended_and_field_scope_tier():
    proc = _run("--files", "10", "--packages", "1")
    data = json.loads(proc.stdout)
    assert data["tier"] == 2
    assert "recommended" in data
    assert data["FILE_SCOPE_TIER"] == 2
