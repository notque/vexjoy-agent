#!/usr/bin/env python3
"""
Threat Model Validator — Phase 5 gate of the security-threat-model skill.

Validates that security/threat-model.md contains all required sections and
that security/audit-badge.json contains the required fields with valid values.

Required threat-model.md sections (exact heading text):
  # Threat Model
  ## Run Metadata
  ## Attack Surface Inventory
  ## Active Threats
  ## Mitigations In Place
  ## Gaps and Recommended Next Controls
  ## Deny-List Status
  ## Supply-Chain Audit Summary
  ## Learning DB Sanitization Summary

Required audit-badge.json fields:
  status, timestamp, run_id, critical_count, warning_count, phases_completed

Usage:
    python3 scripts/validate-threat-model.py --threat-model security/threat-model.md --badge security/audit-badge.json
    python3 scripts/validate-threat-model.py --help
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

# ─── Required Sections ─────────────────────────────────────────

# Each entry is the heading text as it should appear in the document.
# Matching is heading-level-aware (# vs ##) and strips trailing whitespace.
REQUIRED_SECTIONS: list[tuple[str, re.Pattern]] = [
    ("# Threat Model", re.compile(r"^#\s+Threat Model\s*$", re.MULTILINE)),
    ("## Run Metadata", re.compile(r"^##\s+Run Metadata\s*$", re.MULTILINE)),
    ("## Attack Surface Inventory", re.compile(r"^##\s+Attack Surface Inventory\s*$", re.MULTILINE)),
    ("## Active Threats", re.compile(r"^##\s+Active Threats\b", re.MULTILINE)),
    ("## Mitigations In Place", re.compile(r"^##\s+Mitigations In Place\s*$", re.MULTILINE)),
    (
        "## Gaps and Recommended Next Controls",
        re.compile(r"^##\s+Gaps and Recommended Next Controls\s*$", re.MULTILINE),
    ),
    ("## Deny-List Status", re.compile(r"^##\s+Deny-List Status\s*$", re.MULTILINE)),
    ("## Supply-Chain Audit Summary", re.compile(r"^##\s+Supply-Chain Audit Summary\s*$", re.MULTILINE)),
    ("## Learning DB Sanitization Summary", re.compile(r"^##\s+Learning DB Sanitization Summary\s*$", re.MULTILINE)),
]

# Required audit-badge.json fields and their expected types
REQUIRED_BADGE_FIELDS: dict[str, type] = {
    "status": str,
    "timestamp": str,
    "run_id": str,
    "critical_count": int,
    "warning_count": int,
    "phases_completed": int,
}

VALID_STATUSES: frozenset[str] = frozenset(["pass", "fail"])


# ─── Validation Logic ──────────────────────────────────────────


def validate_threat_model(path: Path) -> list[str]:
    """
    Validate threat-model.md for required sections.
    Returns list of error strings (empty = pass).
    """
    errors: list[str] = []

    if not path.exists():
        return [f"threat-model.md not found: {path}"]

    try:
        text = path.read_text(encoding="utf-8")
    except Exception as e:
        return [f"Cannot read {path}: {e}"]

    if len(text.strip()) < 100:
        errors.append(f"threat-model.md is suspiciously short ({len(text)} chars) — likely incomplete")

    for section_name, pattern in REQUIRED_SECTIONS:
        if not pattern.search(text):
            errors.append(f"Missing required section: '{section_name}'")

    return errors


def validate_badge(path: Path) -> list[str]:
    """
    Validate audit-badge.json for required fields and valid values.
    Returns list of error strings (empty = pass).
    """
    errors: list[str] = []

    if not path.exists():
        return [f"audit-badge.json not found: {path}"]

    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as e:
        return [f"audit-badge.json is invalid JSON: {e}"]

    for field, expected_type in REQUIRED_BADGE_FIELDS.items():
        if field not in data:
            errors.append(f"audit-badge.json missing required field: '{field}'")
        elif not isinstance(data[field], expected_type):
            actual = type(data[field]).__name__
            errors.append(
                f"audit-badge.json field '{field}' has wrong type: expected {expected_type.__name__}, got {actual}"
            )

    if "status" in data and data["status"] not in VALID_STATUSES:
        errors.append(f"audit-badge.json 'status' must be one of {sorted(VALID_STATUSES)}, got: '{data['status']}'")

    if "phases_completed" in data:
        phases = data["phases_completed"]
        if isinstance(phases, int) and phases < 1:
            errors.append(f"audit-badge.json 'phases_completed' must be >= 1, got {phases}")

    if "critical_count" in data:
        cc = data["critical_count"]
        if isinstance(cc, int) and cc < 0:
            errors.append(f"audit-badge.json 'critical_count' must be >= 0, got {cc}")

    return errors


# ─── Main ──────────────────────────────────────────────────────


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Validate threat-model.md and audit-badge.json outputs.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument(
        "--threat-model",
        default="security/threat-model.md",
        help="Path to threat-model.md (default: security/threat-model.md)",
    )
    parser.add_argument(
        "--badge",
        default="security/audit-badge.json",
        help="Path to audit-badge.json (default: security/audit-badge.json)",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        dest="json_output",
        help="Output results as JSON instead of plain text",
    )
    args = parser.parse_args()

    threat_model_path = Path(args.threat_model)
    badge_path = Path(args.badge)

    model_errors = validate_threat_model(threat_model_path)
    badge_errors = validate_badge(badge_path)

    all_errors = model_errors + badge_errors
    passed = len(all_errors) == 0

    if args.json_output:
        result = {
            "passed": passed,
            "threat_model_errors": model_errors,
            "badge_errors": badge_errors,
            "total_errors": len(all_errors),
        }
        print(json.dumps(result, indent=2))
    else:
        if passed:
            print(f"[validate] PASS: threat-model.md and audit-badge.json are valid")
        else:
            print(f"[validate] FAIL: {len(all_errors)} error(s) found")
            for err in model_errors:
                print(f"  [threat-model] {err}")
            for err in badge_errors:
                print(f"  [badge] {err}")

    sys.exit(0 if passed else 1)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        sys.exit(1)
    except Exception as e:
        print(f"[validate] FATAL: {e}", file=sys.stderr)
        sys.exit(1)
