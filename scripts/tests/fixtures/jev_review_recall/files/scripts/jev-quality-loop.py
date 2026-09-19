#!/usr/bin/env python3
"""Iterative Jev quality scoring loop: score, flag, (external fix), re-score, verify.

The Jev LOOP pattern. Takes text (code or prose), scores it with Jev Score and
Noul questions, identifies problems, and re-scores after external modifications
to verify improvement. The loop continues until quality meets threshold or max
iterations are reached.

The script itself does not fix problems -- it provides the scoring loop. An
agent or user applies fixes between iterations. The key property: Jev scores
are cheap enough to run in a tight loop.

Three modes:
  code   -- readability, naming, complexity, slop, dead code, error handling
  prose  -- density, completeness, clarity, AI tells, passive voice, jargon
  review -- meta-scoring of Jev's own findings (genuine, actionable, severity)

Iteration-aware: each iteration's Jev instructions include the PREVIOUS
iteration's scores as context, letting the model focus on whether problems
improved since the last pass.

Usage:
    python3 scripts/jev-quality-loop.py --file src/server.py --mode code --json-compact
    cat draft.md | python3 scripts/jev-quality-loop.py --mode prose --threshold 0.7
    python3 scripts/jev-quality-loop.py --file src/server.py --mode code --iterate --max-iter 3
    python3 scripts/jev-quality-loop.py --findings findings.json --mode review

Exit codes:
    0 -- always (output is JSON to stdout; errors go to stderr)
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

_SCRIPTS_DIR = Path(__file__).resolve().parent
if str(_SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS_DIR))
import jev_router_common

DEFAULT_THRESHOLD = 0.7
DEFAULT_MAX_ITERATIONS = 5
DEFAULT_TIMEOUT = 8.0

# Score criteria per mode. Each Score question maps an ordered list of labels
# from worst to best. The "Acceptable" label (index 2) is the pass threshold
# for Score questions. Noul questions flag when the score exceeds the threshold.

CODE_SCORE_QUESTIONS: dict[str, dict] = {
    "readability": {
        "type": "score",
        "instructions": {"core": "Rate the readability of this code."},
        "criteria": ["Unreadable", "Poor", "Acceptable", "Good", "Excellent"],
    },
    "naming": {
        "type": "score",
        "instructions": {"core": "Rate the quality of variable, function, and class names in this code."},
        "criteria": ["Meaningless names", "Vague", "Acceptable", "Domain-specific", "Self-documenting"],
    },
    "complexity": {
        "type": "score",
        "instructions": {"core": "Rate the complexity level of this code."},
        "criteria": ["Trivially simple", "Appropriate", "Somewhat complex", "Over-engineered", "Deeply nested/complex"],
    },
}

CODE_NOUL_QUESTIONS: dict[str, dict] = {
    "slop": {
        "type": "noul",
        "instructions": "True when the code contains AI-generated boilerplate: obvious LLM patterns, generic placeholder code, or formulaic structure that a human developer would not write.",
        "criteria": {
            "true": {
                "what": "AI-generated boilerplate patterns",
                "examples": [
                    "# TODO: implement this function",
                    "Generic CRUD with no domain logic",
                    "Overly verbose docstrings restating the function name",
                ],
            },
            "false": {
                "what": "Purposeful, domain-specific code",
                "examples": [
                    "Custom validation logic for business rules",
                    "Targeted error handling for known failure modes",
                ],
            },
        },
    },
    "dead_code": {
        "type": "noul",
        "instructions": "True when the code contains unreachable or unused code: commented-out blocks, unreachable branches, unused imports, or functions that nothing calls.",
        "criteria": {
            "true": {
                "what": "Unreachable or unused code",
                "examples": [
                    "# old_function() -- keeping for reference",
                    "if False: ...",
                    "import os  # never used",
                ],
            },
            "false": {
                "what": "All code serves a purpose",
                "examples": [
                    "Conditional branches that handle real edge cases",
                    "Imports used later in the file",
                ],
            },
        },
    },
    "error_handling": {
        "type": "noul",
        "instructions": "True when proper error handling is present: exceptions caught specifically, errors reported usefully, resources cleaned up. False when errors are swallowed, caught too broadly, or absent where needed.",
        "criteria": {
            "true": {
                "what": "Proper error handling present",
                "examples": [
                    "except ValueError as exc: log and re-raise",
                    "try/finally for resource cleanup",
                    "Specific exception types caught",
                ],
            },
            "false": {
                "what": "Missing or poor error handling",
                "examples": [
                    "except: pass",
                    "No try/except around I/O operations",
                    "Bare except swallowing all errors",
                ],
            },
        },
    },
    # v2: additional code quality Nouls.
    "has_type_safety_issues": {
        "type": "noul",
        "instructions": (
            "True when the code has type-related risks: missing type annotations on public APIs, "
            "unsafe casts, Any types where specific types are known, or dynamic attribute access "
            "that bypasses type checking."
        ),
        "criteria": {
            "true": {
                "what": "Type safety gaps that could cause runtime errors",
                "examples": [
                    "Public function with no return type annotation",
                    "Unsafe dict access with [] instead of .get() on untrusted data",
                    "typing.Any used where the actual type is known",
                ],
                "not_for": "Internal helpers where types are obvious from context, or dynamically-typed languages where annotations are not convention.",
            },
            "false": {
                "what": "Types are properly annotated or safely handled",
                "examples": [
                    "All public functions have type annotations",
                    "Dict access uses .get() with defaults for external data",
                    "Specific types used instead of Any",
                ],
            },
        },
    },
    "has_duplication": {
        "type": "noul",
        "instructions": (
            "True when the code contains duplicated logic that should be extracted into a shared "
            "function or constant. Not about similar structure (e.g., test cases) — about identical "
            "logic repeated where a change to one copy must be manually applied to all others."
        ),
        "criteria": {
            "true": {
                "what": "Duplicated logic that creates maintenance risk",
                "examples": [
                    "Same 10-line HTTP call pattern in 3 functions",
                    "Identical validation logic in 2 handlers",
                    "Same error message string hardcoded in 4 places",
                ],
                "not_for": "Similar-looking test cases or intentionally repeated patterns with different semantics.",
            },
            "false": {
                "what": "No problematic duplication",
                "examples": [
                    "Shared logic extracted to helper functions",
                    "Constants used instead of magic values",
                    "Test cases that look similar but test different behavior",
                ],
            },
        },
    },
    "has_hardcoded_values": {
        "type": "noul",
        "instructions": (
            "True when the code contains magic numbers, hardcoded URLs, IP addresses, timeouts, "
            "or configuration values that should be named constants or pulled from config."
        ),
        "criteria": {
            "true": {
                "what": "Magic values that should be named constants or config",
                "examples": [
                    "time.sleep(3.7)",
                    "url = 'http://192.168.1.100:8080'",
                    "if retries > 5:",
                    "timeout=30 scattered across multiple functions",
                ],
                "not_for": "Named constants (DEFAULT_TIMEOUT = 10), 0/1 in boolean contexts, or test fixtures.",
            },
            "false": {
                "what": "Values are named constants or pulled from config",
                "examples": [
                    "MAX_RETRIES = 5; if retries > MAX_RETRIES:",
                    "timeout=DEFAULT_TIMEOUT",
                    "url = os.environ['API_URL']",
                ],
            },
        },
    },
}

# Complexity is inverted: higher scores are WORSE. "Appropriate" (index 1) is
# the acceptable ceiling. Scores above index 2 fail.
_COMPLEXITY_ACCEPTABLE_INDEX = 1

PROSE_SCORE_QUESTIONS: dict[str, dict] = {
    "density": {
        "type": "score",
        "instructions": {
            "core": "Rate the information density of this text. Dense writing carries meaning in every word."
        },
        "criteria": ["Wordy -- heavy padding", "Some filler", "Acceptable", "Dense", "Every word earns its place"],
    },
    "completeness": {
        "type": "score",
        "instructions": {"core": "Rate whether this text covers all the points its topic requires."},
        "criteria": ["Missing key points", "Gaps", "Acceptable", "Complete", "Thorough"],
    },
    "clarity": {
        "type": "score",
        "instructions": {"core": "Rate how clearly this text communicates its ideas."},
        "criteria": ["Confusing", "Unclear spots", "Acceptable", "Clear", "Crystal clear"],
    },
}

PROSE_NOUL_QUESTIONS: dict[str, dict] = {
    "has_ai_tells": {
        "type": "noul",
        "instructions": "True when the text contains AI-tell patterns: generic transitions ('Furthermore', 'Moreover'), hedge stacking ('It's worth noting that'), or filler that adds no information.",
        "criteria": {
            "true": {
                "what": "AI-generated writing patterns",
                "examples": [
                    "Furthermore, it is important to note",
                    "In today's fast-paced world",
                    "It's worth noting that",
                ],
            },
            "false": {
                "what": "Direct, specific writing",
                "examples": [
                    "The cache TTL is 24 hours",
                    "Three things broke in production",
                ],
            },
        },
    },
    "has_passive_voice": {
        "type": "noul",
        "instructions": "True when the text overuses passive constructions, hiding actors. Occasional technical passive is fine; systematic passive avoidance of naming who did what is the flag.",
        "criteria": {
            "true": {
                "what": "Excessive passive construction",
                "examples": [
                    "The feature was implemented",
                    "It has been determined that changes are needed",
                    "The report was generated",
                ],
            },
            "false": {
                "what": "Active voice with clear actors",
                "examples": [
                    "The team shipped the feature",
                    "We determined the root cause",
                ],
            },
        },
    },
    "has_jargon": {
        "type": "noul",
        "instructions": "True when the text uses jargon, buzzwords, or corporate-speak where plain words serve. Technical terms for technical audiences are fine; inflated language is the flag.",
        "criteria": {
            "true": {
                "what": "Jargon where plain words serve",
                "examples": [
                    "leverage synergies",
                    "robust and comprehensive solution",
                    "innovative paradigm shift",
                ],
            },
            "false": {
                "what": "Plain language or necessary technical terms",
                "examples": [
                    "Use the cache to avoid repeated database queries",
                    "The TCP handshake adds 30ms of latency",
                ],
            },
        },
    },
    # v2: additional prose quality Nouls.
    "has_ungrounded_claims": {
        "type": "noul",
        "instructions": (
            "True when the text makes factual claims without evidence, citations, or context that "
            "would let a reader verify them. Opinions clearly marked as opinions are fine."
        ),
        "criteria": {
            "true": {
                "what": "Factual claims without support",
                "examples": [
                    "This approach is 10x faster (no benchmark cited)",
                    "Most developers prefer X (no survey or source)",
                    "The industry is moving towards Y (no evidence)",
                ],
                "not_for": "Clearly-labeled opinions ('I think', 'In my experience') or well-known facts.",
            },
            "false": {
                "what": "Claims are supported or clearly marked as opinion",
                "examples": [
                    "Cache reads cost $0.25/MTok (Fable 5.1 pricing)",
                    "In my experience, this pattern works well for small teams",
                    "Python is dynamically typed (established fact)",
                ],
            },
        },
    },
    "has_conclusion_restating_intro": {
        "type": "noul",
        "instructions": (
            "True when the conclusion or summary paragraph merely restates the introduction "
            "without adding new insight, action items, or forward-looking content."
        ),
        "criteria": {
            "true": {
                "what": "Conclusion repeats what was already said",
                "examples": [
                    "In conclusion, we have explored the benefits of caching (same as intro)",
                    "To summarize, the three key points are... (identical to opening)",
                ],
            },
            "false": {
                "what": "Conclusion adds value beyond the introduction",
                "examples": [
                    "Conclusion names specific next steps",
                    "Summary synthesizes findings into a recommendation",
                    "Ending offers a new perspective not in the intro",
                ],
            },
        },
    },
    "has_excessive_qualifications": {
        "type": "noul",
        "instructions": (
            "True when the text stacks qualifiers and hedges that weaken every statement: "
            "'It might perhaps be possible that...' instead of making a clear claim with an "
            "explicit confidence marker."
        ),
        "criteria": {
            "true": {
                "what": "Stacked hedges that avoid committing to a claim",
                "examples": [
                    "It could potentially be argued that this might help",
                    "This is perhaps one of the approaches that could possibly work",
                    "It should probably be noted that this may sometimes apply",
                ],
                "not_for": "Single honest qualifiers: 'I think', 'probably', 'in some cases'. One hedge is fine; three stacked is the flag.",
            },
            "false": {
                "what": "Clear claims with honest uncertainty markers when needed",
                "examples": [
                    "This approach works for small teams; I haven't tested it at scale",
                    "Jev handles classification. I don't know if it holds up adversarially yet",
                ],
            },
        },
    },
}


# Score evaluation: does a Score label meet the threshold?

# Acceptable is index 2 in the criteria list (0-indexed). Scores at or above
# this index pass. Complexity is inverted: index 0-1 are acceptable, 2+ fail.
ACCEPTABLE_INDEX = 2


def _score_index(criteria: list[str], chosen: object) -> int | None:
    """Resolve a Score answer value to a criteria index.

    Primary path: ``chosen`` is the numeric weighted mean a live Jev Score
    returns; bucket it with ``score_level``. Legacy path: ``chosen`` is a
    label string; match by equality. Anything else -> None.
    """
    if isinstance(chosen, str):
        return criteria.index(chosen) if chosen in criteria else None
    return jev_router_common.score_level({"score": chosen}, len(criteria))


def _score_passes(criteria: list[str], chosen: object, *, inverted: bool = False) -> bool:
    """Return True when the Score answer meets the pass threshold.

    ``chosen`` is the numeric weighted mean from a live Jev Score answer
    (primary) or a legacy label string (matched by equality).

    For normal scores (readability, naming, density, etc.), "Acceptable" (index 2)
    or above passes. For inverted scores (complexity), index 0-1 pass and 2+ fail.
    """
    idx = _score_index(criteria, chosen)
    if idx is None:
        # Unknown label or non-numeric score -- fail safe.
        return False
    if inverted:
        return idx <= _COMPLEXITY_ACCEPTABLE_INDEX
    return idx >= ACCEPTABLE_INDEX


def _score_value_and_label(criteria: list[str], answer: dict) -> tuple[float | str | None, str | None]:
    """Extract (raw score value, level label) from one Score answer.

    Live Jev: ``answer["score"]`` is a float mean -> label is the criteria
    entry at the rounded level. Legacy: ``choice``/``score`` is a label
    string -> returned as-is when it is a known criterion.
    """
    raw = answer.get("choice")
    if raw is None:
        raw = answer.get("score")
    idx = _score_index(criteria, raw)
    label = criteria[idx] if idx is not None else None
    if isinstance(raw, bool) or not isinstance(raw, (int, float, str)):
        raw = None
    return raw, label


#
# Each iteration's instructions include the PREVIOUS iteration's scores as
# context: Nathan's structured JSON instructions pattern (instructions as
# objects, not strings).


def _inject_iteration_context(
    question: dict,
    key: str,
    iteration: int,
    history: list[dict],
) -> dict:
    """Return a copy of the question with iteration-aware instructions.

    On iteration 0, instructions are just the core text. On iteration 1+,
    instructions include previous scores so Jev can evaluate improvement.
    """
    q = dict(question)
    instructions = question.get("instructions", "")

    # String instructions (Noul questions): wrap in an object for consistency.
    if isinstance(instructions, str):
        instructions = {"core": instructions}
    else:
        instructions = dict(instructions)

    if iteration > 0 and history:
        prev_entries: list[dict[str, str | int]] = []
        for h in history:
            prev_score = h.get("scores", {}).get(key) or h.get("flags", {}).get(key)
            if prev_score is not None:
                prev_entries.append({"iteration": h["iteration"], "score": str(prev_score)})
        if prev_entries:
            instructions["prev"] = prev_entries
            instructions["focus"] = f"Has {key} improved since the previous iteration?"

    q["instructions"] = instructions
    return q


def _build_code_questions(iteration: int, history: list[dict]) -> dict[str, dict]:
    """Build the Jev question set for code mode, with iteration context."""
    questions: dict[str, dict] = {}
    for key, q in CODE_SCORE_QUESTIONS.items():
        questions[key] = _inject_iteration_context(q, key, iteration, history)
    for key, q in CODE_NOUL_QUESTIONS.items():
        questions[key] = _inject_iteration_context(q, key, iteration, history)
    return questions


def _build_prose_questions(iteration: int, history: list[dict]) -> dict[str, dict]:
    """Build the Jev question set for prose mode, with iteration context."""
    questions: dict[str, dict] = {}
    for key, q in PROSE_SCORE_QUESTIONS.items():
        questions[key] = _inject_iteration_context(q, key, iteration, history)
    for key, q in PROSE_NOUL_QUESTIONS.items():
        questions[key] = _inject_iteration_context(q, key, iteration, history)
    return questions


def _build_review_questions(findings: list[dict]) -> dict[str, dict]:
    """Build the Jev question set for review mode (meta-scoring findings).

    Each finding gets a genuine/actionable Noul and a severity Score.
    """
    questions: dict[str, dict] = {}
    for i, finding in enumerate(findings):
        prefix = f"finding_{i}"
        # Include the finding text in each question's instructions.
        finding_text = json.dumps(finding, indent=None)
        questions[f"{prefix}_genuine"] = {
            "type": "noul",
            "instructions": f"True when this finding describes a real issue in the code, not a false positive or stylistic nit. Finding: {finding_text}",
        }
        questions[f"{prefix}_actionable"] = {
            "type": "noul",
            "instructions": f"True when someone can fix this finding with a concrete code change. False when the finding is vague or describes a preference with no clear fix. Finding: {finding_text}",
        }
        questions[f"{prefix}_severity"] = {
            "type": "score",
            "instructions": f"Rate the severity of this finding. Finding: {finding_text}",
            "criteria": ["Cosmetic", "Minor", "Moderate", "Major", "Critical"],
        }
    return questions


def _parse_code_iteration(answers: dict, threshold: float) -> dict:
    """Parse Jev answers for one code-mode iteration."""
    scores: dict[str, str | None] = {}
    score_values: dict[str, float | str | None] = {}
    flags: dict[str, float] = {}
    failing: list[str] = []

    for key, q in CODE_SCORE_QUESTIONS.items():
        answer = answers.get(key, {})
        chosen, label = _score_value_and_label(q["criteria"], answer)
        scores[key] = label
        score_values[key] = chosen
        inverted = key == "complexity"
        if not _score_passes(q["criteria"], chosen, inverted=inverted):
            failing.append(key)

    # Noul questions. For error_handling, the polarity is inverted: a HIGH
    # score means error handling IS present (good). For slop, dead_code,
    # has_type_safety_issues, has_duplication, has_hardcoded_values, a HIGH
    # score means the problem IS present (bad).
    _POSITIVE_CODE_NOULS = {"error_handling"}
    for key, q in CODE_NOUL_QUESTIONS.items():
        answer = answers.get(key, {})
        score = float(answer.get("noul", 0.0))
        flags[key] = round(score, 3)
        if key in _POSITIVE_CODE_NOULS:
            # Positive noul: flag when ABSENT (low score).
            if score < (1.0 - threshold):
                failing.append(key)
        else:
            if score >= threshold:
                failing.append(key)

    passed = len(failing) == 0
    return {"scores": scores, "score_values": score_values, "flags": flags, "failing": failing, "passed": passed}


def _parse_prose_iteration(answers: dict, threshold: float) -> dict:
    """Parse Jev answers for one prose-mode iteration."""
    scores: dict[str, str | None] = {}
    score_values: dict[str, float | str | None] = {}
    flags: dict[str, float] = {}
    failing: list[str] = []

    for key, q in PROSE_SCORE_QUESTIONS.items():
        answer = answers.get(key, {})
        chosen, label = _score_value_and_label(q["criteria"], answer)
        scores[key] = label
        score_values[key] = chosen
        if not _score_passes(q["criteria"], chosen):
            failing.append(key)

    for key in PROSE_NOUL_QUESTIONS:
        answer = answers.get(key, {})
        score = float(answer.get("noul", 0.0))
        flags[key] = round(score, 3)
        if score >= threshold:
            failing.append(key)

    passed = len(failing) == 0
    return {"scores": scores, "score_values": score_values, "flags": flags, "failing": failing, "passed": passed}


def _parse_review_iteration(answers: dict, finding_count: int) -> dict:
    """Parse Jev answers for review mode."""
    findings_out: list[dict] = []
    for i in range(finding_count):
        prefix = f"finding_{i}"
        genuine_answer = answers.get(f"{prefix}_genuine", {})
        actionable_answer = answers.get(f"{prefix}_actionable", {})
        severity_answer = answers.get(f"{prefix}_severity", {})

        findings_out.append(
            {
                "index": i,
                "genuine": round(float(genuine_answer.get("noul", 0.0)), 3),
                "actionable": round(float(actionable_answer.get("noul", 0.0)), 3),
                "severity": severity_answer.get("choice") or severity_answer.get("score", ""),
            }
        )

    return {"findings": findings_out, "passed": True}


def _compute_improvements(current: dict, previous: dict) -> list[str]:
    """Compute improvement descriptions between two iterations."""
    improvements: list[str] = []

    for key in current.get("scores", {}):
        curr_val = current["scores"][key]
        prev_val = previous.get("scores", {}).get(key)
        if prev_val and curr_val != prev_val:
            improvements.append(f"{key}: {prev_val} -> {curr_val}")

    for key in current.get("flags", {}):
        curr_val = current["flags"][key]
        prev_val = previous.get("flags", {}).get(key)
        if prev_val is not None and curr_val != prev_val:
            improvements.append(f"{key}: {prev_val} -> {curr_val}")

    return improvements


def score_iteration(
    text: str,
    mode: str,
    iteration: int,
    history: list[dict],
    *,
    threshold: float = DEFAULT_THRESHOLD,
    timeout: float = DEFAULT_TIMEOUT,
    findings: list[dict] | None = None,
) -> dict:
    """Run one scoring iteration against the given text.

    Args:
        text: The text (code or prose) to score. For review mode, this is
            ignored and findings must be provided.
        mode: One of "code", "prose", or "review".
        iteration: 0-indexed iteration number.
        history: List of previous iteration result dicts (empty on first call).
        threshold: Noul score above which a flag fires (default 0.7).
        timeout: Jev HTTP call timeout in seconds.
        findings: For review mode only -- list of finding dicts to evaluate.

    Returns:
        Dict with keys: iteration, passed, scores, flags, failing, latency_ms, usage.
    """
    available, reason = jev_router_common.typesafe_available()
    if not available:
        return {
            "iteration": iteration,
            "passed": False,
            "scores": {},
            "flags": {},
            "failing": ["unavailable"],
            "latency_ms": None,
            "usage": None,
            "error": f"TypeSafe unavailable: {reason}",
        }

    api_key = os.environ.get("TYPESAFE_API_KEY", "").strip()

    if mode == "code":
        questions = _build_code_questions(iteration, history)
    elif mode == "prose":
        questions = _build_prose_questions(iteration, history)
    elif mode == "review":
        if not findings:
            return {
                "iteration": iteration,
                "passed": True,
                "findings": [],
                "latency_ms": None,
                "usage": None,
            }
        questions = _build_review_questions(findings)
        text = json.dumps(findings, indent=2)
    else:
        return {
            "iteration": iteration,
            "passed": False,
            "scores": {},
            "flags": {},
            "failing": ["invalid_mode"],
            "latency_ms": None,
            "usage": None,
            "error": f"Unknown mode: {mode!r}. Use 'code', 'prose', or 'review'.",
        }

    payload = {"state": text, "model": jev_router_common.JEV_MODEL, "questions": questions}

    try:
        data, latency_ms = jev_router_common.call_jev(payload, api_key, timeout, script_name="jev-quality-loop.py")
    except Exception as exc:
        print(
            f"[jev-quality-loop] Jev call failed (iteration {iteration}): {type(exc).__name__}: {exc}", file=sys.stderr
        )
        return {
            "iteration": iteration,
            "passed": False,
            "scores": {},
            "flags": {},
            "failing": ["jev_call_failed"],
            "latency_ms": None,
            "usage": None,
            "error": f"{type(exc).__name__}: {str(exc)[:200]}",
        }

    answers = data.get("answers", {})
    usage = jev_router_common.extract_usage(data)

    if mode == "code":
        result = _parse_code_iteration(answers, threshold)
    elif mode == "prose":
        result = _parse_prose_iteration(answers, threshold)
    else:
        result = _parse_review_iteration(answers, len(findings or []))

    result["iteration"] = iteration
    result["latency_ms"] = round(latency_ms, 1)
    result["usage"] = usage

    if history:
        result["improvements"] = _compute_improvements(result, history[-1])

    return result


def quality_loop(
    text: str,
    mode: str,
    *,
    threshold: float = DEFAULT_THRESHOLD,
    max_iterations: int = DEFAULT_MAX_ITERATIONS,
    timeout: float = DEFAULT_TIMEOUT,
    iterate: bool = False,
    file_path: Path | None = None,
    findings: list[dict] | None = None,
) -> dict:
    """Run iterative Jev quality scoring. Returns full result with iteration history.

    In single-shot mode (iterate=False), scores once and returns.
    In iterate mode (iterate=True), re-reads file_path between iterations
    (assumes external edits between calls) and loops until quality passes
    or max_iterations is reached.

    Args:
        text: The text to score (used for first iteration; ignored on re-reads
            when iterate=True and file_path is set).
        mode: One of "code", "prose", or "review".
        threshold: Noul score above which a flag fires.
        max_iterations: Maximum number of scoring iterations.
        timeout: Jev HTTP call timeout in seconds.
        iterate: When True, re-read file_path between iterations.
        file_path: Path to the file being scored (required for iterate mode).
        findings: For review mode -- list of finding dicts.

    Returns:
        Dict with keys: mode, iterations, final_passed, total_iterations,
        latency_ms (per-iteration and total).
    """
    history: list[dict] = []
    total_latency_ms = 0.0
    latency_per_iteration: dict[str, float | None] = {}

    effective_max = 1 if not iterate or mode == "review" else max_iterations

    for i in range(effective_max):
        # On iteration 1+, re-read the file if iterating.
        if i > 0 and iterate and file_path is not None:
            try:
                text = file_path.read_text(encoding="utf-8")
            except Exception as exc:
                print(
                    f"[jev-quality-loop] re-read failed (iteration {i}): {type(exc).__name__}: {exc}", file=sys.stderr
                )
                break

        iteration_result = score_iteration(
            text,
            mode,
            i,
            history,
            threshold=threshold,
            timeout=timeout,
            findings=findings,
        )
        history.append(iteration_result)

        iter_latency = iteration_result.get("latency_ms")
        latency_per_iteration[f"iteration_{i}"] = iter_latency
        if iter_latency is not None:
            total_latency_ms += iter_latency

        if iteration_result.get("passed"):
            break

        # If there was an error, stop looping.
        if iteration_result.get("error"):
            break

    final_passed = history[-1].get("passed", False) if history else False

    latency_per_iteration["total"] = round(total_latency_ms, 1)

    return {
        "mode": mode,
        "iterations": history,
        "final_passed": final_passed,
        "total_iterations": len(history),
        "latency_ms": latency_per_iteration,
    }


def main() -> int:
    """CLI entry point."""
    parser = argparse.ArgumentParser(
        description="Iterative Jev quality scoring loop: score, flag, (external fix), re-score, verify.",
    )
    input_group = parser.add_mutually_exclusive_group()
    input_group.add_argument("--file", help="Path to a text file to score.")
    input_group.add_argument("--findings", help="Path to a JSON file of findings (review mode).")
    parser.add_argument(
        "--mode",
        choices=["code", "prose", "review"],
        default="code",
        help="Scoring mode (default: code).",
    )
    parser.add_argument(
        "--threshold",
        type=float,
        default=DEFAULT_THRESHOLD,
        help=f"Noul score above which a flag fires (default {DEFAULT_THRESHOLD}).",
    )
    parser.add_argument(
        "--max-iter",
        type=int,
        default=DEFAULT_MAX_ITERATIONS,
        help=f"Maximum scoring iterations (default {DEFAULT_MAX_ITERATIONS}).",
    )
    parser.add_argument(
        "--iterate",
        action="store_true",
        help="Re-read the file between iterations (assumes external edits).",
    )
    parser.add_argument("--json-compact", action="store_true", help="Compact JSON output.")
    parser.add_argument(
        "--timeout",
        type=float,
        default=DEFAULT_TIMEOUT,
        help=f"Jev HTTP call timeout in seconds (default {DEFAULT_TIMEOUT}).",
    )
    args = parser.parse_args()

    try:
        file_path: Path | None = None
        findings: list[dict] | None = None
        text = ""

        if args.findings:
            findings_path = Path(args.findings)
            raw = json.loads(findings_path.read_text(encoding="utf-8"))
            findings = raw if isinstance(raw, list) else raw.get("findings", [])
            text = json.dumps(findings, indent=2)
            if args.mode != "review":
                print("[jev-quality-loop] --findings implies --mode review", file=sys.stderr)
                args.mode = "review"
        elif args.file:
            file_path = Path(args.file)
            text = file_path.read_text(encoding="utf-8")
        elif not sys.stdin.isatty():
            text = sys.stdin.read()
        else:
            print("[jev-quality-loop] no input: use --file, --findings, or pipe to stdin", file=sys.stderr)
            print(json.dumps({"error": "no input provided", "mode": args.mode, "final_passed": False}))
            return 0

        result = quality_loop(
            text,
            args.mode,
            threshold=args.threshold,
            max_iterations=args.max_iter,
            timeout=args.timeout,
            iterate=args.iterate,
            file_path=file_path,
            findings=findings,
        )

        indent = None if args.json_compact else 2
        print(json.dumps(result, indent=indent))

    except Exception as exc:
        import traceback

        traceback.print_exc(file=sys.stderr)
        error_result = {
            "error": f"{type(exc).__name__}: {str(exc)[:200]}",
            "mode": args.mode,
            "iterations": [],
            "final_passed": False,
            "total_iterations": 0,
            "latency_ms": {"total": 0},
        }
        print(json.dumps(error_result))

    return 0


if __name__ == "__main__":
    sys.exit(main())
