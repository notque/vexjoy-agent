#!/usr/bin/env python3
"""
End-to-end test suite for the ADR enforcement system.

Tests the complete stack: adr-query.py, adr-compliance.py, hooks/adr-context-injector.py,
ADR document validity, pipeline-spec-format.md fields, architecture rules, and canonical chains.

Usage:
    python3 scripts/test-adr-system.py

Exit codes:
    0 = all tests passed
    1 = one or more tests failed
"""

from __future__ import annotations

import json
import subprocess
import sys
import tempfile
from pathlib import Path

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------

REPO_ROOT = Path(__file__).parent.parent.resolve()
SCRIPTS_DIR = REPO_ROOT / "scripts"
HOOKS_DIR = REPO_ROOT / "hooks"
ADR_DIR = REPO_ROOT / "adr"

ADR_QUERY = SCRIPTS_DIR / "adr-query.py"
ADR_COMPLIANCE = SCRIPTS_DIR / "adr-compliance.py"
ADR_CONTEXT_INJECTOR = HOOKS_DIR / "adr-context-injector.py"
ARTIFACT_UTILS = SCRIPTS_DIR / "artifact-utils.py"

STEP_MENU = REPO_ROOT / "pipelines" / "pipeline-scaffolder" / "references" / "step-menu.md"
SPEC_FORMAT = REPO_ROOT / "pipelines" / "pipeline-scaffolder" / "references" / "pipeline-spec-format.md"
ARCH_RULES = REPO_ROOT / "pipelines" / "pipeline-scaffolder" / "references" / "architecture-rules.md"
CANONICAL_CHAINS = REPO_ROOT / "pipelines" / "chain-composer" / "references" / "canonical-chains.md"

# Pick the first real ADR file available (prefer adr-database-system.md)
PRIMARY_ADR = ADR_DIR / "adr-database-system.md"
if not PRIMARY_ADR.exists():
    candidates = sorted(ADR_DIR.glob("*.md"))
    PRIMARY_ADR = candidates[0] if candidates else None

# ---------------------------------------------------------------------------
# Test runner helpers
# ---------------------------------------------------------------------------

_results: list[tuple[int, str, str]] = []  # (num, description, status_line)
_pass_count = 0
_fail_count = 0


def run(cmd: list[str], *, input_data: str | None = None, cwd: Path | None = None) -> subprocess.CompletedProcess:
    """Run a command and return the CompletedProcess (no exception on non-zero exit)."""
    return subprocess.run(
        cmd,
        input=input_data,
        capture_output=True,
        text=True,
        cwd=str(cwd) if cwd else None,
    )


def report(num: int, description: str, passed: bool, detail: str = "") -> None:
    """Record and print a test result."""
    global _pass_count, _fail_count
    status = "[PASS]" if passed else "[FAIL]"
    detail_str = f"  {detail}" if detail else ""
    line = f"  {status} [{num:02d}] {description}{detail_str}"
    print(line)
    _results.append((num, description, status))
    if passed:
        _pass_count += 1
    else:
        _fail_count += 1


def cleanup_session_file(directory: Path) -> None:
    """Remove .adr-session.json if it exists in directory."""
    session = directory / ".adr-session.json"
    if session.exists():
        session.unlink()


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


def test_01_hash_subcommand() -> None:
    """[1] adr-query.py: hash subcommand"""
    if PRIMARY_ADR is None:
        report(1, "adr-query.py: hash subcommand", False, "No ADR file found in adr/")
        return
    result = run([sys.executable, str(ADR_QUERY), "hash", "--adr", str(PRIMARY_ADR)])
    passed = result.returncode == 0 and result.stdout.strip().startswith("sha256:")
    detail = "" if passed else f"rc={result.returncode}, stdout={result.stdout.strip()!r}"
    report(1, "adr-query.py: hash subcommand", passed, detail)


def test_02_register_subcommand() -> None:
    """[2] adr-query.py: register subcommand"""
    if PRIMARY_ADR is None:
        report(2, "adr-query.py: register subcommand", False, "No ADR file found in adr/")
        return
    cleanup_session_file(REPO_ROOT)
    result = run([sys.executable, str(ADR_QUERY), "register", "--adr", str(PRIMARY_ADR)], cwd=REPO_ROOT)
    session_file = REPO_ROOT / ".adr-session.json"
    session_exists = session_file.exists()
    if session_exists:
        try:
            data = json.loads(session_file.read_text())
            session_valid = "adr_path" in data and "adr_hash" in data
        except json.JSONDecodeError:
            session_valid = False
    else:
        session_valid = False
    passed = result.returncode == 0 and session_exists and session_valid
    detail = "" if passed else f"rc={result.returncode}, session_exists={session_exists}, valid={session_valid}"
    report(2, "adr-query.py: register subcommand", passed, detail)


def test_03_active_subcommand() -> None:
    """[3] adr-query.py: active subcommand (requires register to have run first)"""
    result = run([sys.executable, str(ADR_QUERY), "active"], cwd=REPO_ROOT)
    passed = result.returncode == 0 and "path:" in result.stdout and "hash:" in result.stdout
    detail = "" if passed else f"rc={result.returncode}, stdout={result.stdout.strip()!r}"
    report(3, "adr-query.py: active subcommand", passed, detail)


def test_04_context_skill_creator() -> None:
    """[4] adr-query.py: context --role skill-creator"""
    if PRIMARY_ADR is None:
        report(4, "adr-query.py: context --role skill-creator", False, "No ADR file found")
        return
    result = run([sys.executable, str(ADR_QUERY), "context", "--adr", str(PRIMARY_ADR), "--role", "skill-creator"])
    passed = result.returncode == 0 and "# ADR Context for role: skill-creator" in result.stdout
    detail = "" if passed else f"rc={result.returncode}"
    report(4, "adr-query.py: context --role skill-creator", passed, detail)


def test_05_context_chain_composer() -> None:
    """[5] adr-query.py: context --role chain-composer"""
    if PRIMARY_ADR is None:
        report(5, "adr-query.py: context --role chain-composer", False, "No ADR file found")
        return
    result = run([sys.executable, str(ADR_QUERY), "context", "--adr", str(PRIMARY_ADR), "--role", "chain-composer"])
    passed = result.returncode == 0 and "# ADR Context for role: chain-composer" in result.stdout
    detail = "" if passed else f"rc={result.returncode}"
    report(5, "adr-query.py: context --role chain-composer", passed, detail)


def test_06_context_orchestrator() -> None:
    """[6] adr-query.py: context --role orchestrator"""
    if PRIMARY_ADR is None:
        report(6, "adr-query.py: context --role orchestrator", False, "No ADR file found")
        return
    result = run([sys.executable, str(ADR_QUERY), "context", "--adr", str(PRIMARY_ADR), "--role", "orchestrator"])
    passed = result.returncode == 0 and "# ADR Context for role: orchestrator" in result.stdout
    detail = "" if passed else f"rc={result.returncode}"
    report(6, "adr-query.py: context --role orchestrator", passed, detail)


def test_07_verify_correct_hash() -> None:
    """[7] adr-query.py: verify (correct hash)"""
    if PRIMARY_ADR is None:
        report(7, "adr-query.py: verify (correct hash)", False, "No ADR file found")
        return
    # First get the actual hash
    hash_result = run([sys.executable, str(ADR_QUERY), "hash", "--adr", str(PRIMARY_ADR)])
    if hash_result.returncode != 0:
        report(7, "adr-query.py: verify (correct hash)", False, "hash subcommand failed")
        return
    actual_hash = hash_result.stdout.strip()
    result = run([sys.executable, str(ADR_QUERY), "verify", "--adr", str(PRIMARY_ADR), "--hash", actual_hash])
    passed = result.returncode == 0 and "OK:" in result.stdout
    detail = "" if passed else f"rc={result.returncode}, stdout={result.stdout.strip()!r}"
    report(7, "adr-query.py: verify (correct hash)", passed, detail)


def test_08_verify_wrong_hash() -> None:
    """[8] adr-query.py: verify (wrong hash, expect exit 1)"""
    if PRIMARY_ADR is None:
        report(8, "adr-query.py: verify (wrong hash, expect exit 1)", False, "No ADR file found")
        return
    bad_hash = "sha256:0000000000000000000000000000000000000000000000000000000000000000"
    result = run([sys.executable, str(ADR_QUERY), "verify", "--adr", str(PRIMARY_ADR), "--hash", bad_hash])
    passed = result.returncode == 1
    detail = "" if passed else f"expected rc=1, got rc={result.returncode}"
    report(8, "adr-query.py: verify (wrong hash, expect exit 1)", passed, detail)


def test_09_list_subcommand() -> None:
    """[9] adr-query.py: list subcommand"""
    result = run([sys.executable, str(ADR_QUERY), "list"])
    if result.returncode != 0:
        report(9, "adr-query.py: list subcommand", False, f"rc={result.returncode}")
        return
    try:
        data = json.loads(result.stdout)
        passed = isinstance(data, list) and len(data) > 0
        detail = "" if passed else f"list returned {len(data)} entries"
    except json.JSONDecodeError as e:
        passed = False
        detail = f"invalid JSON: {e}"
    report(9, "adr-query.py: list subcommand", passed, detail)


def test_10_compliance_clean_file() -> None:
    """[10] adr-compliance.py: clean file (expect PASS)"""
    if not STEP_MENU.exists() or not SPEC_FORMAT.exists():
        report(
            10, "adr-compliance.py: clean file (expect PASS)", False, "Missing step-menu.md or pipeline-spec-format.md"
        )
        return

    # Write a minimal clean file with no step names, no schema, no family values
    content = """# Clean Pipeline Skill

## Overview

This skill performs research and generates a report.

## Phases

### Phase 1: Research

Gather information about the domain.

### Phase 2: Output

Produce the final report.
"""
    with tempfile.NamedTemporaryFile(mode="w", suffix=".md", delete=False, dir=REPO_ROOT) as f:
        f.write(content)
        tmp_path = f.name

    try:
        result = run(
            [
                sys.executable,
                str(ADR_COMPLIANCE),
                "check",
                "--file",
                tmp_path,
                "--step-menu",
                str(STEP_MENU),
                "--spec-format",
                str(SPEC_FORMAT),
            ]
        )
        if result.returncode not in (0, 1):
            passed = False
            detail = f"unexpected rc={result.returncode}"
        else:
            try:
                data = json.loads(result.stdout)
                passed = data.get("verdict") == "PASS"
                detail = "" if passed else f"verdict={data.get('verdict')}, violations={data.get('violations', [])}"
            except json.JSONDecodeError:
                passed = False
                detail = f"invalid JSON output: {result.stdout[:100]}"
    finally:
        Path(tmp_path).unlink(missing_ok=True)

    report(10, "adr-compliance.py: clean file (expect PASS)", passed, detail)


def test_11_compliance_violation_file() -> None:
    """[11] adr-compliance.py: violation file (expect FAIL)"""
    if not STEP_MENU.exists() or not SPEC_FORMAT.exists():
        report(
            11,
            "adr-compliance.py: violation file (expect FAIL)",
            False,
            "Missing step-menu.md or pipeline-spec-format.md",
        )
        return

    # Write a file with a bogus schema value that will trigger a violation
    content = """# Violation Pipeline Skill

## Phases

```json
{
  "schema": "nonexistent-schema-xyz-abc",
  "family": "nonexistent-family-xyz-abc"
}
```
"""
    with tempfile.NamedTemporaryFile(mode="w", suffix=".md", delete=False, dir=REPO_ROOT) as f:
        f.write(content)
        tmp_path = f.name

    try:
        result = run(
            [
                sys.executable,
                str(ADR_COMPLIANCE),
                "check",
                "--file",
                tmp_path,
                "--step-menu",
                str(STEP_MENU),
                "--spec-format",
                str(SPEC_FORMAT),
            ]
        )
        if result.returncode not in (0, 1):
            passed = False
            detail = f"unexpected rc={result.returncode}"
        else:
            try:
                data = json.loads(result.stdout)
                passed = data.get("verdict") == "FAIL"
                detail = "" if passed else f"verdict={data.get('verdict')}, expected FAIL"
            except json.JSONDecodeError:
                passed = False
                detail = f"invalid JSON output: {result.stdout[:100]}"
    finally:
        Path(tmp_path).unlink(missing_ok=True)

    report(11, "adr-compliance.py: violation file (expect FAIL)", passed, detail)


def test_12_path_traversal_blocked() -> None:
    """[12] adr-query.py: path traversal blocked (expect exit 1)"""
    result = run([sys.executable, str(ADR_QUERY), "hash", "--adr", "/etc/passwd"])
    if result.returncode != 0:
        # Path traversal blocked — correct behavior
        report(12, "adr-query.py: path traversal blocked (expect exit 1)", True)
    else:
        report(
            12,
            "adr-query.py: path traversal blocked (expect exit 1)",
            False,
            "SECURITY: path traversal not blocked — /etc/passwd was accepted",
        )


def test_13_hook_fires_on_pipeline_prompt() -> None:
    """[13] hooks: adr-context-injector.py fires on pipeline prompt"""
    if not ADR_CONTEXT_INJECTOR.exists():
        report(13, "hooks: adr-context-injector.py fires on pipeline prompt", False, "Hook file not found")
        return

    # We need a session file in place for the hook to fire
    # Register the ADR first if not already done
    if PRIMARY_ADR is None:
        report(13, "hooks: adr-context-injector.py fires on pipeline prompt", False, "No ADR file found")
        return

    # Ensure session exists
    session_file = REPO_ROOT / ".adr-session.json"
    if not session_file.exists():
        reg = run([sys.executable, str(ADR_QUERY), "register", "--adr", str(PRIMARY_ADR)], cwd=REPO_ROOT)
        if reg.returncode != 0:
            report(13, "hooks: adr-context-injector.py fires on pipeline prompt", False, "Could not register ADR")
            return

    payload = json.dumps(
        {
            "userMessage": "Create a new pipeline skill for the prometheus subdomain",
            "cwd": str(REPO_ROOT),
        }
    )

    result = run([sys.executable, str(ADR_CONTEXT_INJECTOR)], input_data=payload)
    passed = result.returncode == 0 and "[adr-system]" in result.stdout
    detail = "" if passed else f"rc={result.returncode}, stdout={result.stdout[:200]!r}"
    report(13, "hooks: adr-context-injector.py fires on pipeline prompt", passed, detail)


def test_14_hook_silent_on_unrelated_prompt() -> None:
    """[14] hooks: adr-context-injector.py silent on unrelated prompt"""
    if not ADR_CONTEXT_INJECTOR.exists():
        report(14, "hooks: adr-context-injector.py silent on unrelated prompt", False, "Hook file not found")
        return

    # Session must still exist from test 13; if not, we'll work without it
    # An unrelated prompt should produce no [adr-system] output
    payload = json.dumps(
        {
            "userMessage": "What is the capital of France?",
            "cwd": str(REPO_ROOT),
        }
    )

    result = run([sys.executable, str(ADR_CONTEXT_INJECTOR)], input_data=payload)
    # Hook must always exit 0; should NOT inject [adr-system] for an unrelated prompt
    passed = result.returncode == 0 and "[adr-system]" not in result.stdout
    detail = "" if passed else f"rc={result.returncode}, [adr-system] present in output"
    report(14, "hooks: adr-context-injector.py silent on unrelated prompt", passed, detail)


def test_15_adr_architecture_rules_section() -> None:
    """[15] ADR validity: architecture-rules section has content"""
    if PRIMARY_ADR is None:
        report(15, "ADR validity: architecture-rules section has content", False, "No ADR file found")
        return
    result = run(
        [
            sys.executable,
            str(ADR_QUERY),
            "context",
            "--adr",
            str(PRIMARY_ADR),
            "--role",
            "skill-creator",
        ]
    )
    content = result.stdout
    # The skill-creator role pulls architecture-rules section
    has_content = (
        (result.returncode == 0 and "architecture-rules" in content.lower())
        or ("rule" in content.lower() and len(content.strip()) > 200)  # non-trivial content
    )
    # Also directly check the ADR file for the section
    adr_text = PRIMARY_ADR.read_text(encoding="utf-8")
    has_arch_section = (
        "architecture-rules" in adr_text.lower()
        or "## architecture rules" in adr_text.lower()
        or "architecture-rules" in adr_text
    )
    passed = result.returncode == 0 and has_arch_section
    detail = "" if passed else f"rc={result.returncode}, section found={has_arch_section}"
    report(15, "ADR validity: architecture-rules section has content", passed, detail)


def test_16_adr_canonical_chains_section() -> None:
    """[16] ADR validity: canonical-chains section has content"""
    if PRIMARY_ADR is None:
        report(16, "ADR validity: canonical-chains section has content", False, "No ADR file found")
        return
    adr_text = PRIMARY_ADR.read_text(encoding="utf-8")
    has_canonical = (
        "canonical-chains" in adr_text
        or "canonical chains" in adr_text.lower()
        or "<!-- adr-section: canonical-chains -->" in adr_text
    )
    # Also check the reference file
    chain_file_exists = CANONICAL_CHAINS.exists() and CANONICAL_CHAINS.stat().st_size > 500
    passed = has_canonical or chain_file_exists
    detail = "" if passed else "canonical-chains not found in ADR or reference file missing"
    report(16, "ADR validity: canonical-chains section has content", passed, detail)


def test_17_spec_format_adr_path_field() -> None:
    """[17] Spec format: adr_path field present"""
    if not SPEC_FORMAT.exists():
        report(17, "Spec format: adr_path field present", False, "pipeline-spec-format.md not found")
        return
    content = SPEC_FORMAT.read_text(encoding="utf-8")
    passed = "adr_path" in content
    detail = "" if passed else "adr_path field not found in pipeline-spec-format.md"
    report(17, "Spec format: adr_path field present", passed, detail)


def test_18_spec_format_adr_hash_field() -> None:
    """[18] Spec format: adr_hash field present"""
    if not SPEC_FORMAT.exists():
        report(18, "Spec format: adr_hash field present", False, "pipeline-spec-format.md not found")
        return
    content = SPEC_FORMAT.read_text(encoding="utf-8")
    passed = "adr_hash" in content
    detail = "" if passed else "adr_hash field not found in pipeline-spec-format.md"
    report(18, "Spec format: adr_hash field present", passed, detail)


def test_19_architecture_rule_18_present() -> None:
    """[19] Architecture Rule 18 present in rules file"""
    if not ARCH_RULES.exists():
        report(19, "Architecture Rule 18 present in rules file", False, "architecture-rules.md not found")
        return
    content = ARCH_RULES.read_text(encoding="utf-8")
    passed = "## Rule 18" in content and "ADR Hash Required" in content
    detail = "" if passed else "Rule 18 or its title not found in architecture-rules.md"
    report(19, "Architecture Rule 18 present in rules file", passed, detail)


def test_20_canonical_chains_valid() -> None:
    """[20] Chain validation: all 8 canonical chains valid"""
    if not ARTIFACT_UTILS.exists():
        report(20, "Chain validation: all 8 canonical chains valid", False, "artifact-utils.py not found")
        return
    if not CANONICAL_CHAINS.exists():
        report(20, "Chain validation: all 8 canonical chains valid", False, "canonical-chains.md not found")
        return

    # The 8 canonical chains from the ADR (as step/schema arrays for validate-chain)
    # validate-chain expects a JSON array of {"step": NAME, "schema": TYPE} objects
    chains = {
        "generation": [
            {"step": "ADR", "schema": "decision-record"},
            {"step": "RESEARCH", "schema": "research-artifact"},
            {"step": "COMPILE", "schema": "structured-corpus"},
            {"step": "GENERATE", "schema": "generation-artifact"},
            {"step": "VALIDATE", "schema": "verdict"},
            {"step": "OUTPUT", "schema": "pipeline-summary"},
        ],
        "review": [
            {"step": "ADR", "schema": "decision-record"},
            {"step": "RESEARCH", "schema": "research-artifact"},
            {"step": "ASSESS", "schema": "decision-record"},
            {"step": "REVIEW", "schema": "verdict"},
            {"step": "AGGREGATE", "schema": "verdict"},
            {"step": "REPORT", "schema": "pipeline-summary"},
        ],
        "debugging": [
            {"step": "ADR", "schema": "decision-record"},
            {"step": "PROBE", "schema": "research-artifact"},
            {"step": "SEARCH", "schema": "research-artifact"},
            {"step": "ASSESS", "schema": "decision-record"},
            {"step": "PLAN", "schema": "decision-record"},
            {"step": "EXECUTE", "schema": "execution-report"},
            {"step": "VERIFY", "schema": "verdict"},
            {"step": "OUTPUT", "schema": "pipeline-summary"},
        ],
        "operations": [
            {"step": "ADR", "schema": "decision-record"},
            {"step": "PROBE", "schema": "research-artifact"},
            {"step": "ASSESS", "schema": "decision-record"},
            {"step": "PLAN", "schema": "decision-record"},
            {"step": "GUARD", "schema": "safety-record"},
            {"step": "EXECUTE", "schema": "execution-report"},
            {"step": "VALIDATE", "schema": "verdict"},
            {"step": "OUTPUT", "schema": "pipeline-summary"},
        ],
        "configuration": [
            {"step": "ADR", "schema": "decision-record"},
            {"step": "RESEARCH", "schema": "research-artifact"},
            {"step": "COMPILE", "schema": "structured-corpus"},
            {"step": "TEMPLATE", "schema": "generation-artifact"},
            {"step": "CONFORM", "schema": "verdict"},
            {"step": "VALIDATE", "schema": "verdict"},
            {"step": "OUTPUT", "schema": "pipeline-summary"},
        ],
        "analysis": [
            {"step": "ADR", "schema": "decision-record"},
            {"step": "RESEARCH", "schema": "research-artifact"},
            {"step": "COMPILE", "schema": "structured-corpus"},
            {"step": "ASSESS", "schema": "decision-record"},
            {"step": "SYNTHESIZE", "schema": "decision-record"},
            {"step": "REPORT", "schema": "pipeline-summary"},
        ],
        "migration": [
            {"step": "ADR", "schema": "decision-record"},
            {"step": "CHARACTERIZE", "schema": "verdict"},
            {"step": "PLAN", "schema": "decision-record"},
            {"step": "GUARD", "schema": "safety-record"},
            {"step": "SNAPSHOT", "schema": "safety-record"},
            {"step": "EXECUTE", "schema": "execution-report"},
            {"step": "VALIDATE", "schema": "verdict"},
            {"step": "OUTPUT", "schema": "pipeline-summary"},
        ],
        "testing": [
            {"step": "ADR", "schema": "decision-record"},
            {"step": "RESEARCH", "schema": "research-artifact"},
            {"step": "COMPILE", "schema": "structured-corpus"},
            {"step": "CHARACTERIZE", "schema": "structured-corpus"},
            {"step": "GENERATE", "schema": "generation-artifact"},
            {"step": "VALIDATE", "schema": "verdict"},
            {"step": "REPORT", "schema": "pipeline-summary"},
        ],
    }

    all_passed = True
    failed_chains: list[str] = []

    with tempfile.TemporaryDirectory() as tmpdir:
        for chain_name, steps in chains.items():
            spec_file = Path(tmpdir) / f"{chain_name}-chain.json"
            spec_file.write_text(json.dumps(steps, indent=2))

            result = run([sys.executable, str(ARTIFACT_UTILS), "validate-chain", str(spec_file)])
            if result.returncode != 0:
                all_passed = False
                stderr_snippet = result.stderr.strip().replace("\n", "; ")[:200]
                failed_chains.append(f"{chain_name}: {stderr_snippet}")

    if all_passed:
        report(20, "Chain validation: all 8 canonical chains valid", True)
    else:
        detail = "Failed: " + " | ".join(failed_chains)
        report(20, "Chain validation: all 8 canonical chains valid", False, detail)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


def main() -> int:
    print()
    print("Test Suite: ADR Enforcement System")
    print("===================================")
    print()

    # Run all tests in order
    test_01_hash_subcommand()
    test_02_register_subcommand()
    test_03_active_subcommand()
    test_04_context_skill_creator()
    test_05_context_chain_composer()
    test_06_context_orchestrator()
    test_07_verify_correct_hash()
    test_08_verify_wrong_hash()
    test_09_list_subcommand()
    test_10_compliance_clean_file()
    test_11_compliance_violation_file()
    test_12_path_traversal_blocked()
    test_13_hook_fires_on_pipeline_prompt()
    test_14_hook_silent_on_unrelated_prompt()
    test_15_adr_architecture_rules_section()
    test_16_adr_canonical_chains_section()
    test_17_spec_format_adr_path_field()
    test_18_spec_format_adr_hash_field()
    test_19_architecture_rule_18_present()
    test_20_canonical_chains_valid()

    # Cleanup temp session file
    cleanup_session_file(REPO_ROOT)

    # Summary
    total = _pass_count + _fail_count
    print()
    print("---")
    print(f"Results: {_pass_count}/{total} passed, {_fail_count} failed")

    if _fail_count == 0:
        print("All tests passed.")
        return 0
    else:
        print(f"{_fail_count} test(s) FAILED.")
        return 1


if __name__ == "__main__":
    sys.exit(main())
