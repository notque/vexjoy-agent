#!/usr/bin/env python3
"""Grill-Jev: context-specific Jev interrogation against any artifact.

Evaluates a question battery supplied by the LLM running the skill through Jev.
Static question-battery.md is available as a fallback.

Usage:
    python3 scripts/grill-jev.py --file task_plan.md --mode plan
    python3 scripts/grill-jev.py --text "..." --mode plan
    python3 scripts/grill-jev.py --file design.md --questions-file /tmp/questions.json

Exit codes:
    0 — no high-signal findings or all below threshold
    1 — one or more high-signal findings at or above threshold
    2 — transport error or invalid input
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).parent))

import jev_transport

# ---------------------------------------------------------------------------
# On-the-fly question generation
# ---------------------------------------------------------------------------

GENERATION_SYSTEM_PROMPT = """You are generating a Jev question battery to interrogate an artifact.
The artifact will be provided as state at the key "artifact".
If a "context" key is present in state, use it to sharpen questions — it may describe
the system, the audience for the artifact, known risks, or the decision this artifact supports.

Generate between 20 and 50 questions. Scale the count to the artifact's complexity:
- 3-5 step bug fix or config change: 15-20 questions
- Multi-step feature plan or design doc: 25-35 questions
- Multi-service migration or architecture change: 40-50 questions

Question quality rules:
- SPECIFIC to artifact: questions must name specific steps, systems, or claims in the artifact.
  A generic "does this have rollback?" is worse than "does step 4's schema migration define a
  rollback that is safe to run while the service is live?".
- MENTIONS = deeper scrutiny: when the artifact mentions a risk, gap, or uncertainty, generate
  MORE targeted questions about it — not fewer. Acknowledgment is not mitigation. The author
  saying "this is risky" without defining how the risk is managed is itself a finding. Probe the
  quality, completeness, and safety of whatever is described.
- AUDIENCE weight: if context describes the audience (SRE, junior dev, external reviewer, product
  owner), weight question focus toward what that audience needs to execute or approve the artifact.
  An SRE needs ops-specific questions; a product owner needs outcome and risk questions.
- COVERAGE: aim for breadth across the relevant risk categories (completeness, feasibility, risk,
  scope, verification, consistency, reversibility, security). Do not cluster 20 questions on one
  category. Skip a category only when the artifact has no content that could trigger it.
- FINDING POLARITY: each NOUL question must include "report_when" with "true" or "false";
  each CHOICE question must include "report_choices" with only the concerning options. A positive
  or neutral answer must never become a finding merely because it is confident.

For each question, choose the most appropriate Jev primitive and shape:

NOUL — yes/no probability. Use for: is something present/absent, does a risk exist.
Always add structured criteria when the boundary is non-obvious:
  "criteria": {
    "true": {"what": "...", "examples": [...]},
    "false": {"what": "...", "examples": [...]}
  }

CHOICE — pick one from a known set. Use for: risk levels, reversibility classifications,
severity categories. Each option should have "what" (and optionally "not_for", "examples"):
  "criteria": {
    "option_name": {"what": "...", "not_for": "...", "examples": [...]}
  }

SCORE — position on a spectrum. Use for: completeness, timeline realism, detection speed.
Each level needs "summary" and "signals":
  "criteria": [
    {"summary": "...", "signals": [...]},
    ...
  ]

Use array compare instructions when two or more state paths must be compared:
  "instructions": {"question": "...", "compare": ["artifact", "context"], "focus": "..."}

Output a JSON object: {"questions": {"question_id": <jev_question_def>, ...}}
question_id should be short_snake_case describing what the question tests.
"""

GENERATION_USER_TEMPLATE = """Artifact (mode: {mode}):

{artifact}
{seed_section}
Generate {min_q}-{max_q} context-specific Jev questions for this artifact.
Focus on risks, gaps, and assumptions that are specific to what the artifact contains.
Output JSON: {{"questions": {{...}}}}"""


def _load_questions(path: str) -> dict[str, Any]:
    """Load a battery authored by the LLM executing the skill."""
    try:
        payload = json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError(f"invalid question battery: {exc}") from exc
    questions = payload.get("questions", payload)
    if not isinstance(questions, dict) or not questions:
        raise ValueError("question battery must be a non-empty JSON object")
    return questions


# ---------------------------------------------------------------------------
# Static fallback battery when the invoking LLM does not supply a JSON battery.
# ---------------------------------------------------------------------------

# Minimal inline fallback — eight representative questions, one per category.
# The full static battery is in references/question-battery.md and was used
# before on-the-fly generation was introduced.
FALLBACK_QUESTIONS: dict[str, Any] = {
    "c_has_success_criteria": {
        "type": "noul",
        "report_when": "false",
        "instructions": {
            "question": "Does the artifact define measurable success criteria?",
            "inspect": "artifact",
        },
        "criteria": {
            "true": {
                "what": "Specific, observable outcomes are named",
                "examples": ["all tests pass", "p95 latency < 200ms"],
            },
            "false": {
                "what": "Success is vague, absent, or only implied",
                "examples": ["it works", "done"],
            },
        },
    },
    "f_timeline_realistic": {
        "type": "score",
        "instructions": {
            "question": "How realistic is the timeline given the work described?",
            "focus": "Buffer for unknowns, dependency chains, and parallelism assumptions.",
        },
        "criteria": [
            {"summary": "Unrealistic", "signals": ["no buffer", "ignores known blockers"]},
            {"summary": "Optimistic", "signals": ["tight but possible if nothing goes wrong"]},
            {"summary": "Realistic", "signals": ["reasonable buffer", "dependencies called out"]},
            {"summary": "Conservative", "signals": ["explicit buffer", "blockers have fallback plans"]},
        ],
    },
    "r_blast_radius": {
        "type": "choice",
        "report_choices": ["broad", "systemic"],
        "instructions": {
            "question": "What is the blast radius if this change fails?",
            "focus": "How many users, services, or systems are affected by complete failure?",
        },
        "criteria": {
            "isolated": {
                "what": "Failure affects one component with no cross-system impact",
                "examples": ["feature behind a flag affecting 1% of users"],
            },
            "limited": {
                "what": "Failure affects one service; others continue normally",
                "examples": ["one microservice fails, others unaffected"],
            },
            "broad": {
                "what": "Failure degrades multiple services or a large user segment",
                "examples": ["shared cache layer failure"],
            },
            "critical": {
                "what": "Failure causes platform-wide outage or data loss",
                "examples": ["auth service outage", "primary DB migration failure"],
            },
        },
    },
    "s_scope_boundary_explicit": {
        "type": "noul",
        "report_when": "false",
        "instructions": {
            "question": "Does the artifact explicitly state what is out of scope?",
            "inspect": "artifact",
        },
        "criteria": {
            "true": {
                "what": "At least one out-of-scope item is named",
                "examples": ["does not cover service B"],
            },
            "false": {
                "what": "Scope is implied only by what is included",
                "examples": [],
            },
        },
    },
    "v_success_observable": {
        "type": "noul",
        "report_when": "false",
        "instructions": {
            "question": "Can success be observed externally after execution, without reading the code?",
            "inspect": "artifact",
        },
        "criteria": {
            "true": {
                "what": "An external observer could verify success using listed criteria",
                "examples": ["health check returns 200", "latency drops in Grafana"],
            },
            "false": {
                "what": "Success requires the author to explain what to look for",
                "examples": [],
            },
        },
    },
    "k_internal_contradiction": {
        "type": "noul",
        "report_when": "true",
        "instructions": {
            "question": "Does the artifact contain internal contradictions?",
            "inspect": "artifact",
        },
        "criteria": {
            "true": {
                "what": "Two statements cannot both be true",
                "examples": ["scope says no schema changes but step 3 alters a table"],
            },
            "false": {
                "what": "All statements are internally consistent",
                "examples": [],
            },
        },
    },
    "rev_can_be_undone": {
        "type": "choice",
        "report_choices": ["partially_reversible", "irreversible"],
        "instructions": {
            "question": "Can this change be completely undone after deployment?",
            "focus": "Consider data mutations, schema changes, and user-visible behavior changes.",
        },
        "criteria": {
            "fully_reversible": {
                "what": "All changes can be reverted with no lasting side effect",
                "examples": ["feature flag change", "config value change"],
            },
            "mostly_reversible": {
                "what": "Code can be reverted but some side effects remain",
                "examples": ["column added (data preserved)"],
            },
            "partially_reversible": {
                "what": "Some parts can be undone but not all",
                "examples": ["schema migration needing manual backfill to undo"],
            },
            "irreversible": {
                "what": "Cannot be undone without significant manual work or data loss",
                "examples": ["DROP TABLE", "permanent user data deletion"],
            },
        },
    },
    "sec_credential_exposure": {
        "type": "noul",
        "report_when": "true",
        "instructions": {
            "question": "Could this change expose credentials, secrets, or PII?",
            "inspect": "artifact",
            "focus": "Logging sensitive values, plaintext storage, or API responses.",
        },
        "criteria": {
            "true": {
                "what": "Credentials or PII could be logged, stored in plaintext, or returned in responses",
                "examples": ["logging full request body including auth headers"],
            },
            "false": {
                "what": "Secrets managed via env vars or secret managers; not touched by this change",
                "examples": [],
            },
        },
    },
}

# ---------------------------------------------------------------------------
# Category labels for display
# ---------------------------------------------------------------------------

_PREFIX_TO_CATEGORY = {
    "c": "completeness",
    "f": "feasibility",
    "r": "risk",
    "s": "scope",
    "v": "verification",
    "k": "consistency",
    "rev": "reversibility",
    "sec": "security",
}


def _question_category(qid: str) -> str:
    prefix = qid.split("_")[0]
    return _PREFIX_TO_CATEGORY.get(prefix, prefix)


# ---------------------------------------------------------------------------
# Scoring helpers
# ---------------------------------------------------------------------------

BATCH_SIZE = 25


def _is_high_signal(question: dict[str, Any], answer: dict[str, Any], threshold: float) -> bool:
    """Return True when an answer warrants reporting."""
    qtype = question.get("type", "noul")
    if qtype == "noul":
        report_when = question.get("report_when")
        if report_when not in {"true", "false"}:
            return False
        probability = answer.get("noul", 0.5)
        return probability >= threshold if report_when == "true" else probability <= 1 - threshold
    if qtype == "choice":
        return answer.get("choice") in question.get("report_choices", []) and answer.get("confidence", 0.0) >= threshold
    if qtype == "score":
        return answer.get("score", 1.5) <= 1.0
    return False


def _format_answer(qtype: str, answer: dict[str, Any]) -> str:
    if qtype == "noul":
        noul_val = answer.get("noul", 0.5)
        direction = "TRUE" if noul_val >= 0.5 else "FALSE"
        return f"noul={noul_val:.2f} {direction}"
    if qtype == "choice":
        choice = answer.get("choice", "?")
        conf = answer.get("confidence", 0.0)
        return f"choice={choice} conf={conf:.2f}"
    if qtype == "score":
        score_val = answer.get("score", 0.0)
        legend = answer.get("legend", {})
        level = round(score_val)
        label = legend.get(str(level), legend.get(level, ""))
        return f"score={score_val:.2f} ({label})"
    return str(answer)


def _suggest_action(qid: str, qtype: str, answer: dict[str, Any], question_text: str) -> str:
    """Return a one-line action suggestion for a high-signal finding."""
    if qtype == "noul":
        noul_val = answer.get("noul", 0.5)
        verb = "address" if noul_val >= 0.7 else "review"
        return f"{verb}: {question_text.lower().rstrip('?')}"
    if qtype == "choice":
        choice = answer.get("choice", "?")
        category = _question_category(qid)
        if category == "risk" and choice in ("high", "critical", "broad"):
            return f"risk level is {choice} — review blast radius and add mitigation"
        if "reversib" in qid and choice in ("irreversible", "partially_reversible"):
            return f"change is {choice} — define rollback strategy or accept the risk explicitly"
        return f"choice '{choice}' — review whether this aligns with requirements"
    if qtype == "score":
        score_val = answer.get("score", 0.0)
        legend = answer.get("legend", {})
        label = legend.get(str(round(score_val)), "")
        if "timeline" in qid:
            return f"timeline is '{label}' — add buffer or parallelize steps"
        if "detection" in qid or "failure" in qid:
            return f"failure detection is '{label}' — add monitoring or post-deploy checks"
        if "complet" in qid:
            return f"artifact is '{label}' ({score_val:.1f}/3) — fill gaps before executing"
        return f"score {score_val:.1f}/3 ('{label}') — review and improve"
    return f"review: {question_text.lower().rstrip('?')}"


# ---------------------------------------------------------------------------
# Batching + evaluation
# ---------------------------------------------------------------------------


def _run_battery(
    state: dict[str, Any],
    questions: dict[str, Any],
    timeout: float,
) -> dict[str, Any]:
    """Run all questions in batches, returning merged answers dict."""
    question_ids = list(questions.keys())
    batches = [question_ids[i : i + BATCH_SIZE] for i in range(0, len(question_ids), BATCH_SIZE)]
    all_answers: dict[str, Any] = {}
    for batch in batches:
        batch_qs = {qid: questions[qid] for qid in batch}
        result = jev_transport.evaluate(state, batch_qs, timeout=timeout)
        all_answers.update(result.get("answers", {}))
    return all_answers


# ---------------------------------------------------------------------------
# Report
# ---------------------------------------------------------------------------


def _print_report(
    answers: dict[str, Any],
    questions: dict[str, Any],
    mode: str,
    threshold: float,
    generated: bool,
) -> int:
    """Print findings report. Returns exit code (0=clean, 1=findings)."""
    source_label = "generated" if generated else "static fallback"
    print(f"\nGRILL-JEV FINDINGS — mode: {mode} — {len(questions)} questions ({source_label})")
    print("=" * 60)

    high_signal: list[tuple[str, dict[str, Any], str]] = []
    category_counts: dict[str, int] = {}

    for qid, qdef in questions.items():
        answer = answers.get(qid, {})
        if not answer:
            continue
        qtype = qdef.get("type", "noul")
        category = _question_category(qid)
        if _is_high_signal(qdef, answer, threshold):
            high_signal.append((qid, answer, category))
            category_counts[category] = category_counts.get(category, 0) + 1

    if high_signal:
        print(f"\nHIGH SIGNAL ({len(high_signal)} finding{'s' if len(high_signal) != 1 else ''}):")
        for qid, answer, category in high_signal:
            qdef = questions[qid]
            qtype = qdef.get("type", "noul")
            instructions = qdef.get("instructions", {})
            question_text = instructions.get("question", qid) if isinstance(instructions, dict) else str(instructions)
            fmt = _format_answer(qtype, answer)
            action = _suggest_action(qid, qtype, answer, question_text)
            print(f"  [{category}/{qid}] {fmt}")
            print(f"    → {action}")
    else:
        print("\nno high-signal findings — artifact looks solid")

    if category_counts:
        print("\nCATEGORY SUMMARY:")
        for cat, count in sorted(category_counts.items()):
            print(f"  {cat}  {count} finding{'s' if count != 1 else ''}")

    # Overall readiness — look for any score question about completeness
    for qid, qdef in questions.items():
        if qdef.get("type") == "score" and "complet" in qid:
            completeness_answer = answers.get(qid, {})
            if completeness_answer:
                score_val = completeness_answer.get("score", -1.0)
                if score_val >= 0:
                    legend = completeness_answer.get("legend", {})
                    label = legend.get(str(round(score_val)), "")
                    note = "address findings before executing" if score_val < 2.0 else "ready to proceed"
                    print(f"\nOVERALL READINESS: {score_val:.1f}/3 — {label}; {note}")
                break

    print()
    return 1 if high_signal else 0


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def main() -> None:
    parser = argparse.ArgumentParser(description="Grill-Jev: context-specific Jev interrogation battery")
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--file", help="Path to artifact file to evaluate")
    group.add_argument("--text", help="Artifact text to evaluate")
    parser.add_argument(
        "--mode",
        choices=["plan", "code", "design", "general"],
        default="general",
        help="Artifact type — shapes question count and focus (default: general)",
    )
    parser.add_argument(
        "--questions-file",
        metavar="PATH",
        help="JSON battery authored by the LLM executing the Grill-Jev skill",
    )
    parser.add_argument(
        "--threshold",
        type=float,
        default=0.7,
        help="Signal threshold for Noul and Choice confidence (default: 0.7)",
    )
    parser.add_argument(
        "--timeout",
        type=float,
        default=30.0,
        help="Jev request timeout in seconds per batch (default: 30)",
    )
    parser.add_argument(
        "--context",
        help="Optional context about the system (supplements the artifact in state)",
    )
    parser.add_argument(
        "--json",
        dest="output_json",
        action="store_true",
        help="Emit raw answers as JSON instead of the findings report",
    )
    args = parser.parse_args()

    # Load artifact
    if args.file:
        artifact_path = Path(args.file)
        if not artifact_path.is_file():
            print(f"error: file not found: {args.file}", file=sys.stderr)
            sys.exit(2)
        artifact_text = artifact_path.read_text(encoding="utf-8")
    else:
        artifact_text = args.text

    if not artifact_text.strip():
        print("error: artifact is empty", file=sys.stderr)
        sys.exit(2)

    state: dict[str, Any] = {"artifact": artifact_text}
    if args.context:
        state["context"] = args.context

    generated = bool(args.questions_file)
    try:
        questions = _load_questions(args.questions_file) if args.questions_file else FALLBACK_QUESTIONS.copy()
    except ValueError as exc:
        print(f"error: {exc}", file=sys.stderr)
        sys.exit(2)

    try:
        answers = _run_battery(state, questions, timeout=args.timeout)
    except jev_transport.JevTransportError as exc:
        print(f"error: Jev transport failed: {exc}", file=sys.stderr)
        sys.exit(2)

    if args.output_json:
        print(json.dumps({"questions": questions, "answers": answers}, indent=2))
        sys.exit(0)

    exit_code = _print_report(answers, questions, args.mode, args.threshold, generated)
    sys.exit(exit_code)


if __name__ == "__main__":
    main()
