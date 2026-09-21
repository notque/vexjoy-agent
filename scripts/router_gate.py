"""Mandatory handoff checks for /d and /do supported runtime entrypoints.

Decision card (router-required-v1): each handoff must validate actual request,
intent and route using the existing batched d-intent-v1 rubric/model/thresholds.
No new semantic head is introduced. A fresh aligned result permits dispatch;
review, malformed and unavailable results block with explicit diagnostics.
Structural baseline: builder previously accepted missing intent validation.
Tests falsify bypasses (missing phases/artifacts, stale requests and supplied
receipts); they make no claim about semantic accuracy or model calibration.
The user requested enforcement of existing checks, not a shadow-mode new head.
Model/rubric changes require semantic re-evaluation; gate changes require the
structural regression suite. Hook enforcement is limited to supported harnesses.
"""

from __future__ import annotations

import fcntl
import hashlib
import json
import os
import subprocess
import sys
import tempfile
import uuid
from contextlib import contextmanager
from pathlib import Path
from typing import Any


class RouterGateError(ValueError):
    """A mandatory router prerequisite has not been met."""


def text_hash(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def session_id() -> str:
    return next(
        (
            os.environ[key]
            for key in ("JEV_SESSION_ID", "CLAUDE_SESSION_ID", "CODEX_SESSION_ID", "CODEX_THREAD_ID")
            if os.environ.get(key)
        ),
        "",
    )


def _marker_path(session: str) -> Path:
    root = Path(os.environ.get("JEV_ROUTER_STATE_DIR", str(Path.home() / ".claude/state/router-required")))
    return root / (text_hash(session) + ".json")


@contextmanager
def _marker_lock(session: str):
    path = _marker_path(session).with_suffix(".lock")
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    with path.open("a") as stream:
        fcntl.flock(stream.fileno(), fcntl.LOCK_EX)
        try:
            yield
        finally:
            fcntl.flock(stream.fileno(), fcntl.LOCK_UN)


def _write_marker(session: str, marker: dict[str, Any]) -> None:
    path = _marker_path(session)
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    descriptor, temporary = tempfile.mkstemp(prefix=".router-", dir=path.parent)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as stream:
            json.dump(marker, stream)
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def set_required_router(session: str, router: str, request: str) -> None:
    if not session or router not in ("d", "do"):
        raise RouterGateError("router marker requires session id and router d or do")
    with _marker_lock(session):
        _write_marker(
            session,
            {"router": router, "request_hash": text_hash(request), "pending": True, "generation": uuid.uuid4().hex},
        )


def continue_required_router(session: str, request: str) -> None:
    """Keep unfinished routing obligations across unprefixed clarification."""
    if not session:
        return
    with _marker_lock(session):
        marker = get_required_router(session)
        if marker is None:
            return
        prior = list(dict.fromkeys([*marker.get("prior_request_hashes", []), marker["request_hash"]]))
        if len(prior) > 8:
            prior = [prior[0], *prior[-7:]]
        _write_marker(
            session,
            {
                "router": marker["router"],
                "request_hash": text_hash(request),
                "prior_request_hashes": prior,
                "pending": True,
                "generation": uuid.uuid4().hex,
            },
        )


def clear_required_router(session: str) -> None:
    if session:
        with _marker_lock(session):
            _marker_path(session).unlink(missing_ok=True)


def get_required_router(session: str) -> dict[str, Any] | None:
    if not session:
        return None
    try:
        marker = json.loads(_marker_path(session).read_text(encoding="utf-8"))
    except FileNotFoundError:
        return None
    except (OSError, ValueError) as exc:
        raise RouterGateError(f"cannot read mandatory router marker: {exc}") from exc
    if (
        not isinstance(marker, dict)
        or marker.get("router") not in ("d", "do")
        or not isinstance(marker.get("request_hash"), str)
        or not isinstance(marker.get("pending"), bool)
        or not isinstance(marker.get("generation"), str)
    ):
        raise RouterGateError("invalid mandatory router marker")
    return marker


def mark_validated(
    session: str, request: str, intent: str, route: dict[str, Any], *, expected_generation: str | None = None
) -> None:
    if not session:
        return
    with _marker_lock(session):
        marker = get_required_router(session)
        if marker is None:
            if expected_generation is not None:
                raise RouterGateError("router invocation changed while validation was running")
            return
        if marker["request_hash"] != text_hash(request) or (
            expected_generation is not None and marker.get("generation") != expected_generation
        ):
            raise RouterGateError("request changed while mandatory intent validation was running")
        marker.update(
            pending=False,
            status="validated",
            intent_hash=text_hash(intent),
            route_hash=text_hash(json.dumps(route, sort_keys=True)),
        )
        _write_marker(session, marker)


def authorize_dispatch(session: str, request: str, prompt: str, *, expected_generation: str | None = None) -> None:
    """Queue an exact checked dispatch; concurrent fan-out retains every hash."""
    if not session:
        return
    with _marker_lock(session):
        marker = get_required_router(session)
        if marker is None:
            if expected_generation is not None:
                raise RouterGateError("router invocation changed while validation was running")
            return
        if marker["request_hash"] != text_hash(request) or (
            expected_generation is not None and marker.get("generation") != expected_generation
        ):
            raise RouterGateError("request changed before dispatch authorization")
        hashes = marker.get("dispatch_prompt_hashes", [])
        hashes.append(text_hash(prompt))
        marker.update(pending=False, status="dispatch_ready", dispatch_prompt_hashes=hashes)
        _write_marker(session, marker)


def consume_dispatch(session: str, prompt: str) -> bool:
    """Authorize one native Agent/Task invocation; return false on mismatch."""
    if not session:
        return False
    with _marker_lock(session):
        marker = get_required_router(session)
        if marker is None or marker.get("status") != "dispatch_ready":
            return False
        hashes = marker.get("dispatch_prompt_hashes", [])
        digest = text_hash(prompt)
        if digest not in hashes:
            return False
        hashes.remove(digest)
        marker.update(pending=False, status="dispatch_ready" if hashes else "dispatched", dispatch_prompt_hashes=hashes)
        _write_marker(session, marker)
        return True


def mark_checked_blocked(session: str, request: str, *, expected_generation: str | None = None) -> None:
    if not session:
        return
    with _marker_lock(session):
        marker = get_required_router(session)
        if (
            marker is not None
            and marker["request_hash"] == text_hash(request)
            and (expected_generation is None or marker.get("generation") == expected_generation)
        ):
            marker.update(pending=True, status="checked_blocked")
            _write_marker(session, marker)


def _text(mapping: dict, key: str, prefix: str) -> str:
    value = mapping.get(key)
    if not isinstance(value, str) or not value.strip():
        raise RouterGateError(f'{prefix}.{key} must contain explicit evidence (use "none" where inapplicable)')
    return value


def _gate(decision: dict, name: str, required: bool, repo_root: Path) -> None:
    gates = decision.get("routing_gates")
    gate = gates.get(name) if isinstance(gates, dict) else None
    if not isinstance(gate, dict) or gate.get("status") not in ("applied", "not_applicable"):
        raise RouterGateError(f"routing_gates.{name} requires status applied or not_applicable")
    _text(gate, "reason", f"routing_gates.{name}")
    if required and gate["status"] != "applied":
        raise RouterGateError(f"routing_gates.{name} is mandatory for this request")
    if required and name != "composition":
        artifact = Path(_text(gate, "artifact", f"routing_gates.{name}"))
        artifact = artifact if artifact.is_absolute() else repo_root / artifact
        if not artifact.is_file() or not artifact.read_text(encoding="utf-8").strip():
            raise RouterGateError(f"routing_gates.{name}.artifact must name an existing nonempty evidence file")


def _protected_guard(request: str, decision: dict) -> None:
    """Re-run protected routing rules; supplied claims cannot bypass them."""
    try:
        proc = subprocess.run(
            [sys.executable, str(Path(__file__).with_name("pre-route.py")), "--request", request, "--json-compact"],
            capture_output=True,
            text=True,
            timeout=30,
            check=False,
        )
        guard = json.loads(proc.stdout) if proc.returncode == 0 else None
    except (OSError, subprocess.SubprocessError, ValueError) as exc:
        raise RouterGateError(f"mandatory deterministic route guard failed: {exc}") from exc
    if not isinstance(guard, dict):
        raise RouterGateError("mandatory deterministic route guard returned invalid output")
    if (
        guard.get("match_type") == "force_route"
        and guard.get("confidence") == "high"
        and guard.get("skill") in ("pr-workflow", "security")
    ):
        if decision.get("skill") != guard["skill"]:
            raise RouterGateError(f"protected route requires skill {guard['skill']}")
        missing = set(guard.get("stack") or []) - set(decision.get("stack") or [])
        if missing:
            raise RouterGateError(f"protected route requires stack: {', '.join(sorted(missing))}")


def validate_router_handoff(decision: dict, repo_root: Path, *, direct: bool = False) -> dict[str, Any] | None:
    """Check prerequisites and run a fresh intent judgment, never trust a receipt.

    Marker completion is deliberately separate: the builder marks success only
    after its manifest, path, model and preamble checks have also succeeded.
    """
    marker = get_required_router(session_id())
    generation = marker.get("generation") if marker else None
    router = decision.get("router")
    if marker is not None:
        if router != marker["router"]:
            raise RouterGateError("active router invocation requires matching router field; it cannot be omitted")
    if router is None:
        if direct:
            raise RouterGateError("--router-finalize requires router d or do")
        return None  # Other callers retain their existing builder contract.
    if router not in ("d", "do"):
        raise RouterGateError("router must be d or do")
    complexity = decision.get("complexity")
    if complexity not in ("trivial", "simple", "medium", "complex"):
        raise RouterGateError("router requires an explicit valid complexity")
    if direct != (complexity == "trivial"):
        raise RouterGateError("trivial requests must use --router-finalize; Simple+ must dispatch")
    spec = decision.get("task_spec")
    if not isinstance(spec, dict):
        raise RouterGateError("router task_spec must be an object")
    for field in (
        "request_verbatim",
        "intent",
        "constraints",
        "decisions",
        "gaps",
        "acceptance",
        "files",
        "ownership",
        "operator_context",
    ):
        _text(spec, field, "task_spec")
    request, intent = spec["request_verbatim"], spec["intent"]
    if marker is not None and marker["request_hash"] != text_hash(request):
        raise RouterGateError("task_spec.request_verbatim does not match the current router invocation")
    if marker and marker.get("prior_request_hashes"):
        context = spec.get("prior_context")
        if not isinstance(context, list) or not all(isinstance(message, str) for message in context):
            raise RouterGateError("unfinished router continuation requires verbatim task_spec.prior_context")
        supplied = {text_hash(message) for message in context}
        if not set(marker["prior_request_hashes"]).issubset(supplied):
            raise RouterGateError("task_spec.prior_context omits the unfinished router request or clarification")
    from jev_intent_align import alignment_budget_error

    try:
        budget_error = alignment_budget_error(request, intent, spec.get("prior_context"))
    except ValueError as exc:
        raise RouterGateError(str(exc)) from exc
    if budget_error:
        mark_checked_blocked(session_id(), request, expected_generation=generation)
        raise RouterGateError(budget_error)
    steps = decision.get("routing_steps")
    if not isinstance(steps, dict):
        raise RouterGateError("routing_steps must record classification, selection, enhancement and handoff evidence")
    for step in ("classification", "selection", "enhancement", "handoff"):
        _text(steps, step, "routing_steps")
    for field in ("creation_request", "code_change", "explicit_workflow"):
        if not isinstance(decision.get(field), bool):
            raise RouterGateError(f"{field} must be an explicit boolean")
    if not direct:
        _text(decision, "agent", "decision")
        _text(decision, "skill", "decision")
        plan = Path(_text(decision, "plan_file", "decision"))
        plan = plan if plan.is_absolute() else repo_root / plan
        if plan.name != "task_plan.md" or not plan.is_file() or not plan.read_text(encoding="utf-8").strip():
            raise RouterGateError("Simple+ requires an existing nonempty task_plan.md at plan_file")
        stack = decision.get("stack")
        if not isinstance(stack, list) or "anti-rationalization-core" not in stack:
            raise RouterGateError("Simple+ requires anti-rationalization-core in stack")
    _gate(decision, "creation", decision["creation_request"], repo_root)
    _gate(decision, "quality_loop", decision["code_change"] and complexity in ("medium", "complex"), repo_root)
    _gate(
        decision,
        "workflow",
        bool(decision.get("pipeline")) or complexity == "complex" or decision["explicit_workflow"],
        repo_root,
    )
    _gate(decision, "composition", complexity == "complex", repo_root)
    if complexity == "complex":
        agents = decision.get("agents", [])
        skills = decision.get("skills", [])
        if (
            not isinstance(agents, list)
            or not isinstance(skills, list)
            or not all(isinstance(name, str) for name in agents + skills)
        ):
            raise RouterGateError("composition agents and skills must be lists of names")
        complete = (
            len(set(agents + [decision["agent"]])) >= 2
            and len(set(skills + [decision["skill"]])) >= 2
            and bool(decision.get("pipeline"))
        )
        if not complete:
            _text(decision, "composition_exception", "decision")
    # A continuation does not cancel the original protected methodology. These
    # guards select a method, never permission: newer "do not push" constraints
    # still reach intent validation unchanged. A replacement task must start a
    # fresh explicit router invocation instead of quietly weakening its guard.
    required_prior = set(marker.get("prior_request_hashes", [])) if marker else set()
    for message in spec.get("prior_context") or []:
        if text_hash(message) in required_prior:
            _protected_guard(message, decision)
    _protected_guard(request, decision)
    # Import lazily: non-router builder users require no Jev transport.
    from jev_intent_align import evaluate_alignment

    route = {key: decision.get(key) for key in ("agent", "skill", "pipeline", "complexity", "source", "reasoning")}
    try:
        context = spec.get("prior_context")
        receipt = evaluate_alignment(
            request, route, intent, **({"prior_context": context} if context is not None else {})
        )
    except Exception as exc:
        mark_checked_blocked(session_id(), request, expected_generation=generation)
        raise RouterGateError(f"intent validation failed; dispatch blocked: {exc}") from exc
    if (
        not isinstance(receipt, dict)
        or receipt.get("alignment") != "aligned"
        or receipt.get("aligned") is not True
        or receipt.get("clarification_needed") is not False
    ):
        mark_checked_blocked(session_id(), request, expected_generation=generation)
        raise RouterGateError(
            "intent validation did not approve this handoff; correct the intent/route or restore Jev and retry. Receipt: "
            + json.dumps(receipt, sort_keys=True)
        )
    receipt["_router_generation"] = generation
    return receipt
