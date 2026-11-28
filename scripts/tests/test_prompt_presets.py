#!/usr/bin/env python3
"""Tests for scripts/prompt_presets.py and its integration with scripts/build-dispatch.py."""

from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
from pathlib import Path
from unittest.mock import patch

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
PRESETS_SCRIPT = REPO_ROOT / "scripts" / "prompt_presets.py"
BUILD_DISPATCH_SCRIPT = REPO_ROOT / "scripts" / "build-dispatch.py"


def _load(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec is not None and spec.loader is not None
    mod = importlib.util.module_from_spec(spec)
    with patch("sys.exit"):
        spec.loader.exec_module(mod)
    return mod


pp = _load(PRESETS_SCRIPT, "prompt_presets")
bd = _load(BUILD_DISPATCH_SCRIPT, "build_dispatch")


EXPECTED_CONSTRAINTS = {
    "strict-scope": (
        "Touch only the files and symbols required for the stated outcome; "
        "make zero opportunistic refactors or unrelated edits."
    ),
    "spike": (
        "Time-boxed prototype or investigation; prioritize answering the question "
        "with evidence and keep changes disposable/unmerged."
    ),
    "review-only": (
        "Read-only inspection and findings with file:line evidence; "
        "make zero file edits, commits, or mutating commands."
    ),
    "ship": (
        "Deliver end-to-end: implement, run full relevant tests and linters, "
        "verify exit codes, open/update PR, and wait for green CI before merging."
    ),
    "local-only": ("Keep all changes local: make zero git pushes, PR creations, merges, or remote mutations."),
}


def test_all_five_presets_defined_with_expected_constraints() -> None:
    assert list(pp.PRESETS) == ["strict-scope", "spike", "review-only", "ship", "local-only"]
    for name, expected_text in EXPECTED_CONSTRAINTS.items():
        entry = pp.PRESETS[name]
        assert entry["name"] == name
        assert entry["flag"] == f"--{name}"
        assert entry["constraint"] == expected_text
        assert entry["summary"]


@pytest.mark.parametrize(
    ("text", "expected_names", "expected_cleaned"),
    [
        ("--strict-scope fix the auth bug", ["strict-scope"], "fix the auth bug"),
        ("fix the auth bug --local-only", ["local-only"], "fix the auth bug"),
        ("fix --review-only the --spike module", ["review-only", "spike"], "fix the module"),
        ("--SHIP --STRICT-SCOPE deploy fix", ["ship", "strict-scope"], "deploy fix"),
        ("--strict-scope", ["strict-scope"], ""),
        ("--strict-scope\nfix auth\n--local-only", ["strict-scope", "local-only"], "fix auth"),
        ("plain prompt without flags", [], "plain prompt without flags"),
        ("", [], ""),
    ],
)
def test_extract_presets_basic_and_case_insensitive(
    text: str, expected_names: list[str], expected_cleaned: str
) -> None:
    names, cleaned = pp.extract_presets(text)
    assert names == expected_names
    assert cleaned == expected_cleaned


@pytest.mark.parametrize(
    "text",
    [
        "foo--ship bar",
        "run --shipping check",
        "pass --ship-it to cli",
        "edit path/to/--spike/file.py",
        "inspect ./--local-only",
        "cmd --ship=true --review-only.md",
        "check C:\\repo\\--strict-scope\\a.py",
    ],
)
def test_extract_presets_ignores_substrings_paths_and_shell_tokens(text: str) -> None:
    names, cleaned = pp.extract_presets(text)
    assert names == []
    assert cleaned == text


def test_extract_presets_deduplicates_preserving_first_seen_order() -> None:
    names, cleaned = pp.extract_presets("--local-only --strict-scope fix bug --LOCAL-ONLY --ship --strict-scope")
    assert names == ["local-only", "strict-scope", "ship"]
    assert cleaned == "fix bug"


def test_resolve_presets_merges_explicit_and_text_deduplicated_in_order() -> None:
    resolved = pp.resolve_presets(
        names=["--spike", "strict-scope", "spike"],
        text="--strict-scope inspect auth --local-only",
    )
    assert [item["name"] for item in resolved] == ["spike", "strict-scope", "local-only"]
    assert [item["flag"] for item in resolved] == ["--spike", "--strict-scope", "--local-only"]
    # Returned dicts are copies, so caller mutation does not corrupt PRESETS.
    resolved[0]["constraint"] = "mutated"
    assert pp.PRESETS["spike"]["constraint"] == EXPECTED_CONSTRAINTS["spike"]


@pytest.mark.parametrize("bad_names", [["unknown-preset"], ["--shipping"], [""], "strict-scope", [123]])
def test_resolve_presets_rejects_invalid_names(bad_names: object) -> None:
    with pytest.raises(ValueError):
        pp.resolve_presets(names=bad_names)  # type: ignore[arg-type]


def test_format_helpers() -> None:
    assert pp.format_preset_constraints([]) == ""
    assert pp.format_preset_banner([]) == ""

    resolved = pp.resolve_presets(["strict-scope", "local-only"])
    banner = pp.format_preset_banner(resolved)
    assert banner == "Prompt presets: --strict-scope, --local-only"

    constraints = pp.format_preset_constraints(resolved)
    assert f"[strict-scope] {EXPECTED_CONSTRAINTS['strict-scope']}" in constraints
    assert f"[local-only] {EXPECTED_CONSTRAINTS['local-only']}" in constraints


def test_cli_list_plain_and_json() -> None:
    plain = subprocess.run(
        [sys.executable, str(PRESETS_SCRIPT), "--list"],
        capture_output=True,
        text=True,
        check=False,
    )
    assert plain.returncode == 0
    for name in EXPECTED_CONSTRAINTS:
        assert f"--{name}:" in plain.stdout

    as_json = subprocess.run(
        [sys.executable, str(PRESETS_SCRIPT), "--list", "--json"],
        capture_output=True,
        text=True,
        check=False,
    )
    assert as_json.returncode == 0
    data = json.loads(as_json.stdout)
    assert [item["name"] for item in data["presets"]] == list(EXPECTED_CONSTRAINTS)


def test_cli_extract_json_and_plain() -> None:
    as_json = subprocess.run(
        [sys.executable, str(PRESETS_SCRIPT), "--extract", "--strict-scope fix foo --local-only", "--json"],
        capture_output=True,
        text=True,
        check=False,
    )
    assert as_json.returncode == 0
    payload = json.loads(as_json.stdout)
    assert payload["presets"] == ["strict-scope", "local-only"]
    assert payload["cleaned_text"] == "fix foo"
    assert payload["banner"] == "Prompt presets: --strict-scope, --local-only"
    assert EXPECTED_CONSTRAINTS["strict-scope"] in payload["constraints"]
    assert EXPECTED_CONSTRAINTS["local-only"] in payload["constraints"]

    plain = subprocess.run(
        [sys.executable, str(PRESETS_SCRIPT), "--extract", "no flags here"],
        capture_output=True,
        text=True,
        check=False,
    )
    assert plain.returncode == 0
    assert "Prompt presets: none" in plain.stdout
    assert "Cleaned text: no flags here" in plain.stdout


@pytest.mark.usefixtures("use_public_index")
def test_build_dispatch_explicit_and_auto_extracted_presets() -> None:
    decision = {
        "skill": "testing",
        "complexity": "medium",
        "model": "opus",
        "prompt_presets": ["strict-scope"],
        "task_spec": {
            "request_verbatim": "--local-only --strict-scope add unit tests",
            "intent": "Add unit tests for parser",
            "constraints": "Keep runtime under 2s.",
        },
    }
    preamble = bd.build_preamble(decision, gather=False)
    lines = preamble.splitlines()
    assert lines[0].startswith("[do-route] ")
    assert "Prompt presets: --strict-scope, --local-only" in preamble
    assert "**Request (verbatim):** --local-only --strict-scope add unit tests" in preamble
    expected_constraints_line = (
        "**Constraints:** Keep runtime under 2s. "
        f"[strict-scope] {EXPECTED_CONSTRAINTS['strict-scope']} "
        f"[local-only] {EXPECTED_CONSTRAINTS['local-only']}"
    )
    assert expected_constraints_line in preamble


@pytest.mark.usefixtures("use_public_index")
def test_build_dispatch_presets_create_constraints_field_when_absent() -> None:
    decision = {
        "skill": "review",
        "complexity": "medium",
        "model": "opus",
        "task_spec": {
            "request_verbatim": "--review-only inspect scripts/prompt_presets.py",
            "intent": "Review prompt presets script",
        },
    }
    preamble = bd.build_preamble(decision, gather=False)
    assert "Prompt presets: --review-only" in preamble
    assert f"**Constraints:** [review-only] {EXPECTED_CONSTRAINTS['review-only']}" in preamble


@pytest.mark.usefixtures("use_public_index")
def test_build_dispatch_unchanged_without_presets() -> None:
    base_decision = {
        "skill": "testing",
        "complexity": "medium",
        "model": "opus",
        "task_spec": {
            "request_verbatim": "run tests on foo--ship and --shipping",
            "intent": "Run unit tests",
            "constraints": "Branch from main.",
        },
    }
    with_empty_key = {**base_decision, "prompt_presets": []}
    out_base = bd.build_preamble(base_decision, gather=False)
    out_empty = bd.build_preamble(with_empty_key, gather=False)
    assert out_base == out_empty
    assert "Prompt presets:" not in out_base
    assert "**Constraints:** Branch from main." in out_base


@pytest.mark.usefixtures("use_public_index")
def test_build_dispatch_main_thread_with_and_without_presets() -> None:
    base = {
        "execution": "main",
        "skill": "testing",
        "complexity": "simple",
        "task_spec": {"intent": "fix typo"},
    }
    out_plain = bd.build_preamble(base, gather=False)
    assert "Prompt presets:" not in out_plain

    with_preset = {**base, "prompt_presets": ["spike"]}
    out_preset = bd.build_preamble(with_preset, gather=False)
    assert "Prompt presets: --spike" in out_preset
    assert EXPECTED_CONSTRAINTS["spike"] in out_preset


@pytest.mark.usefixtures("use_public_index")
def test_build_dispatch_rejects_unknown_preset() -> None:
    decision = {
        "skill": "testing",
        "complexity": "medium",
        "model": "opus",
        "prompt_presets": ["nonexistent"],
        "task_spec": {"intent": "test"},
    }
    with pytest.raises(bd.InputError, match="unknown prompt preset"):
        bd.build_preamble(decision, gather=False)

    cli = subprocess.run(
        [sys.executable, str(BUILD_DISPATCH_SCRIPT), "--no-gather", "--json", json.dumps(decision)],
        capture_output=True,
        text=True,
        check=False,
    )
    assert cli.returncode == 2
    assert cli.stdout == ""
    assert "unknown prompt preset" in cli.stderr


def test_cli_extract_file_handles_single_flag_metachars_and_stdin(tmp_path: Path) -> None:
    single_flag = tmp_path / "single.txt"
    single_flag.write_text("--strict-scope", encoding="utf-8")
    res_single = subprocess.run(
        [sys.executable, str(PRESETS_SCRIPT), "--extract-file", str(single_flag), "--json"],
        capture_output=True,
        text=True,
        check=False,
    )
    assert res_single.returncode == 0
    payload_single = json.loads(res_single.stdout)
    assert payload_single["presets"] == ["strict-scope"]
    assert payload_single["cleaned_text"] == ""
    assert payload_single["banner"] == "Prompt presets: --strict-scope"

    meta_file = tmp_path / "meta.txt"
    meta_file.write_text('--local-only fix "quoted" $(not_executed) `ticks`\n--review-only', encoding="utf-8")
    res_meta = subprocess.run(
        [sys.executable, str(PRESETS_SCRIPT), "--extract-file", str(meta_file), "--json"],
        capture_output=True,
        text=True,
        check=False,
    )
    assert res_meta.returncode == 0
    payload_meta = json.loads(res_meta.stdout)
    assert payload_meta["presets"] == ["local-only", "review-only"]
    assert payload_meta["cleaned_text"] == 'fix "quoted" $(not_executed) `ticks`'

    res_stdin = subprocess.run(
        [sys.executable, str(PRESETS_SCRIPT), "--extract-file", "-", "--json"],
        input="--spike",
        capture_output=True,
        text=True,
        check=False,
    )
    assert res_stdin.returncode == 0
    payload_stdin = json.loads(res_stdin.stdout)
    assert payload_stdin["presets"] == ["spike"]
    assert payload_stdin["cleaned_text"] == ""

    res_missing = subprocess.run(
        [sys.executable, str(PRESETS_SCRIPT), "--extract-file", str(tmp_path / "missing.txt")],
        capture_output=True,
        text=True,
        check=False,
    )
    assert res_missing.returncode == 2
    assert "error reading" in res_missing.stderr
