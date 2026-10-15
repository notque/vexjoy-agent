#!/usr/bin/env python3
"""Every hooks/*.py entrypoint must read a bypass env var.

A misbehaving hook needs an off switch that does not touch settings.json.
The convention: a module constant `_BYPASS_ENV = "<HOOK_NAME>_BYPASS"`, read
with `os.environ.get(_BYPASS_ENV) == "1"` at the top of `main()`, exiting 0
silently. Older hooks use `_DISABLE` or `_SKIP` names; those count too.

Run with: python3 -m pytest hooks/tests/test_every_hook_has_bypass.py -v
"""

from __future__ import annotations

import ast
import json
import os
import re
import subprocess
import sys
from pathlib import Path

import pytest

HOOKS_DIR = Path(__file__).resolve().parent.parent

# Files that are not hook entrypoints.
EXEMPT = {
    "__init__.py": "package marker",
    "voice-pipeline-tracker.py": "CLI utility called with arguments, not a hook",
}

_BYPASS_NAME = re.compile(r"_(BYPASS|DISABLE|SKIP)$")


def _string_constants(tree: ast.AST) -> dict[str, str]:
    """Module-level NAME = "literal" assignments."""
    out: dict[str, str] = {}
    for node in getattr(tree, "body", []):
        if isinstance(node, ast.Assign) and isinstance(node.value, ast.Constant) and isinstance(node.value.value, str):
            for target in node.targets:
                if isinstance(target, ast.Name):
                    out[target.id] = node.value.value
    return out


def find_bypass_envs(source: str) -> list[str]:
    """Env var names that end in _BYPASS/_DISABLE/_SKIP and are read via os.environ.get."""
    tree = ast.parse(source)
    consts = _string_constants(tree)
    found: list[str] = []
    for node in ast.walk(tree):
        if not (
            isinstance(node, ast.Call)
            and isinstance(node.func, ast.Attribute)
            and node.func.attr == "get"
            and isinstance(node.func.value, ast.Attribute)
            and node.func.value.attr == "environ"
            and node.args
        ):
            continue
        arg = node.args[0]
        if isinstance(arg, ast.Constant) and isinstance(arg.value, str):
            name = arg.value
        elif isinstance(arg, ast.Name) and arg.id in consts:
            name = consts[arg.id]
        else:
            continue
        if _BYPASS_NAME.search(name):
            found.append(name)
    return found


def _hook_files() -> list[Path]:
    return sorted(p for p in HOOKS_DIR.glob("*.py") if p.name not in EXEMPT)


def _bypass_constant(path: Path) -> str | None:
    return _string_constants(ast.parse(path.read_text(encoding="utf-8"))).get("_BYPASS_ENV")


HOOKS = _hook_files()
CONVENTION_HOOKS = [p for p in HOOKS if _bypass_constant(p)]


def test_exempt_files_exist():
    for name in EXEMPT:
        assert (HOOKS_DIR / name).is_file(), f"stale exemption: {name}"


@pytest.mark.parametrize("path", HOOKS, ids=lambda p: p.name)
def test_hook_reads_a_bypass_env(path: Path):
    envs = find_bypass_envs(path.read_text(encoding="utf-8"))
    assert envs, (
        f'{path.name} has no bypass env var. Add `_BYPASS_ENV = "<HOOK_NAME>_BYPASS"` and exit 0 '
        'when `os.environ.get(_BYPASS_ENV) == "1"` at the top of main().'
    )


@pytest.mark.parametrize("path", CONVENTION_HOOKS, ids=lambda p: p.name)
def test_bypass_exits_zero_with_no_output(path: Path, tmp_path: Path):
    env = {k: v for k, v in os.environ.items() if k != "CLAUDE_HOOKS_DEBUG"}
    env[_bypass_constant(path)] = "1"
    env["HOME"] = str(tmp_path)
    result = subprocess.run(
        [sys.executable, str(path)],
        input="{}",
        capture_output=True,
        text=True,
        env=env,
        cwd=tmp_path,
        timeout=15,
    )
    assert result.returncode == 0, result.stderr
    # Silent, or the empty-output envelope some older hooks print: no context, no decision.
    if result.stdout.strip():
        payload = json.loads(result.stdout)
        assert set(payload) == {"hookSpecificOutput"}
        assert set(payload["hookSpecificOutput"]) <= {"hookEventName"}, result.stdout


class TestDetector:
    def test_constant_read_counts(self):
        src = 'import os\n_BYPASS_ENV = "X_BYPASS"\ndef main():\n    if os.environ.get(_BYPASS_ENV) == "1":\n        pass\n'
        assert find_bypass_envs(src) == ["X_BYPASS"]

    def test_inline_literal_counts(self):
        src = 'import os\nif os.environ.get("X_DISABLE") == "1":\n    pass\n'
        assert find_bypass_envs(src) == ["X_DISABLE"]

    def test_removed_bypass_is_detected(self):
        src = "import os\ndef main():\n    return 0\n"
        assert find_bypass_envs(src) == []

    def test_constant_never_read_does_not_count(self):
        src = 'import os\n_BYPASS_ENV = "X_BYPASS"\ndef main():\n    return 0\n'
        assert find_bypass_envs(src) == []

    def test_unrelated_env_does_not_count(self):
        src = 'import os\nif os.environ.get("CLAUDE_HOOKS_DEBUG"):\n    pass\n'
        assert find_bypass_envs(src) == []
