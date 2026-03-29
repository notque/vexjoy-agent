#!/usr/bin/env python3
"""Generate blind A/B comparison HTML from eval workspace data.

Scans workspace, collects output files, runs deterministic checks
(go build, go vet, go test -race where applicable), loads grading
and blind comparison data, injects into compare.html template.
Outputs compare_report.html.

Usage:
    python3 eval_compare.py <workspace_dir>
    python3 eval_compare.py --help
"""

import argparse
import json
import os
import subprocess
import sys
from pathlib import Path


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        description="Generate blind A/B comparison HTML from eval workspace data.",
        epilog="Workspace must contain compare.html template and iteration-*/ directories.",
    )
    p.add_argument("workspace", type=Path, help="Path to the eval workspace directory")
    p.add_argument(
        "--output", type=Path, default=None, help="Output HTML path (default: <workspace>/compare_report.html)"
    )
    return p


def load_json_safe(path: Path) -> dict | None:
    """Load JSON from a file, returning None on any error."""
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError, UnicodeDecodeError) as e:
        print(f"WARNING: Could not load {path}: {e}", file=sys.stderr)
        return None


def read_text_safe(path: Path) -> str:
    """Read text file with encoding fallback."""
    try:
        return path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return ""


def find_files(outputs_dir: Path) -> list[str]:
    """List all files relative to outputs dir."""
    files = []
    for root, _, filenames in os.walk(outputs_dir):
        for f in filenames:
            rel = os.path.relpath(Path(root, f), outputs_dir)
            files.append(rel)
    return sorted(files)


def count_go_lines(outputs_dir: Path) -> int:
    """Count total lines across all .go files."""
    total = 0
    for root, _, filenames in os.walk(outputs_dir):
        for f in filenames:
            if f.endswith(".go"):
                content = read_text_safe(Path(root, f))
                total += len(content.splitlines())
    return total


def get_code_preview(outputs_dir: Path, max_lines: int = 60) -> str:
    """Get preview of main .go file content."""
    for root, _, filenames in os.walk(outputs_dir):
        for f in sorted(filenames):
            if f.endswith(".go") and not f.endswith("_test.go"):
                content = read_text_safe(Path(root, f))
                lines = content.splitlines()
                if len(lines) > max_lines:
                    return "\n".join(lines[:max_lines]) + f"\n... ({len(lines) - max_lines} more lines)"
                return content
    return ""


def run_go_check(outputs_dir: Path, cmd: list[str], timeout: int = 30) -> str:
    """Run a go command in the outputs directory, return 'yes'/'no'/'clean'/'issues'."""
    # Find the go module root (prefer directory with go.mod)
    mod_root = None
    go_dirs = []
    for root, _, files in os.walk(outputs_dir):
        if "go.mod" in files:
            mod_root = root
            break
        if any(f.endswith(".go") for f in files):
            go_dirs.append(root)

    target = mod_root or (go_dirs[0] if go_dirs else None)
    if target is None:
        return "no_go_files"

    try:
        result = subprocess.run(cmd, cwd=target, capture_output=True, text=True, timeout=timeout)
        if result.returncode == 0:
            return "yes" if "build" in cmd or "test" in cmd else "clean"
        return "no" if "build" in cmd or "test" in cmd else "issues"
    except (subprocess.TimeoutExpired, FileNotFoundError):
        return "skip"


def load_grading(variant_dir: Path) -> dict | None:
    """Load and normalize grading.json."""
    path = variant_dir / "grading.json"
    if not path.exists():
        return None
    raw = load_json_safe(path)
    if raw is None:
        return None
    exps = raw.get("expectations", raw.get("assertions", []))
    normalized = []
    for e in exps:
        text = e.get("text", e.get("assertion", "?"))
        is_pass = e.get("passed") is True or e.get("verdict", "") == "PASS"
        evidence = e.get("evidence", "")
        normalized.append({"text": text, "passed": is_pass, "evidence": evidence})
    passed = sum(1 for n in normalized if n["passed"])
    tl = raw.get("pass_count")
    if tl is not None:
        passed = tl
    total = len(normalized)
    return {
        "expectations": normalized,
        "summary": {
            "passed": passed,
            "failed": total - passed,
            "total": total,
            "pass_rate": round(passed / total, 3) if total > 0 else 0,
        },
    }


def build_variant_data(variant_dir: Path) -> dict:
    """Build data dict for one variant."""
    outputs = variant_dir / "outputs"
    if not outputs.exists():
        return {}
    files = find_files(outputs)
    return {
        "lines": count_go_lines(outputs),
        "files": files,
        "fileCount": len(files),
        "code_preview": get_code_preview(outputs),
        "compiles": run_go_check(outputs, ["go", "build", "./..."]),
        "tests_pass": run_go_check(outputs, ["go", "test", "-race", "-count=1", "./..."]),
        "govet": run_go_check(outputs, ["go", "vet", "./..."]),
        "grading": load_grading(variant_dir),
    }


def find_iteration_dirs(workspace: Path) -> list[Path]:
    """Find all iteration-N directories, sorted by number."""
    dirs = sorted(workspace.glob("iteration-*"))
    return [d for d in dirs if d.is_dir()]


def load_optimization_data(workspace: Path) -> dict | None:
    """Load optimization loop results when present in the workspace."""
    def looks_like_optimization_results(data: dict) -> bool:
        return isinstance(data, dict) and "iterations" in data and "baseline_score" in data and "target" in data

    candidates = [
        workspace / "results.json",
        workspace / "evals" / "iterations" / "results.json",
        workspace / "out" / "results.json",
    ]
    for path in candidates:
        if path.exists():
            data = load_json_safe(path)
            if data is not None and looks_like_optimization_results(data):
                return data
    return None


def build_data(workspace: Path) -> dict:
    """Build full comparison data."""
    evals_path = workspace / "evals" / "evals.json"
    evals_meta = {}
    evals_raw = None
    if evals_path.exists():
        evals_raw = load_json_safe(evals_path)
        if evals_raw:
            for ev in evals_raw.get("evals", []):
                evals_meta[ev.get("name", ev.get("id", ""))] = ev

    evals_data = []
    benchmark = []

    # Use the latest iteration directory (or iteration-1 as fallback)
    iterations = find_iteration_dirs(workspace)
    if not iterations:
        return {
            "evals": [],
            "benchmark": [],
            "variantAName": "Variant A",
            "variantBName": "Variant B",
            "variantCName": "Variant C",
            "optimization": load_optimization_data(workspace),
        }

    iteration = iterations[-1]  # Latest iteration

    for eval_dir in sorted(iteration.iterdir()):
        if not eval_dir.is_dir():
            continue
        name = eval_dir.name
        a_data = build_variant_data(eval_dir / "variant-A")
        b_data = build_variant_data(eval_dir / "variant-B")
        c_data = build_variant_data(eval_dir / "variant-C")

        prompt = evals_meta.get(name, {}).get("prompt", "")

        # Load blind comparisons if available
        blind = (
            load_json_safe(eval_dir / "blind_comparison.json")
            if (eval_dir / "blind_comparison.json").exists()
            else None
        )
        blind_bc = (
            load_json_safe(eval_dir / "blind_comparison_bc.json")
            if (eval_dir / "blind_comparison_bc.json").exists()
            else None
        )

        eval_entry = {
            "name": name,
            "prompt": prompt,
            "variantA": a_data,
            "variantB": b_data,
            "blind_comparison": blind,
            "blind_comparison_bc": blind_bc,
        }
        if c_data:
            eval_entry["variantC"] = c_data
        evals_data.append(eval_entry)

        a_rate = a_data.get("grading", {}).get("summary", {}).get("pass_rate", 0) if a_data.get("grading") else 0
        b_rate = b_data.get("grading", {}).get("summary", {}).get("pass_rate", 0) if b_data.get("grading") else 0
        c_rate = c_data.get("grading", {}).get("summary", {}).get("pass_rate", 0) if c_data.get("grading") else 0
        bm = {"name": name, "aRate": a_rate, "bRate": b_rate}
        if c_data:
            bm["cRate"] = c_rate
        benchmark.append(bm)

    variants = evals_raw.get("variants", {}) if evals_raw else {}

    return {
        "evals": evals_data,
        "benchmark": benchmark,
        "variantAName": variants.get("A", {}).get("name", "Variant A"),
        "variantBName": variants.get("B", {}).get("name", "Variant B"),
        "variantCName": variants.get("C", {}).get("name", "Variant C"),
        "optimization": load_optimization_data(workspace),
    }


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()

    workspace = args.workspace.resolve()
    template = workspace / "compare.html"
    output = (args.output or workspace / "compare_report.html").resolve()

    if not template.exists():
        print(f"Error: {template} not found", file=sys.stderr)
        return 1

    data = build_data(workspace)
    html = read_text_safe(template).replace("__DATA_PLACEHOLDER__", json.dumps(data, indent=2))
    output.write_text(html, encoding="utf-8")

    print(f"Report: {output}")
    print(f"Evals: {len(data['evals'])}")
    for ev in data["evals"]:
        a = ev.get("variantA", {})
        b = ev.get("variantB", {})
        print(
            f"  {ev['name']}: A={a.get('lines', 0)}L/{a.get('compiles', '?')} B={b.get('lines', 0)}L/{b.get('compiles', '?')}"
        )

    return 0


if __name__ == "__main__":
    sys.exit(main())
