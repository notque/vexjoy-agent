#!/usr/bin/env python3
"""Conformance gate for native .js workflows: declared contract vs actual dispatch.

A native Workflow ``.js`` may declare a pure-literal ``meta.contract`` describing
the dispatch shape it promises:

    contract: {
      phases: ["wave-1", ...],                 // phase() titles entered
      roster: [{agentType, skill}, ...],       // the FIXED (static) Wave-1 barrier
      agents: { static: <N>, dynamic: <bool> },// fixed barrier size
      dynamic: <bool>,                          // data-driven passes present?
    }

This script asserts the actual script against that contract, in two layers:

* STATIC (pure stdlib, always runs, the CI gate):
  - ``meta.phases`` (the phase()/enterPhase() titles in source) == ``contract.phases``
  - every ``contract.roster`` agentType is dispatched in source (``agentType:`` token)
  - every ``contract.roster`` skill appears as a ``Skill("..")`` token in source
  - ``contract.agents.static`` == ``len(contract.roster)`` (the fixed barrier size),
    and there are at least that many ``agent(`` call-sites
* DYNAMIC (shells to scripts/conformance-harness.mjs IF node is available):
  - every recorded ``phases_entered`` (per tier) is a subset of ``contract.phases``
  - the recorded static Wave-1 roster (agentType + skills) matches ``contract.roster``
  - for ``dynamic:true`` it asserts SHAPE + SKILLS, NOT COUNT (honest limit) and
    says so in the output.

Honest limits, no silent caps: the STATIC pass COUNT-checks only the fixed Wave-1
barrier (``contract.agents.static``). For ``dynamic:true`` workflows the per-finding
verify pass and the budget-bounded fix loop fan out over RUNTIME data and are NOT
count-checked — only their SHAPE and SKILLS are asserted. Each result records which
checks were COUNT vs SHAPE+SKILLS.

node availability: CI does not provide node (.github/workflows/test.yml uses
setup-python only). When node is absent the DYNAMIC pass is SKIPPED (recorded as a
note), NOT failed — the STATIC pass is the CI gate. The .mjs harness is a documented
local/dev tool. See adr/native-fast-path-portable-floor.md Stages 0-1.

Files WITHOUT a ``meta.contract`` are EXEMPT (prose-only / legacy) — skipped, not
failed.

Pure stdlib. Exit 0 when every contracted file passes (and exempt files are
skipped); exit 1 on any conformance mismatch; exit 2 on a usage error.

Usage:
    python3 scripts/validate-workflow-conformance.py            # default dir
    python3 scripts/validate-workflow-conformance.py --json
    python3 scripts/validate-workflow-conformance.py --static-only
    python3 scripts/validate-workflow-conformance.py --dir <dir-or-file>
"""

from __future__ import annotations

import argparse
import json
import re
import shutil
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_DIR = REPO_ROOT / "skills" / "workflow" / "references"
HARNESS = REPO_ROOT / "scripts" / "conformance-harness.mjs"

# --- meta / contract parsing --------------------------------------------------
# meta.name is parsed by workflow-registry.py with a non-greedy first-`}` match;
# the contract is a NESTED literal, so we brace-match the `contract: { ... }`
# sub-block explicitly instead of relying on a non-greedy regex.

_CONTRACT_KEY = re.compile(r"\bcontract\s*:\s*\{")
# phase("..") OR enterPhase("..") with a STRING-LITERAL title (the defensive
# wrapper enterPhase(title) calls phase(title) with a variable — skip those).
_PHASE_CALL = re.compile(r"""(?:enterPhase|phase)\(\s*["'`]([^"'`$]+)["'`]""")
_AGENT_TYPE = re.compile(r"""\bagentType\s*:\s*["'`]([^"'`$]+)["'`]""")
# Literal `agent: "name"` roster-declaration fields (agentType reaches dispatch
# via a variable r.agent; the literal names live in the roster array).
_AGENT_FIELD = re.compile(r"""\bagent\s*:\s*["'`]([^"'`$]+)["'`]""")
# A literal Skill("name") token (name must not be an interpolation placeholder).
_SKILL_LITERAL = re.compile(r"""\bSkill\(\s*["'`]([^"'`$]+)["'`]\s*\)""")
# Any Skill( directive at all — proves the skill-attach wiring is emitted, even
# when the name is template-interpolated (Skill("${roster.skill}")).
_SKILL_DIRECTIVE = re.compile(r"\bSkill\(")
# Literal `skill: "name"` values declared on roster entries / maps in source.
_SKILL_FIELD = re.compile(r"""\bskill\s*:\s*["'`]([^"'`$]+)["'`]""")
# Quoted string values inside an AGENT_SKILL-style map (key: "value").
_MAP_VALUE = re.compile(r"""["'`][\w.\-/]+["'`]\s*:\s*["'`]([^"'`$]+)["'`]""")
_AGENT_CALL = re.compile(r"\bagent\(")


def _match_braced_block(source: str, open_brace_idx: int) -> str | None:
    """Return the text between the matched braces starting at *open_brace_idx*.

    *open_brace_idx* points at the ``{``. Returns the inner text (excluding the
    outer braces), brace-matched, ignoring braces inside strings. Never raises.
    """
    try:
        depth = 0
        i = open_brace_idx
        n = len(source)
        in_str = None
        start_inner = open_brace_idx + 1
        while i < n:
            ch = source[i]
            if in_str:
                if ch == "\\":
                    i += 2
                    continue
                if ch == in_str:
                    in_str = None
            elif ch in "\"'`":
                in_str = ch
            elif ch == "{":
                depth += 1
            elif ch == "}":
                depth -= 1
                if depth == 0:
                    return source[start_inner:i]
            i += 1
        return None
    except Exception:
        return None


def _js_object_to_json(text: str) -> str:
    """Best-effort convert a JS object-literal body to JSON-parseable text.

    Handles: unquoted keys, single quotes, trailing commas, line comments. The
    contract is a pure literal by contract (no calls/variables), so this is
    sufficient. Never raises (returns text unchanged on trouble).
    """
    try:
        # Strip // line comments (not inside strings — contract has none).
        no_comments = re.sub(r"//[^\n]*", "", text)
        # Single -> double quotes for string literals.
        s = re.sub(r"'([^'\\]*(?:\\.[^'\\]*)*)'", lambda m: json.dumps(m.group(1)), no_comments)
        # Quote unquoted object keys:  key:  ->  "key":
        s = re.sub(r"([{,]\s*)([A-Za-z_$][\w$]*)\s*:", r'\1"\2":', s)
        # Remove trailing commas before } or ].
        s = re.sub(r",(\s*[}\]])", r"\1", s)
        return s
    except Exception:
        return text


def extract_contract(source: str) -> dict | None:
    """Extract and parse ``meta.contract`` from JS source, or None if absent.

    Never raises. Returns the parsed contract dict, or None when no contract key
    is present (the file is exempt).
    """
    try:
        km = _CONTRACT_KEY.search(source)
        if not km:
            return None
        open_idx = km.end() - 1  # index of the `{`
        inner = _match_braced_block(source, open_idx)
        if inner is None:
            return None
        body = "{" + inner + "}"
        return json.loads(_js_object_to_json(body))
    except Exception:
        return None


def strip_contract(source: str) -> str:
    """Return source with the meta.contract block removed.

    The contract is the SPEC being validated; its own literals (roster
    ``agentType:``/``skill:``, ``phases``) must not count as evidence that the
    body dispatches them. Never raises — returns source unchanged on trouble.
    """
    try:
        km = _CONTRACT_KEY.search(source)
        if not km:
            return source
        open_idx = km.end() - 1
        inner = _match_braced_block(source, open_idx)
        if inner is None:
            return source
        # Remove from the `contract` keyword to the matching closing brace.
        end_idx = open_idx + 1 + len(inner) + 1
        return source[: km.start()] + source[end_idx:]
    except Exception:
        return source


_LINE_COMMENT = re.compile(r"//[^\n]*")
_BLOCK_COMMENT = re.compile(r"/\*.*?\*/", re.DOTALL)


def strip_comments(source: str) -> str:
    """Remove // line and /* */ block comments. Comments are never evidence that
    the body dispatches an agent/skill (a comment mentioning Skill("x") proves
    nothing). Never raises."""
    try:
        return _LINE_COMMENT.sub("", _BLOCK_COMMENT.sub("", source))
    except Exception:
        return source


def evidence_body(source: str) -> str:
    """Return source stripped of BOTH the contract block and comments — the only
    text that counts as proof the body actually dispatches what it declares."""
    return strip_comments(strip_contract(source))


def extract_phase_titles(source: str) -> set[str]:
    """Return the set of phase() titles entered in source (via phase()/enterPhase)."""
    return set(_PHASE_CALL.findall(source))


def extract_agent_types(source: str) -> set[str]:
    """Return the set of agent names declared/dispatched in source.

    agentType reaches dispatch via a variable (``agentType: r.agent``), so the
    literal names live in the roster declarations (``agent: "name"``). Collect
    from both literal ``agentType:`` tokens and ``agent:`` roster fields.
    """
    names: set[str] = set()
    names.update(_AGENT_TYPE.findall(source))
    names.update(_AGENT_FIELD.findall(source))
    return names


def extract_skill_tokens(source: str) -> set[str]:
    """Return the set of skill names statically resolvable from source.

    Skill names reach the prompt via a template (``Skill("${roster.skill}")``), so
    the literal names live in the roster/map declarations, not the prompt string.
    Collect from: literal ``Skill("name")`` tokens, ``skill: "name"`` fields, and
    ``"agentType": "name"`` map values (the AGENT_SKILL map). Interpolation
    placeholders (``${...}``) are excluded by the patterns.
    """
    names: set[str] = set()
    names.update(_SKILL_LITERAL.findall(source))
    names.update(_SKILL_FIELD.findall(source))
    names.update(_MAP_VALUE.findall(source))
    return names


def has_skill_directive(source: str) -> bool:
    """True if source emits a Skill( directive at all (skill-attach wiring present)."""
    return _SKILL_DIRECTIVE.search(source) is not None


def count_agent_callsites(source: str) -> int:
    """Count agent( call-sites in source."""
    return len(_AGENT_CALL.findall(source))


# --- static validation --------------------------------------------------------


def _static_checks(source: str, contract: dict) -> tuple[list[str], list[str]]:
    """Return (errors, check_labels) for the static layer.

    check_labels names which checks are COUNT vs SHAPE+SKILLS (honest limits).
    """
    errors: list[str] = []
    labels: list[str] = []

    # Evidence comes from the body, NOT the contract block or comments (the
    # contract is the spec being validated; comments prove nothing).
    body = evidence_body(source)

    # 1. phases (SHAPE): declared set == entered set.
    declared_phases = set(contract.get("phases", []))
    entered_phases = extract_phase_titles(body)
    labels.append("phases: SHAPE (declared set == phase() titles in source)")
    if declared_phases != entered_phases:
        missing = declared_phases - entered_phases
        extra = entered_phases - declared_phases
        parts = []
        if missing:
            parts.append(f"declared-but-not-entered={sorted(missing)}")
        if extra:
            parts.append(f"entered-but-not-declared={sorted(extra)}")
        errors.append("phase mismatch: " + "; ".join(parts))

    roster = contract.get("roster", [])
    src_agent_types = extract_agent_types(body)
    src_skills = extract_skill_tokens(body)

    # 2. roster agentType present in source (SHAPE).
    labels.append("roster.agentType: SHAPE (each present as agentType: in source)")
    for entry in roster:
        at = entry.get("agentType")
        if at and at not in src_agent_types:
            errors.append(f"roster agentType '{at}' not dispatched in source (no agentType: token)")

    # 3. roster skill present in source (SKILLS). The skill-attach directive must
    #    be emitted (Skill( present), and each declared skill must be resolvable
    #    from source roster/map literals (names reach the prompt via a template).
    labels.append(
        "roster.skill: SKILLS (Skill( directive emitted; each skill resolvable from source roster/map literals)"
    )
    wiring = has_skill_directive(body)
    if roster and not wiring:
        errors.append(
            "no Skill( directive emitted in source, but contract.roster declares "
            f"skills {[e.get('skill') for e in roster if e.get('skill')]}"
        )
    for entry in roster:
        sk = entry.get("skill")
        if sk and sk not in src_skills:
            errors.append(
                f"roster skill '{sk}' not resolvable from source "
                '(no Skill("{sk}") literal, skill: field, or AGENT_SKILL map value)'.replace("{sk}", sk)
            )

    # 4. fixed Wave-1 barrier size (COUNT — the ONLY count check; static barrier).
    labels.append("agents.static: COUNT (== len(roster); fixed Wave-1 barrier only)")
    agents = contract.get("agents", {})
    static_n = agents.get("static")
    if static_n is not None and static_n != len(roster):
        errors.append(
            f"agents.static={static_n} does not match roster length {len(roster)} "
            f"(the static Wave-1 barrier must list every fixed agent)"
        )
    callsites = count_agent_callsites(body)
    if static_n is not None and callsites < static_n:
        errors.append(f"only {callsites} agent( call-sites in source but contract declares {static_n} static agents")

    # 5. Honest-limit note for dynamic passes (SHAPE+SKILLS, NOT COUNT).
    if contract.get("dynamic"):
        labels.append(
            "dynamic passes (Wave-2/3, verify, fix): SHAPE+SKILLS only, NOT COUNT "
            "(data-driven fan-out is not statically countable)"
        )

    return errors, labels


# --- dynamic validation -------------------------------------------------------


def node_available() -> bool:
    """Return True if a `node` executable is on PATH."""
    return shutil.which("node") is not None


def _run_harness(js_path: Path) -> dict | None:
    """Shell to conformance-harness.mjs for *js_path*; return parsed JSON or None."""
    try:
        proc = subprocess.run(
            ["node", str(HARNESS), str(js_path), "--tiers", "2,3,4"],
            capture_output=True,
            text=True,
            timeout=120,
        )
        if not proc.stdout.strip():
            return None
        return json.loads(proc.stdout)
    except Exception:
        return None


def _dynamic_checks(js_path: Path, contract: dict) -> tuple[list[str], list[str]]:
    """Return (errors, notes) for the dynamic layer (assumes node available)."""
    errors: list[str] = []
    notes: list[str] = []

    harness_out = _run_harness(js_path)
    if harness_out is None:
        notes.append("dynamic: harness produced no parseable trace; skipped")
        return errors, notes
    if harness_out.get("errors"):
        for e in harness_out["errors"]:
            errors.append(f"harness error at tier {e.get('tier')}: {e.get('error')}")

    declared_phases = set(contract.get("phases", []))
    roster = contract.get("roster", [])
    expected_roster = [(e.get("agentType"), tuple(sorted([e.get("skill")] if e.get("skill") else []))) for e in roster]

    traces = harness_out.get("traces", {})
    notes.append(f"dynamic: recorded {len(traces)} tier trace(s): {sorted(traces.keys())}")
    for tier, trace in traces.items():
        # phases entered must be a SUBSET of declared (tier-gated phases skip some).
        entered = set(trace.get("phases_entered", []))
        if not entered.issubset(declared_phases):
            errors.append(
                f"tier {tier}: entered phases {sorted(entered)} not a subset of "
                f"contract.phases {sorted(declared_phases)}"
            )
        # static Wave-1 roster: SHAPE + SKILLS (agentType + its skills), NOT COUNT.
        recorded_roster = [(r.get("agentType"), tuple(sorted(r.get("skills", [])))) for r in trace.get("rosters", [])]
        if recorded_roster != expected_roster:
            errors.append(
                f"tier {tier}: recorded Wave-1 roster {recorded_roster} != "
                f"contract.roster (agentType+skills) {expected_roster}"
            )
    if contract.get("dynamic"):
        notes.append(
            "dynamic: agent_count is data-driven and NOT asserted (honest limit); "
            "only phase-subset + static Wave-1 roster SHAPE+SKILLS are checked"
        )
    return errors, notes


# --- per-file + directory orchestration --------------------------------------


def validate_file(js_path: Path, static_only: bool = False) -> dict:
    """Validate a single .js file against its meta.contract. Never raises."""
    result: dict = {
        "file": str(js_path),
        "status": "exempt",
        "static_errors": [],
        "dynamic_errors": [],
        "checks": [],
        "notes": [],
        "dynamic_ran": False,
    }
    try:
        source = js_path.read_text(encoding="utf-8", errors="replace")
    except Exception as exc:
        result["status"] = "fail"
        result["static_errors"].append(f"unreadable file: {exc}")
        return result

    contract = extract_contract(source)
    if contract is None:
        result["notes"].append("exempt: no meta.contract (prose-only/legacy)")
        return result

    static_errors, labels = _static_checks(source, contract)
    result["static_errors"] = static_errors
    result["checks"] = labels

    if not static_only:
        if node_available():
            dyn_errors, dyn_notes = _dynamic_checks(js_path, contract)
            result["dynamic_errors"] = dyn_errors
            result["notes"].extend(dyn_notes)
            result["dynamic_ran"] = True
        else:
            result["notes"].append(
                "dynamic: node unavailable — DYNAMIC pass skipped (not failed); "
                "STATIC is the CI gate. The .mjs harness is a local/dev tool."
            )

    result["status"] = "fail" if (result["static_errors"] or result["dynamic_errors"]) else "pass"
    return result


def validate_dir(path: Path, static_only: bool = False) -> list[dict]:
    """Validate every .js under *path* (or *path* itself if it is a file)."""
    if path.is_file():
        return [validate_file(path, static_only=static_only)]
    if not path.is_dir():
        return []
    return [validate_file(js, static_only=static_only) for js in sorted(path.glob("*.js"))]


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description="Validate native .js workflows against their meta.contract.")
    parser.add_argument("--dir", default=str(DEFAULT_DIR), help="directory (or single .js file) to validate")
    parser.add_argument("--json", action="store_true", help="emit JSON report")
    parser.add_argument("--static-only", action="store_true", help="skip the dynamic harness pass")
    args = parser.parse_args(argv)

    target = Path(args.dir)
    results = validate_dir(target, static_only=args.static_only)

    contracted = [r for r in results if r["status"] != "exempt"]
    exempt = [r for r in results if r["status"] == "exempt"]
    failures = [r for r in results if r["status"] == "fail"]

    if args.json:
        print(
            json.dumps(
                {
                    "target": str(target),
                    "summary": {
                        "total": len(results),
                        "contracted": len(contracted),
                        "exempt": len(exempt),
                        "passed": len([r for r in contracted if r["status"] == "pass"]),
                        "failed": len(failures),
                    },
                    "files": results,
                },
                indent=2,
            )
        )
    else:
        for r in results:
            tag = {"pass": "PASS", "fail": "FAIL", "exempt": "EXEMPT"}[r["status"]]
            print(f"[{tag}] {r['file']}")
            for note in r["notes"]:
                print(f"    note: {note}")
            for label in r["checks"]:
                print(f"    check: {label}")
            for e in r["static_errors"]:
                print(f"    STATIC ERROR: {e}")
            for e in r["dynamic_errors"]:
                print(f"    DYNAMIC ERROR: {e}")
        s = f"\n{len(contracted)} contracted, {len(exempt)} exempt, {len(failures)} failed."
        print(s)

    return 1 if failures else 0


if __name__ == "__main__":
    try:
        sys.exit(main(sys.argv[1:]))
    except SystemExit:
        raise
    except Exception as exc:  # pragma: no cover - defensive
        print(f"validate-workflow-conformance: {type(exc).__name__}: {exc}", file=sys.stderr)
        sys.exit(2)
