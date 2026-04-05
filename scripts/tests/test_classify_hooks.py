"""Tests for classify-hooks.py (ADR-175).

Covers:
- branch-safety hook classified as Tier 1
- error-learner hook classified as Tier 2
- capability-catalog hook classified as Tier 3
- --tier N filters to only matching tier
- --json produces valid JSON with tier field
- Missing settings.json exits 1 with error message
"""

from __future__ import annotations

import importlib
import json
import subprocess
import sys
from pathlib import Path

import pytest

# ---------------------------------------------------------------------------
# Module import
# ---------------------------------------------------------------------------

_SCRIPTS_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_SCRIPTS_DIR))
ch = importlib.import_module("classify-hooks")
sys.path.pop(0)

SCRIPT_PATH = _SCRIPTS_DIR / "classify-hooks.py"


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


def _make_settings(tmp_path: Path, hook_commands: list[tuple[str, str]]) -> Path:
    """Write a minimal settings.json with the given hooks.

    Args:
        tmp_path: Temporary directory to write the file into.
        hook_commands: List of (event_type, command) tuples.

    Returns:
        Path to the written settings.json.
    """
    hooks_by_event: dict[str, list] = {}
    for event_type, command in hook_commands:
        if event_type not in hooks_by_event:
            hooks_by_event[event_type] = []
        hooks_by_event[event_type].append(
            {
                "matcher": "",
                "hooks": [{"type": "command", "command": command}],
            }
        )

    settings = {"hooks": hooks_by_event}
    path = tmp_path / "settings.json"
    path.write_text(json.dumps(settings, indent=2), encoding="utf-8")
    return path


@pytest.fixture()
def settings_all_tiers(tmp_path: Path) -> Path:
    """Settings.json with one hook from each tier across different event types."""
    return _make_settings(
        tmp_path,
        [
            ("PreToolUse", "python3 /home/user/.claude/hooks/branch-safety.py"),
            ("PostToolUse", "python3 /home/user/.claude/hooks/error-learner.py"),
            ("SessionStart", "python3 /home/user/.claude/hooks/capability-catalog.py"),
            ("UserPromptSubmit", "python3 /home/user/.claude/hooks/injection-scanner.py"),
            ("PostToolUse", "python3 /home/user/.claude/hooks/synthesis-gate.py"),
        ],
    )


# ---------------------------------------------------------------------------
# Unit tests (module-level functions)
# ---------------------------------------------------------------------------


def test_extract_hook_name_full_path() -> None:
    """extract_hook_name returns basename without extension."""
    name = ch.extract_hook_name("python3 /home/user/.claude/hooks/branch-safety.py")
    assert name == "branch-safety"


def test_extract_hook_name_no_path() -> None:
    """extract_hook_name handles command without directory path."""
    name = ch.extract_hook_name("branch-safety.py")
    assert name == "branch-safety"


def test_extract_hook_name_sh_extension() -> None:
    """extract_hook_name works with .sh scripts."""
    name = ch.extract_hook_name("bash /usr/local/bin/injection-scanner.sh")
    assert name == "injection-scanner"


def test_classify_tier1_branch_safety() -> None:
    """branch-safety hook is Tier 1."""
    tier, reason = ch.classify_hook("branch-safety")
    assert tier == 1
    assert "branch-safety" in reason


def test_classify_tier1_injection_scanner() -> None:
    """injection-scanner hook is Tier 1."""
    tier, _ = ch.classify_hook("injection-scanner")
    assert tier == 1


def test_classify_tier1_bash_injection() -> None:
    """bash-injection hook is Tier 1."""
    tier, _ = ch.classify_hook("bash-injection")
    assert tier == 1


def test_classify_tier2_error_learner() -> None:
    """error-learner hook is Tier 2."""
    tier, reason = ch.classify_hook("error-learner")
    assert tier == 2
    assert "error-learner" in reason


def test_classify_tier2_auto_plan() -> None:
    """auto-plan hook is Tier 2."""
    tier, _ = ch.classify_hook("auto-plan")
    assert tier == 2


def test_classify_tier2_synthesis_gate() -> None:
    """synthesis-gate hook is Tier 2."""
    tier, _ = ch.classify_hook("synthesis-gate")
    assert tier == 2


def test_classify_tier3_capability_catalog() -> None:
    """capability-catalog hook is Tier 3 (no matching keywords)."""
    tier, reason = ch.classify_hook("capability-catalog")
    assert tier == 3
    assert "no safety or productivity keywords matched" in reason


def test_classify_tier3_unknown_hook() -> None:
    """Random unknown hook name is Tier 3."""
    tier, _ = ch.classify_hook("my-custom-hook")
    assert tier == 3


def test_load_hook_records_all_tiers(settings_all_tiers: Path) -> None:
    """load_hook_records returns records for all registered hooks."""
    records = ch.load_hook_records(settings_all_tiers)
    assert len(records) == 5
    names = [r["hook_name"] for r in records]
    assert "branch-safety" in names
    assert "error-learner" in names
    assert "capability-catalog" in names


def test_load_hook_records_tier_assignment(settings_all_tiers: Path) -> None:
    """load_hook_records assigns correct tiers."""
    records = ch.load_hook_records(settings_all_tiers)
    by_name = {r["hook_name"]: r for r in records}
    assert by_name["branch-safety"]["tier"] == 1
    assert by_name["error-learner"]["tier"] == 2
    assert by_name["capability-catalog"]["tier"] == 3


def test_load_hook_records_event_type(settings_all_tiers: Path) -> None:
    """load_hook_records captures the event_type for each hook."""
    records = ch.load_hook_records(settings_all_tiers)
    by_name = {r["hook_name"]: r for r in records}
    assert by_name["branch-safety"]["event_type"] == "PreToolUse"
    assert by_name["error-learner"]["event_type"] == "PostToolUse"
    assert by_name["capability-catalog"]["event_type"] == "SessionStart"


# ---------------------------------------------------------------------------
# Subprocess (CLI) tests
# ---------------------------------------------------------------------------


def _run(args: list[str]) -> subprocess.CompletedProcess:
    """Run the script via subprocess and return the result."""
    return subprocess.run(
        [sys.executable, str(SCRIPT_PATH)] + args,
        capture_output=True,
        text=True,
    )


def test_cli_markdown_output(settings_all_tiers: Path) -> None:
    """CLI default output is a markdown table containing all hooks."""
    result = _run(["--settings", str(settings_all_tiers)])
    assert result.returncode == 0
    assert "branch-safety" in result.stdout
    assert "error-learner" in result.stdout
    assert "capability-catalog" in result.stdout
    assert "| Hook Name" in result.stdout


def test_cli_tier_filter_tier1(settings_all_tiers: Path) -> None:
    """--tier 1 shows only Tier 1 hooks in markdown output."""
    result = _run(["--settings", str(settings_all_tiers), "--tier", "1"])
    assert result.returncode == 0
    assert "branch-safety" in result.stdout
    assert "injection-scanner" in result.stdout
    assert "error-learner" not in result.stdout
    assert "capability-catalog" not in result.stdout


def test_cli_tier_filter_tier2(settings_all_tiers: Path) -> None:
    """--tier 2 shows only Tier 2 hooks."""
    result = _run(["--settings", str(settings_all_tiers), "--tier", "2"])
    assert result.returncode == 0
    assert "error-learner" in result.stdout
    assert "synthesis-gate" in result.stdout
    assert "branch-safety" not in result.stdout


def test_cli_tier_filter_tier3(settings_all_tiers: Path) -> None:
    """--tier 3 shows only Tier 3 hooks."""
    result = _run(["--settings", str(settings_all_tiers), "--tier", "3"])
    assert result.returncode == 0
    assert "capability-catalog" in result.stdout
    assert "branch-safety" not in result.stdout
    assert "error-learner" not in result.stdout


def test_cli_json_output(settings_all_tiers: Path) -> None:
    """--json produces valid JSON list with tier field."""
    result = _run(["--settings", str(settings_all_tiers), "--json"])
    assert result.returncode == 0
    data = json.loads(result.stdout)
    assert isinstance(data, list)
    assert len(data) == 5
    assert all("tier" in r for r in data)


def test_cli_json_tier_values(settings_all_tiers: Path) -> None:
    """JSON output has correct tier values for known hooks."""
    result = _run(["--settings", str(settings_all_tiers), "--json"])
    assert result.returncode == 0
    data = json.loads(result.stdout)
    by_name = {r["hook_name"]: r for r in data}
    assert by_name["branch-safety"]["tier"] == 1
    assert by_name["error-learner"]["tier"] == 2
    assert by_name["capability-catalog"]["tier"] == 3


def test_cli_json_tier1_filter(settings_all_tiers: Path) -> None:
    """--json --tier 1 returns only Tier 1 records."""
    result = _run(["--settings", str(settings_all_tiers), "--json", "--tier", "1"])
    assert result.returncode == 0
    data = json.loads(result.stdout)
    assert all(r["tier"] == 1 for r in data)
    names = [r["hook_name"] for r in data]
    assert "branch-safety" in names
    assert "injection-scanner" in names


def test_cli_json_schema(settings_all_tiers: Path) -> None:
    """JSON records contain all required fields."""
    result = _run(["--settings", str(settings_all_tiers), "--json"])
    assert result.returncode == 0
    data = json.loads(result.stdout)
    required_keys = {"hook_name", "event_type", "command", "tier", "classification_reason"}
    for record in data:
        assert required_keys.issubset(record.keys()), f"Missing keys in: {record}"


def test_cli_missing_settings(tmp_path: Path) -> None:
    """Missing settings.json prints error and exits 1."""
    missing = tmp_path / "nonexistent.json"
    result = _run(["--settings", str(missing)])
    assert result.returncode == 1
    assert "error" in result.stderr.lower()
    assert str(missing) in result.stderr
