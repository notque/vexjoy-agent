#!/usr/bin/env python3
"""Fast per-file diff triage using TypeSafe Jev classifications.

Pre-filter for code review agents: parses a diff into per-file change
summaries, classifies each file's review priority via Jev (risk level,
needs_review, auto_mergeable), and sorts results so agents spend time
only on files that matter.

One Jev call per batch of ~10 files. State is compact metadata (filename,
line counts, hunk count, detected patterns), not full diff content.

Usage:
    git diff HEAD~1 | python3 scripts/jev-diff-triage.py --json-compact
    python3 scripts/jev-diff-triage.py --diff-file pr.diff --summary
    python3 scripts/jev-diff-triage.py --pr 42 --threshold 0.5
    python3 scripts/jev-diff-triage.py --pr 42 --json-compact

Exit codes:
    0 -- always (output is JSON to stdout; errors go to stderr)
"""

from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
from pathlib import Path

_SCRIPTS_DIR = Path(__file__).resolve().parent
if str(_SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS_DIR))
import jev_router_common

DEFAULT_THRESHOLD = 0.5
DEFAULT_BATCH_SIZE = 10
DEFAULT_TIMEOUT = 8.0

# Risk levels for the Score question (ordered low to high).
RISK_LEVELS = [
    "Cosmetic (formatting, comments)",
    "Low risk (docs, tests, configs)",
    "Medium risk (application code, non-critical paths)",
    "High risk (auth, security, data, core logic)",
    "Critical (credentials, permissions, public exposure)",
]

# Numeric weight per risk level for sorting (higher = more urgent).
RISK_WEIGHT: dict[str, int] = {level: idx for idx, level in enumerate(RISK_LEVELS)}

# Pattern detection regexes for added lines.
_PATTERN_REGEXES: dict[str, re.Pattern[str]] = {
    "has_error_handling": re.compile(
        r"\b(try|except|catch|raise|throw|finally|rescue|on_error|error_handler)\b", re.IGNORECASE
    ),
    "has_auth_code": re.compile(
        r"\b(auth|login|logout|password|credential|token|jwt|oauth|session|permission|rbac|acl)\b", re.IGNORECASE
    ),
    "has_sql": re.compile(
        r"\b(SELECT|INSERT|UPDATE|DELETE|CREATE\s+TABLE|ALTER\s+TABLE|DROP\s+TABLE|JOIN|WHERE)\b", re.IGNORECASE
    ),
    "has_env_vars": re.compile(r"\b(os\.environ|getenv|process\.env|ENV\[|dotenv|\.env)\b"),
    "has_api_changes": re.compile(
        r"\b(endpoint|route|@app\.|@router\.|blueprint|api_view|urlpatterns|openapi|swagger)\b", re.IGNORECASE
    ),
    "has_test_code": re.compile(
        r"\b(def test_|class Test|assert|pytest|unittest|describe|it\(|expect\(|mock|stub)\b", re.IGNORECASE
    ),
}

# File-header regex: "diff --git a/<path> b/<path>"
_DIFF_HEADER_RE = re.compile(r"^diff --git a/(.+?) b/(.+)$")
_HUNK_HEADER_RE = re.compile(r"^@@\s+-\d+(?:,\d+)?\s+\+(\d+)(?:,\d+)?\s+@@")
_BINARY_RE = re.compile(r"^Binary files ")


# Diff parsing.


def _parse_diff(diff_text: str) -> list[dict]:
    """Parse unified diff into per-file change summaries.

    Returns a list of dicts, each with:
      - path: str
      - lines_added: int
      - lines_removed: int
      - hunk_count: int
      - file_type: str (extension or "unknown")
      - added_lines: list[str] (raw added-line text, no leading "+")
      - patterns: list[str] (detected pattern names)
    """
    files: list[dict] = []
    current: dict | None = None

    for line in diff_text.splitlines():
        header_match = _DIFF_HEADER_RE.match(line)
        if header_match:
            if current is not None:
                _finalize_file(current)
                files.append(current)
            path = header_match.group(2)
            ext = Path(path).suffix.lstrip(".") or "unknown"
            current = {
                "path": path,
                "lines_added": 0,
                "lines_removed": 0,
                "hunk_count": 0,
                "file_type": ext,
                "added_lines": [],
                "is_binary": False,
            }
            continue

        if current is None:
            continue

        if _BINARY_RE.match(line):
            current["is_binary"] = True
            continue

        if _HUNK_HEADER_RE.match(line):
            current["hunk_count"] += 1
            continue

        if line.startswith("+") and not line.startswith("+++"):
            current["lines_added"] += 1
            current["added_lines"].append(line[1:])
        elif line.startswith("-") and not line.startswith("---"):
            current["lines_removed"] += 1

    if current is not None:
        _finalize_file(current)
        files.append(current)

    # Drop binary files and files with no changes.
    return [f for f in files if not f.get("is_binary") and (f["lines_added"] > 0 or f["lines_removed"] > 0)]


def _finalize_file(file_info: dict) -> None:
    """Detect patterns in added lines and attach them to the file info."""
    patterns: list[str] = []
    joined = "\n".join(file_info.get("added_lines", []))
    for pattern_name, regex in _PATTERN_REGEXES.items():
        if regex.search(joined):
            patterns.append(pattern_name)

    change_types: list[str] = []
    added = file_info.get("added_lines", [])
    if any(re.match(r"^\s*(import |from .+ import )", line) for line in added):
        change_types.append("import_changes")
    if any(re.match(r"^\s*(def |class |function |const |let |var |func )", line) for line in added):
        change_types.append("function_changes")
    if any(re.match(r"^\s*(#|//|/\*|\*|--)", line) for line in added):
        change_types.append("comment_changes")
    if any(re.match(r"^\s*$", line) for line in added):
        change_types.append("whitespace_changes")

    file_info["patterns"] = patterns
    file_info["change_types"] = change_types


def _build_file_summary(file_info: dict) -> str:
    """Build a compact one-line summary for Jev state.

    Format: path/to/file.py: +45 -12, 3 hunks, types: [function_changes, import_changes], patterns: [has_auth_code]
    """
    parts = [
        f"{file_info['path']}: +{file_info['lines_added']} -{file_info['lines_removed']}",
        f"{file_info['hunk_count']} hunks",
    ]
    if file_info.get("change_types"):
        parts.append(f"types: {file_info['change_types']}")
    if file_info.get("patterns"):
        parts.append(f"patterns: {file_info['patterns']}")
    return ", ".join(parts)


# Jev call construction.


def _build_batch_payload(file_summaries: list[dict], batch_indices: list[int]) -> dict:
    """Build a Jev payload for one batch of files.

    State is the concatenated compact summaries. Questions are per-file
    Score (risk) + two Nouls (needs_review, auto_mergeable).
    """
    state_parts: list[str] = []
    questions: dict[str, dict] = {}

    for local_idx, global_idx in enumerate(batch_indices):
        file_info = file_summaries[global_idx]
        summary = _build_file_summary(file_info)
        state_parts.append(f"[File {local_idx + 1}] {summary}")

        prefix = f"file_{local_idx + 1}"

        questions[f"{prefix}_risk"] = {
            "type": "score",
            "instructions": (
                f"Rate ONLY [File {local_idx + 1}] for review risk based on the file path, "
                "change size, change types, and detected patterns. Consider: auth/security "
                "code is high risk, test additions are low risk, formatting is cosmetic."
            ),
            "criteria": RISK_LEVELS,
        }

        questions[f"{prefix}_needs_review"] = {
            "type": "noul",
            "instructions": (
                f"Evaluate ONLY [File {local_idx + 1}]. True when this file's changes could "
                "introduce bugs, security issues, or behavioral changes."
            ),
            "criteria": {
                "true": {
                    "what": "Changes to logic, APIs, auth, data handling, error paths",
                    "examples": [
                        "modified auth middleware",
                        "changed database query",
                        "altered error handling",
                        "new API endpoint",
                        "modified permission checks",
                    ],
                },
                "false": {
                    "what": "Formatting, comments, docs, dependency bumps, test additions",
                    "examples": [
                        "added README section",
                        "reformatted with prettier",
                        "added unit test",
                        "updated changelog",
                        "fixed typo in comment",
                    ],
                },
            },
        }

        questions[f"{prefix}_auto_mergeable"] = {
            "type": "noul",
            "instructions": (
                f"Evaluate ONLY [File {local_idx + 1}]. True when this file's changes are "
                "safe to auto-merge without human review."
            ),
            "criteria": {
                "true": {
                    "what": "Changes that cannot break behavior: formatting, comments, docs, lockfile updates",
                    "examples": [
                        "whitespace-only changes",
                        "comment text edits",
                        "README updates",
                        "auto-generated lockfile",
                        "changelog entry",
                    ],
                },
                "false": {
                    "what": "Any change to executable code, configuration, or security-relevant files",
                    "examples": [
                        "modified function body",
                        "changed config value",
                        "updated dependency version",
                        "altered build script",
                        "new environment variable",
                    ],
                },
            },
        }

        # v2: additional per-file questions for richer triage signals.
        questions[f"{prefix}_has_security_changes"] = {
            "type": "noul",
            "instructions": (
                f"Evaluate ONLY [File {local_idx + 1}]. True when changes touch auth, "
                "permissions, crypto, secrets, input validation, or security headers."
            ),
            "criteria": {
                "true": {
                    "what": "Security-relevant code modified",
                    "examples": ["auth middleware changed", "password handling altered", "CORS config updated"],
                    "not_for": "Files in a security-related directory with non-security changes (e.g., fixing a typo in auth/README.md).",
                },
                "false": {
                    "what": "No security-relevant changes",
                    "examples": ["business logic only", "UI changes", "test additions"],
                },
            },
        }

        questions[f"{prefix}_has_api_changes"] = {
            "type": "noul",
            "instructions": (
                f"Evaluate ONLY [File {local_idx + 1}]. True when changes modify public "
                "API surfaces: HTTP endpoints, exported function signatures, CLI args, response shapes."
            ),
            "criteria": {
                "true": {
                    "what": "Public API surface modified",
                    "examples": ["endpoint added/removed", "function signature changed", "response format altered"],
                    "not_for": "Internal helper functions or private methods.",
                },
                "false": {
                    "what": "No public API changes",
                    "examples": ["internal refactor", "private helper modified", "test changes"],
                },
            },
        }

        questions[f"{prefix}_has_config_changes"] = {
            "type": "noul",
            "instructions": (
                f"Evaluate ONLY [File {local_idx + 1}]. True when changes modify "
                "configuration, environment variables, feature flags, or build settings."
            ),
            "criteria": {
                "true": {
                    "what": "Configuration or environment settings changed",
                    "examples": ["env var added", "build flag changed", "config key renamed"],
                },
                "false": {
                    "what": "No configuration changes",
                    "examples": ["application logic only", "test code", "documentation"],
                },
            },
        }

        questions[f"{prefix}_is_generated_code"] = {
            "type": "noul",
            "instructions": (
                f"Evaluate ONLY [File {local_idx + 1}]. True when the file is auto-generated: "
                "lockfiles, compiled output, schema-generated types, migration files from a generator."
            ),
            "criteria": {
                "true": {
                    "what": "Auto-generated or machine-produced file",
                    "examples": ["package-lock.json", "go.sum", "generated.ts from schema", ".pb.go protobuf output"],
                    "not_for": "Files that look repetitive but were hand-written.",
                },
                "false": {
                    "what": "Hand-written source code or documentation",
                    "examples": ["application source file", "test file", "README", "config written by a human"],
                },
            },
        }

        questions[f"{prefix}_change_complexity"] = {
            "type": "score",
            "instructions": (
                f"Rate ONLY [File {local_idx + 1}] for change complexity — how hard is it to "
                "review this diff correctly? Consider: number of hunks, conceptual density, "
                "interaction with other code, and the ratio of lines changed to logic altered."
            ),
            "criteria": [
                "Trivial (rename, format, one-line fix)",
                "Simple (single focused change, clear intent)",
                "Moderate (multiple hunks, some interaction with other code)",
                "Complex (significant logic change, multiple concerns)",
                "Very complex (architectural change, many interactions, hard to verify)",
            ],
        }

    state = "\n".join(state_parts)
    return {"state": state, "model": jev_router_common.JEV_MODEL, "questions": questions}


# Answer parsing.

# Short label extracted from the risk level string (everything before the parenthetical).
_RISK_LABEL_RE = re.compile(r"^([^(]+)")


def _short_risk(risk_str: str) -> str:
    """Extract 'High risk' from 'High risk (auth, security, data, core logic)'."""
    match = _RISK_LABEL_RE.match(risk_str)
    return match.group(1).strip() if match else risk_str


def _resolve_risk(risk_answer: dict) -> tuple[float | None, int | None, str]:
    """Return (risk_score, risk_level, risk label) for one file's risk answer.

    Numeric ``score`` (live Jev) is primary. A legacy label string in
    ``choice``/``score`` is matched by equality. Unknown -> (None, None, "unknown").
    """
    level = jev_router_common.score_level(risk_answer, len(RISK_LEVELS))
    if level is not None:
        return float(risk_answer["score"]), level, RISK_LEVELS[level]
    legacy = risk_answer.get("choice", risk_answer.get("score"))
    if isinstance(legacy, str) and legacy in RISK_LEVELS:
        return None, RISK_LEVELS.index(legacy), legacy
    return None, None, "unknown"


def _parse_batch_answers(
    answers: dict,
    batch_indices: list[int],
    file_summaries: list[dict],
    threshold: float,
) -> list[dict]:
    """Parse Jev answers for one batch into per-file result dicts."""
    results: list[dict] = []

    for local_idx, global_idx in enumerate(batch_indices):
        prefix = f"file_{local_idx + 1}"
        file_info = file_summaries[global_idx]

        # Live Jev Score: ``score`` is a weighted mean of 0..len(RISK_LEVELS)-1.
        # Keep the mean (risk_score), the bucket (risk_level), and the label (risk).
        risk_answer = answers.get(f"{prefix}_risk", {})
        risk_score, risk_level, risk_raw = _resolve_risk(risk_answer)

        needs_review_key = f"{prefix}_needs_review"
        needs_review = float(answers[needs_review_key]["noul"]) if needs_review_key in answers else 0.0

        auto_merge_key = f"{prefix}_auto_mergeable"
        auto_mergeable = float(answers[auto_merge_key]["noul"]) if auto_merge_key in answers else 0.0

        # v2: parse additional per-file signals.
        security_key = f"{prefix}_has_security_changes"
        has_security = float(answers.get(security_key, {}).get("noul", 0.0)) if security_key in answers else 0.0

        api_key = f"{prefix}_has_api_changes"
        has_api = float(answers.get(api_key, {}).get("noul", 0.0)) if api_key in answers else 0.0

        config_key = f"{prefix}_has_config_changes"
        has_config = float(answers.get(config_key, {}).get("noul", 0.0)) if config_key in answers else 0.0

        gen_key = f"{prefix}_is_generated_code"
        is_generated = float(answers.get(gen_key, {}).get("noul", 0.0)) if gen_key in answers else 0.0

        complexity_key = f"{prefix}_change_complexity"
        change_complexity = "Simple (single focused change, clear intent)"
        if complexity_key in answers:
            complexity_answer = answers[complexity_key]
            change_complexity = complexity_answer.get("choice") or complexity_answer.get("score", change_complexity)

        results.append(
            {
                "path": file_info["path"],
                "risk": _short_risk(risk_raw),
                "risk_raw": risk_raw,
                "risk_score": risk_score,
                "risk_level": risk_level,
                "needs_review": round(needs_review, 3),
                "auto_mergeable": round(auto_mergeable, 3),
                "has_security_changes": round(has_security, 3),
                "has_api_changes": round(has_api, 3),
                "has_config_changes": round(has_config, 3),
                "is_generated_code": round(is_generated, 3),
                "change_complexity": change_complexity,
                "lines_added": file_info["lines_added"],
                "lines_removed": file_info["lines_removed"],
                "hunk_count": file_info["hunk_count"],
                "file_type": file_info["file_type"],
                "patterns": file_info.get("patterns", []),
                "change_types": file_info.get("change_types", []),
            }
        )

    return results


# Priority sorting.


def _risk_weight(f: dict) -> int:
    """Sort weight for one file: ``risk_level`` first, label fallback, 0 unknown."""
    level = f.get("risk_level")
    if isinstance(level, int) and not isinstance(level, bool):
        return level
    return RISK_WEIGHT.get(f.get("risk_raw", ""), 0)


def _assign_priority(files: list[dict], threshold: float) -> list[dict]:
    """Sort files for review and assign a 1-based ``priority`` rank.

    Files at or above ``threshold`` on ``needs_review`` sort first; within
    each group, higher ``risk_level`` first, then higher ``needs_review``.
    A file below the threshold is demoted behind every file above it, even
    when its risk level is higher.
    """

    def sort_key(f: dict) -> tuple[int, int, float]:
        needs_review = f.get("needs_review", 0.0)
        demoted = 0 if needs_review >= threshold else 1
        return (demoted, -_risk_weight(f), -needs_review)

    files.sort(key=sort_key)
    for idx, f in enumerate(files):
        f["priority"] = idx + 1
    return files


# Public API.


def triage_diff(
    diff_text: str,
    *,
    threshold: float = DEFAULT_THRESHOLD,
    batch_size: int = DEFAULT_BATCH_SIZE,
    timeout: float = DEFAULT_TIMEOUT,
) -> dict:
    """Triage a diff's files for review priority using Jev.

    Importable by other scripts for composability.

    Args:
        diff_text: Unified diff content.
        threshold: Noul score above which needs_review is considered true.
        batch_size: Files per Jev call.
        timeout: HTTP timeout per Jev call in seconds.

    Returns:
        Structured result dict with per-file classifications and aggregates.
    """
    available, reason = jev_router_common.typesafe_available()
    if not available:
        return {
            "error": f"TypeSafe unavailable: {reason}",
            "files_triaged": 0,
            "review_required": 0,
            "auto_mergeable": 0,
            "files": [],
            "latency_ms": 0,
            "jev_calls": 0,
        }

    file_summaries = _parse_diff(diff_text)

    if not file_summaries:
        return {
            "files_triaged": 0,
            "review_required": 0,
            "auto_mergeable": 0,
            "files": [],
            "latency_ms": 0,
            "jev_calls": 0,
        }

    api_key = os.environ.get("TYPESAFE_API_KEY", "").strip()

    batches: list[list[int]] = []
    for i in range(0, len(file_summaries), batch_size):
        batches.append(list(range(i, min(i + batch_size, len(file_summaries)))))

    all_results: list[dict] = []
    total_latency_ms = 0.0
    jev_calls = 0

    for batch_indices in batches:
        payload = _build_batch_payload(file_summaries, batch_indices)
        try:
            data, latency_ms = jev_router_common.call_jev(payload, api_key, timeout, script_name="jev-diff-triage.py")
            total_latency_ms += latency_ms
            jev_calls += 1
            batch_results = _parse_batch_answers(data["answers"], batch_indices, file_summaries, threshold)
            all_results.extend(batch_results)
        except Exception as exc:
            print(f"[jev-diff-triage] batch call failed: {type(exc).__name__}: {exc}", file=sys.stderr)
            # Emit conservative placeholders for the failed batch: assume
            # review is needed so nothing slips through silently.
            for global_idx in batch_indices:
                fi = file_summaries[global_idx]
                all_results.append(
                    {
                        "path": fi["path"],
                        "risk": "unknown",
                        "risk_raw": "unknown",
                        "risk_score": None,
                        "risk_level": None,
                        "needs_review": 1.0,
                        "auto_mergeable": 0.0,
                        "lines_added": fi["lines_added"],
                        "lines_removed": fi["lines_removed"],
                        "hunk_count": fi["hunk_count"],
                        "file_type": fi["file_type"],
                        "patterns": fi.get("patterns", []),
                        "change_types": fi.get("change_types", []),
                        "error": f"{type(exc).__name__}: {str(exc)[:200]}",
                    }
                )

    # Assign priority (sorts in place).
    all_results = _assign_priority(all_results, threshold)

    review_required = sum(1 for r in all_results if r["needs_review"] >= threshold)
    auto_mergeable_count = sum(1 for r in all_results if r["auto_mergeable"] >= threshold)

    return {
        "files_triaged": len(all_results),
        "review_required": review_required,
        "auto_mergeable": auto_mergeable_count,
        "files": all_results,
        "latency_ms": round(total_latency_ms),
        "jev_calls": jev_calls,
    }


# Summary formatter.


def _format_summary(result: dict, threshold: float = DEFAULT_THRESHOLD) -> str:
    """Format a human-readable summary from triage results.

    ``threshold`` must match the one passed to ``triage_diff`` so the
    NEEDS REVIEW / AUTO-MERGEABLE buckets agree with the counts.
    """
    lines: list[str] = []
    lines.append("=" * 60)
    lines.append("  DIFF TRIAGE SUMMARY")
    lines.append("=" * 60)

    if result.get("error"):
        lines.append(f"  Error: {result['error']}")
        lines.append("=" * 60)
        return "\n".join(lines)

    lines.append(f"  Files triaged:       {result['files_triaged']}")
    lines.append(f"  Review required:     {result['review_required']}")
    lines.append(f"  Auto-mergeable:      {result['auto_mergeable']}")
    lines.append(f"  Jev calls:           {result['jev_calls']}")
    lines.append(f"  Latency:             {result['latency_ms']}ms")

    files = result.get("files", [])
    if not files:
        lines.append("")
        lines.append("  No files to triage.")
        lines.append("=" * 60)
        return "\n".join(lines)

    review_files = [f for f in files if f["needs_review"] >= threshold]
    if review_files:
        lines.append("")
        lines.append("  NEEDS REVIEW:")
        for f in review_files:
            lines.append(
                f"    [{f['priority']:>2}] {f['path']}"
                f"  risk={f['risk']}  review={f['needs_review']:.2f}"
                f"  +{f['lines_added']} -{f['lines_removed']}"
            )
            if f.get("patterns"):
                lines.append(f"         patterns: {', '.join(f['patterns'])}")

    auto_files = [f for f in files if f["auto_mergeable"] >= threshold]
    if auto_files:
        lines.append("")
        lines.append("  AUTO-MERGEABLE:")
        for f in auto_files:
            lines.append(f"    [{f['priority']:>2}] {f['path']}  risk={f['risk']}")

    lines.append("=" * 60)
    return "\n".join(lines)


# CLI.


def main() -> int:
    """CLI entry point."""
    parser = argparse.ArgumentParser(
        description="Fast per-file diff triage using Jev classifications.",
    )
    input_group = parser.add_mutually_exclusive_group()
    input_group.add_argument("--diff-file", help="Path to a diff file to triage.")
    input_group.add_argument("--pr", type=int, help="GitHub PR number (fetches diff via gh CLI).")
    parser.add_argument(
        "--threshold",
        type=float,
        default=DEFAULT_THRESHOLD,
        help=f"Noul score above which needs_review is considered true (default {DEFAULT_THRESHOLD}).",
    )
    parser.add_argument(
        "--batch-size",
        type=int,
        default=DEFAULT_BATCH_SIZE,
        help=f"Files per Jev call (default {DEFAULT_BATCH_SIZE}).",
    )
    parser.add_argument("--json-compact", action="store_true", help="Compact JSON output.")
    parser.add_argument("--summary", action="store_true", help="Human-readable summary instead of JSON.")
    parser.add_argument(
        "--timeout",
        type=float,
        default=DEFAULT_TIMEOUT,
        help=f"Jev HTTP call timeout in seconds (default {DEFAULT_TIMEOUT}).",
    )
    args = parser.parse_args()

    try:
        if args.diff_file:
            diff_text = Path(args.diff_file).read_text(encoding="utf-8")
        elif args.pr is not None:
            proc = subprocess.run(
                ["gh", "pr", "diff", str(args.pr)],
                capture_output=True,
                text=True,
                timeout=30,
                check=False,
            )
            if proc.returncode != 0:
                error_msg = proc.stderr.strip() or f"gh pr diff exited {proc.returncode}"
                print(f"[jev-diff-triage] gh pr diff failed: {error_msg}", file=sys.stderr)
                error_result = {
                    "error": f"gh pr diff failed: {error_msg}",
                    "files_triaged": 0,
                    "review_required": 0,
                    "auto_mergeable": 0,
                    "files": [],
                    "latency_ms": 0,
                    "jev_calls": 0,
                }
                print(json.dumps(error_result))
                return 0
            diff_text = proc.stdout
        elif not sys.stdin.isatty():
            diff_text = sys.stdin.read()
        else:
            print("[jev-diff-triage] no input: use --diff-file, --pr, or pipe to stdin", file=sys.stderr)
            print(
                json.dumps(
                    {
                        "error": "no input provided",
                        "files_triaged": 0,
                        "review_required": 0,
                        "auto_mergeable": 0,
                        "files": [],
                        "latency_ms": 0,
                        "jev_calls": 0,
                    }
                )
            )
            return 0

        result = triage_diff(diff_text, threshold=args.threshold, batch_size=args.batch_size, timeout=args.timeout)

        if args.summary:
            print(_format_summary(result, threshold=args.threshold))
        else:
            indent = None if args.json_compact else 2
            print(json.dumps(result, indent=indent))

    except Exception as exc:
        import traceback

        traceback.print_exc(file=sys.stderr)
        error_result = {
            "error": f"{type(exc).__name__}: {str(exc)[:200]}",
            "files_triaged": 0,
            "review_required": 0,
            "auto_mergeable": 0,
            "files": [],
            "latency_ms": 0,
            "jev_calls": 0,
        }
        print(json.dumps(error_result))

    return 0


if __name__ == "__main__":
    sys.exit(main())
