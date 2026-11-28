#!/usr/bin/env python3
"""Offline deterministic and optional live-Jev golden prompt evaluation harness.

Evaluates curated prompt/intent/handoff cases across 6 failure-mode categories:
  - scope_creep
  - partial_delivery
  - constraint_preservation
  - ambiguity_detection
  - handoff_spec_completeness
  - positive_framing

Supports structured JSON scorecards and baseline comparisons for hill-climbing
workflows (hc-SPEC.md).

Usage:
    python3 scripts/prompt-eval.py
    python3 scripts/prompt-eval.py --json
    python3 scripts/prompt-eval.py --category scope_creep
    python3 scripts/prompt-eval.py --write-baseline /tmp/baseline.json
    python3 scripts/prompt-eval.py --compare /tmp/baseline.json
    python3 scripts/prompt-eval.py --live-jev
"""

from __future__ import annotations

import argparse
import importlib.util
import json
import os
import re
import sys
import tempfile
from pathlib import Path
from typing import Any

SCHEMA_VERSION = 1
SCRIPTS_DIR = Path(__file__).resolve().parent
DEFAULT_CASES_PATH = SCRIPTS_DIR / "data" / "prompt-eval-golden.json"
SCAN_NEGATIVE_FRAMING_PATH = SCRIPTS_DIR / "scan-negative-framing.py"

SUPPORTED_CATEGORIES = (
    "scope_creep",
    "partial_delivery",
    "constraint_preservation",
    "ambiguity_detection",
    "handoff_spec_completeness",
    "positive_framing",
)

INTENT_ALIGNMENT_CATEGORIES = frozenset(
    {
        "scope_creep",
        "partial_delivery",
        "constraint_preservation",
        "ambiguity_detection",
    }
)

DEFAULT_REQUIRED_HANDOFF_BLOCKS = (
    "**Request (verbatim):**",
    "**Acceptance criteria:**",
    "## Repo state",
)
DEFAULT_GATED_COMPLEXITIES = ("medium", "complex")
DEFAULT_DISALLOWED_EFFORTS = ("xhigh", "max")

# Specificity heuristics for ambiguity_detection.
_TARGET_RE = re.compile(
    r"(?:"
    r"[A-Za-z0-9_.-]+/[A-Za-z0-9_./-]+"
    r"|\b[A-Za-z0-9_-]+\.(?:py|js|ts|tsx|jsx|go|rs|md|json|yaml|yml|toml|sql|sh|html|css)\b"
    r"|(?<![A-Za-z0-9_-])--[a-z][a-z0-9-]+"
    r"|\b[a-z_][a-z0-9_]*\(\)"
    r"|`[^`]+`"
    r")",
    re.IGNORECASE,
)

_ACTION_VERB_RE = re.compile(
    r"\b(?:"
    r"add|remove|delete|replace|validate|return|returning|reduce|increase|"
    r"parse|export|migrate|reject|cache|paginate|implement|refactor|document|"
    r"limit|enforce|profile|verify|extract|rename|split|convert|restrict|"
    r"fix(?:ing)?\s+(?:the\s+)?(?:http\s*\d{3}|500|400|404|crash|typo|race|timeout|utf-8|parsing|flaky)"
    r")\b",
    re.IGNORECASE,
)

_OUTCOME_RE = re.compile(
    r"(?:"
    r"\b(?:under|below|at\s+most|within|at\s+least)\s+\d+(?:\.\d+)?\s*(?:ms|s|sec|seconds|%|mb|gb|kb|keys|req/s)?\b"
    r"|\b(?:http|status)\s*\d{3}\b"
    r"|\bexit(?:s|ing)?\s+(?:code\s+)?\d+\b"
    r"|\bverified\s+(?:by|via|with)\b"
    r"|\b(?:pytest|unit\s+test|regression\s+test|benchmark)\b"
    r"|\bwhen\s+[A-Za-z0-9_.-]+\s+(?:is|are|equals?|fails?|exceeds?)\b"
    r"|\breturn(?:s|ing)?\s+(?:http\s*\d{3}|a\s+|an\s+|zero|false|true|empty|json)\b"
    r"|\bdefaulting\s+to\s+\S+"
    r")",
    re.IGNORECASE,
)

_CLARIFICATION_RE = re.compile(
    r"(?:"
    r"\?"
    r"|\b(?:clarify|please\s+specify|need(?:s)?\s+clarification|ask\s+the\s+user)\b"
    r"|\bconfirm\s+(?:which|whether|the\s+target)\b"
    r"|\bbefore\s+proceeding\b.*\b(?:specify|confirm|choose|clarify)\b"
    r")",
    re.IGNORECASE,
)

# Positive-framing heuristics for unpaired negative directives.
_NEGATIVE_DIRECTIVE_RE = re.compile(r"\b(?:never|don['\u2019]t|do\s+not)\b", re.IGNORECASE)
_PAIRING_CONNECTOR_RE = re.compile(
    r"(?:;\s*|\s+\u2014\s+|\s+--\s+|:\s*|,\s*instead\b|\binstead\b|\brather\s+than\b|\*\*do\s+instead\*\*|do\s+instead:)",
    re.IGNORECASE,
)
_POSITIVE_ACTION_VERB_RE = re.compile(
    r"\b(?:use|run|load|write|keep|verify|validate|pass|return|set|call|choose|"
    r"prefer|check|configure|define|add|apply|provide|document|confirm|rely\s+on|"
    r"follow|store|read|test|pin|emit|report)\b",
    re.IGNORECASE,
)

_EDITORIAL_PATTERNS_CACHE: list[tuple[str, str, str]] | None = None


def _load_editorial_negative_patterns() -> list[tuple[str, str, str]]:
    """Lazily load NEGATIVE_PATTERNS from scripts/scan-negative-framing.py."""
    global _EDITORIAL_PATTERNS_CACHE
    if _EDITORIAL_PATTERNS_CACHE is not None:
        return _EDITORIAL_PATTERNS_CACHE
    if not SCAN_NEGATIVE_FRAMING_PATH.is_file():
        _EDITORIAL_PATTERNS_CACHE = []
        return _EDITORIAL_PATTERNS_CACHE
    spec = importlib.util.spec_from_file_location("_scan_negative_framing", SCAN_NEGATIVE_FRAMING_PATH)
    if spec is None or spec.loader is None:
        _EDITORIAL_PATTERNS_CACHE = []
        return _EDITORIAL_PATTERNS_CACHE
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    patterns = getattr(mod, "NEGATIVE_PATTERNS", [])
    _EDITORIAL_PATTERNS_CACHE = list(patterns) if isinstance(patterns, list) else []
    return _EDITORIAL_PATTERNS_CACHE


def _phrase_present(text: str, phrase: str) -> bool:
    """Case-insensitive, boundary-aware phrase check."""
    cleaned = phrase.strip()
    if not cleaned:
        return False
    tokens = [re.escape(part) for part in cleaned.split()]
    body = r"\s+".join(tokens)
    prefix = r"(?<![A-Za-z0-9_])" if cleaned[0].isalnum() else (r"(?<![A-Za-z0-9_-])" if cleaned[0] == "-" else "")
    suffix = r"(?![A-Za-z0-9_])" if cleaned[-1].isalnum() else ""
    return re.search(f"{prefix}{body}{suffix}", text, re.IGNORECASE) is not None


def _check_required_phrases(text: str, items: list[Any], label: str) -> list[str]:
    """Return failure reasons for missing required phrases (str or synonym list)."""
    reasons: list[str] = []
    for item in items:
        if isinstance(item, str):
            if not _phrase_present(text, item):
                reasons.append(f"missing {label}: {item}")
        elif isinstance(item, list) and item:
            if not any(isinstance(alt, str) and _phrase_present(text, alt) for alt in item):
                reasons.append(f"missing {label}: {' | '.join(str(alt) for alt in item)}")
    return reasons


def _check_forbidden_phrases(text: str, items: list[Any], label: str) -> list[str]:
    """Return failure reasons for forbidden phrases found in text."""
    reasons: list[str] = []
    for item in items:
        if isinstance(item, str) and _phrase_present(text, item):
            reasons.append(f"forbidden {label} present: {item}")
    return reasons


def get_candidate_text(case: dict[str, Any]) -> str:
    """Extract the candidate prompt/intent text from a golden case."""
    for key in ("candidate_text", "proposed_intent", "dispatch_prompt"):
        val = case.get(key)
        if isinstance(val, str):
            return val
    return ""


def _evaluate_scope_or_delivery(case: dict[str, Any], candidate_text: str) -> tuple[bool, list[str], dict[str, Any]]:
    checks = case.get("checks") or {}
    reasons: list[str] = []
    required = checks.get("required_deliverables") or []
    forbidden = list(checks.get("forbidden_scope_expansions") or []) + list(checks.get("forbidden_scope_terms") or [])
    reasons.extend(_check_required_phrases(candidate_text, required, "deliverable"))
    reasons.extend(_check_forbidden_phrases(candidate_text, forbidden, "scope expansion"))
    details = {
        "required_checked": len(required),
        "forbidden_checked": len(forbidden),
    }
    return len(reasons) == 0, reasons, details


def _evaluate_constraint_preservation(
    case: dict[str, Any], candidate_text: str
) -> tuple[bool, list[str], dict[str, Any]]:
    checks = case.get("checks") or {}
    reasons: list[str] = []
    required = checks.get("required_constraints") or []
    forbidden = checks.get("forbidden_phrases") or []
    reasons.extend(_check_required_phrases(candidate_text, required, "constraint"))
    reasons.extend(_check_forbidden_phrases(candidate_text, forbidden, "phrase"))
    details = {
        "required_constraints_checked": len(required),
        "forbidden_phrases_checked": len(forbidden),
    }
    return len(reasons) == 0, reasons, details


def specificity_signals(text: str) -> dict[str, bool]:
    """Evaluate deterministic actionable specificity signals in a prompt."""
    return {
        "concrete_target": _TARGET_RE.search(text) is not None,
        "concrete_action": _ACTION_VERB_RE.search(text) is not None,
        "observable_outcome": _OUTCOME_RE.search(text) is not None,
    }


def _evaluate_ambiguity_detection(case: dict[str, Any], candidate_text: str) -> tuple[bool, list[str], dict[str, Any]]:
    checks = case.get("checks") or {}
    user_request = str(case.get("user_request") or "")
    signals = specificity_signals(user_request)
    matched_signals = [name for name, present in signals.items() if present]
    min_signals = int(checks.get("min_specificity_signals", 3))
    requires_clarification = bool(checks.get("requires_clarification", False))
    asks_clarification = _CLARIFICATION_RE.search(candidate_text) is not None

    reasons: list[str] = []
    if requires_clarification:
        if not asks_clarification:
            reasons.append("underspecified request requires clarification, but candidate proceeded without asking")
    else:
        if len(matched_signals) < min_signals:
            missing = [name for name, present in signals.items() if not present]
            reasons.append(
                f"prompt lacks actionable specificity ({len(matched_signals)}/{min_signals}); missing: {', '.join(missing)}"
            )

    details = {
        "specificity_signals": signals,
        "specificity_count": len(matched_signals),
        "min_specificity_signals": min_signals,
        "requires_clarification": requires_clarification,
        "candidate_asks_clarification": asks_clarification,
    }
    return len(reasons) == 0, reasons, details


def _parse_do_route_marker(prompt: str) -> tuple[bool, str, str]:
    """Parse [do-route] marker line and return (has_marker, complexity, effort)."""
    head = prompt.lstrip()
    if not head.startswith("[do-route]"):
        return False, "", ""
    first_line = head.split("\n", 1)[0]
    complexity = ""
    effort = ""
    for token in first_line.split():
        if token.startswith("complexity="):
            complexity = token[len("complexity=") :].strip().lower()
        elif token.startswith("effort="):
            effort = token[len("effort=") :].strip().lower()
    return True, complexity, effort


def _evaluate_handoff_spec(case: dict[str, Any], candidate_text: str) -> tuple[bool, list[str], dict[str, Any]]:
    checks = case.get("checks") or {}
    required_blocks = list(checks.get("required_blocks") or DEFAULT_REQUIRED_HANDOFF_BLOCKS)
    gated_complexities = {str(c).lower() for c in (checks.get("gated_complexities") or DEFAULT_GATED_COMPLEXITIES)}
    disallowed_efforts = {str(e).lower() for e in (checks.get("disallowed_efforts") or DEFAULT_DISALLOWED_EFFORTS)}

    has_marker, complexity, effort = _parse_do_route_marker(candidate_text)
    reasons: list[str] = []
    missing_blocks: list[str] = []

    if not has_marker:
        reasons.append("missing [do-route] marker line")
    if complexity in gated_complexities:
        for block in required_blocks:
            if block not in candidate_text:
                missing_blocks.append(block)
                reasons.append(f"missing handoff block: {block}")

    has_override = "[effort-override" in candidate_text.lower()
    if effort in disallowed_efforts and not has_override:
        reasons.append(f"unapproved worker effort={effort} without [effort-override]")

    details = {
        "has_marker": has_marker,
        "complexity": complexity,
        "effort": effort,
        "missing_blocks": missing_blocks,
        "has_effort_override": has_override,
    }
    return len(reasons) == 0, reasons, details


def _split_sentences(text: str) -> list[str]:
    """Split text into sentence/line units for negative-directive pairing analysis."""
    units: list[str] = []
    for raw_line in text.splitlines():
        line = raw_line.strip()
        if not line:
            continue
        for part in re.split(r"(?<=[.!?])\s+", line):
            cleaned = part.strip()
            if cleaned:
                units.append(cleaned)
    return units


def _clause_has_positive_replacement(clause: str) -> bool:
    """Return True if a clause gives a concrete positive action without negating it."""
    if _NEGATIVE_DIRECTIVE_RE.search(clause):
        return False
    return _POSITIVE_ACTION_VERB_RE.search(clause) is not None


def _find_unpaired_negatives(text: str) -> list[str]:
    """Return sentences containing negative directives without a concrete DO replacement."""
    sentences = _split_sentences(text)
    unpaired: list[str] = []
    for idx, sentence in enumerate(sentences):
        if not _NEGATIVE_DIRECTIVE_RE.search(sentence):
            continue
        paired = False
        # Check same sentence after a pairing connector (e.g. "; instead, load ...").
        parts = _PAIRING_CONNECTOR_RE.split(sentence)
        if len(parts) > 1:
            for trailing in parts[1:]:
                if _clause_has_positive_replacement(trailing):
                    paired = True
                    break
        # Check immediately following sentence for a positive DO replacement.
        if not paired and idx + 1 < len(sentences):
            if _clause_has_positive_replacement(sentences[idx + 1]):
                paired = True
        if not paired:
            unpaired.append(sentence)
    return unpaired


def _scan_editorial_negative_framing(text: str) -> list[dict[str, str]]:
    """Scan text against scripts/scan-negative-framing.py patterns."""
    hits: list[dict[str, str]] = []
    for pattern, category, _suggestion in _load_editorial_negative_patterns():
        for match in re.finditer(pattern, text, re.IGNORECASE):
            hits.append({"category": category, "matched": match.group(0)})
    return hits


def _evaluate_positive_framing(case: dict[str, Any], candidate_text: str) -> tuple[bool, list[str], dict[str, Any]]:
    checks = case.get("checks") or {}
    max_unpaired = int(checks.get("max_unpaired_negatives", 0))
    check_editorial = bool(checks.get("check_editorial_negative_framing", False))

    unpaired = _find_unpaired_negatives(candidate_text)
    editorial_hits = _scan_editorial_negative_framing(candidate_text) if check_editorial else []

    reasons: list[str] = []
    if len(unpaired) > max_unpaired:
        reasons.append(f"unpaired negative directives ({len(unpaired)} > {max_unpaired}): {unpaired[0][:80]}")
    for hit in editorial_hits:
        reasons.append(f"editorial negative framing [{hit['category']}]: {hit['matched']}")

    details = {
        "unpaired_negatives_count": len(unpaired),
        "max_unpaired_negatives": max_unpaired,
        "editorial_hits": editorial_hits,
    }
    return len(reasons) == 0, reasons, details


_CATEGORY_EVALUATORS = {
    "scope_creep": _evaluate_scope_or_delivery,
    "partial_delivery": _evaluate_scope_or_delivery,
    "constraint_preservation": _evaluate_constraint_preservation,
    "ambiguity_detection": _evaluate_ambiguity_detection,
    "handoff_spec_completeness": _evaluate_handoff_spec,
    "positive_framing": _evaluate_positive_framing,
}


def _evaluate_live_jev(case: dict[str, Any], candidate_text: str, timeout: float) -> dict[str, Any]:
    """Lazily invoke jev_intent_align.evaluate_alignment() when --live-jev is enabled."""
    if str(SCRIPTS_DIR) not in sys.path:
        sys.path.insert(0, str(SCRIPTS_DIR))
    import jev_intent_align

    route = case.get("route")
    if not isinstance(route, dict):
        route = {"agent": "general-purpose", "skill": "workflow", "pipeline": None}
    raw = jev_intent_align.evaluate_alignment(
        str(case.get("user_request") or ""),
        route,
        candidate_text,
        timeout=timeout,
    )
    return {
        "available": bool(raw.get("available")),
        "source": raw.get("source"),
        "alignment": raw.get("alignment"),
        "aligned": raw.get("aligned"),
        "clarification_needed": raw.get("clarification_needed"),
        "issues": list(raw.get("issues") or []),
        "scores": dict(raw.get("scores") or {}),
        "reason": raw.get("reason"),
    }


def evaluate_case(case: dict[str, Any], *, live_jev: bool = False, timeout: float = 8.0) -> dict[str, Any]:
    """Evaluate a single golden case deterministically (plus optional live Jev)."""
    category = str(case.get("category") or "")
    evaluator = _CATEGORY_EVALUATORS.get(category)
    if evaluator is None:
        raise ValueError(f"unsupported category {category!r} in case {case.get('id')!r}")

    candidate_text = get_candidate_text(case)
    actual_pass, reasons, details = evaluator(case, candidate_text)
    expected_pass = bool(case.get("expected_pass"))
    matched = actual_pass == expected_pass

    record: dict[str, Any] = {
        "id": str(case.get("id") or ""),
        "category": category,
        "expected_pass": expected_pass,
        "actual_pass": actual_pass,
        "matched": matched,
        "false_positive": actual_pass and not expected_pass,
        "false_negative": (not actual_pass) and expected_pass,
        "reasons": reasons,
        "details": details,
        "notes": str(case.get("notes") or ""),
    }
    if live_jev and category in INTENT_ALIGNMENT_CATEGORIES:
        record["live_jev"] = _evaluate_live_jev(case, candidate_text, timeout)
    return record


def evaluate_cases(
    cases: list[dict[str, Any]],
    *,
    live_jev: bool = False,
    timeout: float = 8.0,
    cases_path: str = "",
) -> dict[str, Any]:
    """Run evaluation over a list of cases and assemble a scorecard dict."""
    results = [evaluate_case(case, live_jev=live_jev, timeout=timeout) for case in cases]
    total = len(results)
    matched = sum(1 for r in results if r["matched"])
    false_positives = sum(1 for r in results if r["false_positive"])
    false_negatives = sum(1 for r in results if r["false_negative"])
    accuracy = round(matched / total, 4) if total else 0.0

    by_category: dict[str, dict[str, Any]] = {}
    for cat in sorted({r["category"] for r in results}):
        cat_rows = [r for r in results if r["category"] == cat]
        cat_total = len(cat_rows)
        cat_matched = sum(1 for r in cat_rows if r["matched"])
        cat_actual_pass = sum(1 for r in cat_rows if r["actual_pass"])
        cat_expected_pass = sum(1 for r in cat_rows if r["expected_pass"])
        cat_fp = sum(1 for r in cat_rows if r["false_positive"])
        cat_fn = sum(1 for r in cat_rows if r["false_negative"])
        by_category[cat] = {
            "total": cat_total,
            "matched": cat_matched,
            "accuracy": round(cat_matched / cat_total, 4) if cat_total else 0.0,
            "pass_rate": round(cat_actual_pass / cat_total, 4) if cat_total else 0.0,
            "expected_pass_count": cat_expected_pass,
            "actual_pass_count": cat_actual_pass,
            "false_positives": cat_fp,
            "false_negatives": cat_fn,
        }

    return {
        "schema_version": SCHEMA_VERSION,
        "mode": "live-jev" if live_jev else "offline",
        "cases_path": cases_path,
        "total": total,
        "matched": matched,
        "accuracy": accuracy,
        "false_positives": false_positives,
        "false_negatives": false_negatives,
        "by_category": by_category,
        "results": results,
    }


def load_suite(path: Path) -> dict[str, Any]:
    """Load and validate a golden prompt-eval JSON suite."""
    raw = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(raw, dict) or not isinstance(raw.get("cases"), list):
        raise ValueError(f"invalid prompt-eval suite format in {path}")
    return raw


def write_baseline(path: Path, scorecard: dict[str, Any]) -> None:
    """Atomically write a scorecard JSON baseline with UTF-8 and LF endings."""
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = json.dumps(scorecard, indent=2) + "\n"
    tmp_path: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="w",
            encoding="utf-8",
            newline="\n",
            dir=path.parent,
            prefix=f".{path.name}.",
            suffix=".tmp",
            delete=False,
        ) as handle:
            tmp_path = Path(handle.name)
            handle.write(payload)
        os.replace(tmp_path, path)
    except Exception:
        if tmp_path is not None and tmp_path.exists():
            tmp_path.unlink(missing_ok=True)
        raise


def _delta_status(delta: float) -> str:
    if delta > 0:
        return "improved"
    if delta < 0:
        return "regressed"
    return "unchanged"


def compare_scorecards(baseline: dict[str, Any], current: dict[str, Any]) -> dict[str, Any]:
    """Compare current scorecard against a saved baseline scorecard."""
    base_acc = float(baseline.get("accuracy", 0.0))
    curr_acc = float(current.get("accuracy", 0.0))
    overall_delta = round(curr_acc - base_acc, 4)

    base_cats = baseline.get("by_category") or {}
    curr_cats = current.get("by_category") or {}
    cat_deltas: dict[str, dict[str, Any]] = {}
    for cat in sorted(set(base_cats) | set(curr_cats)):
        b_val = float(base_cats[cat]["accuracy"]) if cat in base_cats else None
        c_val = float(curr_cats[cat]["accuracy"]) if cat in curr_cats else None
        if b_val is not None and c_val is not None:
            delta = round(c_val - b_val, 4)
            status = _delta_status(delta)
        else:
            delta = None
            status = "added" if b_val is None else "removed"
        cat_deltas[cat] = {
            "baseline_accuracy": b_val,
            "current_accuracy": c_val,
            "delta": delta,
            "status": status,
        }

    return {
        "overall": {
            "baseline_accuracy": base_acc,
            "current_accuracy": curr_acc,
            "delta": overall_delta,
            "status": _delta_status(overall_delta),
        },
        "by_category": cat_deltas,
    }


def format_text_report(scorecard: dict[str, Any], comparison: dict[str, Any] | None = None) -> str:
    """Format a concise human-readable evaluation report."""
    lines = [
        f"prompt-eval [{scorecard['mode']}]: "
        f"{scorecard['matched']}/{scorecard['total']} matched "
        f"(accuracy={scorecard['accuracy']:.4f}, "
        f"fp={scorecard['false_positives']}, fn={scorecard['false_negatives']})",
        "",
        "Category breakdown:",
    ]
    for cat, stats in scorecard["by_category"].items():
        lines.append(
            f"  - {cat:26s} {stats['matched']}/{stats['total']} "
            f"accuracy={stats['accuracy']:.4f} pass_rate={stats['pass_rate']:.4f} "
            f"fp={stats['false_positives']} fn={stats['false_negatives']}"
        )

    mismatches = [r for r in scorecard["results"] if not r["matched"]]
    if mismatches:
        lines.append("")
        lines.append("Mismatched cases:")
        for row in mismatches:
            reason_text = "; ".join(row["reasons"]) if row["reasons"] else "all checks passed"
            lines.append(
                f"  - {row['id']} [{row['category']}]: expected_pass={row['expected_pass']} "
                f"actual_pass={row['actual_pass']} ({reason_text})"
            )

    if scorecard["mode"] == "live-jev":
        lines.append("")
        lines.append("Live Jev scores:")
        for row in scorecard["results"]:
            jev = row.get("live_jev")
            if isinstance(jev, dict):
                lines.append(
                    f"  - {row['id']} [{row['category']}]: alignment={jev.get('alignment')} "
                    f"aligned={jev.get('aligned')} clarify={jev.get('clarification_needed')} "
                    f"source={jev.get('source')}"
                )

    if comparison is not None:
        ov = comparison["overall"]
        lines.append("")
        lines.append(
            f"Baseline comparison: {ov['status']} "
            f"(baseline={ov['baseline_accuracy']:.4f} -> current={ov['current_accuracy']:.4f}, "
            f"delta={ov['delta']:+.4f})"
        )
        for cat, stats in comparison["by_category"].items():
            if stats["delta"] is not None:
                lines.append(
                    f"  - {cat:26s} {stats['status']:9s} "
                    f"({stats['baseline_accuracy']:.4f} -> {stats['current_accuracy']:.4f}, "
                    f"delta={stats['delta']:+.4f})"
                )
            else:
                lines.append(f"  - {cat:26s} {stats['status']}")

    return "\n".join(lines)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Golden prompt-evaluation harness (offline deterministic + live Jev).")
    parser.add_argument(
        "--cases",
        type=Path,
        default=DEFAULT_CASES_PATH,
        help="Path to golden prompt-eval JSON suite.",
    )
    parser.add_argument(
        "--category",
        default=None,
        help="Filter evaluation to a single category.",
    )
    parser.add_argument(
        "--min-accuracy",
        type=float,
        default=1.0,
        help="Minimum overall accuracy required to exit 0 (default: 1.0).",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Emit structured JSON scorecard to stdout.",
    )
    parser.add_argument(
        "--write-baseline",
        type=Path,
        default=None,
        help="Write JSON scorecard atomically to PATH for later --compare runs.",
    )
    parser.add_argument(
        "--compare",
        type=Path,
        default=None,
        help="Compare current scorecard against a saved baseline JSON file at PATH.",
    )
    parser.add_argument(
        "--live-jev",
        action="store_true",
        help="Also call jev_intent_align.evaluate_alignment() on intent-alignment categories.",
    )
    parser.add_argument(
        "--timeout",
        type=float,
        default=8.0,
        help="Per-case timeout in seconds for --live-jev mode (default: 8.0).",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    try:
        suite = load_suite(args.cases)
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        print(f"prompt-eval error: {exc}", file=sys.stderr)
        return 2

    cases: list[dict[str, Any]] = list(suite["cases"])
    if args.category is not None:
        cases = [c for c in cases if c.get("category") == args.category]
        if not cases:
            print(f"prompt-eval error: no cases found for category {args.category!r}", file=sys.stderr)
            return 2

    try:
        scorecard = evaluate_cases(
            cases,
            live_jev=args.live_jev,
            timeout=args.timeout,
            cases_path=str(args.cases),
        )
    except ValueError as exc:
        print(f"prompt-eval error: {exc}", file=sys.stderr)
        return 2

    if args.write_baseline is not None:
        write_baseline(args.write_baseline, scorecard)

    comparison: dict[str, Any] | None = None
    if args.compare is not None:
        try:
            baseline = json.loads(args.compare.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            print(f"prompt-eval error: failed to read baseline {args.compare}: {exc}", file=sys.stderr)
            return 2
        comparison = compare_scorecards(baseline, scorecard)

    if args.json:
        output = dict(scorecard)
        if comparison is not None:
            output["comparison"] = comparison
        print(json.dumps(output, indent=2))
    else:
        print(format_text_report(scorecard, comparison=comparison))

    passed_threshold = scorecard["accuracy"] >= args.min_accuracy
    regressed = comparison is not None and comparison["overall"]["status"] == "regressed"
    return 0 if (passed_threshold and not regressed) else 1


if __name__ == "__main__":
    raise SystemExit(main())
