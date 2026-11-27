"""Regression tests for sprite_generate.py and portrait_pipeline.py."""

from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

SCRIPTS_DIR = Path(__file__).resolve().parents[1]


def _load(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec is not None and spec.loader is not None
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


def test_sprite_generate_has_no_hardcoded_home_and_finds_repo_nano_banana() -> None:
    source = (SCRIPTS_DIR / "sprite_generate.py").read_text(encoding="utf-8")
    assert "/home/feedgen" not in source

    mod = _load("game_dev_sprite_generate", SCRIPTS_DIR / "sprite_generate.py")
    found = mod.find_nano_banana_script()
    assert found is not None
    assert found.name == "nano-banana-generate.py"
    assert found.is_file()


def test_portrait_pipeline_emits_verifier_verdict_in_json(capsys) -> None:
    mod = _load("game_dev_portrait_pipeline", SCRIPTS_DIR / "portrait_pipeline.py")

    rc_pass = mod._emit_verifier_result(gates_run=["verify_no_magenta"], failures=[], elapsed_seconds=0.05)
    assert rc_pass == 0
    pass_payload = json.loads(capsys.readouterr().out)
    assert pass_payload["passed"] is True
    assert pass_payload["verifier_verdict"] == "PASS"

    rc_fail = mod._emit_verifier_result(
        gates_run=["verify_no_magenta"],
        failures=[{"check": "verify_no_magenta", "file": "p.png", "details": "magenta bleed"}],
        elapsed_seconds=0.05,
    )
    assert rc_fail == mod.VERIFIER_EXIT_CODE
    fail_payload = json.loads(capsys.readouterr().out)
    assert fail_payload["passed"] is False
    assert fail_payload["verifier_verdict"] == "FAIL"
