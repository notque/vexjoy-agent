"""Tests for scripts/d-preflight.py: hook loading, creation/ADR/synthesis/allowlist/security/private-name checks."""

from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
from pathlib import Path
from unittest.mock import patch

import pytest

REPO = Path(__file__).resolve().parents[2]
SCRIPTS = REPO / "scripts"


def _load_preflight():
    spec = importlib.util.spec_from_file_location("d_preflight_unit", SCRIPTS / "d-preflight.py")
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    with patch("sys.exit"):
        spec.loader.exec_module(mod)
    return mod


preflight = _load_preflight()


def _init_toolkit_fixture(tmp_path: Path) -> Path:
    """Create a minimal git-initialized toolkit-shaped repo with symlinks to real hooks."""
    repo = tmp_path / "toolkit"
    (repo / "agents").mkdir(parents=True)
    (repo / "skills" / "meta" / "d").mkdir(parents=True)
    (repo / "skills" / "meta" / "d" / "SKILL.md").write_text("---\nname: d\n---\n", encoding="utf-8")
    (repo / "hooks").mkdir(parents=True)
    for name in (
        "pretool-unified-gate.py",
        "pretool-adr-creation-gate.py",
        "pretool-synthesis-gate.py",
        "pretool-private-name-leak-gate.py",
    ):
        (repo / "hooks" / name).symlink_to(REPO / "hooks" / name)
    (repo / "hooks" / "lib").symlink_to(REPO / "hooks" / "lib")
    subprocess.run(["git", "init", "-q"], cwd=repo, check=True)
    return repo


def test_all_four_hooks_load_in_toolkit_repo() -> None:
    report = preflight.preflight([], REPO)
    assert report["gates_loaded"] == {
        "unified": True,
        "adr": True,
        "synthesis": True,
        "private-name": True,
    }


def test_new_component_creation_flags_creation_adr_and_synthesis_gates(tmp_path: Path) -> None:
    repo = _init_toolkit_fixture(tmp_path)
    report = preflight.preflight(["agents/new-worker.md", "hooks/new-guard.py"], repo)
    assert report["gates_loaded"] == {
        "unified": True,
        "adr": True,
        "synthesis": True,
        "private-name": True,
    }
    agent_costs = " ".join(report["paths"][0]["costs"])
    assert "creation gate" in agent_costs and "adr/new-worker.md" in agent_costs
    assert "synthesis gate" in agent_costs

    hook_costs = " ".join(report["paths"][1]["costs"])
    assert "ADR gate" in hook_costs and "new-guard" in hook_costs


def test_adr_gate_suppressed_when_adr_already_exists(tmp_path: Path) -> None:
    repo = _init_toolkit_fixture(tmp_path)
    (repo / "adr").mkdir()
    (repo / "adr" / "existing-adr-hook.md").write_text("# ADR\n", encoding="utf-8")

    report = preflight.preflight(["hooks/existing-adr-hook.py"], repo)
    assert report["paths"][0]["costs"] == []


def test_allowlisted_voice_skill_skips_creation_and_adr_gates(tmp_path: Path) -> None:
    repo = _init_toolkit_fixture(tmp_path)
    report = preflight.preflight(["skills/content/voice-demo/SKILL.md"], repo)
    assert report["paths"][0]["costs"] == []


def test_existing_gated_file_edit_checks_active_adr_session(tmp_path: Path) -> None:
    repo = _init_toolkit_fixture(tmp_path)
    target = "skills/meta/d/SKILL.md"

    # Without an active .adr-session.json, editing an existing gated file has no cost.
    assert preflight.preflight([target], repo)["paths"][0]["costs"] == []

    # With an active .adr-session.json and missing synthesis.md, synthesis gate fires.
    session = {"domain": "demo-adr", "adr_path": "adr/demo-adr.md"}
    (repo / ".adr-session.json").write_text(json.dumps(session), encoding="utf-8")
    costs_missing = preflight.preflight([target], repo)["paths"][0]["costs"]
    assert any("synthesis gate" in c and "synthesis.md missing" in c for c in costs_missing)

    # Non-gated paths outside agents/ and skills/ stay clear even during an active ADR session.
    (repo / "README.md").write_text("hi\n", encoding="utf-8")
    assert preflight.preflight(["README.md"], repo)["paths"][0]["costs"] == []

    # BLOCKED verdict still reports synthesis gate cost.
    syn_dir = repo / "adr" / "demo-adr"
    syn_dir.mkdir(parents=True)
    (syn_dir / "synthesis.md").write_text("## Verdict\nBLOCKED\n", encoding="utf-8")
    costs_blocked = preflight.preflight([target], repo)["paths"][0]["costs"]
    assert any("synthesis gate" in c and "BLOCKED" in c for c in costs_blocked)

    # PROCEED verdict clears synthesis gate cost for existing file edits.
    (syn_dir / "synthesis.md").write_text("## Verdict\nPROCEED\n", encoding="utf-8")
    assert preflight.preflight([target], repo)["paths"][0]["costs"] == []


def test_security_findings_redacted(tmp_path: Path) -> None:
    # Construct sample token dynamically so commit-time scanner does not flag this test.
    token = "".join(["AK", "IA", "QWERTYUI", "OPASDFGH"])
    key_name = "_".join(["aws", "access", "key"])
    sample = tmp_path / "config.yml"
    sample.write_text(f"{key_name}: {token}\n", encoding="utf-8")

    report = preflight.preflight([str(sample)], tmp_path)
    assert report["security"]
    rendered = preflight.render(report)
    assert "security review blocks the commit" in rendered
    assert token not in rendered


def test_cli_json_output(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    repo = _init_toolkit_fixture(tmp_path)
    with patch.object(Path, "cwd", return_value=repo):
        rc = preflight.main(["--paths", "skills/content/voice-demo/SKILL.md", "--json"])
    assert rc == 0
    data = json.loads(capsys.readouterr().out)
    assert data["gates_loaded"] == {"unified": True, "adr": True, "synthesis": True, "private-name": True}
    assert data["paths"][0]["costs"] == []
