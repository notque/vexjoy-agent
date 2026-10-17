#!/usr/bin/env python3
"""Pre-route guard, Jev attachment evidence, and route finalization for /d.

The session model picks the primary agent, skill, and pipeline from the full
routing manifest, applying the rule text in `skills/meta/do/SKILL.md` Phase 2
(printed by `scripts/print-route-rules.py`). This script does the work around
that pick. See `skills/meta/d/references/jev-classifier-design.md`.

Two modes, both exit 0 and print JSON to stdout:

  prepare (default)   Runs before the pick.
    1. Deterministic force-route guard (`pre-route.py`). A high-confidence
       match for pr-workflow, pr-pipeline, or security is recorded as
       `forced`: its skill and pipeline are final (`/do` Phase 2 Step 1(a)).
       Every other force match is dropped, as `/do` Step 1(b) drops it.
    2. One Jev evaluation of independent Noul questions: the five stack
       signals and the six domain-attachment questions. They read the request
       only, so they do not depend on the pick. A failed or malformed Jev
       answer leaves the evidence empty; routing still proceeds.
    3. Project facts (names only) detected from `--cwd`, for the pick.

  --finalize          Runs after the pick.
    Takes the prepare result and the model's decision JSON, validates every
    name against the live manifest (`/do` section validator), lets a safety
    force route override the skill and pipeline, fills a missing skill with
    `workflow`, and computes `attach` (extra skills that ride with the primary
    skill) and, for a null or general-purpose agent, the skill's owning agent.
    The output is the route JSON that `jev-intent-align.py --route-file` and
    `build-dispatch.py` consume.

Cost: one Jev evaluation per prepare, none per finalize. Every /d invocation
adds one batched intent-alignment evaluation (`jev_intent_align.py`).

Usage:
    python3 scripts/jev-route.py --request-file /tmp/req.txt --json-compact
    python3 scripts/jev-route.py --finalize --result-file prepared.json --decision-file decision.json

Exit codes:
    0 -- always (output is JSON to stdout; tracebacks, if any, go to stderr)
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
import tempfile
import time
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent

_SCRIPTS_DIR = Path(__file__).resolve().parent
if str(_SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS_DIR))
import jev_transport

JEV_MODEL = "typesafe-ai/jev-1.14.0"

# Noul signal -> booleans at this threshold (raw scores also reported).
STACK_SIGNAL_THRESHOLD = 0.6

DEFAULT_TIMEOUT = 6.5

# Router entry points: skills whose job is to dispatch a request to another
# skill or agent. Following a pick of `d` or `do` through build-dispatch.py's
# "Call the Skill tool with `d`" action would re-enter the router on the same
# request. They are never valid routing targets.
ROUTER_ENTRY_POINT_SKILLS = {"d", "do"}

NOUL_SIGNAL_KEYS = (
    "tests_requested",
    "research_needed",
    "comprehensive_review",
    "local_only",
    "objective_loop_worthy",
)

VALID_COMPLEXITIES = {"simple", "medium", "complex"}

_SANITIZE_RE = re.compile(r"[^a-zA-Z0-9_]")


def _sanitize_key(name: str) -> str:
    """Turn a manifest name into a safe Jev question key (letters/digits/_)."""
    return _SANITIZE_RE.sub("_", name)


TESTS_REQUESTED_INSTRUCTIONS = (
    "True when the request explicitly asks for tests or says the result must be production-ready "
    '(e.g. "with tests", "production ready", "make sure it is tested").'
)
RESEARCH_NEEDED_INSTRUCTIONS = (
    "True when the request says research or investigation must happen before or as part of the work "
    '(e.g. "research needed", "investigate first", "look into how X works before building").'
)
COMPREHENSIVE_REVIEW_INSTRUCTIONS = (
    "True when the request asks for a comprehensive, thorough, or full review, or names 5 or more files to "
    "review, with no single diff driving the review."
)
LOCAL_ONLY_INSTRUCTIONS = (
    "True when the request says the work must stay local and not be pushed or published "
    '(e.g. "local only", "no push", "keep it local", "stay local").'
)
OBJECTIVE_LOOP_WORTHY_INSTRUCTIONS = (
    "True when the request states an objective with explicit done-criteria and asks the work to continue, "
    'retrying or iterating, until that objective is met (e.g. "loop until done", an explicit definition of done).'
)

# Domain-attachment Nouls, multi-select. The primary `skill` slot holds ONE
# methodology; these ask, one property each, whether a domain umbrella skill
# must ride along so its references load (Go patterns, UI design, Kubernetes,
# testing, Jev program design). Policy (threshold, cap, ordering) stays in
# `_attachments`. Keys are the manifest skill names.
DOMAIN_NOUL_INSTRUCTIONS = {
    "programming": (
        "True when the work reads, writes, reviews, tests, or fixes Go, Kotlin, PHP, Swift, or TypeScript source "
        "code. False when the only code is Python, when no source code is involved, or when 'go' is an ordinary "
        'verb ("go ahead", "go through").'
    ),
    "frontend": (
        "True when the work creates, changes, or judges a web page's visual design, layout, styling, UI "
        "components, or accessibility. False for type errors, build configuration, or backend work with no "
        "visible interface change."
    ),
    "kubernetes": (
        "True when the work creates, changes, or diagnoses Kubernetes or Helm resources: pods, deployments, "
        "charts, namespaces, RBAC, or resource limits."
    ),
    "testing": (
        "True when writing, fixing, or running automated tests is part of the deliverable (new tests, a flaky "
        "test, a regression test, coverage). False when tests are not mentioned and the request only builds or "
        "explains something."
    ),
    "building-with-jev": (
        "True when the work writes, changes, tunes, or evaluates a program that calls Jev, TypeSafe's judgment "
        "model, including its questions and criteria."
    ),
    "research": (
        "True when the deliverable is findings gathered from external sources (web pages, documentation, papers, "
        "public claims) and checked or cited. False when the investigation only reads this repository's code, "
        "logs, or runtime behavior."
    ),
}
DOMAIN_NOUL_PREFIX = "domain__"

# Deterministic domain floor: an agent whose whole domain is one umbrella
# skill always carries that skill. Only unambiguous pairs belong here; mixed
# agents (TypeScript, Python) rely on the domain Nouls above.
DOMAIN_SKILL_BY_AGENT = {
    "golang-general-engineer": "programming",
    "kotlin-general-engineer": "programming",
    "php-general-engineer": "programming",
    "swift-general-engineer": "programming",
    "kubernetes-helm-engineer": "kubernetes",
    "ui-design-engineer": "frontend",
}

# Stack signal -> callable skill (or shared pattern) it attaches.
SIGNAL_SKILLS = {
    "tests_requested": "testing",
    "comprehensive_review": "review",
    "objective_loop_worthy": "workflow",
    "local_only": "local-only",
}
# research_needed is not mapped: it fires on ordinary diagnosis ("find why"),
# and /d answers it with a research-coordinator-engineer fan-out, not a skill.

# Agent default when the route has no domain agent (null or general-purpose):
# the skill's owning agent, mirroring /do's Pairing rule.
AGENT_BY_SKILL = {
    "building-with-jev": "python-general-engineer",
    "jev-design": "typescript-frontend-engineer",
    "kubernetes": "kubernetes-helm-engineer",
    "frontend": "ui-design-engineer",
    "research": "research-coordinator-engineer",
    "testing": "testing-automation-engineer",
    "toolkit": "toolkit-governance-engineer",
    "docs-sync-checker": "technical-documentation-engineer",
    "security": "reviewer-system",
    "review": "reviewer-code",
    "writing": "technical-journalist-writer",
}

# Force routes that stay authoritative for their slot. Mirrors /do Phase 2
# Step 1(a): only genuine git/PR work and security work override the semantic
# pick. Every other force match is dropped.
SAFETY_FORCE_NAMES = frozenset({"pr-workflow", "pr-pipeline", "security"})

MAX_ATTACHMENTS = 3  # extra skills beyond the primary; keeps precision high

# Skill filled in when the pick leaves the skill slot empty: /do's
# Skill-greediness gate fallback.
FALLBACK_SKILL = "workflow"

NOUL_INSTRUCTIONS = {
    "tests_requested": TESTS_REQUESTED_INSTRUCTIONS,
    "research_needed": RESEARCH_NEEDED_INSTRUCTIONS,
    "comprehensive_review": COMPREHENSIVE_REVIEW_INSTRUCTIONS,
    "local_only": LOCAL_ONLY_INSTRUCTIONS,
    "objective_loop_worthy": OBJECTIVE_LOOP_WORTHY_INSTRUCTIONS,
}


def _norm(value: object) -> str | None:
    """Normalize a route field: treat null-likes as None, else stripped str."""
    if value is None:
        return None
    text = str(value).strip()
    if text == "" or text.lower() in {"null", "none", "n/a", "na"}:
        return None
    return text


def _run_pre_route(request_text: str) -> dict:
    """Shell out to pre-route.py via a temp file, with an argument list only.

    A temp file holds the request so shell metacharacters in it can never
    break the subprocess call (no shell interpretation is involved at all),
    and the temp file is removed afterward.
    """
    tmp_path: str | None = None
    try:
        with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False, encoding="utf-8") as tmp:
            tmp.write(request_text)
            tmp_path = tmp.name
        proc = subprocess.run(
            [sys.executable, str(REPO_ROOT / "scripts" / "pre-route.py"), "--request-file", tmp_path, "--json-compact"],
            capture_output=True,
            text=True,
            cwd=str(REPO_ROOT),
            timeout=30,
            check=False,
        )
        return json.loads(proc.stdout)
    except Exception as exc:
        # pre-route.py itself never raises (exit 0 always, JSON to stdout); a
        # failure here means the subprocess could not run at all. Fail safe
        # to "no force-route match" so the request still reaches the pick.
        print(f"[jev-route] pre-route subprocess failed: {type(exc).__name__}: {exc}", file=sys.stderr)
        return {
            "matched": False,
            "agent": None,
            "skill": None,
            "pipeline": None,
            "confidence": "low",
            "match_type": "fallthrough",
            "reasoning": f"pre-route subprocess failed: {type(exc).__name__}: {exc}",
            "stack": [],
        }
    finally:
        if tmp_path:
            try:
                Path(tmp_path).unlink(missing_ok=True)
            except OSError:
                pass


def _load_manifest_entries() -> list[dict]:
    """Live AGENTS:/SKILLS:/PIPELINES: membership via routing-manifest.py --json.

    Subprocess, not import: routing-manifest.py has a hyphenated filename.
    """
    proc = subprocess.run(
        [sys.executable, str(REPO_ROOT / "scripts" / "routing-manifest.py"), "--json"],
        capture_output=True,
        text=True,
        cwd=str(REPO_ROOT),
        timeout=30,
        check=True,
    )
    return json.loads(proc.stdout)


def _membership_sets(entries: list[dict]) -> tuple[set[str], set[str], set[str]]:
    """Live AGENTS:/SKILLS:/PIPELINES: name sets. Router entry points are not skills."""
    agent_names = {e["name"] for e in entries if e.get("type") == "agent"}
    agent_names.add("general-purpose")  # built-in fallback agent, absent from the manifest
    skill_names = {
        e["name"] for e in entries if e.get("type") == "skill" and e["name"] not in ROUTER_ENTRY_POINT_SKILLS
    }
    pipeline_names = {e["name"] for e in entries if e.get("type") == "pipeline"}
    return agent_names, skill_names, pipeline_names


def _noul(answers: dict, key: str) -> float:
    """Read one Noul probability; raise unless it is a number in [0, 1].

    A malformed answer must fail the call (the caller drops the evidence), not
    be clamped or coerced into a confident-looking score.
    """
    value = answers[key]["noul"]
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not 0.0 <= value <= 1.0:
        raise ValueError(f"Jev answer {key!r} is not a probability in [0, 1]: {value!r}")
    return float(value)


_LANGUAGE_MARKERS = (
    ("python", ("pyproject.toml", "requirements.txt", "setup.py", "Pipfile")),
    ("typescript", ("tsconfig.json",)),
    ("javascript", ("package.json",)),
    ("go", ("go.mod",)),
    ("rust", ("Cargo.toml",)),
    ("php", ("composer.json",)),
    ("kotlin", ("build.gradle.kts",)),
    ("swift", ("Package.swift",)),
    ("ruby", ("Gemfile",)),
)
_DEPENDENCY_FILES = ("pyproject.toml", "requirements.txt", "Pipfile", "package.json", "go.mod", "composer.json")
_FRAMEWORK_TOKENS = (
    ("flask", "flask"),
    ("django", "django"),
    ("fastapi", "fastapi"),
    ("react", '"react"'),
    ("next.js", '"next"'),
    ("express", '"express"'),
    ("vue", '"vue"'),
    ("laravel", "laravel/framework"),
)
_DATASTORE_TOKENS = (
    ("sqlite", "sqlite"),
    ("peewee", "peewee"),
    ("postgres", "psycopg"),
    ("postgres", '"pg"'),
    ("mysql", "mysql"),
    ("redis", "redis"),
    ("mongodb", "mongo"),
)
_MAX_DEPENDENCY_BYTES = 200_000


def detect_project_context(cwd: str | Path | None) -> dict | None:
    """Languages, frameworks, and datastores of the repository at `cwd`, from marker files.

    Pure code, no Jev call. Reads only file names and dependency manifests in
    the top directory; returns names, never paths or file contents. Returns
    None when nothing is detected.
    """
    if not cwd:
        return None
    try:
        root = Path(cwd)
        if not root.is_dir():
            return None
        present = {name for _, names in _LANGUAGE_MARKERS for name in names if (root / name).is_file()}
        languages = [lang for lang, names in _LANGUAGE_MARKERS if any(n in present for n in names)]
        text = ""
        for name in _DEPENDENCY_FILES:
            path = root / name
            if path.is_file() and path.stat().st_size <= _MAX_DEPENDENCY_BYTES:
                text += path.read_text(encoding="utf-8", errors="replace").lower() + "\n"
    except OSError:
        return None
    frameworks = list(dict.fromkeys(label for label, token in _FRAMEWORK_TOKENS if token in text))
    datastores = list(dict.fromkeys(label for label, token in _DATASTORE_TOKENS if token in text))
    if not (languages or frameworks or datastores):
        return None
    context: dict[str, list[str]] = {}
    if languages:
        context["languages"] = languages
    if frameworks:
        context["frameworks"] = frameworks
    if datastores:
        context["datastores"] = datastores
    return context


def _state(request_text: str, project: dict | None) -> str | dict:
    """Bare request when no project facts exist; otherwise request plus observed project facts."""
    if not project:
        return request_text
    return {"request": request_text, "project": project}


def _build_attach_payload(request_text: str, project: dict | None = None) -> dict:
    """One Jev payload: the stack signals and the domain-attachment questions."""
    questions: dict[str, dict] = {
        key: {"type": "noul", "instructions": NOUL_INSTRUCTIONS[key]} for key in NOUL_SIGNAL_KEYS
    }
    for name, instructions in DOMAIN_NOUL_INSTRUCTIONS.items():
        questions[f"{DOMAIN_NOUL_PREFIX}{_sanitize_key(name)}"] = {"type": "noul", "instructions": instructions}
    return {"state": _state(request_text, project), "model": JEV_MODEL, "questions": questions}


def _call_jev(payload: dict, timeout: float) -> tuple[dict, float]:
    """Evaluate one Jev payload through the selected transport.

    Both transports redact before sending. Transport failures retain safe
    receipts; callers still own fail-open behavior.
    """
    started = time.monotonic()
    # Packed: split at the reliable request size up front (jev-production-lessons fact 2).
    data = jev_transport.evaluate_packed(payload.get("state", {}), payload.get("questions", {}), timeout=timeout)
    return data, (time.monotonic() - started) * 1000.0


def _extract_usage(data: dict) -> dict | None:
    """Passthrough token usage from one Jev response. Never fabricated."""
    usage_raw = data.get("usage")
    if not isinstance(usage_raw, dict):
        return None
    input_tokens = usage_raw.get("input_tokens")
    output_tokens = usage_raw.get("output_tokens")
    if isinstance(input_tokens, int) and isinstance(output_tokens, int):
        return {"input_tokens": input_tokens, "output_tokens": output_tokens}
    return None


def _parse_attach(data: dict) -> dict:
    """Parse the attachment call's answers. Raises on a malformed or missing answer."""
    answers = data["answers"]
    signals: dict[str, bool] = {}
    signal_scores: dict[str, float] = {}
    for key in NOUL_SIGNAL_KEYS:
        score = _noul(answers, key)
        signal_scores[key] = score
        signals[key] = score >= STACK_SIGNAL_THRESHOLD
    domain_scores = {
        name: _noul(answers, f"{DOMAIN_NOUL_PREFIX}{_sanitize_key(name)}") for name in DOMAIN_NOUL_INSTRUCTIONS
    }
    return {"signals": signals, "signal_scores": signal_scores, "domain_scores": domain_scores}


def _is_force(pre_route: dict) -> bool:
    return bool(
        pre_route.get("matched")
        and pre_route.get("confidence") == "high"
        and pre_route.get("match_type") == "force_route"
    )


def _is_safety_force(pre_route: dict) -> bool:
    return _norm(pre_route.get("skill")) in SAFETY_FORCE_NAMES or _norm(pre_route.get("pipeline")) in SAFETY_FORCE_NAMES


def _forced(pre_route: dict) -> dict | None:
    """The safety force route, or None. Non-safety force matches are not carried forward."""
    if not (_is_force(pre_route) and _is_safety_force(pre_route)):
        return None
    return {
        "agent": _norm(pre_route.get("agent")),
        "skill": _norm(pre_route.get("skill")),
        "pipeline": _norm(pre_route.get("pipeline")),
        "stack": list(pre_route.get("stack") or []),
        "match_type": "force_route",
        "reasoning": str(pre_route.get("reasoning", "")),
    }


def prepare(request_text: str, timeout: float, project: dict | None = None) -> dict:
    """Guard and gather attachment evidence for one request string. Never raises."""
    pre_route = _run_pre_route(request_text)
    forced = _forced(pre_route)
    result: dict = {
        "available": False,
        "jev_called": False,
        "source": "pre-route-force" if forced else "session",
        "forced": forced,
        "stack": list(forced["stack"]) if forced else [],
        "project": project,
        "signals": None,
        "signal_scores": None,
        "domain_scores": None,
        "error": None,
        "latency_ms": None,
        "usage": None,
    }
    available, reason = jev_transport.available()
    if not available:
        result["error"] = f"Jev unavailable: {reason}"
        return result
    result["available"] = True
    try:
        result["jev_called"] = True
        data, latency = _call_jev(_build_attach_payload(request_text, project), timeout)
        result.update(_parse_attach(data))
        result["latency_ms"] = latency
        result["usage"] = _extract_usage(data)
    except Exception as exc:
        result["error"] = f"attachment evidence failed: {type(exc).__name__}: {str(exc)[:200]}"
        telemetry = getattr(exc, "telemetry", None)
        if isinstance(telemetry, dict):
            result["transport_retry"] = telemetry
    return result


def _attachments(result: dict, skill_names: set[str]) -> list[str]:
    """Extra skills (and shared patterns) that ride with the primary skill. Pure policy.

    Order: pre-route stack, the agent's domain floor, domain Nouls by score,
    then stack signals. Unknown names are dropped; at most MAX_ATTACHMENTS
    skills are kept (shared patterns such as local-only do not count).
    """
    primary = result.get("skill")
    candidates: list[str] = list(result.get("stack") or [])
    floor = DOMAIN_SKILL_BY_AGENT.get(result.get("agent") or "")
    if floor:
        candidates.append(floor)
    domain_scores = result.get("domain_scores") or {}
    candidates += [
        name for name, score in sorted(domain_scores.items(), key=lambda kv: -kv[1]) if score >= STACK_SIGNAL_THRESHOLD
    ]
    signals = result.get("signals") or {}
    candidates += [skill for key, skill in SIGNAL_SKILLS.items() if signals.get(key)]

    attach: list[str] = []
    n_skills = 0
    for name in candidates:
        if not name or name == primary or name in attach:
            continue
        if name == "local-only":
            attach.append(name)
            continue
        if skill_names and name not in skill_names:
            continue
        if n_skills >= MAX_ATTACHMENTS:
            continue
        attach.append(name)
        n_skills += 1
    return attach


def _default_agent(result: dict) -> str | None:
    """Owning agent for the primary or an attached skill when the route has no domain agent."""
    for name in [result.get("skill")] + list(result.get("attach") or []):
        agent = AGENT_BY_SKILL.get(name or "")
        if agent:
            return agent
    return None


def _derive_complexity(pipeline: str | None, agents: list[str], signals: dict | None) -> str:
    """Fallback when the decision carries no valid complexity."""
    if pipeline or agents:
        return "complex"
    if any((signals or {}).values()):
        return "medium"
    return "simple"


def finalize(prepared: dict, decision: dict, entries: list[dict]) -> dict:
    """Validate the session model's pick and build the route. Pure; never calls Jev.

    `problems` lists every correction the caller should review: a name absent
    from the live manifest was dropped, or general-purpose has no reason.
    """
    agent_names, skill_names, pipeline_names = _membership_sets(entries)
    problems: list[str] = []

    agent = _norm(decision.get("agent"))
    skill = _norm(decision.get("skill"))
    pipeline = _norm(decision.get("pipeline"))

    # /do section validator: an agent slot holding a skill name moves to the skill slot.
    if agent and agent not in agent_names:
        if agent in skill_names:
            skill = skill or agent
        problems.append(f"agent {agent!r} is not in AGENTS")
        agent = None
    if skill and skill not in skill_names:
        problems.append(f"skill {skill!r} is not in SKILLS")
        skill = None
    if pipeline and pipeline not in pipeline_names:
        problems.append(f"pipeline {pipeline!r} is not in PIPELINES")
        pipeline = None

    raw_agents = decision.get("agents")
    agents: list[str] = []
    for item in raw_agents if isinstance(raw_agents, list) else []:
        name = _norm(item)
        if not name or name == agent or name in agents:
            continue
        if name in agent_names and name != "general-purpose":
            agents.append(name)
        else:
            problems.append(f"fan-out agent {name!r} is not in AGENTS")

    forced = prepared.get("forced") or {}
    forced_applied = False
    if forced.get("skill") and forced["skill"] in skill_names:
        skill, forced_applied = forced["skill"], True
    if forced.get("pipeline") and forced["pipeline"] in pipeline_names:
        pipeline, forced_applied = forced["pipeline"], True
    forced_agent = forced.get("agent") if forced.get("agent") in agent_names else None
    if forced_agent:
        agent = forced_agent

    skill_source = "pre-route" if forced.get("skill") and skill == forced["skill"] else "session"
    if skill is None and FALLBACK_SKILL in skill_names:
        skill, skill_source = FALLBACK_SKILL, "fallback"

    route: dict = {
        "agent": agent,
        "skill": skill,
        "pipeline": pipeline,
        "agents": agents,
        "stack": list(prepared.get("stack") or []),
        "signals": prepared.get("signals"),
        "signal_scores": prepared.get("signal_scores"),
        "domain_scores": prepared.get("domain_scores"),
    }
    route["attach"] = _attachments(route, skill_names)
    route["agent_source"] = "pre-route" if forced_agent and agent == forced_agent else "session"
    if agent in (None, "general-purpose"):
        default = _default_agent(route)
        if default:
            route["agent"] = default
            route["agent_source"] = "skill-default"
        else:
            route["agent"] = "general-purpose"
            route["agent_source"] = "session"
            if not _norm(decision.get("fallback_reason")):
                problems.append("general-purpose needs a fallback_reason: general-purpose: <why no agent covers this>")

    complexity = _norm(decision.get("complexity"))
    if complexity not in VALID_COMPLEXITIES:
        complexity = _derive_complexity(pipeline, agents, route["signals"])
    confidence = _norm(decision.get("confidence"))
    return {
        "source": "pre-route-force" if forced_applied else "session",
        "agent": route["agent"],
        "agent_source": route["agent_source"],
        "skill": skill,
        "skill_source": skill_source,
        "pipeline": pipeline,
        "agents": agents,
        "attach": route["attach"],
        "stack": route["stack"],
        "complexity": complexity,
        "confidence": confidence if confidence in {"high", "medium", "low"} else "medium",
        "reasoning": str(decision.get("reasoning") or ""),
        "fallback_reason": _norm(decision.get("fallback_reason")),
        "signals": route["signals"],
        "signal_scores": route["signal_scores"],
        "domain_scores": route["domain_scores"],
        "problems": problems,
    }


def _error_route(exc: Exception, reason_prefix: str) -> dict:
    return {
        "available": False,
        "jev_called": False,
        "source": "error",
        "forced": None,
        "stack": [],
        "project": None,
        "signals": None,
        "signal_scores": None,
        "domain_scores": None,
        "error": f"{reason_prefix}: {type(exc).__name__}: {str(exc)[:200]}",
        "latency_ms": None,
        "usage": None,
    }


def _read_json_object(path: str, label: str) -> dict:
    value = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"{label} must hold one JSON object")
    return value


def main() -> int:
    """CLI entry point."""
    parser = argparse.ArgumentParser(
        description="Pre-route guard, Jev attachment evidence, and route finalization for /d dispatch.",
    )
    parser.add_argument("--json-compact", action="store_true", help="Output compact JSON (no indentation).")
    parser.add_argument(
        "--finalize",
        action="store_true",
        help="Validate a decision and compute attach. Needs --result-file and --decision-file.",
    )
    parser.add_argument("--result-file", help="--finalize: file holding the prepare result.")
    parser.add_argument("--decision-file", help="--finalize: file holding the model's decision JSON.")
    req_group = parser.add_mutually_exclusive_group()
    req_group.add_argument("--request", help="The user request string to route.")
    req_group.add_argument(
        "--request-file", help="Path to a file containing the request string (avoids shell-splicing)."
    )
    parser.add_argument(
        "--timeout",
        type=float,
        default=DEFAULT_TIMEOUT,
        help=f"Jev HTTP call timeout in seconds (default {DEFAULT_TIMEOUT}).",
    )
    parser.add_argument(
        "--cwd",
        default=None,
        help="Repository directory the request is about. Its languages and frameworks are detected from marker "
        "files and passed on as project facts. Omit to send none.",
    )
    parser.add_argument(
        "--project-json",
        default=None,
        help='Project facts as JSON, e.g. {"languages":["python"]}. Overrides --cwd detection (eval use).',
    )
    args = parser.parse_args()

    try:
        if args.finalize:
            if not (args.result_file and args.decision_file):
                parser.error("--finalize needs --result-file and --decision-file")
            result = finalize(
                _read_json_object(args.result_file, "--result-file"),
                _read_json_object(args.decision_file, "--decision-file"),
                _load_manifest_entries(),
            )
        else:
            if not (args.request or args.request_file):
                parser.error("one of --request or --request-file is required")
            request_text = Path(args.request_file).read_text(encoding="utf-8") if args.request_file else args.request
            project = None
            if args.project_json:
                parsed = json.loads(args.project_json)
                project = parsed if isinstance(parsed, dict) and parsed else None
            elif args.cwd:
                project = detect_project_context(args.cwd)
            result = prepare(request_text, args.timeout, project)
    except SystemExit:
        raise
    except Exception as exc:
        import traceback

        traceback.print_exc(file=sys.stderr)
        result = _error_route(exc, "jev-route error")

    indent = None if args.json_compact else 2
    print(json.dumps(result, indent=indent))
    return 0


if __name__ == "__main__":
    sys.exit(main())
