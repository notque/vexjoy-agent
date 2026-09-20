#!/usr/bin/env python3
"""Jev intent/route alignment check for every /d invocation.

The router chooses a method; this checker verifies that the proposed outcome
still represents the user's request. It asks independent atomic questions in
one gateway request and returns facts for the dispatcher to act on. It never
invents a new goal and never silently blocks work on a weak score.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import sys
import time
from pathlib import Path
from typing import Any

import jev_transport

try:
    import tomllib
except ModuleNotFoundError:  # Python 3.10; keep the runtime dependency-free.
    tomllib = None  # type: ignore[assignment]

_HOOKS_LIB = Path(__file__).resolve().parent.parent / "hooks" / "lib"
if str(_HOOKS_LIB) not in sys.path:
    sys.path.insert(0, str(_HOOKS_LIB))
try:
    from learning_db_v2 import record_jev_intent_alignment as _record_intent_alignment
except Exception:  # pragma: no cover - telemetry is optional
    _record_intent_alignment = None

DEFAULT_TIMEOUT = 8.0
YES_THRESHOLD = 0.60
CORE_ALIGNMENT_THRESHOLD = 0.50
MAX_ALIGNMENT_STATE_CHARS = 180_000


def proposed_intent(request: str, route: dict[str, Any]) -> str:
    """Produce a conservative intent candidate when the caller has none."""
    route_bits = [str(route.get(key)).strip() for key in ("agent", "skill", "pipeline") if route.get(key)]
    method = ", ".join(route_bits) if route_bits else "direct handling"
    return (
        f"Fulfill the user's request: {request}. Use {method} only as the execution method; "
        "preserve the requested outcome and explicit constraints."
    )


def _noul(question: str, *paths: str) -> dict[str, Any]:
    return {"type": "noul", "instructions": {"question": question, "inspect": list(paths)}}


def build_payload(request: str, intent: str, route: dict[str, Any]) -> dict[str, Any]:
    """Build one evidence state and all independent validation questions."""
    route_state = {key: route.get(key) for key in ("agent", "skill", "pipeline", "complexity", "source", "reasoning")}
    route_state["validation_context"] = (
        "The route was selected by a deterministic force-route guard or a manifest-validated Jev classifier. Treat opaque agent and skill labels as valid execution methods unless the route visibly conflicts with the user request."
    )
    state = {"user_request": request, "proposed_intent": intent, "selected_route": route_state}
    questions = {
        "has_actionable_outcome": _noul(
            "Does `user_request` state an outcome that can be acted on now? Answer false only when no outcome can be inferred.",
            "user_request",
        ),
        "intent_preserves_requested_outcome": _noul(
            "Does `proposed_intent` preserve the outcome in `user_request` without changing its meaning?",
            "user_request",
            "proposed_intent",
        ),
        "intent_preserves_explicit_constraints": _noul(
            "Does `proposed_intent` preserve every explicit constraint, limitation, authorization, and requested scope in `user_request`?",
            "user_request",
            "proposed_intent",
        ),
        "route_supports_requested_outcome": _noul(
            "Does `selected_route` avoid conflicting with the outcome in `user_request`? Treat a deterministic force route or manifest-validated route as suitable unless it visibly conflicts. Direct handling suits a simple answer.",
            "user_request",
            "selected_route",
        ),
        "intent_is_too_narrow": _noul(
            "Does `proposed_intent` drop a material deliverable, surface, state, or success condition from `user_request`?",
            "user_request",
            "proposed_intent",
        ),
        "intent_adds_unrequested_work": _noul(
            "Does `proposed_intent` add a material goal, deliverable, or decision absent from `user_request`?",
            "user_request",
            "proposed_intent",
        ),
        "route_omits_material_scope": _noul(
            "Is `selected_route` plainly unable to cover a material part of `user_request`?",
            "user_request",
            "selected_route",
        ),
        "essential_clarification_needed": _noul(
            "Would executing `proposed_intent` require the user to resolve an essential ambiguity, contradiction, or explicitly reserved choice first? Answer true even when planning could begin but execution cannot. Routine implementation choices do not require clarification.",
            "user_request",
            "proposed_intent",
        ),
        "can_proceed_with_proposed_intent": _noul(
            "Can work proceed from `proposed_intent` because `user_request` is actionable and its outcome and constraints are preserved? Routine choices may be resolved by the worker.",
            "user_request",
            "proposed_intent",
            "selected_route",
        ),
    }
    return {"state": state, "questions": questions}


def _prob(answers: dict[str, Any], key: str) -> float:
    raw = answers.get(key, {}) if isinstance(answers, dict) else {}
    value = raw.get("noul", 0.5) if isinstance(raw, dict) else 0.5
    try:
        return max(0.0, min(1.0, float(value)))
    except (TypeError, ValueError):
        return 0.5


def _complete_answers(answers: Any, keys: Any) -> bool:
    """Require a numeric noul probability for every batched question."""
    if not isinstance(answers, dict):
        return False
    for key in keys:
        answer = answers.get(key)
        if not isinstance(answer, dict) or isinstance(answer.get("noul"), bool):
            return False
        try:
            float(answer["noul"])
        except (KeyError, TypeError, ValueError):
            return False
    return True


def _text_hash(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()[:16]


def _agent_profile() -> tuple[str | None, str | None, str | None]:
    """Return the configured executing-agent profile without claiming runtime certainty."""
    model = os.environ.get("JEV_AGENT_MODEL")
    effort = os.environ.get("JEV_AGENT_EFFORT")
    runtime = os.environ.get("JEV_AGENT_RUNTIME")
    if model or effort or runtime:
        return model, effort, runtime or "explicit"

    if os.environ.get("CODEX_SESSION_ID") or os.environ.get("CODEX_THREAD_ID"):
        try:
            config_text = (Path.home() / ".codex" / "config.toml").read_text(encoding="utf-8")
            if tomllib is not None:
                config = tomllib.loads(config_text)
            else:
                # Python 3.10 has no stdlib TOML parser. These two top-level
                # string keys are all telemetry needs, so avoid adding a
                # runtime dependency solely for optional metadata.
                config = {
                    match.group(1): match.group(3)
                    for line in config_text.splitlines()
                    if (
                        match := re.fullmatch(
                            r"\s*(model|model_reasoning_effort)\s*=\s*(['\"])(.*?)\2\s*(?:#.*)?",
                            line,
                        )
                    )
                }
        except (OSError, ValueError):
            config = {}
        return (
            config.get("model") if isinstance(config.get("model"), str) else None,
            config.get("model_reasoning_effort") if isinstance(config.get("model_reasoning_effort"), str) else None,
            "codex",
        )

    try:
        settings = json.loads((Path.home() / ".claude" / "settings.json").read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        settings = {}
    model = os.environ.get("ANTHROPIC_MODEL") or os.environ.get("CLAUDE_MODEL")
    if model is None and isinstance(settings.get("model"), str):
        model = settings["model"]
    effort = settings.get("effortLevel") if isinstance(settings.get("effortLevel"), str) else None
    return model, effort, "claude" if os.environ.get("CLAUDE_SESSION_ID") or settings else None


def _materially_differs(scores: dict[str, float]) -> bool:
    """Return whether the restatement itself changes the requested work."""
    return (
        scores.get("intent_preserves_requested_outcome", 0.5) < CORE_ALIGNMENT_THRESHOLD
        or scores.get("intent_preserves_explicit_constraints", 0.5) < CORE_ALIGNMENT_THRESHOLD
        or scores.get("intent_is_too_narrow", 0.5) >= YES_THRESHOLD
        or scores.get("intent_adds_unrequested_work", 0.5) >= YES_THRESHOLD
    )


def _finish_receipt(
    result: dict[str, Any],
    *,
    request: str,
    candidate: str,
    phase: str,
    data: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Normalize and persist one privacy-bounded alignment receipt."""
    source = str(result.get("source") or "unavailable")
    default_model = None
    if source == jev_transport.VERCEL:
        default_model = "typesafe-ai/jev"
    elif source == jev_transport.DIRECT:
        default_model = "jev-latest"
    normalized = {
        "available": False,
        "source": source,
        "model": default_model,
        "proposed_intent": candidate,
        "alignment": "error",
        "aligned": False,
        "clarification_needed": False,
        "issues": [],
        "scores": {},
        "questions_version": "d-intent-v1",
        "latency_ms": None,
        "usage": None,
        "transport_retry": None,
        "reason": None,
    }
    normalized.update(result)
    result = normalized
    if _record_intent_alignment is None:
        return result
    scores = result.get("scores") if isinstance(result.get("scores"), dict) else None
    materially_differs = None
    route_mismatch = None
    if scores is not None:
        materially_differs = _materially_differs(scores)
        route_mismatch = (
            scores.get("route_supports_requested_outcome", 0.5) < CORE_ALIGNMENT_THRESHOLD
            or scores.get("route_omits_material_scope", 0.5) >= YES_THRESHOLD
        )
    model = data.get("model") if isinstance(data, dict) and isinstance(data.get("model"), str) else None
    model = model or result.get("model")
    agent_model, agent_effort, agent_runtime = _agent_profile()
    _record_intent_alignment(
        phase=phase,
        transport=str(result.get("source") or "unknown"),
        model=model,
        agent_model=agent_model,
        agent_effort=agent_effort,
        agent_runtime=agent_runtime,
        alignment=str(result.get("alignment") or "unknown"),
        materially_differs=materially_differs,
        route_mismatch=route_mismatch,
        clarification_needed=result.get("clarification_needed")
        if isinstance(result.get("clarification_needed"), bool)
        else None,
        questions_version=str(result.get("questions_version") or "d-intent-v1"),
        issues=result.get("issues") if isinstance(result.get("issues"), list) else None,
        scores=scores,
        request_hash=_text_hash(request),
        proposed_intent_hash=_text_hash(candidate),
        latency_ms=result.get("latency_ms"),
        session_id=os.environ.get("JEV_SESSION_ID") or os.environ.get("CLAUDE_SESSION_ID"),
    )
    return result


def evaluate_alignment(
    request: str, route: dict[str, Any], intent: str | None, timeout: float = DEFAULT_TIMEOUT
) -> dict[str, Any]:
    """Evaluate candidate intent through the selected Jev transport."""
    phase = "proposed" if isinstance(intent, str) and intent.strip() else "baseline"
    candidate = intent if isinstance(intent, str) and intent.strip() else proposed_intent(request, route)
    transport, transport_reason = jev_transport.select()
    source = transport or "unavailable"
    if transport is None:
        return _finish_receipt(
            {
                "available": False,
                "source": source,
                "proposed_intent": candidate,
                "reason": transport_reason,
                "alignment": "unavailable",
                "questions_version": "d-intent-v1",
            },
            request=request,
            candidate=candidate,
            phase=phase,
        )
    if len(request) + len(candidate) > MAX_ALIGNMENT_STATE_CHARS:
        return _finish_receipt(
            {
                "available": True,
                "source": source,
                "proposed_intent": candidate,
                "alignment": "error",
                "aligned": False,
                "clarification_needed": False,
                "issues": ["intent-alignment state exceeds the safe request budget"],
                "reason": "intent-alignment state exceeds the safe request budget",
                "questions_version": "d-intent-v1",
            },
            request=request,
            candidate=candidate,
            phase=phase,
        )
    payload = build_payload(request, candidate, route)
    started = time.monotonic()
    try:
        data = jev_transport.evaluate(payload["state"], payload["questions"], timeout=timeout)
    except jev_transport.JevTransportError as exc:
        return _finish_receipt(
            {
                "available": True,
                "source": exc.source,
                "proposed_intent": candidate,
                "alignment": "error",
                "reason": str(exc)[:300],
                "transport_retry": exc.telemetry,
                "questions_version": "d-intent-v1",
            },
            request=request,
            candidate=candidate,
            phase=phase,
        )
    answers = data.get("answers", {}) if isinstance(data, dict) else {}
    if not _complete_answers(answers, payload["questions"]):
        meta = data.get("_meta") if isinstance(data, dict) else None
        return _finish_receipt(
            {
                "available": True,
                "source": source,
                "proposed_intent": candidate,
                "alignment": "error",
                "aligned": False,
                "clarification_needed": False,
                "issues": ["Jev returned an incomplete intent-alignment response"],
                "reason": "incomplete intent-alignment response",
                "questions_version": "d-intent-v1",
                "latency_ms": round((time.monotonic() - started) * 1000, 2),
                "usage": data.get("usage") if isinstance(data, dict) else None,
                "transport_retry": meta.get("retry") if isinstance(meta, dict) else None,
            },
            request=request,
            candidate=candidate,
            phase=phase,
            data=data,
        )
    scores = {key: round(_prob(answers, key), 4) for key in payload["questions"]}
    intent_mismatch = _materially_differs(scores)
    route_mismatch = (
        scores["route_supports_requested_outcome"] < CORE_ALIGNMENT_THRESHOLD
        or scores["route_omits_material_scope"] >= YES_THRESHOLD
    )
    mismatch = intent_mismatch or route_mismatch
    # A bad restatement can be corrected without interrupting the user. Ask a
    # question only when the remaining blocker is genuinely user-owned.
    clarification = scores["essential_clarification_needed"] >= YES_THRESHOLD and not intent_mismatch
    required = (
        "has_actionable_outcome",
        "intent_preserves_requested_outcome",
        "intent_preserves_explicit_constraints",
        "route_supports_requested_outcome",
        "can_proceed_with_proposed_intent",
    )
    aligned = all(scores[key] >= CORE_ALIGNMENT_THRESHOLD for key in required) and not mismatch and not clarification
    issues: list[str] = []
    core_issues = {
        "has_actionable_outcome": "request lacks an actionable outcome",
        "intent_preserves_requested_outcome": "proposed intent changes the requested outcome",
        "intent_preserves_explicit_constraints": "proposed intent drops explicit constraints",
        "route_supports_requested_outcome": "selected route conflicts with the requested outcome",
        "can_proceed_with_proposed_intent": "cannot proceed with the proposed intent",
    }
    issues.extend(message for key, message in core_issues.items() if scores[key] < CORE_ALIGNMENT_THRESHOLD)
    if scores["intent_is_too_narrow"] >= YES_THRESHOLD:
        issues.append("proposed intent drops material scope")
    if scores["intent_adds_unrequested_work"] >= YES_THRESHOLD:
        issues.append("proposed intent adds unrequested work")
    if scores["route_omits_material_scope"] >= YES_THRESHOLD:
        issues.append("selected route omits material scope")
    if clarification:
        issues.append("essential clarification is needed")
    meta = data.get("_meta") if isinstance(data, dict) else None
    model = data.get("model") if isinstance(data, dict) and isinstance(data.get("model"), str) else None
    result = {
        "available": True,
        "source": source,
        "model": model or ("typesafe-ai/jev" if source == jev_transport.VERCEL else "jev-latest"),
        "proposed_intent": candidate,
        "alignment": "aligned" if aligned else "review",
        "aligned": aligned,
        "clarification_needed": clarification,
        "issues": issues,
        "scores": scores,
        "questions_version": "d-intent-v1",
        "latency_ms": round((time.monotonic() - started) * 1000, 2),
        "usage": data.get("usage") if isinstance(data, dict) else None,
        "transport_retry": meta.get("retry") if isinstance(meta, dict) else None,
    }
    return _finish_receipt(result, request=request, candidate=candidate, phase=phase, data=data)


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate a /d proposed intent through Jev.")
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--request")
    group.add_argument("--request-file")
    route_group = parser.add_mutually_exclusive_group(required=True)
    route_group.add_argument("--route-json", help="JSON object from jev-route.py")
    route_group.add_argument("--route-file", help="File containing JSON from jev-route.py")
    parser.add_argument("--proposed-intent", default=None)
    parser.add_argument("--proposed-intent-file", default=None)
    parser.add_argument("--timeout", type=float, default=DEFAULT_TIMEOUT)
    parser.add_argument("--json-compact", action="store_true")
    args = parser.parse_args()
    try:
        request = Path(args.request_file).read_text(encoding="utf-8") if args.request_file else args.request
        route_text = Path(args.route_file).read_text(encoding="utf-8") if args.route_file else args.route_json
        route = json.loads(route_text)
        if not isinstance(route, dict):
            raise ValueError("--route-json must be an object")
        intent = (
            Path(args.proposed_intent_file).read_text(encoding="utf-8")
            if args.proposed_intent_file
            else args.proposed_intent
        )
        result = evaluate_alignment(request or "", route, intent, args.timeout)
    except Exception as exc:
        result = _finish_receipt(
            {
                "available": False,
                "source": "unavailable",
                "alignment": "error",
                "reason": f"{type(exc).__name__}: {str(exc)[:200]}",
            },
            request=locals().get("request") or "",
            candidate=locals().get("intent") or "",
            phase="proposed" if locals().get("intent") else "baseline",
        )
    print(json.dumps(result, indent=None if args.json_compact else 2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
