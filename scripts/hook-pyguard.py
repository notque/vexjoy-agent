#!/usr/bin/env python3
"""Stamp a Python version guard at the top of every registered hook.

Hooks use 3.10-only runtime syntax (``X | None`` annotations). Under 3.9 they
crash at import with exit 1, and Claude Code blocks only on exit 2, so a
safety gate would fail open without a word. The guard runs before any other
import and parses and runs on 3.8+. Under <3.10 it first re-execs the hook
under the newest ``python3.1x`` it finds on PATH, ``/opt/homebrew/bin``,
``/usr/local/bin``, or ``/usr/bin`` (shim dirs skipped; once per run, via
``VEXJOY_PYGUARD_REEXEC``). That keeps sessions working during an upgrade
whose settings still say bare ``python3``, and lets the SessionStart sync
repair the interpreter link. When none is found it decides:

| mode     | hooks                                    | under <3.10                         |
|----------|------------------------------------------|-------------------------------------|
| gate     | ``GATES``: PreToolUse hooks that deny    | exit 2 + one-line message           |
| advisory | every other registered hook              | exit 0 + one-line stderr warning    |
| adapter  | ``codex-hook-adapter.py``                | exit 2 when ``--failure-policy closed``, else exit 0 |

Stop and SubagentStop hooks stay advisory: exit 2 there makes the model keep
going, so a broken interpreter would trap every session or subagent in a loop.

Registered = repo ``.claude/settings.json`` + codex and reasonix allowlists
(files that exist) + the codex adapter.

Every guarded file must also parse with the 3.8 grammar, since a 3.10-only
construct (``match``) is a SyntaxError on 3.9 before the guard can run.

Usage:
    python3 scripts/hook-pyguard.py --check    # exit 1 when a hook lacks the right guard
    python3 scripts/hook-pyguard.py --apply    # stamp or restamp every registered hook
    python3 scripts/hook-pyguard.py --apply --file hooks/new-hook.py   # one hook, before registering it
"""

from __future__ import annotations

import argparse
import ast
import json
import re
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
HOOKS = REPO / "hooks"
SETTINGS = REPO / ".claude" / "settings.json"
ALLOWLISTS = (REPO / "scripts" / "codex-hooks-allowlist.txt", REPO / "scripts" / "reasonix-hooks-allowlist.txt")
ADAPTER = "codex-hook-adapter.py"
MARK = "# vexjoy-pyguard"
GATES = frozenset(
    {
        "ci-merge-gate.py",
        "pipeline-phase-gate.py",
        "pretool-adr-creation-gate.py",
        "pretool-branch-safety.py",
        "pretool-dispatch-spec-gate.py",
        "pretool-plan-gate.py",
        "pretool-private-name-leak-gate.py",
        "pretool-review-before-push-gate.py",
        "pretool-ruff-format-gate.py",
        "pretool-synthesis-gate.py",
        "pretool-unified-gate.py",
        "pretool-worktree-edit-guard.py",
        "security-review-hook.py",
    }
)
_HOOK_RE = re.compile(r"hooks/([A-Za-z0-9._-]+\.py)")
_ALLOW_RE = re.compile(r"^[A-Za-z]+:([A-Za-z0-9._-]+\.py)\b")
_EXIT = {
    "gate": "    sys.exit(2)\n",
    "advisory": "    sys.exit(0)\n",
    "adapter": (
        '    _a = sys.argv[sys.argv.index("--failure-policy") + 1 :] if "--failure-policy" in sys.argv else []\n'
        '    sys.exit(2 if _a[:1] == ["closed"] else 0)\n'
    ),
}


REEXEC_ENV = "VEXJOY_PYGUARD_REEXEC"


def guard_block(mode: str) -> str:
    """The guard text for *mode*; valid Python 3.8+ and stable under ruff format."""
    return (
        f"import sys  {MARK}\n"
        "\n"
        f"if sys.version_info < (3, 10):  {MARK} {mode}\n"
        "    import os\n"
        "\n"
        f'    if not os.environ.get("{REEXEC_ENV}"):\n'
        f'        os.environ["{REEXEC_ENV}"] = "1"\n'
        '        for _d in [*os.environ.get("PATH", "").split(os.pathsep), "/opt/homebrew/bin", "/usr/local/bin", "/usr/bin"]:\n'
        '            for _v in ("14", "13", "12", "11", "10"):\n'
        '                _p = os.path.join(_d, "python3." + _v)\n'
        '                if _d and "/shims" not in _d and os.access(_p, os.X_OK):\n'
        "                    os.execv(_p, [_p, *sys.argv])\n"
        "    sys.stderr.write(\n"
        '        "[vexjoy] hook %s needs Python 3.10+, got %s (%s); run ./install.sh in vexjoy-agent from a terminal"\n'
        '        " outside Claude Code (gated tool calls stay blocked until then)\\n"\n'
        '        % (__file__.rsplit("/", 1)[-1], sys.version.split()[0], sys.executable)\n'
        "    )\n" + _EXIT[mode]
    )


def mode_for(name: str) -> str:
    """Guard mode for hook file *name*."""
    if name == ADAPTER:
        return "adapter"
    return "gate" if name in GATES else "advisory"


def registered() -> list[str]:
    """Every hook file name a runtime config names, sorted."""
    names: set[str] = {ADAPTER}
    try:
        names.update(_HOOK_RE.findall(SETTINGS.read_text(encoding="utf-8")))
    except OSError:
        pass
    for path in ALLOWLISTS:
        try:
            lines = path.read_text(encoding="utf-8").splitlines()
        except OSError:
            continue
        names.update(m.group(1) for line in lines if (m := _ALLOW_RE.match(line.strip())))
    return sorted(n for n in names if (HOOKS / n).is_file())


def _strip(text: str) -> str:
    lines = text.splitlines(keepends=True)
    for i, line in enumerate(lines):
        if line.rstrip("\n") == f"import sys  {MARK}":
            j = i + 1
            while j < len(lines) and not lines[j].startswith("    sys.exit("):
                j += 1
            end = j + 1
            if end < len(lines) and lines[end].strip() == "":
                end += 1
            return "".join(lines[:i] + lines[end:])
    return text


def _insert_at(text: str) -> int:
    """0-based line index after the docstring and ``from __future__`` imports."""
    tree = ast.parse(text)
    body = tree.body
    end = 0
    k = 0
    if body and isinstance(body[0], ast.Expr) and isinstance(getattr(body[0], "value", None), ast.Constant):
        if isinstance(body[0].value.value, str):
            end = body[0].end_lineno or 0
            k = 1
    while k < len(body) and isinstance(body[k], ast.ImportFrom) and body[k].module == "__future__":
        end = body[k].end_lineno or end
        k += 1
    if end == 0 and body:
        return body[0].lineno - 1
    return end


def stamp(text: str, mode: str) -> str:
    """*text* with exactly one guard of *mode* in place."""
    text = _strip(text)
    lines = text.splitlines(keepends=True)
    at = _insert_at(text)
    head = lines[:at]
    tail = lines[at:]
    while tail and tail[0].strip() == "":
        tail = tail[1:]
    if head and head[-1].strip() != "":
        head.append("\n")
    return "".join([*head, guard_block(mode), "\n", *tail]) if tail else "".join([*head, guard_block(mode)])


def problems(name: str, text: str) -> list[str]:
    """Why *text* (hook file *name*) is not correctly guarded; empty when it is."""
    mode = mode_for(name)
    block = guard_block(mode)
    if block not in text:
        found = re.search(rf"{re.escape(MARK)} (\w+)", text)
        return [f"{name}: guard {'mode ' + found.group(1) if found else 'missing'}, want {mode}"]
    try:
        tree = ast.parse(text, feature_version=(3, 8))
    except SyntaxError as exc:
        return [f"{name}: does not parse with the 3.8 grammar, so 3.9 fails before the guard: {exc}"]
    guard_line = text[: text.index(block)].count("\n") + 1
    for node in tree.body:
        if node.lineno >= guard_line:
            break
        if isinstance(node, ast.ImportFrom) and node.module == "__future__":
            continue
        if isinstance(node, ast.Expr) and isinstance(getattr(node, "value", None), ast.Constant):
            continue
        return [f"{name}: statement at line {node.lineno} runs before the guard"]
    return []


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--check", action="store_true")
    group.add_argument("--apply", action="store_true")
    parser.add_argument("--file", type=Path, action="append", help="hook file(s) instead of every registered hook")
    args = parser.parse_args(argv)
    bad: list[str] = []
    changed = 0
    paths = [p.resolve() for p in args.file] if args.file else [HOOKS / n for n in registered()]
    for path in paths:
        name = path.name
        text = path.read_text(encoding="utf-8")
        if args.apply:
            new = stamp(text, mode_for(name))
            if new != text:
                path.write_text(new, encoding="utf-8")
                changed += 1
            text = new
        bad.extend(problems(name, text))
    if args.apply:
        print(f"[hook-pyguard] {changed} file(s) stamped")
    for line in bad:
        print(f"[hook-pyguard] {line}", file=sys.stderr)
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
