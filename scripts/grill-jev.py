#!/usr/bin/env python3
"""Grill-Jev: context-specific Jev interrogation against any artifact.

Evaluates a question battery supplied by the LLM running the skill through Jev.
Static question-battery.md is available as a fallback.

Usage:
    python3 scripts/grill-jev.py --file task_plan.md --mode plan
    python3 scripts/grill-jev.py --text "..." --mode plan
    python3 scripts/grill-jev.py --file design.md --questions-file /tmp/questions.json
    python3 scripts/grill-jev.py --images-dir shots/ --questions-file /tmp/questions.json
    python3 scripts/grill-jev.py --image home=home.png --image cpu.png --text "dashboard review"

Images (--image, --images-dir) force the direct Jev API and need TYPESAFE_API_KEY.

Exit codes:
    0 — no high-signal findings or all below threshold
    1 — one or more high-signal findings at or above threshold
    2 — Jev outage, invalid input, or a question left unanswered after splitting
"""

from __future__ import annotations

import argparse
import json
import math
import os
import re
import sys
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).parent))

import jev_images
import jev_limits
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
  scope, verification, consistency, reversibility, security, cost & throughput). Do not cluster
  20 questions on one category. Skip a category only when the artifact has no content that could
  trigger it. Prefix ids by category (c_, f_, r_, s_, v_, k_, rev_, sec_, cost_).
- COST & THROUGHPUT: when the artifact calls Jev, an LLM, or another metered API, ask whether it
  prices tokens and requests per run AND per second against the provider's documented rate limits,
  caps concurrency, uses a cheap wide stage before full detail over many units, retries with
  jittered exponential backoff and a per-run budget, and prices any eval. Per-request fit alone
  does not show the run fits.
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
    if not isinstance(payload, dict):
        raise ValueError(
            f"invalid question battery: top level is a JSON {type(payload).__name__}; "
            'expected {"questions": {"<id>": {...}}}'
        )
    questions = payload.get("questions", payload)
    if not isinstance(questions, dict) or not questions:
        raise ValueError('question battery must be a non-empty JSON object: {"questions": {"<id>": {...}}}')
    problems = _battery_problems(questions)
    if problems:
        raise ValueError("invalid question battery: " + "; ".join(problems))
    return questions


def _battery_problems(questions: dict[str, Any]) -> list[str]:
    """Shape errors Jev would reject, one per bad question id."""
    problems: list[str] = []
    for qid, q in questions.items():
        if not isinstance(q, dict):
            problems.append(f"{qid}: must be an object")
            continue
        qtype, criteria = q.get("type"), q.get("criteria")
        if qtype not in {"noul", "choice", "score"}:
            problems.append(f"{qid}: type must be noul, choice, or score")
        elif not q.get("instructions"):
            problems.append(f"{qid}: needs instructions")
        elif qtype == "noul" and q.get("report_when") not in {"true", "false"}:
            problems.append(f'{qid}: noul needs report_when "true" or "false"')
        elif qtype == "score" and criteria is not None:
            if not isinstance(criteria, list) or not all(isinstance(c, dict) and c.get("summary") for c in criteria):
                problems.append(f"{qid}: score criteria must be a list of {{summary, signals}} levels, lowest first")
        elif qtype == "choice" and not (isinstance(criteria, dict) and criteria):
            problems.append(f"{qid}: choice criteria must map each option to {{what, not_for, examples}}")
    return problems


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
    "cost": "cost & throughput",
}


def _question_category(qid: str) -> str:
    prefix = qid.split("_")[0]
    return _PREFIX_TO_CATEGORY.get(prefix, prefix)


# ---------------------------------------------------------------------------
# Scoring helpers
# ---------------------------------------------------------------------------

BATCH_SIZE = 25
# Too much context is the most common Jev failure through Vercel AI Gateway.
# The artifact (state) is resent with every batch, so batches are packed by
# estimated tokens (jev_limits.pack_questions), capped at BATCH_SIZE questions,
# and a state too large for even one question is refused before any call.
TARGET_REQUEST_TOKENS = jev_limits.TARGET_REQUEST_TOKENS
RequestTooLarge = jev_limits.RequestTooLarge


def _estimate_tokens(state: Any, questions: dict[str, Any]) -> int:
    return jev_limits.request_tokens(state, questions)["total"]


def _pack_batches(state: Any, questions: dict[str, Any], target: int = TARGET_REQUEST_TOKENS) -> list[list[str]]:
    """Group question ids so each request (state + batch) stays at or under ``target``."""
    groups = jev_limits.pack_questions(state, questions, target=target, max_questions=BATCH_SIZE)
    return [list(group) for group in groups]


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


def _is_probability(value: Any) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool) and 0.0 <= value <= 1.0


def _answer_problem(question: dict[str, Any], answer: Any) -> str | None:
    """Why ``answer`` is not a usable answer to ``question``, or None when it is.

    A missing or malformed answer is unknown, never a pass: the caller records it
    as unanswered (exit 2) instead of reading it as "no finding".
    """
    if not isinstance(answer, dict):
        return "no answer returned"
    qtype = question.get("type", "noul")
    criteria = question.get("criteria")
    if qtype == "noul":
        return None if _is_probability(answer.get("noul")) else "noul is not a probability in [0, 1]"
    if qtype == "choice":
        choice = answer.get("choice")
        if not isinstance(choice, str) or (isinstance(criteria, dict) and criteria and choice not in criteria):
            return "choice is not one of the offered options"
        if answer.get("confidence") is not None and not _is_probability(answer["confidence"]):
            return "confidence is not a probability in [0, 1]"
        return None
    if qtype == "score":
        score = answer.get("score")
        if isinstance(score, bool) or not isinstance(score, (int, float)) or not math.isfinite(score):
            return "score is not a number"
        if isinstance(criteria, list) and criteria and not 0 <= score <= len(criteria) - 1:
            return "score is outside the offered levels"
    return None


_BATCH_FATAL = frozenset(
    {jev_transport.REQUEST_TOO_LARGE, jev_transport.IMAGES_UNSUPPORTED, jev_transport.INVALID_IMAGE}
)


def _run_battery(
    state: dict[str, Any],
    questions: dict[str, Any],
    timeout: float,
    images: dict[str, jev_images.JevImage] | None = None,
) -> dict[str, Any]:
    """Run all questions in batches, returning merged answers dict.

    A failed batch is halved and retried down to single questions, so one bad
    or oversized question costs only its own answer. A question that still
    fails is recorded as ``{"error": ...}`` (unknown, never a pass). If the
    first single-question failure also fails a tiny probe, Jev is down: raise.

    With ``images`` ({name: JevImage}), each request carries only the images its
    questions use (see ``_image_plan``), and all requests go to the direct API.
    """
    all_answers: dict[str, Any] = {}
    service_ok: list[bool] = []  # set once by the probe
    plans: dict[str, tuple[list[str], dict[str, int]]] = {}

    if images:
        names = list(images)
        plans = {qid: _image_plan(qid, q, names) for qid, q in questions.items()}
        tokens = {n: img.resolve().est_tokens for n, img in images.items()}
        batches, refused = _image_batches(state, questions, plans, tokens)
        for qid, reason in refused.items():
            all_answers[qid] = {"type": questions[qid].get("type"), "error": reason}
    else:
        batches = _pack_batches(state, questions)

    def build(batch_qs: dict[str, Any]) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any] | None]:
        if not images:
            return state, batch_qs, None
        carried = [n for n in images if any(n in plans[qid][0] for qid in batch_qs)]
        inline = {n for qid in batch_qs for n in plans[qid][1]}
        batch_state = dict(state)
        if carried:
            batch_state[IMAGES_KEY] = {n: images[n] for n in carried}
        batch_images = {n: images[n] for n in images if n in carried or n in inline}
        return batch_state, {qid: _wire_question(q) for qid, q in batch_qs.items()}, batch_images

    def send(batch_qs: dict[str, Any]) -> None:
        batch_state, wire_qs, batch_images = build(batch_qs)
        try:
            reply = jev_transport.evaluate(batch_state, wire_qs, timeout=timeout, images=batch_images)
        except jev_transport.JevTransportError as exc:
            if exc.source in _BATCH_FATAL:
                raise
            if len(batch_qs) > 1:
                ids = list(batch_qs)
                mid = len(ids) // 2
                send({k: batch_qs[k] for k in ids[:mid]})
                send({k: batch_qs[k] for k in ids[mid:]})
                return
            if not service_ok:
                jev_transport.evaluate(_PROBE_STATE, _PROBE_QUESTION, timeout=timeout)  # raises on outage
                service_ok.append(True)
            qid = next(iter(batch_qs))
            all_answers[qid] = {"type": batch_qs[qid].get("type"), "error": str(exc)}
        else:
            replied = reply.get("answers") if isinstance(reply, dict) else None
            for qid, question in batch_qs.items():
                answer = replied.get(qid) if isinstance(replied, dict) else None
                problem = _answer_problem(question, answer)
                all_answers[qid] = {"type": question.get("type"), "error": problem} if problem else answer

    for i, batch in enumerate(batches):
        try:
            send({qid: questions[qid] for qid in batch})
        except (RequestTooLarge, jev_transport.JevTransportError) as exc:
            if isinstance(exc, jev_transport.JevTransportError) and exc.source not in _BATCH_FATAL:
                exc.partial_answers = all_answers  # type: ignore[attr-defined]  # outage: main reports what was paid for
                raise
            # Keep every answer already paid for; list what did not run and why.
            for qid in (q for later in batches[i:] for q in later):
                if qid not in all_answers:
                    all_answers[qid] = {"type": questions[qid].get("type"), "error": f"not run: {exc}"}
            break
    return all_answers


# Known-good minimal request: tells a bad question apart from a Jev outage.
_PROBE_STATE = {"artifact": "The sky is blue."}
_PROBE_QUESTION = {
    "probe": {"type": "noul", "report_when": "true", "instructions": {"question": "Does the artifact name a color?"}}
}


# ---------------------------------------------------------------------------
# Images
# ---------------------------------------------------------------------------

IMAGE_SUFFIXES = frozenset({".png", ".jpg", ".jpeg", ".webp"})
_NAME_OK = re.compile(r"^[A-Za-z0-9_.-]+$")
_PLACEHOLDER = re.compile(r"\{img:([A-Za-z0-9_.-]+)\}")
IMAGES_KEY = "images"  # state key that holds the batch's images, and the per-question field


def _safe_name(stem: str) -> str:
    return re.sub(r"[^A-Za-z0-9_.-]", "_", stem) or "image"


def _parse_image_specs(specs: list[str], images_dir: str | None) -> dict[str, Path]:
    """Map image name -> file from ``--image`` values (``PATH`` or ``name=PATH``) and ``--images-dir``.

    An unnamed image is named by its file stem. Raises ValueError on a missing
    file, a bad name, or a duplicate name.
    """
    found: dict[str, Path] = {}

    def add(name: str, path: Path, origin: str) -> None:
        if name in found:
            raise ValueError(f"duplicate image name {name!r}; name one with name=PATH")
        if not path.is_file():
            raise ValueError(f"image not found: {path} (from {origin!r}; use NAME=PATH to name an image)")
        found[name] = path

    for spec in specs:
        name, sep, rest = spec.partition("=")
        if sep and _NAME_OK.match(name) and not Path(spec).is_file():
            add(name, Path(rest), spec)
        else:
            add(_safe_name(Path(spec).stem), Path(spec), spec)
    if images_dir:
        root = Path(images_dir)
        if not root.is_dir():
            raise ValueError(f"images dir not found: {images_dir}")
        files = sorted(f for f in root.iterdir() if f.is_file() and f.suffix.lower() in IMAGE_SUFFIXES)
        if not files:
            raise ValueError(f"no png/jpg/jpeg/webp files in {images_dir}")
        for f in files:
            add(_safe_name(f.stem), f, str(f))
    return found


def _image_plan(qid: str, question: dict[str, Any], names: list[str]) -> tuple[list[str], dict[str, int]]:
    """Which images a question needs: (names carried in state, placeholder name -> uses).

    ``"images": [names]`` on the question carries those in state. ``{img:name}``
    in the question text references an image inline. A question with neither gets
    every image in state. Raises ValueError on an unknown name.
    """
    explicit = question.get(IMAGES_KEY)
    if explicit is not None and not (isinstance(explicit, list) and all(isinstance(n, str) for n in explicit)):
        raise ValueError(f"{qid}: images must be a list of image names")
    wire_text = json.dumps({k: v for k, v in question.items() if k != IMAGES_KEY}, ensure_ascii=False)
    inline: dict[str, int] = {}
    for name in _PLACEHOLDER.findall(wire_text):
        inline[name] = inline.get(name, 0) + 1
    unknown = sorted({*(explicit or []), *inline} - set(names))
    if unknown:
        raise ValueError(f"{qid}: unknown image name(s) {unknown}; have {sorted(names)}")
    if explicit is None and not inline:
        return list(names), {}
    return [n for n in names if n in (explicit or [])], inline


def _neutralize_placeholders(text: str) -> str:
    """Break ``{img:name}`` in free text so it is sent literally and never binds to an image."""
    return text.replace("{img:", "{img :")


def _fallback_per_image(questions: dict[str, Any], names: list[str]) -> dict[str, Any]:
    """One copy of each fallback question per image, so no request has to carry every image."""
    expanded: dict[str, Any] = {}
    for name in names:
        for qid, q in questions.items():
            copy = json.loads(json.dumps(q))
            instructions = copy.get("instructions")
            note = f" Judge only the image named {name!r}."
            if isinstance(instructions, dict) and isinstance(instructions.get("question"), str):
                instructions["question"] += note
            elif isinstance(instructions, str):
                copy["instructions"] = instructions + note
            copy[IMAGES_KEY] = [name]
            expanded[f"{qid}@{name}"] = copy
    return expanded


def _wire_question(question: dict[str, Any]) -> dict[str, Any]:
    """The question as Jev sees it: without the grill-jev-only ``images`` field."""
    return {k: v for k, v in question.items() if k != IMAGES_KEY}


def _image_batches(
    base_state: dict[str, Any],
    questions: dict[str, Any],
    plans: dict[str, tuple[list[str], dict[str, int]]],
    tokens: dict[str, int],
    target: int = jev_limits.IMAGE_REQUEST_TARGET_TOKENS,
) -> tuple[list[list[str]], dict[str, str]]:
    """Pack question ids into requests that each fit ``target`` tokens, images included.

    Questions with the same image set share requests; an image is resent once
    for each request that uses it. A question whose own request (its images plus state) is
    over ``target`` is not sent: it is returned in the second value with the reason.
    """

    def question_cost(qid: str) -> int:
        inline = plans[qid][1]
        return jev_limits.estimate_tokens(_wire_question(questions[qid])) + sum(
            tokens[n] * uses for n, uses in inline.items()
        )

    def images_cost(names: list[str]) -> int:
        stub = {n: "0" * 32 for n in names}
        return jev_limits.estimate_tokens(stub) + sum(tokens[n] for n in names) if names else 0

    state_cost = jev_limits.estimate_tokens(base_state)
    refused: dict[str, str] = {}
    by_set: dict[tuple[str, ...], list[str]] = {}
    for qid in questions:
        carried = tuple(plans[qid][0])
        if state_cost + images_cost(list(carried)) + question_cost(qid) > target:
            all_refs = not _explicit_images(questions[qid]) and not plans[qid][1]
            refused[qid] = (
                f"no image reference and all {len(carried)} images do not fit one request "
                f"(~{state_cost + images_cost(list(carried)) + question_cost(qid)} tokens, target {target}); "
                f'pass --questions-file and give this question "images": ["{carried[0]}"] (one or more image names)'
                if all_refs
                else f"its images and state are ~{state_cost + images_cost(list(carried)) + question_cost(qid)} "
                f"tokens (target {target}); reference fewer or smaller images"
            )
            continue
        by_set.setdefault(carried, []).append(qid)

    batches: list[list[str]] = []
    for carried, qids in by_set.items():
        fixed = state_cost + images_cost(list(carried))
        current: list[str] = []
        used = fixed
        for qid in qids:
            cost = question_cost(qid)
            if current and (used + cost > target or len(current) >= BATCH_SIZE):
                batches.append(current)
                current, used = [], fixed
            current.append(qid)
            used += cost
        if current:
            batches.append(current)
    return batches, refused


def _explicit_images(question: dict[str, Any]) -> bool:
    return question.get(IMAGES_KEY) is not None


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
    """Print findings report. Returns exit code (0=clean, 1=findings, 2=unanswered questions)."""
    source_label = "questions file" if generated else "static fallback"
    print(f"\nGRILL-JEV FINDINGS — mode: {mode} — {len(questions)} questions ({source_label})")
    print("=" * 60)

    high_signal: list[tuple[str, dict[str, Any], str]] = []
    category_counts: dict[str, int] = {}

    for qid, qdef in questions.items():
        answer = answers.get(qid, {})
        if not answer or "error" in answer:
            continue
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

    unanswered = {qid: answers[qid]["error"] for qid in questions if "error" in answers.get(qid, {})}
    if unanswered:
        print(f"\nUNANSWERED ({len(unanswered)}; unknown, not a pass):")
        for qid, err in unanswered.items():
            print(f"  [{qid}] {err}")

    print()
    if unanswered:
        return 2
    return 1 if high_signal else 0


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def main() -> None:
    parser = argparse.ArgumentParser(description="Grill-Jev: context-specific Jev interrogation battery")
    group = parser.add_mutually_exclusive_group()
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
        "--image",
        action="append",
        default=[],
        metavar="[NAME=]PATH",
        help="Image to judge; repeat for more. NAME= sets the name (default: file stem) that questions "
        "use as {img:NAME} or in an 'images' list. Forces the direct Jev API (needs TYPESAFE_API_KEY)",
    )
    parser.add_argument(
        "--images-dir",
        metavar="DIR",
        help="Add every png/jpg/jpeg/webp in DIR, named by file stem",
    )
    parser.add_argument(
        "--json",
        dest="output_json",
        action="store_true",
        help="Emit raw answers as JSON instead of the findings report",
    )
    args = parser.parse_args()

    images: dict[str, jev_images.JevImage] = {}
    if args.image or args.images_dir:
        if not os.environ.get("TYPESAFE_API_KEY", "").strip():
            print(
                "error: images need the direct Jev API: set TYPESAFE_API_KEY (the Vercel gateway cannot carry images)",
                file=sys.stderr,
            )
            sys.exit(2)
        requested = os.environ.get("JEV_TRANSPORT", "").strip().lower()
        if jev_transport._ALIASES.get(requested) == jev_transport.VERCEL:
            print(f"warning: JEV_TRANSPORT={requested} ignored: images need the direct Jev API", file=sys.stderr)
        os.environ["JEV_TRANSPORT"] = "direct"  # never Vercel, including the outage probe
        try:
            paths = _parse_image_specs(args.image, args.images_dir)
            images = {name: jev_images.JevImage(path) for name, path in paths.items()}
            for img in images.values():
                img.resolve()
        except (ValueError, jev_images.JevImageError) as exc:
            print(f"error: {exc}", file=sys.stderr)
            sys.exit(2)

    # Load artifact
    if args.file:
        artifact_path = Path(args.file)
        if not artifact_path.is_file():
            print(f"error: file not found: {args.file}", file=sys.stderr)
            sys.exit(2)
        artifact_text = artifact_path.read_text(encoding="utf-8")
    elif args.text is not None:
        artifact_text = args.text
    elif images:
        artifact_text = "Review the attached images. Images are attached to the questions that reference them."
    else:
        print("error: give --file, --text, or an image", file=sys.stderr)
        sys.exit(2)

    if not artifact_text.strip():
        print("error: artifact is empty", file=sys.stderr)
        sys.exit(2)

    context_text = args.context
    if images:  # a literal {img:x} in artifact or context must not bind to an image or abort the run
        artifact_text = _neutralize_placeholders(artifact_text)
        context_text = _neutralize_placeholders(context_text) if context_text else context_text
    state: dict[str, Any] = {"artifact": artifact_text}
    if context_text:
        state["context"] = context_text

    generated = bool(args.questions_file)
    try:
        questions = _load_questions(args.questions_file) if args.questions_file else FALLBACK_QUESTIONS.copy()
    except ValueError as exc:
        print(f"error: {exc}", file=sys.stderr)
        sys.exit(2)

    if images and not generated and len(images) > 1:
        questions = _fallback_per_image(questions, list(images))
        print(
            f"note: no --questions-file; fallback battery sent once per image: {len(questions)} questions "
            f"over {len(images)} images (each image is billed once per request that carries it)",
            file=sys.stderr,
        )

    try:
        if images:
            for qid, q in questions.items():
                _image_plan(qid, q, list(images))
        elif any(isinstance(q, dict) and IMAGES_KEY in q for q in questions.values()):
            raise ValueError('questions use "images" but no --image or --images-dir was given')
    except ValueError as exc:
        print(f"error: {exc}", file=sys.stderr)
        sys.exit(2)

    try:
        answers = _run_battery(state, questions, timeout=args.timeout, images=images or None)
    except RequestTooLarge as exc:
        print(f"error: {exc}", file=sys.stderr)
        sys.exit(2)
    except jev_transport.JevTransportError as exc:
        print(f"error: Jev transport failed: {exc}", file=sys.stderr)
        partial = getattr(exc, "partial_answers", None)
        if not partial:
            sys.exit(2)
        answers = dict(partial)  # report what was already paid for; the rest is unknown
        for qid, q in questions.items():
            answers.setdefault(qid, {"type": q.get("type"), "error": f"not run: {exc}"})

    if args.output_json:
        print(json.dumps({"questions": questions, "answers": answers}, indent=2))
        sys.exit(2 if any("error" in a for a in answers.values()) else 0)

    exit_code = _print_report(answers, questions, args.mode, args.threshold, generated)
    sys.exit(exit_code)


if __name__ == "__main__":
    main()
