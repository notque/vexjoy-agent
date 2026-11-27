#!/usr/bin/env python3
"""Route-time preflight for /d: which safety gates the planned paths will hit, and what each costs.

The gates (creation gate, ADR creation gate, consultation synthesis gate,
security review, private-name leak gate) fire mid-task, often at commit time
after the work is done. This script asks the same questions up front so the
cost shows while another approach is still cheap. It imports each hook's own
path rules read-only and runs the repo's deterministic security scanner; it
never edits a hook, never blocks, and prints redacted findings only.

Usage:
    python3 scripts/d-preflight.py --paths agents/README.md skills/meta/d/SKILL.md
    python3 scripts/d-preflight.py --paths-file planned.txt --json

Exit 0 always (advisory). Stdlib only.
"""

from __future__ import annotations

import argparse
import importlib.util
import json
import os
import subprocess
import sys
import time
from pathlib import Path
from types import ModuleType

sys.dont_write_bytecode = True  # importing the hooks must not leave __pycache__ behind

TIME_BUDGET_S = 20.0
SCRIPTS = Path(__file__).resolve().parent

COST_ADR = "write adr/{name}.md and run `python3 scripts/adr-query.py register --adr adr/{name}.md` before the Write"
COST_SYNTHESIS = (
    "with an ADR session active, every write under agents/ or skills/ needs adr/<adr-name>/synthesis.md with a "
    "PROCEED verdict: a 3-reviewer consultation (assessment skill, ADR Consultation)"
)


def toolkit_root(start: Path) -> Path | None:
    """The git top level of `start` when it holds skills/ and hooks/, else None."""
    try:
        top = subprocess.run(
            ["git", "-C", str(start), "rev-parse", "--show-toplevel"], capture_output=True, text=True, timeout=5
        ).stdout.strip()
    except (OSError, subprocess.SubprocessError):
        return None
    root = Path(top) if top else None
    return root if root and (root / "skills").is_dir() and (root / "hooks").is_dir() else None


def load_hook(name: str, roots: list[Path]) -> ModuleType | None:
    """Import one hook module read-only (its main() is guarded), from the first root that has it."""
    for root in roots:
        path = root / name
        if not path.is_file():
            continue
        try:
            spec = importlib.util.spec_from_file_location(f"preflight_{path.stem.replace('-', '_')}", path)
            module = importlib.util.module_from_spec(spec)
            sys.path.insert(0, str(path.parent))
            sys.path.insert(0, str(path.parent / "lib"))
            spec.loader.exec_module(module)
            return module
        except Exception:
            continue
        finally:
            for p in (str(path.parent / "lib"), str(path.parent)):
                if p in sys.path:
                    sys.path.remove(p)
    return None


def creation_costs(abs_path: str, gates: dict[str, ModuleType | None], base_dir: Path | None = None) -> list[str]:
    """Costs for a path that does not exist yet (creation) or sits in a consultation-gated dir."""
    costs: list[str] = []
    exists = os.path.exists(abs_path)
    norm_path = abs_path.replace("\\", "/")
    effective_base = (base_dir or Path.cwd()).resolve()

    unified = gates.get("unified")
    if unified is not None and not exists:
        is_component = any(
            getattr(unified, attr).search(norm_path)
            for attr in ("_AGENT_PATTERN", "_SKILL_PATTERN", "_WORKFLOW_REF_PATTERN")
            if hasattr(unified, attr)
        )
        allowed = any(p.search(norm_path) for p, _ in getattr(unified, "_CREATION_PATH_ALLOWLIST", []))
        if is_component and not allowed:
            name = unified._creation_component_name(abs_path) or Path(abs_path).stem
            costs.append(f"creation gate: new component '{name}': " + COST_ADR.format(name=name))

    adr = gates.get("adr")
    if adr is not None and not exists:
        adr_allowed = any(p.search(norm_path) for p, _ in getattr(adr, "_ADR_PATH_ALLOWLIST", []))
        if not adr_allowed:
            name = adr._extract_component_name(abs_path)
            if name and not any(name in c for c in costs):
                has_adr = False
                find_adr = getattr(adr, "_find_adr", None)
                if callable(find_adr):
                    try:
                        has_adr = find_adr(name, effective_base) is not None
                    except Exception:
                        has_adr = False
                if not has_adr:
                    costs.append(f"ADR gate: new component '{name}': " + COST_ADR.format(name=name))

    synthesis = gates.get("synthesis")
    if synthesis is not None and synthesis._is_gated(abs_path):
        if costs:
            costs.append("synthesis gate: " + COST_SYNTHESIS)
        else:
            load_session = getattr(synthesis, "_load_session", None)
            verdict_fn = getattr(synthesis, "_synthesis_verdict", None)
            session = load_session(effective_base) if callable(load_session) else None
            if isinstance(session, dict):
                domain = session.get("domain", "")
                adr_name = domain or Path(session.get("adr_path", "unknown")).stem
                synthesis_path = effective_base / "adr" / adr_name / "synthesis.md"
                verdict = verdict_fn(synthesis_path) if callable(verdict_fn) else None
                if verdict != "PROCEED":
                    state = f"verdict={verdict}" if verdict else "synthesis.md missing"
                    costs.append(f"synthesis gate (active ADR '{adr_name}', {state}): " + COST_SYNTHESIS)
    return costs


def security_findings(files: list[str], budget: float) -> list[dict]:
    """Redacted findings from scripts/security-review-scan.py for existing files: severity, file, line, rule."""
    scanner = SCRIPTS / "security-review-scan.py"
    if not files or not scanner.is_file():
        return []
    try:
        out = subprocess.run(
            [sys.executable, str(scanner), "--files", *files, "--format", "json", "--time-budget", str(int(budget))],
            capture_output=True,
            text=True,
            timeout=budget + 5,
        ).stdout
        data = json.loads(out or "{}")
    except (OSError, subprocess.SubprocessError, ValueError):
        return [
            {
                "severity": "unknown",
                "file": "-",
                "line": 0,
                "rule": "scanner did not finish; commit-time scan still runs",
            }
        ]
    keep = []
    for f in data.get("findings") or []:
        if str(f.get("severity", "")).lower() in ("critical", "high"):
            keep.append(
                {
                    "severity": str(f.get("severity")).lower(),
                    "file": str(f.get("file") or f.get("path") or "-"),
                    "line": int(f.get("line") or 0),
                    "rule": str(f.get("rule") or f.get("rule_id") or f.get("category") or "finding"),
                }
            )
    return keep


def private_term_hits(files: list[str], leak: ModuleType | None, root: Path | None) -> list[dict]:
    """Files whose text holds a private skill or brand term, with the term redacted."""
    if leak is None or root is None or not files:
        return []
    try:
        leaves, strong = leak.private_terms(root)
        pattern = leak.term_pattern(leaves, strong)
    except Exception:
        return []
    if pattern is None:
        return []
    hits = []
    for name in files:
        try:
            text = Path(name).read_text(encoding="utf-8", errors="ignore")
        except OSError:
            continue
        for lineno, line in enumerate(text.splitlines(), 1):
            m = pattern.search(line)
            if m:
                hits.append({"file": name, "line": lineno, "term": leak._redact(m.group(0))})
                break
    return hits


def preflight(paths: list[str], cwd: Path) -> dict:
    start = time.monotonic()
    root = toolkit_root(cwd)
    hook_roots = [r for r in ((root / "hooks") if root else None, Path.home() / ".claude" / "hooks") if r]
    gates = {
        "unified": load_hook("pretool-unified-gate.py", hook_roots),
        "adr": load_hook("pretool-adr-creation-gate.py", hook_roots),
        "synthesis": load_hook("pretool-synthesis-gate.py", hook_roots),
    }
    leak = load_hook("pretool-private-name-leak-gate.py", hook_roots)
    report: dict = {"paths": [], "security": [], "private_terms": [], "gates_loaded": {}}
    report["gates_loaded"] = {k: v is not None for k, v in {**gates, "private-name": leak}.items()}
    existing: list[str] = []
    for raw in paths:
        abs_path = str((cwd / raw).resolve()) if not os.path.isabs(raw) else raw
        costs = creation_costs(abs_path, gates, base_dir=root or cwd)
        report["paths"].append({"path": raw, "exists": os.path.exists(abs_path), "costs": costs})
        if os.path.isfile(abs_path):
            existing.append(abs_path)
    remaining = max(1.0, TIME_BUDGET_S - (time.monotonic() - start))
    report["security"] = [{**f, "file": _rel(f["file"], cwd)} for f in security_findings(existing, remaining)]
    report["private_terms"] = [{**h, "file": _rel(h["file"], cwd)} for h in private_term_hits(existing, leak, root)]
    return report


def _rel(path: str, cwd: Path) -> str:
    try:
        return os.path.relpath(path, cwd)
    except ValueError:
        return path


def render(report: dict) -> str:
    lines = ["/d preflight (advisory): gates the planned paths will hit"]
    for p in report["paths"]:
        for cost in p["costs"]:
            lines.append(f"  - {p['path']}: {cost}")
    for f in report["security"]:
        lines.append(
            f"  - security review blocks the commit: [{f['severity']}] {f['file']}:{f['line']} {f['rule']}; "
            "replace the value with a placeholder before staging"
        )
    for h in report["private_terms"]:
        lines.append(
            f"  - private-name gate blocks commit/push: {h['file']}:{h['line']} holds {h['term']}; "
            "remove it before staging"
        )
    missing = [k for k, ok in report["gates_loaded"].items() if not ok]
    if missing:
        lines.append(f"  (could not load: {', '.join(missing)}; those gates still run at write and commit time)")
    if len(lines) == 1:
        lines.append("  none found")
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Advisory /d preflight: gate costs for planned paths.")
    ap.add_argument("--paths", nargs="*", default=[], help="planned paths (new or existing), relative to cwd")
    ap.add_argument("--paths-file", type=Path, help="file with one planned path per line")
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args(argv)
    paths = list(args.paths)
    if args.paths_file:
        try:
            paths += [ln.strip() for ln in args.paths_file.read_text(encoding="utf-8").splitlines() if ln.strip()]
        except OSError as exc:
            print(f"d-preflight: cannot read {args.paths_file}: {exc}", file=sys.stderr)
    try:
        report = preflight(paths, Path.cwd())
    except Exception as exc:  # advisory: never block the route
        print(f"d-preflight: skipped ({type(exc).__name__}); the gates still run at write and commit time")
        return 0
    print(json.dumps(report, indent=2) if args.json else render(report))
    return 0


if __name__ == "__main__":
    sys.exit(main())
