#!/usr/bin/env python3
"""Scan a PR diff for AI slop using the TypeSafe Jev API.

Detects pointless comments, over-engineered functions, boilerplate code,
dead code, and meaningless names. Uses one batched Jev API call per changed
file for fast, cheap semantic classification instead of expensive LLM passes.

Input: unified diff via --diff-file, --pr (gh pr diff), or stdin.
Output: structured JSON findings to stdout.

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
import time
from pathlib import Path

_SCRIPTS_DIR = Path(__file__).resolve().parent
if str(_SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS_DIR))
import jev_router_common

DEFAULT_THRESHOLD = 0.6
DEFAULT_TIMEOUT = 8.0

# Comment patterns by language (applied to added lines after stripping the leading +).
_COMMENT_RE = re.compile(
    r"^\s*(?:"
    r"//.*"  # C-style single-line
    r"|#(?!!)\s.*"  # Python/shell (exclude shebangs)
    r"|/\*.*\*/"  # Single-line block comment
    r'|""".*?"""'  # Python docstring single-line
    r"|'''.*?'''"  # Python docstring single-line
    r"|--\s.*"  # SQL/Haskell
    r")\s*$"
)


# Ordered low -> high. No numerals in the labels: Jev returns ``score`` as a
# weighted mean of the level index 0..4, so a numeral in the text gives it
# nothing to match. ``slop_density_level`` in results is 1-based for humans.
SLOP_DENSITY_CRITERIA = [
    "No slop detected, code reads as human-written",
    "Minor (1-2 isolated instances, mostly clean)",
    "Moderate (slop patterns present but mixed with good code)",
    "Heavy (slop patterns throughout, reads as LLM-generated)",
    "Pervasive (entire diff reads as unedited LLM output)",
]
_LEGACY_NUMERAL_RE = re.compile(r"^\s*\d+\s*[—-]+\s*")


def _resolve_slop_density(answer: dict) -> tuple[float | None, int | None, str]:
    """Return (mean, 1-based level, label) for the slop_density Score answer.

    Numeric ``score`` (live Jev) is primary. A legacy label string, with or
    without a leading numeral, is matched by text. Unknown -> (None, None, "Unknown").
    """
    level0 = jev_router_common.score_level(answer, len(SLOP_DENSITY_CRITERIA))
    if level0 is not None:
        return float(answer["score"]), level0 + 1, SLOP_DENSITY_CRITERIA[level0]
    legacy = answer.get("score", answer.get("choice"))
    if isinstance(legacy, str):
        stripped = _LEGACY_NUMERAL_RE.sub("", legacy).strip()
        if stripped in SLOP_DENSITY_CRITERIA:
            idx = SLOP_DENSITY_CRITERIA.index(stripped)
            return None, idx + 1, SLOP_DENSITY_CRITERIA[idx]
    return None, None, "Unknown"


def _parse_diff(diff_text: str) -> list[dict]:
    """Parse unified diff into per-file records with hunk text and added lines.

    Returns a list of dicts:
        {"file": str, "hunk": str, "added_lines": list[{"lineno": int, "text": str}]}

    Binary files, empty diffs, and files with no added lines are skipped.
    """
    file_records: list[dict] = []
    current_file: str | None = None
    hunk_lines: list[str] = []
    added_lines: list[dict] = []
    lineno = 0

    def _flush() -> None:
        nonlocal current_file, hunk_lines, added_lines
        if current_file and added_lines:
            file_records.append(
                {
                    "file": current_file,
                    "hunk": "\n".join(hunk_lines),
                    "added_lines": list(added_lines),
                }
            )
        current_file = None
        hunk_lines = []
        added_lines = []

    for raw_line in diff_text.splitlines():
        # New file header.
        if raw_line.startswith("diff --git "):
            _flush()
            # Extract b/ path.
            parts = raw_line.split(" b/", 1)
            if len(parts) == 2:
                current_file = parts[1]
            continue

        # Skip binary files.
        if raw_line.startswith("Binary files "):
            current_file = None
            continue

        # Hunk header -- reset line counter.
        if raw_line.startswith("@@"):
            match = re.search(r"\+(\d+)", raw_line)
            lineno = int(match.group(1)) if match else 0
            hunk_lines.append(raw_line)
            continue

        if current_file is None:
            continue

        hunk_lines.append(raw_line)
        if raw_line.startswith("+") and not raw_line.startswith("+++"):
            added_lines.append({"lineno": lineno, "text": raw_line[1:]})
            lineno += 1
        elif raw_line.startswith("-") and not raw_line.startswith("---"):
            # Removed lines do not advance the target line counter.
            pass
        else:
            lineno += 1

    _flush()
    return file_records


def _extract_comments(added_lines: list[dict]) -> list[dict]:
    """Extract comment lines from added lines.

    Returns list of {"lineno": int, "text": str} for lines matching comment patterns.
    """
    return [line for line in added_lines if _COMMENT_RE.match(line["text"])]


def _build_file_questions(comments: list[dict]) -> dict:
    """Build the Jev questions dict for one file's diff hunk.

    v2: 11 aggregate questions (each isolating one slop dimension) + 1 Score
    + per-comment Nouls when >3 comments. Criteria encode the hard cases
    where slop detection is ambiguous.
    """
    questions: dict[str, dict] = {}

    questions["has_comments_restating_code"] = {
        "type": "noul",
        "instructions": (
            "True when added comments restate what the code obviously does, using different "
            "words but adding no information. The distinction: a comment explaining WHY is "
            "useful even if it describes the code; a comment saying 'increment counter' next "
            "to 'i += 1' is pure restatement."
        ),
        "criteria": {
            "true": {
                "what": "Comment restates the code in different words without adding context",
                "examples": [
                    "'// increment counter' next to i += 1",
                    "'// return the result' above return result",
                    "'# loop through items' above for item in items:",
                    "'// set name to value' above self.name = value",
                ],
                "not_for": (
                    "Comments that explain WHY even if they mention what the code does. "
                    "'// increment retry counter — we allow up to 3 before failing' describes "
                    "the code but adds the retry policy context."
                ),
            },
            "false": {
                "what": "Comment adds context the code alone does not convey",
                "examples": [
                    "'// Retry limit: API rate-limits at 100/s' — explains why the number matters",
                    "'// Must hold lock before read — concurrent writers possible' — documents invariant",
                    "'// Legacy format: clients prior to v3 send this shape' — documents compatibility reason",
                ],
            },
        },
    }

    questions["has_overengineered_abstractions"] = {
        "type": "noul",
        "instructions": (
            "True when added code introduces abstraction layers, design patterns, or indirection "
            "beyond what the problem requires. The distinction: a factory pattern with one "
            "implementation is overengineering; an interface with three implementations is not."
        ),
        "criteria": {
            "true": {
                "what": "Abstraction that serves no current purpose",
                "examples": [
                    "Factory pattern for a single implementation that will never be swapped",
                    "Abstract base class with exactly one concrete subclass",
                    "Strategy pattern where a simple if/else covers all cases",
                    "Generic type parameters on a function called in one place with one type",
                ],
                "not_for": (
                    "Abstractions that serve multiple implementations or have documented "
                    "extension points. An interface with two implementations is appropriate "
                    "even if one was added recently."
                ),
            },
            "false": {
                "what": "Abstraction justified by current usage",
                "examples": [
                    "Interface implemented by multiple concrete types",
                    "Error handler covering genuinely different failure modes",
                    "Generic utility imported and used in multiple modules",
                ],
            },
        },
    }

    questions["has_boilerplate_error_handling"] = {
        "type": "noul",
        "instructions": (
            "True when added error handling follows a generic template without adapting to the "
            "specific error conditions: catch-all exceptions with generic messages, identical "
            "try/catch blocks copy-pasted around different operations, or error handling that "
            "catches errors it cannot meaningfully recover from."
        ),
        "criteria": {
            "true": {
                "what": "Generic error handling not adapted to the specific operation",
                "examples": [
                    "except Exception as e: print(f'Error: {e}') — catches everything, helps nothing",
                    "Identical try/catch wrapper around 5 different API calls with the same generic message",
                    "catch(error) { console.error('Something went wrong') } — no specifics",
                ],
                "not_for": (
                    "Broad catches that are intentional fail-safe designs. A top-level "
                    "catch-all in a hook that must exit 0 is intentional, not boilerplate."
                ),
            },
            "false": {
                "what": "Error handling specific to the operation's failure modes",
                "examples": [
                    "except ConnectionError: retry with backoff — specific error, specific recovery",
                    "except json.JSONDecodeError: return fallback_default — specific error, specific action",
                    "if response.status_code == 429: wait and retry — rate limit handling",
                ],
            },
        },
    }

    questions["has_generic_variable_names"] = {
        "type": "noul",
        "instructions": (
            "True when added code uses vague, generic names that force the reader to trace "
            "the variable to understand what it holds. The distinction: 'data' in a generic "
            "utility function is acceptable; 'data' in a domain function where 'user_profile' "
            "or 'order_payload' would be clearer is generic."
        ),
        "criteria": {
            "true": {
                "what": "Names that carry no domain meaning in context",
                "examples": [
                    "'data' for a user profile object",
                    "'result' for a list of matching orders",
                    "'temp' or 'tmp' for a variable that persists beyond the next line",
                    "'handler' or 'processor' when 'auth_validator' or 'diff_parser' fits",
                ],
                "not_for": (
                    "Short names in tight scopes. 'x' in a lambda, 'i' in a loop, 'e' in "
                    "an except clause, 'f' in a file-open block — these are conventional."
                ),
            },
            "false": {
                "what": "Names that tell the reader what the variable holds or does",
                "examples": [
                    "'user_email' instead of 'data'",
                    "'retry_count' instead of 'count'",
                    "'parse_diff_hunks' instead of 'process'",
                ],
            },
        },
    }

    questions["has_redundant_type_annotations"] = {
        "type": "noul",
        "instructions": (
            "True when added type annotations are redundant: annotating what the initializer "
            "already makes obvious, or adding complex generic types that the type checker would "
            "infer. The distinction: 'x: int = 5' is redundant; 'x: UserId' is not (it adds "
            "domain meaning). 'items: list[str] = []' is borderline acceptable for documentation."
        ),
        "criteria": {
            "true": {
                "what": "Type annotation adds no information beyond what the assignment shows",
                "examples": [
                    "x: int = 5 — literal makes the type obvious",
                    "name: str = 'hello' — string literal is obviously str",
                    "d: dict[str, Any] = {} — Any removes all type safety",
                ],
                "not_for": (
                    "Annotations that clarify domain types or narrow broad types. "
                    "'user_id: UserId = row[0]' adds meaning even though row[0] is known."
                ),
            },
            "false": {
                "what": "Annotation adds domain meaning or narrows an ambiguous type",
                "examples": [
                    "timeout: Seconds = config.get('timeout') — 'Seconds' documents the unit",
                    "results: list[Finding] = [] — 'Finding' documents what the list holds",
                    "def process(items: Sequence[T]) -> list[T] — generic bounds on a reusable function",
                ],
            },
        },
    }

    questions["has_apologetic_comments"] = {
        "type": "noul",
        "instructions": (
            "True when added comments apologize, hedge, or express uncertainty in a way that "
            "signals the author did not resolve the issue: 'This might not be ideal', 'Sorry "
            "for the hack', 'Not sure if this is right'. The distinction: a TODO with a "
            "tracking issue is a plan, not an apology."
        ),
        "criteria": {
            "true": {
                "what": "Comment expresses unresolved doubt or apologizes for the code",
                "examples": [
                    "# This is a bit hacky but it works",
                    "// Not sure if this is the right approach",
                    "# Sorry for the mess, will clean up later",
                    "// FIXME: this probably needs to be refactored",
                ],
                "not_for": (
                    "TODOs with tracking issues or concrete plans. "
                    "'# TODO(JIRA-42): migrate to new API' is a tracked plan, not an apology."
                ),
            },
            "false": {
                "what": "Comment states a fact or a tracked plan",
                "examples": [
                    "# TODO(JIRA-42): migrate to v2 API before Q4",
                    "# Known limitation: does not handle concurrent writes (see RFC-103)",
                    "# Workaround for upstream bug #1234, remove after v3.2 release",
                ],
            },
        },
    }

    questions["has_excessive_logging"] = {
        "type": "noul",
        "instructions": (
            "True when added logging is disproportionate to the operation: logging every loop "
            "iteration, logging full request/response bodies at INFO level, or logging entering "
            "and exiting every function. The distinction: debug-level logging in a complex "
            "pipeline is appropriate; INFO-level logging of every variable assignment is not."
        ),
        "criteria": {
            "true": {
                "what": "Logging volume disproportionate to the operation's complexity",
                "examples": [
                    "logger.info() inside a tight loop processing thousands of items",
                    "Logging full request and response bodies at INFO level",
                    "Log statements at entry and exit of every function",
                    "logger.debug(f'Processing item {i}: {item}') in a loop over 10k items",
                ],
                "not_for": (
                    "Targeted debug logging at key decision points. Logging the final result "
                    "of a pipeline, or logging when a retry occurs, is appropriate."
                ),
            },
            "false": {
                "what": "Logging at key decision points proportionate to the operation",
                "examples": [
                    "logger.info('Processing batch of %d items', len(batch)) — once per batch",
                    "logger.warning('Retry %d/%d after %s', attempt, max_retries, error)",
                    "logger.debug('Cache miss for key %s', key) — debug level, not info",
                ],
            },
        },
    }

    questions["has_cargo_cult_patterns"] = {
        "type": "noul",
        "instructions": (
            "True when added code copies patterns from elsewhere without understanding why they "
            "exist: unused configuration that was copied from a template, defensive checks for "
            "conditions that cannot occur in this context, or patterns from a different framework "
            "applied to this one."
        ),
        "criteria": {
            "true": {
                "what": "Code patterns copied without contextual justification",
                "examples": [
                    "null check on a value guaranteed non-null by the type system",
                    "Thread synchronization in single-threaded code",
                    "CORS headers on an internal-only endpoint",
                    "Connection pooling config copied from a template but never tuned",
                ],
                "not_for": (
                    "Defensive coding in APIs where callers are not trusted. "
                    "A public endpoint validating input is defensive, not cargo cult."
                ),
            },
            "false": {
                "what": "Patterns applied because the context requires them",
                "examples": [
                    "Null check on external API response — external data is untrusted",
                    "Thread safety in code called from a concurrent handler",
                    "CORS headers on a public API endpoint",
                ],
            },
        },
    }

    questions["has_unnecessary_null_checks"] = {
        "type": "noul",
        "instructions": (
            "True when added code checks for null/None/undefined in contexts where the value "
            "is guaranteed non-null by the type system, a preceding guard, or the language semantics. "
            "The distinction: checking a database result for null is prudent; checking a local "
            "variable assigned two lines above is unnecessary."
        ),
        "criteria": {
            "true": {
                "what": "Null check on a value that cannot be null in this context",
                "examples": [
                    "if x is not None: ... — right after x = 5",
                    "Optional check on a field the type system marks as required",
                    "if user is not None: ... — inside a block guarded by 'if user:'",
                ],
                "not_for": (
                    "Null checks on external data, database results, API responses, or "
                    "values from dynamic sources. Those are always prudent."
                ),
            },
            "false": {
                "what": "Null check on a value from an untrusted or dynamic source",
                "examples": [
                    "if response.data is not None: ... — API response could be null",
                    "if row is not None: ... — database query could return nothing",
                    "if config.get('timeout') is not None: ... — config key may be absent",
                ],
            },
        },
    }

    questions["has_dead_code"] = {
        "type": "noul",
        "instructions": (
            "True when added code is unreachable, commented-out, or demonstrably never called. "
            "The distinction: a conditional branch for an edge case is reachable even if rare; "
            "code after an unconditional return is truly dead."
        ),
        "criteria": {
            "true": {
                "what": "Code that provably cannot execute",
                "examples": [
                    "Code after an unconditional return/raise/break",
                    "Commented-out function body left in the diff",
                    "Import that nothing in the file references",
                    "Function defined but never called and not exported",
                ],
                "not_for": (
                    "Conditional branches for rare edge cases. An 'except KeyError' in a "
                    "dict lookup is reachable even if the key is usually present."
                ),
            },
            "false": {
                "what": "All added code has a reachable execution path",
                "examples": [
                    "Guard clause that returns early on invalid input",
                    "Exception handler for a known failure mode",
                    "Fallback branch in a match/switch statement",
                ],
            },
        },
    }

    questions["slop_density"] = {
        "type": "score",
        "instructions": (
            "Rate the overall density of AI-generated slop patterns in this diff. "
            "Consider all signals together: restating comments, overengineered abstractions, "
            "boilerplate error handling, generic names, cargo cult patterns, dead code."
        ),
        "criteria": SLOP_DENSITY_CRITERIA,
    }

    # Per-comment questions (only when >3 comments).
    if len(comments) > 3:
        for i, comment in enumerate(comments):
            comment_preview = comment["text"].strip()[:80]
            questions[f"comment_{i}_useful"] = {
                "type": "noul",
                "instructions": f"Does this comment add information a reader needs? Comment: {comment_preview!r}",
            }
            questions[f"comment_{i}_accurate"] = {
                "type": "noul",
                "instructions": f"Does this comment match what the surrounding code does? Comment: {comment_preview!r}",
            }

    return questions


def scan_diff(
    diff_text: str,
    *,
    threshold: float = DEFAULT_THRESHOLD,
    timeout: float = DEFAULT_TIMEOUT,
    verbose: bool = False,
) -> dict:
    """Scan a unified diff for AI slop. Returns the full result dict.

    Importable by other scripts. Never raises -- errors are captured in
    the result dict.
    """
    scan_start = time.monotonic()

    available, reason = jev_router_common.typesafe_available()
    if not available:
        return {
            "error": f"TypeSafe unavailable: {reason}",
            "files_scanned": 0,
            "files_flagged": 0,
            "total_findings": 0,
            "findings": [],
            "latency_ms": 0,
            "jev_calls": 0,
        }

    api_key = os.environ.get("TYPESAFE_API_KEY", "").strip()

    file_diffs = _parse_diff(diff_text)
    if not file_diffs:
        return {
            "files_scanned": 0,
            "files_flagged": 0,
            "total_findings": 0,
            "findings": [],
            "latency_ms": 0,
            "jev_calls": 0,
        }

    file_findings: list[dict] = []
    errors: list[dict] = []
    total_latency_ms = 0.0
    jev_calls = 0
    flagged_check_count = 0

    for file_diff in file_diffs:
        comments = _extract_comments(file_diff["added_lines"])
        questions = _build_file_questions(comments)

        payload = {
            "state": file_diff["hunk"],
            "model": jev_router_common.JEV_MODEL,
            "questions": questions,
        }

        if verbose:
            print(
                f"[slop-scan] scanning {file_diff['file']} ({len(file_diff['added_lines'])} added lines, "
                f"{len(comments)} comments, {len(questions)} questions)",
                file=sys.stderr,
            )

        try:
            data, latency_ms = jev_router_common.call_jev(payload, api_key, timeout, script_name="jev-pr-slop-scan.py")
            total_latency_ms += latency_ms
            jev_calls += 1
        except Exception as exc:
            message = f"{type(exc).__name__}: {str(exc)[:200]}"
            print(f"[slop-scan] jev call failed for {file_diff['file']}: {message}", file=sys.stderr)
            errors.append({"file": file_diff["file"], "error": message})
            continue

        answers = data.get("answers", {})
        file_result = _parse_file_answers(file_diff["file"], answers, comments, threshold)
        if file_result["flagged"]:
            flagged_check_count += sum(1 for f in file_result["flags"].values() if f["flagged"])
            flagged_check_count += sum(1 for c in file_result.get("comments", []) if c["flagged"])

        file_findings.append(file_result)

    scan_latency_ms = round((time.monotonic() - scan_start) * 1000.0)
    files_flagged = sum(1 for f in file_findings if f["flagged"])

    # files_scanned counts files that got a Jev answer; files_attempted counts
    # every file in the diff, so a failed call never hides inside a clean total.
    return {
        "files_attempted": len(file_diffs),
        "files_scanned": len(file_findings),
        "files_failed": len(errors),
        "files_flagged": files_flagged,
        "total_findings": flagged_check_count,
        "findings": file_findings,
        "errors": errors,
        "latency_ms": scan_latency_ms,
        "jev_calls": jev_calls,
    }


def _parse_file_answers(
    filename: str,
    answers: dict,
    comments: list[dict],
    threshold: float,
) -> dict:
    """Parse Jev answers for one file into a finding dict."""
    slop_density_score, slop_density_level, slop_density = _resolve_slop_density(answers.get("slop_density", {}))

    noul_check_mapping = [
        ("comments_restating_code", "has_comments_restating_code"),
        ("overengineered_abstractions", "has_overengineered_abstractions"),
        ("boilerplate_error_handling", "has_boilerplate_error_handling"),
        ("generic_variable_names", "has_generic_variable_names"),
        ("redundant_type_annotations", "has_redundant_type_annotations"),
        ("apologetic_comments", "has_apologetic_comments"),
        ("excessive_logging", "has_excessive_logging"),
        ("cargo_cult_patterns", "has_cargo_cult_patterns"),
        ("unnecessary_null_checks", "has_unnecessary_null_checks"),
        ("dead_code", "has_dead_code"),
    ]
    flags: dict[str, dict] = {}
    has_flagged_check = False
    for flag_name, question_key in noul_check_mapping:
        answer = answers.get(question_key, {})
        score = float(answer.get("noul", 0.0))
        flagged = score >= threshold
        flags[flag_name] = {"flagged": flagged, "score": round(score, 3)}
        if flagged:
            has_flagged_check = True

    per_comment_verdicts: list[dict] = []
    if len(comments) > 3:
        for i, comment in enumerate(comments):
            useful_answer = answers.get(f"comment_{i}_useful", {})
            accurate_answer = answers.get(f"comment_{i}_accurate", {})
            useful_score = float(useful_answer.get("noul", 0.5))
            accurate_score = float(accurate_answer.get("noul", 0.5))
            # A comment is flagged when it scores LOW on usefulness.
            flagged = useful_score < (1.0 - threshold)
            per_comment_verdicts.append(
                {
                    "line": comment["lineno"],
                    "text": comment["text"].strip(),
                    "useful": round(useful_score, 3),
                    "accurate": round(accurate_score, 3),
                    "flagged": flagged,
                }
            )
            if flagged:
                has_flagged_check = True

    return {
        "file": filename,
        "slop_density": slop_density,
        "slop_density_score": slop_density_score,
        "slop_density_level": slop_density_level,
        "flags": flags,
        "comments": per_comment_verdicts,
        "flagged": has_flagged_check,
    }


def _format_summary(result: dict) -> str:
    """Format scan result as a human-readable summary."""
    lines: list[str] = []

    if "error" in result:
        return f"Error: {result['error']}"

    lines.append(
        f"Scanned {result['files_scanned']} files, {result['files_flagged']} flagged, "
        f"{result['total_findings']} findings ({result['latency_ms']}ms, {result['jev_calls']} Jev calls)"
    )
    lines.append("")

    for file_scan in result["findings"]:
        if not file_scan["flagged"]:
            continue
        level = file_scan.get("slop_density_level")
        level_text = f"{level}/{len(SLOP_DENSITY_CRITERIA)} " if level is not None else ""
        lines.append(f"  {file_scan['file']}  (slop density: {level_text}{file_scan['slop_density']})")
        for flag_name, flag_data in file_scan["flags"].items():
            if flag_data["flagged"]:
                label = flag_name.replace("_", " ")
                lines.append(f"    - {label}: {flag_data['score']:.2f}")
        for comment in file_scan.get("comments", []):
            if comment["flagged"]:
                comment_preview = comment["text"][:60]
                lines.append(f"    - L{comment['line']}: {comment_preview!r} (useful={comment['useful']:.2f})")
        lines.append("")

    if result["files_flagged"] == 0:
        lines.append("  No slop detected.")

    for err in result.get("errors", []):
        lines.append(f"  [ERROR] {err['file']}: {err['error']}")

    return "\n".join(lines)


def _read_diff(args: argparse.Namespace) -> str:
    """Read diff text from the source specified by CLI args."""
    if args.diff_file:
        return Path(args.diff_file).read_text(encoding="utf-8")
    if args.pr is not None:
        proc = subprocess.run(
            ["gh", "pr", "diff", str(args.pr)],
            capture_output=True,
            text=True,
            timeout=30,
            check=False,
        )
        if proc.returncode != 0:
            print(f"[slop-scan] gh pr diff failed: {proc.stderr.strip()[:200]}", file=sys.stderr)
            return ""
        return proc.stdout
    if sys.stdin.isatty():
        print("[slop-scan] reading diff from stdin (pipe a diff or use --diff-file / --pr)", file=sys.stderr)
    return sys.stdin.read()


def main() -> int:
    """CLI entry point."""
    parser = argparse.ArgumentParser(
        description="Scan a PR diff for AI slop using the TypeSafe Jev API.",
    )
    input_group = parser.add_mutually_exclusive_group()
    input_group.add_argument(
        "--diff-file",
        help="Path to a unified diff file.",
    )
    input_group.add_argument(
        "--pr",
        type=int,
        help="GitHub PR number (runs gh pr diff).",
    )
    parser.add_argument(
        "--threshold",
        type=float,
        default=DEFAULT_THRESHOLD,
        help=f"Noul score above this = flagged (default {DEFAULT_THRESHOLD}).",
    )
    parser.add_argument(
        "--timeout",
        type=float,
        default=DEFAULT_TIMEOUT,
        help=f"Jev HTTP call timeout in seconds per file (default {DEFAULT_TIMEOUT}).",
    )
    parser.add_argument(
        "--json-compact",
        action="store_true",
        help="Output compact JSON (no indentation).",
    )
    parser.add_argument(
        "--summary",
        action="store_true",
        help="Print human-readable summary instead of JSON.",
    )
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="Print progress to stderr.",
    )
    args = parser.parse_args()

    try:
        diff_text = _read_diff(args)
        result = scan_diff(diff_text, threshold=args.threshold, timeout=args.timeout, verbose=args.verbose)
    except Exception as exc:
        import traceback

        traceback.print_exc(file=sys.stderr)
        result = {
            "error": f"{type(exc).__name__}: {str(exc)[:200]}",
            "files_scanned": 0,
            "files_flagged": 0,
            "total_findings": 0,
            "findings": [],
            "latency_ms": 0,
            "jev_calls": 0,
        }

    if args.summary:
        print(_format_summary(result))
    else:
        indent = None if args.json_compact else 2
        print(json.dumps(result, indent=indent))
    return 0


if __name__ == "__main__":
    sys.exit(main())
