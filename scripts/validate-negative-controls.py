#!/usr/bin/env python3
"""Validate that every hard CI gate has at least one test proving it can fail.

A "hard gate" is a `scripts/validate-*.py` or `scripts/check-*.py` invocation
in `.github/workflows/test.yml` whose step has no `continue-on-error: true`
and whose `run:` command has no trailing `|| true`.

A "negative test" is any test in `scripts/tests/test_<name>*.py` that asserts
a non-zero exit code or a SystemExit with a non-zero code.

Exit codes:
  0 — all hard gates have negative tests, no stale allowlist entries.
  1 — at least one hard gate lacks a negative test, or a stale allowlist entry exists.
"""

from __future__ import annotations

import argparse
import ast
import json
import re
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent

# Validator/check scripts plus generators used as strict ``--check`` gates.
_SCRIPT_RE = re.compile(r"\b((?:validate|check|generate)[-_][\w-]+\.py)\b")


# ---------------------------------------------------------------------------
# Workflow parsing
# ---------------------------------------------------------------------------


def _parse_workflow(workflow_path: Path) -> list[dict]:
    """Parse the GitHub Actions workflow and return gate metadata.

    Each item: {script, hard: bool, job_name, step_name}.
    """
    import yaml

    text = workflow_path.read_text(encoding="utf-8")
    data = yaml.safe_load(text)
    if not isinstance(data, dict):
        return []

    gates: list[dict] = []
    jobs = data.get("jobs", {})
    if not isinstance(jobs, dict):
        return []

    for job_name, job_def in jobs.items():
        if not isinstance(job_def, dict):
            continue
        job_coe = job_def.get("continue-on-error", False)

        steps = job_def.get("steps", [])
        if not isinstance(steps, list):
            continue

        for step in steps:
            if not isinstance(step, dict):
                continue
            run_cmd = step.get("run", "")
            if not isinstance(run_cmd, str):
                continue

            matches = _SCRIPT_RE.findall(run_cmd)
            matches = [m for m in matches if not m.startswith(("generate-", "generate_")) or "--check" in run_cmd]
            if not matches:
                continue

            step_coe = step.get("continue-on-error", False)
            has_or_true = run_cmd.rstrip().endswith("|| true")

            is_advisory = bool(job_coe) or bool(step_coe) or has_or_true

            step_name = step.get("name", "")

            for script in matches:
                gates.append(
                    {
                        "script": script,
                        "hard": not is_advisory,
                        "job_name": job_name,
                        "step_name": step_name,
                    }
                )

    return gates


# ---------------------------------------------------------------------------
# Test file analysis (AST-based)
# ---------------------------------------------------------------------------


def _has_negative_test(test_path: Path, script_name: str) -> bool:
    """Return True if the test file contains at least one assertion of non-zero exit.

    Detected patterns (conservative — false negatives OK, false positives NOT):
      - `assert ... returncode == 1`
      - `assert ... returncode != 0`
      - `assert rc == 1` / `assert rc != 0`
      - `pytest.raises(SystemExit, match="<non-zero code>")`

    A comparison counts only when it is the condition of an ``assert``. Bare
    comparisons in helper logic do not prove anything, and an unconstrained
    ``pytest.raises(SystemExit)`` can accept ``SystemExit(0)``.
    """
    try:
        source = test_path.read_text(encoding="utf-8")
        tree = ast.parse(source, filename=str(test_path))
    except (OSError, SyntaxError):
        return False

    target_names = _target_path_names(tree, script_name)
    target_modules = _target_module_names(tree, script_name)
    target_helpers = _target_helper_returns(tree, script_name, target_names, target_modules)

    for test in (n for n in ast.walk(tree) if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))):
        if not test.name.startswith("test_") or _is_skipped_test(test):
            continue
        local_targets = _local_target_path_names(test, script_name, target_names)
        executed: set[str] = set()
        for node in ast.walk(test):
            if isinstance(node, (ast.Assign, ast.AnnAssign)):
                value = node.value
                targets = node.targets if isinstance(node, ast.Assign) else [node.target]
                target_call = value if isinstance(value, ast.Call) else None
                is_attr_rc = (
                    isinstance(value, ast.Attribute)
                    and value.attr == "returncode"
                    and isinstance(value.value, ast.Call)
                )
                if is_attr_rc:
                    target_call = value.value
                if target_call is not None and _call_executes_target(
                    target_call, script_name, local_targets, target_modules
                ):
                    executed.update(t.id for t in targets if isinstance(t, ast.Name))
                elif (
                    target_call is not None
                    and isinstance(target_call.func, ast.Name)
                    and target_call.func.id in target_helpers
                ):
                    kind = target_helpers[target_call.func.id]
                    if kind in {"proc", "rc"} or (is_attr_rc and kind == "proc"):
                        executed.update(t.id for t in targets if isinstance(t, ast.Name))
                    elif isinstance(kind, tuple) and not is_attr_rc:
                        _, idx = kind
                        for t in targets:
                            if isinstance(t, (ast.Tuple, ast.List)) and idx < len(t.elts):
                                elem = t.elts[idx]
                                if isinstance(elem, ast.Name):
                                    executed.add(elem.id)

        for node in ast.walk(test):
            if isinstance(node, ast.Assert) and isinstance(node.test, ast.Compare):
                if _is_negative_returncode_compare(
                    node.test,
                    executed,
                    script_name=script_name,
                    target_names=local_targets,
                    target_modules=target_modules,
                    target_helpers=target_helpers,
                ):
                    return True

            if isinstance(node, ast.With):
                for item in node.items:
                    if not isinstance(item.context_expr, ast.Call):
                        continue
                    if not _is_pytest_raises_nonzero_systemexit(item.context_expr):
                        continue
                    if any(
                        isinstance(child, ast.Call)
                        and (
                            _call_executes_target(child, script_name, local_targets, target_modules)
                            or (isinstance(child.func, ast.Name) and child.func.id in target_helpers)
                        )
                        for stmt in node.body
                        for child in ast.walk(stmt)
                    ):
                        return True

    return False


def _is_skipped_test(node: ast.FunctionDef | ast.AsyncFunctionDef) -> bool:
    """Return True for skip/xfail-decorated tests or tests calling pytest.skip."""
    decorators = " ".join(ast.unparse(d) for d in node.decorator_list)
    if "skip" in decorators or "xfail" in decorators:
        return True
    return any(
        isinstance(child, ast.Call)
        and isinstance(child.func, ast.Attribute)
        and isinstance(child.func.value, ast.Name)
        and child.func.value.id == "pytest"
        and child.func.attr == "skip"
        for child in ast.walk(node)
    )


def _collect_target_path_names(stmts: list[ast.stmt], script_name: str, seed: set[str] | None = None) -> set[str]:
    """Return variables assigned a static path (or alias) to the exact target script."""
    names: set[str] = set(seed) if seed else set()
    aliases: list[tuple[str, str]] = []
    for node in stmts:
        if not isinstance(node, (ast.Assign, ast.AnnAssign)):
            continue
        value = node.value
        if value is None:
            continue
        targets = node.targets if isinstance(node, ast.Assign) else [node.target]
        target_ids = [target.id for target in targets if isinstance(target, ast.Name)]
        if not target_ids:
            continue
        if _static_path_tail(value) == script_name:
            names.update(target_ids)
        elif isinstance(value, ast.Name):
            for tid in target_ids:
                aliases.append((tid, value.id))

    changed = True
    while changed:
        changed = False
        for tid, src in aliases:
            if src in names and tid not in names:
                names.add(tid)
                changed = True
    return names


def _target_path_names(tree: ast.AST, script_name: str) -> set[str]:
    """Return module-level variables statically assigned a path to the exact target script."""
    return _collect_target_path_names(list(getattr(tree, "body", [])), script_name)


def _local_target_path_names(
    func: ast.FunctionDef | ast.AsyncFunctionDef,
    script_name: str,
    module_names: set[str],
) -> set[str]:
    """Return module and function-local variables bound to the target script path."""
    return _collect_target_path_names(list(func.body), script_name, seed=module_names)


def _helper_expr_kind(
    expr: ast.AST,
    script_name: str,
    local_targets: set[str],
    target_modules: set[str],
    proc_vars: set[str],
    rc_vars: set[str],
) -> str | None:
    """Classify a return expression inside a helper as returning a proc or returncode."""
    if isinstance(expr, ast.Call) and _call_executes_target(expr, script_name, local_targets, target_modules):
        return "proc"
    if isinstance(expr, ast.Name):
        if expr.id in proc_vars:
            return "proc"
        if expr.id in rc_vars:
            return "rc"
    if isinstance(expr, ast.Attribute) and expr.attr == "returncode":
        if (
            isinstance(expr.value, ast.Call)
            and _call_executes_target(expr.value, script_name, local_targets, target_modules)
        ) or (isinstance(expr.value, ast.Name) and expr.value.id in proc_vars):
            return "rc"
    return None


def _target_helper_returns(
    tree: ast.AST,
    script_name: str,
    target_names: set[str],
    target_modules: set[str],
) -> dict[str, str | tuple[str, int]]:
    """Find single-hop module-local helper functions that execute the target script.

    Returns a mapping from helper function name to its return shape:
      - ``"proc"``: returns the ``subprocess.CompletedProcess`` from executing the target
      - ``"rc"``: returns ``.returncode`` directly
      - ``("tuple_rc", idx)``: returns a tuple whose element ``idx`` is ``.returncode``
      - ``("tuple_proc", idx)``: returns a tuple whose element ``idx`` is the process result
    """
    helpers: dict[str, str | tuple[str, int]] = {}
    for node in getattr(tree, "body", []):
        if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        if node.name.startswith("test_"):
            continue
        local_targets = _local_target_path_names(node, script_name, target_names)
        proc_vars: set[str] = set()
        rc_vars: set[str] = set()

        for stmt in ast.walk(node):
            if isinstance(stmt, (ast.Assign, ast.AnnAssign)) and stmt.value is not None:
                val = stmt.value
                targets = stmt.targets if isinstance(stmt, ast.Assign) else [stmt.target]
                target_ids = [t.id for t in targets if isinstance(t, ast.Name)]
                if not target_ids:
                    continue
                if isinstance(val, ast.Call) and _call_executes_target(val, script_name, local_targets, target_modules):
                    proc_vars.update(target_ids)
                elif isinstance(val, ast.Attribute) and val.attr == "returncode":
                    if (
                        isinstance(val.value, ast.Call)
                        and _call_executes_target(val.value, script_name, local_targets, target_modules)
                    ) or (isinstance(val.value, ast.Name) and val.value.id in proc_vars):
                        rc_vars.update(target_ids)

        for stmt in ast.walk(node):
            if not isinstance(stmt, ast.Return) or stmt.value is None:
                continue
            direct = _helper_expr_kind(stmt.value, script_name, local_targets, target_modules, proc_vars, rc_vars)
            if direct is not None:
                helpers[node.name] = direct
                break
            if isinstance(stmt.value, ast.Tuple):
                for idx, elt in enumerate(stmt.value.elts):
                    ek = _helper_expr_kind(elt, script_name, local_targets, target_modules, proc_vars, rc_vars)
                    if ek == "rc":
                        helpers[node.name] = ("tuple_rc", idx)
                        break
                    if ek == "proc":
                        helpers[node.name] = ("tuple_proc", idx)
                        break
                if node.name in helpers:
                    break

    return helpers


def _static_path_tail(node: ast.AST) -> str | None:
    """Return the exact basename contributed by a static path expression's tail."""
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        return Path(node.value).name
    if isinstance(node, ast.BinOp) and isinstance(node.op, ast.Div):
        return _static_path_tail(node.right) or _static_path_tail(node.left)
    if isinstance(node, ast.Call) and node.args:
        return _static_path_tail(node.args[-1])
    return None


def _target_module_names(tree: ast.AST, script_name: str) -> set[str]:
    """Return aliases that import the exact target module."""
    module_name = script_name.removesuffix(".py").replace("-", "_")
    names: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                if alias.name == module_name:
                    names.add(alias.asname or alias.name)
    return names


def _call_executes_target(
    node: ast.Call,
    script_name: str,
    target_names: set[str],
    target_modules: set[str],
) -> bool:
    """Return True only for a real subprocess execution of the target script."""
    func = node.func
    if (
        isinstance(func, ast.Attribute)
        and isinstance(func.value, ast.Name)
        and func.value.id in target_modules
        and func.attr == "main"
    ):
        return True
    is_subprocess_run = (
        isinstance(func, ast.Attribute)
        and isinstance(func.value, ast.Name)
        and func.value.id == "subprocess"
        and func.attr == "run"
    )
    if not is_subprocess_run:
        return False

    if not node.args or not isinstance(node.args[0], (ast.List, ast.Tuple)):
        return False
    argv = node.args[0].elts
    if not argv:
        return False
    script_pos = 1 if _is_python_interpreter_operand(argv[0]) else 0
    if script_pos >= len(argv):
        return False
    return _is_exact_script_operand(argv[script_pos], script_name, target_names)


def _is_python_interpreter_operand(node: ast.AST) -> bool:
    """Recognize only explicit Python interpreter argv operands."""
    if (
        isinstance(node, ast.Attribute)
        and isinstance(node.value, ast.Name)
        and node.value.id == "sys"
        and node.attr == "executable"
    ):
        return True
    return (
        isinstance(node, ast.Constant)
        and isinstance(node.value, str)
        and Path(node.value).name in {"python", "python3"}
    )


def _is_exact_script_operand(node: ast.AST, script_name: str, target_names: set[str]) -> bool:
    """Match only the argv element executed as the script, by exact basename."""
    if isinstance(node, ast.Name):
        return node.id in target_names
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        return Path(node.value).name == script_name
    if (
        isinstance(node, ast.Call)
        and isinstance(node.func, ast.Name)
        and node.func.id in {"str", "Path"}
        and len(node.args) == 1
    ):
        return _is_exact_script_operand(node.args[0], script_name, target_names)
    return False


def _is_pytest_raises_nonzero_systemexit(node: ast.Call) -> bool:
    """Check for ``pytest.raises(SystemExit, match=...)`` with a non-zero code."""
    func = node.func
    if isinstance(func, ast.Attribute) and func.attr == "raises":
        if isinstance(func.value, ast.Name) and func.value.id == "pytest":
            if not any(isinstance(arg, ast.Name) and arg.id == "SystemExit" for arg in node.args):
                return False
            for keyword in node.keywords:
                if keyword.arg != "match":
                    continue
                if not isinstance(keyword.value, ast.Constant) or not isinstance(keyword.value.value, str):
                    return False
                return bool(re.search(r"[1-9]", keyword.value.value))
    return False


def _is_negative_returncode_compare(
    node: ast.Compare,
    executed: set[str],
    *,
    script_name: str = "",
    target_names: set[str] | None = None,
    target_modules: set[str] | None = None,
    target_helpers: dict[str, str | tuple[str, int]] | None = None,
) -> bool:
    """Check if a Compare node asserts a non-zero exit code.

    Matches:
      - <expr>.returncode == 1  (or any non-zero int)
      - <expr>.returncode != 0
      - <expr>.returncode > 0 / >= 1
      - rc == 1 / rc != 0 / rc > 0 (where rc is bound to an executed target)
    """
    # We check left and comparators for returncode-shaped expressions.
    left = node.left
    for op, comparator in zip(node.ops, node.comparators):
        if _is_returncode_nonzero(
            left,
            op,
            comparator,
            executed,
            script_name=script_name,
            target_names=target_names,
            target_modules=target_modules,
            target_helpers=target_helpers,
        ):
            return True
        # Reversed comparison: `1 == result.returncode` or `0 < result.returncode`
        if _is_returncode_nonzero(
            comparator,
            _flip_op(op),
            left,
            executed,
            script_name=script_name,
            target_names=target_names,
            target_modules=target_modules,
            target_helpers=target_helpers,
        ):
            return True
    return False


def _is_returncode_attr_or_rc_name(
    node: ast.AST,
    executed: set[str],
    *,
    script_name: str = "",
    target_names: set[str] | None = None,
    target_modules: set[str] | None = None,
    target_helpers: dict[str, str | tuple[str, int]] | None = None,
) -> bool:
    """True if node is `<executed>.returncode`, `<call>.returncode`, or an executed Name."""
    if isinstance(node, ast.Attribute) and node.attr == "returncode":
        if isinstance(node.value, ast.Name) and node.value.id in executed:
            return True
        if isinstance(node.value, ast.Call):
            if script_name and _call_executes_target(
                node.value, script_name, target_names or set(), target_modules or set()
            ):
                return True
            if (
                target_helpers
                and isinstance(node.value.func, ast.Name)
                and target_helpers.get(node.value.func.id) == "proc"
            ):
                return True
        return False
    if isinstance(node, ast.Name) and node.id in executed:
        return True
    if (
        isinstance(node, ast.Call)
        and target_helpers
        and isinstance(node.func, ast.Name)
        and target_helpers.get(node.func.id) == "rc"
    ):
        return True
    return False


def _is_returncode_nonzero(
    left: ast.AST,
    op: ast.cmpop,
    right: ast.AST,
    executed: set[str],
    *,
    script_name: str = "",
    target_names: set[str] | None = None,
    target_modules: set[str] | None = None,
    target_helpers: dict[str, str | tuple[str, int]] | None = None,
) -> bool:
    """True if `left <op> right` asserts a non-zero exit code."""
    if not _is_returncode_attr_or_rc_name(
        left,
        executed,
        script_name=script_name,
        target_names=target_names,
        target_modules=target_modules,
        target_helpers=target_helpers,
    ):
        return False

    if not isinstance(right, ast.Constant) or not isinstance(right.value, int) or isinstance(right.value, bool):
        return False

    value = right.value

    # returncode == <non-zero>
    if isinstance(op, ast.Eq) and value != 0:
        return True
    # returncode != 0
    if isinstance(op, ast.NotEq) and value == 0:
        return True
    # returncode > 0 or returncode >= 1
    if (isinstance(op, ast.Gt) and value >= 0) or (isinstance(op, ast.GtE) and value >= 1):
        return True

    return False


def _flip_op(op: ast.cmpop) -> ast.cmpop:
    """Flip a comparison operator for reversed comparisons."""
    flips: dict[type, type] = {
        ast.Eq: ast.Eq,
        ast.NotEq: ast.NotEq,
        ast.Lt: ast.Gt,
        ast.Gt: ast.Lt,
        ast.LtE: ast.GtE,
        ast.GtE: ast.LtE,
    }
    return flips.get(type(op), type(op))()


# ---------------------------------------------------------------------------
# Allowlist
# ---------------------------------------------------------------------------


def _parse_allowlist(path: Path) -> dict[str, str]:
    """Parse `script-name.py: reason` lines. Returns {script: reason}."""
    out: dict[str, str] = {}
    if not path.exists():
        return out
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        if ":" in line:
            name, reason = line.split(":", 1)
            name, reason = name.strip(), reason.strip()
            if name:
                out[name] = reason
    return out


# ---------------------------------------------------------------------------
# Locate test files
# ---------------------------------------------------------------------------


def _find_test_files(script_name: str, tests_dir: Path) -> list[Path]:
    """Find test files matching a script name.

    validate-foo.py -> test_validate_foo*.py
    check-bar.py    -> test_check_bar*.py
    """
    stem = script_name.removesuffix(".py")
    test_prefix = "test_" + stem.replace("-", "_")
    results: list[Path] = []
    if tests_dir.is_dir():
        for p in tests_dir.iterdir():
            if p.name.startswith(test_prefix) and p.suffix == ".py":
                results.append(p)
    return results


# ---------------------------------------------------------------------------
# Core validation
# ---------------------------------------------------------------------------


def validate(
    workflow_path: Path,
    tests_dir: Path,
    allowlist_path: Path,
    *,
    strict: bool = False,
) -> tuple[list[dict], list[dict]]:
    """Run the validation. Returns (gates, findings).

    Each gate: {script, hard, job_name, step_name, has_test_file, has_negative_test}.
    Each finding: {script, kind, message}.
    """
    gates = _parse_workflow(workflow_path)
    allowlist = _parse_allowlist(allowlist_path)
    findings: list[dict] = []

    # Deduplicate gates by script name (same script may appear in multiple steps).
    seen: set[str] = set()
    deduped: list[dict] = []
    for g in gates:
        if g["script"] not in seen:
            seen.add(g["script"])
            deduped.append(g)
        else:
            # If any invocation is hard, the gate is hard.
            for d in deduped:
                if d["script"] == g["script"] and g["hard"]:
                    d["hard"] = True

    for g in deduped:
        test_files = _find_test_files(g["script"], tests_dir)
        g["has_test_file"] = len(test_files) > 0
        g["has_negative_test"] = any(_has_negative_test(tf, g["script"]) for tf in test_files)
        g["allowlisted"] = g["script"] in allowlist and not strict

    # Check hard gates without negative tests.
    for g in deduped:
        if not g["hard"]:
            continue
        if g["has_negative_test"]:
            continue
        if g["script"] in allowlist and not strict:
            continue
        kind = "missing-test-file" if not g["has_test_file"] else "no-negative-test"
        findings.append(
            {
                "script": g["script"],
                "kind": kind,
                "message": (
                    f"{g['script']}: hard gate has no test proving it can fail"
                    if kind == "no-negative-test"
                    else f"{g['script']}: hard gate has no test file"
                ),
            }
        )

    # Check stale allowlist entries.
    gate_scripts = {g["script"] for g in deduped}
    for script, reason in allowlist.items():
        # Stale if: script is no longer in CI.
        if script not in gate_scripts:
            findings.append(
                {
                    "script": script,
                    "kind": "stale-allowlist-not-in-ci",
                    "message": f"{script}: allowlisted but no longer in CI — remove from allowlist",
                }
            )
            continue
        # Stale if: script now has a negative test.
        for g in deduped:
            if g["script"] == script and g["has_negative_test"]:
                findings.append(
                    {
                        "script": script,
                        "kind": "stale-allowlist-has-test",
                        "message": f"{script}: allowlisted but now has a negative test — remove from allowlist",
                    }
                )
                break

    return deduped, findings


# ---------------------------------------------------------------------------
# Output
# ---------------------------------------------------------------------------


def _print_table(gates: list[dict], findings: list[dict]) -> None:
    """Print a human-readable results table."""
    print(f"{'Script':<45} {'Type':<10} {'Test File':<10} {'Neg Test':<10} {'Status'}")
    print("-" * 95)

    for g in sorted(gates, key=lambda x: x["script"]):
        gate_type = "hard" if g["hard"] else "advisory"
        has_file = "yes" if g.get("has_test_file") else "no"
        has_neg = "yes" if g.get("has_negative_test") else "no"

        if not g["hard"]:
            status = "skip (advisory)"
        elif g.get("has_negative_test"):
            status = "OK"
        elif g.get("allowlisted"):
            status = "allowlisted"
        else:
            status = "FAIL"

        print(f"{g['script']:<45} {gate_type:<10} {has_file:<10} {has_neg:<10} {status}")

    print()
    if findings:
        print(f"{len(findings)} finding(s):")
        for f in findings:
            print(f"  {f['kind']}: {f['message']}")
    else:
        print("0 finding(s): every hard gate has a negative test or an explicit allowlist entry.")


def _print_json(gates: list[dict], findings: list[dict]) -> None:
    """Print JSON output."""
    output = {
        "gates": gates,
        "findings": findings,
        "pass": len(findings) == 0,
    }
    print(json.dumps(output, indent=2))


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def main() -> int:
    """Validate that every hard CI gate has a negative test.

    Returns:
        0 if all hard gates pass, 1 if any finding exists.
    """
    parser = argparse.ArgumentParser(
        description="Validate that every hard CI gate has at least one test proving it can fail."
    )
    parser.add_argument(
        "--workflow",
        type=Path,
        default=None,
        help="Path to GitHub Actions workflow (default: .github/workflows/test.yml)",
    )
    parser.add_argument(
        "--tests-dir",
        type=Path,
        default=None,
        help="Path to tests directory (default: scripts/tests)",
    )
    parser.add_argument(
        "--allowlist",
        type=Path,
        default=None,
        help="Path to allowlist file (default: scripts/negative-control-allowlist.txt)",
    )
    parser.add_argument(
        "--repo-root",
        type=Path,
        default=None,
        help="Repository root (default: parent of scripts/)",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        dest="json_output",
        help="Output JSON instead of human-readable table",
    )
    parser.add_argument(
        "--strict",
        action="store_true",
        help="Treat allowlisted debt as findings (promotion target mode).",
    )
    args = parser.parse_args()

    repo_root = args.repo_root or REPO_ROOT
    workflow = args.workflow or (repo_root / ".github" / "workflows" / "test.yml")
    tests_dir = args.tests_dir or (repo_root / "scripts" / "tests")
    allowlist = args.allowlist or (repo_root / "scripts" / "negative-control-allowlist.txt")

    if not workflow.exists():
        print(f"ERROR: workflow not found: {workflow}", file=sys.stderr)
        return 1

    gates, findings = validate(workflow, tests_dir, allowlist, strict=args.strict)

    if args.json_output:
        _print_json(gates, findings)
    else:
        _print_table(gates, findings)

    return 1 if findings else 0


if __name__ == "__main__":
    sys.exit(main())
