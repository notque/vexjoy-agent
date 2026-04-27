#!/usr/bin/env python3
"""Regression tests for ADR-207 Rule 2 (write_manifest_record contract).

The manifest writer assertion: a record with ``verifier_verdict == "PASS"``
and a non-empty ``verifier_failures`` is structurally inconsistent and
cannot be persisted. This closes RC-2 at the producer-side boundary --
the field cannot enter an inconsistent state in the first place.

These tests exercise:

  1. PASS verdict + empty failures -> writes successfully.
  2. PASS verdict + non-empty failures -> raises ValueError citing ADR-207.
  3. FAIL verdict + non-empty failures -> writes successfully.
  4. FAIL verdict + empty failures -> raises ValueError (the inverse
     contract violation).
  5. Missing verdict -> writes (legacy records).
  6. Verdict derivation: verifier_verdict_from_passed maps cleanly.

Run with pytest:

    pytest skills/game-sprite-pipeline/scripts/test_no_status_laundering.py -v
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

SCRIPT_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPT_DIR))

import sprite_verify


# ---------------------------------------------------------------------------
# Test 1: happy path PASS + empty failures
# ---------------------------------------------------------------------------
def test_write_manifest_record_pass_with_no_failures(tmp_path: Path) -> None:
    record = {
        "name": "luchadora-highflyer-05-specials",
        "verifier_verdict": "PASS",
        "verifier_failures": [],
    }
    out = tmp_path / "ok.json"
    sprite_verify.write_manifest_record(out, record)
    assert out.exists()
    loaded = json.loads(out.read_text(encoding="utf-8"))
    assert loaded["verifier_verdict"] == "PASS"
    assert loaded["verifier_failures"] == []


# ---------------------------------------------------------------------------
# Test 2: laundering attempt — PASS + non-empty failures must raise
# ---------------------------------------------------------------------------
def test_write_manifest_record_blocks_pass_with_failures(tmp_path: Path) -> None:
    """The exact RC-2 attack pattern: claim PASS while failures list is populated."""
    record = {
        "name": "veteran-indie-05-specials",
        "verifier_verdict": "PASS",
        "verifier_failures": [
            {"check": "frames_have_content", "details": {"blank_cells": [{"cell_index": 17}]}},
            {"check": "cell_parity", "details": {"blank_cells": [{"cell_index": 32}]}},
        ],
    }
    out = tmp_path / "bad.json"
    with pytest.raises(ValueError) as exc:
        sprite_verify.write_manifest_record(out, record)
    msg = str(exc.value)
    assert "ADR-207" in msg, msg
    assert "verifier_verdict='PASS'" in msg, msg
    assert "verifier_failures" in msg, msg
    # File must NOT have been written.
    assert not out.exists(), f"writer should refuse to write a contradictory record; file exists at {out}"


# ---------------------------------------------------------------------------
# Test 3: FAIL + non-empty failures (correct contract)
# ---------------------------------------------------------------------------
def test_write_manifest_record_fail_with_failures(tmp_path: Path) -> None:
    record = {
        "name": "veteran-indie-05-specials",
        "verifier_verdict": "FAIL",
        "verifier_failures": [
            {"check": "cell_parity", "details": {"blank_cells": [{"cell_index": 32}]}},
        ],
    }
    out = tmp_path / "fail.json"
    sprite_verify.write_manifest_record(out, record)
    assert out.exists()
    loaded = json.loads(out.read_text(encoding="utf-8"))
    assert loaded["verifier_verdict"] == "FAIL"
    assert len(loaded["verifier_failures"]) == 1


# ---------------------------------------------------------------------------
# Test 4: FAIL + empty failures (inverse contract violation)
# ---------------------------------------------------------------------------
def test_write_manifest_record_blocks_fail_without_failures(tmp_path: Path) -> None:
    """A FAIL verdict with no failures is also structurally inconsistent."""
    record = {
        "name": "luchadora-highflyer-05-specials",
        "verifier_verdict": "FAIL",
        "verifier_failures": [],
    }
    out = tmp_path / "bad_inverse.json"
    with pytest.raises(ValueError) as exc:
        sprite_verify.write_manifest_record(out, record)
    msg = str(exc.value)
    assert "ADR-207" in msg, msg
    assert "FAIL" in msg, msg
    assert not out.exists(), out


# ---------------------------------------------------------------------------
# Test 5: missing verdict -> writes (backward-compatible)
# ---------------------------------------------------------------------------
def test_write_manifest_record_no_verdict_is_permissive(tmp_path: Path) -> None:
    """Records without verifier_verdict (legacy / pre-ADR-207) must still write."""
    record = {
        "name": "legacy-record",
        "some_other_field": "value",
    }
    out = tmp_path / "legacy.json"
    sprite_verify.write_manifest_record(out, record)
    assert out.exists()


# ---------------------------------------------------------------------------
# Test 6: verifier_verdict_from_passed mapping
# ---------------------------------------------------------------------------
def test_verifier_verdict_from_passed_mapping() -> None:
    assert sprite_verify.verifier_verdict_from_passed(True) == "PASS"
    assert sprite_verify.verifier_verdict_from_passed(False) == "FAIL"


# ---------------------------------------------------------------------------
# Standalone runner
# ---------------------------------------------------------------------------
def main() -> int:
    import tempfile

    tmp_tests = [
        test_write_manifest_record_pass_with_no_failures,
        test_write_manifest_record_blocks_pass_with_failures,
        test_write_manifest_record_fail_with_failures,
        test_write_manifest_record_blocks_fail_without_failures,
        test_write_manifest_record_no_verdict_is_permissive,
    ]
    no_arg_tests = [test_verifier_verdict_from_passed_mapping]
    failures: list[tuple[str, str]] = []
    for t in tmp_tests:
        with tempfile.TemporaryDirectory() as td:
            try:
                t(Path(td))
                print(f"PASS {t.__name__}")
            except AssertionError as e:
                print(f"FAIL {t.__name__}: {e}")
                failures.append((t.__name__, str(e)))
            except Exception as e:
                print(f"FAIL {t.__name__}: unexpected {type(e).__name__}: {e}")
                failures.append((t.__name__, str(e)))
    for t in no_arg_tests:
        try:
            t()
            print(f"PASS {t.__name__}")
        except AssertionError as e:
            print(f"FAIL {t.__name__}: {e}")
            failures.append((t.__name__, str(e)))
    if failures:
        print(f"\n{len(failures)} FAIL")
        return 1
    print(f"\nAll {len(tmp_tests) + len(no_arg_tests)} tests passed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
