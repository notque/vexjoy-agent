#!/usr/bin/env python3
"""Merged deterministic-guard + two-stage Jev classifier CLI for /d dispatch.

v2 redesign (2026-09-16), replacing v1's single flat Choice call. v1 asked one
`Choice` over ALL manifest candidates per dimension with descriptions
truncated to ~100 chars, and that truncation regularly cut the exact
`not_for` disambiguation text that would have prevented a miss. This version
adopts a two-stage progressive-disclosure pattern (TypeSafe's own
`skill_suggestion` cookbook: cheap wide rank, then full-detail shortlist
rerank) but does NOT transplant that cookbook's shape wholesale — the
cookbook is a single-pick recipe, and /do's actual routing contract is
multi-slot (one primary agent + an independent fan-out `agents` list, one
skill + an independent `stack` list, one optional pipeline). See
`skills/meta/d/references/jev-classifier-design.md` for the full design
writeup, including exactly which cookbook ideas were reused and where this
design deliberately diverges and why.

Flow, in order:
  1. Deterministic force-route guard (`pre-route.py`), applied as
     `skills/meta/do/SKILL.md` Phase 2 Step 1 does. A high-confidence
     force_route match for pr-workflow, pr-pipeline, or security keeps its
     skill and pipeline; Jev never overrides them and only supplies the
     agent and attachments. Any other force match is a hint that joins the
     stage-2 skill shortlist (2026-09-22: keyword matches such as "write
     post" in "Write a PostToolUse hook" were ending classification with no
     agent). If Jev fails, a force match stands as before.
  2. Jev transport presence check (Vercel Gateway or direct Jev API).
  3. Live manifest membership (`routing-manifest.py --json`, subprocess —
     hyphenated filename, not import-able).
  4. STAGE 1 (one Jev HTTP call): a wide, cheap rank over ALL manifest
     candidates per single-select dimension (agent/skill/pipeline Choice,
     using the same ~100-char truncated descriptions v1 built), plus 3
     parallel gate Noul questions ("needs a skill," "a pipeline would
     apply," "prose alone suffices" (inverted)). `gate_score` is the mean of
     the oriented gate nouls. Below `--gate-threshold` (default 0.30): this
     is a Trivial-bypass — no agent/skill/pipeline needed at all, matching
     `/do`'s own Trivial classification. Stage 2 is skipped entirely; the
     result is a real terminal state (`source: "jev-trivial-bypass"`), not a
     fallback.
  5. STAGE 2 (one Jev HTTP call, only when gate_score clears the threshold):
     for each single-select dimension, rerank ONLY its stage-1 top-~3
     shortlist (top-1 for pipeline, see the design reference for why) using
     FULL untruncated descriptions plus `not_for` text, each paired with a
     per-candidate "does this genuinely fit" Noul. The 5 stack-signal Nouls
     (independent, multi-select) and 0-3 fan-out-candidate Nouls (agents
     ranked just below the primary shortlist, only asked when the request
     plausibly spans multiple domains) ride in the same call.
  6. Manifest-membership validation (never trust a hallucinated name) is the
     ONLY thing that can invalidate a primary agent/skill/pipeline pick as of
     2026-09-16. The earlier `--fits-threshold`-gated rejection on primary
     selection was removed per the owner's explicit instruction (it was
     bouncing ~26% of requests back to a full /do manifest read AFTER a real
     Jev call had already happened — the worst-case token cost /d exists to
     avoid, for a threshold never validated as correlating with quality):
     Jev's top-ranked Choice pick is always used once it is a valid,
     shortlisted name. `agent` or `skill` being an invalid/off-shortlist name
     (near the ~0% error rate, not a confidence judgment) is still a genuine
     "nothing to act on" condition -> `fallback: true`, callers MUST defer to
     full /do Phase 1-4. `fits_threshold`/`--fits-threshold` still exists,
     scoped down to gating optional fan-out-candidate inclusion only (a
     genuine "does this extra agent apply at all" decision, not "which real
     option wins").
  7. Attachment (pure code, `_attachments`): extra skills that ride with
     the primary skill, from the pre-route stack, the agent's domain floor,
     stage-2 domain Nouls, and stack signals; at most MAX_ATTACHMENTS. A
     route with no domain agent takes the skill's owning agent
     (`_default_agent`). Measured by scripts/router_attachment/.
  8. Complexity is derived deterministically in Python from the final
     picks and signals (pipeline or fan-out present -> complex; any stack
     signal true -> medium; else simple) rather than asked as a Jev
     question — see the design reference for why this slot was dropped from
     the Jev call entirely in v2.

Cost model (hard constraint): classification uses at most 2 Jev evaluations
(0 when unavailable, 1 on trivial-bypass, 2 otherwise, force routes
included), each packed at the reliable request size, and every /d
invocation adds one batched intent-alignment evaluation — never one request
per question.

Mirrors `pre-route.py`'s CLI shape and JSON-output discipline: exit 0 always,
JSON to stdout, never raise past `main()`. Jev transport is selected by
`jev_transport.py`; transport clients own their retry behavior.

Usage:
    python3 scripts/jev-route.py --request "push my changes" --json-compact
    python3 scripts/jev-route.py --request-file /tmp/req.txt --json-compact

Exit codes:
    0 -- always (output is JSON to stdout; tracebacks, if any, go to stderr)
"""

from __future__ import annotations

import argparse
import json
import os
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
import jev_intent_align
import jev_transport
from routing_index_merge import gate_private_entries

JEV_MODEL = "typesafe-ai/jev"

# Noul signal -> booleans at this threshold (raw scores also reported).
STACK_SIGNAL_THRESHOLD = 0.6

# Superseded (see _parse_stage2 and the 2026-09-16 fallback-threshold removal
# note in this module's docstring); kept for CLI backward compatibility only,
# has no effect on routing. A user-supplied override is never silently
# dropped -- main() prints a one-line stderr notice when it differs from
# this default.
DEFAULT_CONFIDENCE_FLOOR = 0.7

DEFAULT_GATE_THRESHOLD = 0.30
DEFAULT_FITS_THRESHOLD = 0.30
DEFAULT_TIMEOUT = 6.5

STAGE1_SHORTLIST_N = 6  # accepted agent in top 6: 81% on dev; top 3: 63%

# Router entry points: skills whose entire job is to dispatch a request to
# ANOTHER skill/agent (they own the pre-route guard, the Jev call, and
# build-dispatch.py) -- never a legitimate routing destination in their own
# right. Both are indexed in skills/INDEX.json like any real skill (they have
# ordinary frontmatter), so without this exclusion Jev is free to rank and
# pick them, and following build-dispatch.py's own "Call the Skill tool with
# `d`" action contract on a self-selected `d`/`do` pick would re-enter the
# router on the same request -- an infinite loop. Confirmed 2026-09-16 by a
# live repro (jev-route.py returned skill="d" on a request complaining about
# `/d`'s own behavior). Excluded from the candidate set at the source (before
# either stage's criteria maps are built), the same class of fix as the
# existing manifest-membership validation: a name can be technically present
# in the manifest and still be structurally invalid as a routing target.
# Audited skills/meta/ on 2026-09-16 (grep for `build-dispatch.py` across
# every skill in the repo) -- `d` and `do` are the only two skills with this
# shape; no other meta-router entry point exists today. If a third one is
# ever added, add its name here too.
ROUTER_ENTRY_POINT_SKILLS = {"d", "do"}
FANOUT_MAX_CANDIDATES = 3
FANOUT_RANK_START = 3  # fan-out candidates are shortlist[3:3+MAX] -- ranks 4-6
FANOUT_DOMINANCE_PROB = 0.75  # skip fan-out nouls when one agent clearly dominates stage 1
FANOUT_GATE_SCORE_MIN = 0.6  # skip fan-out nouls on borderline-trivial requests

NOUL_SIGNAL_KEYS = (
    "tests_requested",
    "research_needed",
    "comprehensive_review",
    "local_only",
    "objective_loop_worthy",
)

GATE_NOUL_KEYS = ("needs_skill", "needs_pipeline", "prose_suffices")

VALID_COMPLEXITIES = {"trivial", "simple", "medium", "complex"}

_SANITIZE_RE = re.compile(r"[^a-zA-Z0-9_]")


def _sanitize_key(name: str) -> str:
    """Turn a manifest name into a safe Jev question key (letters/digits/_)."""
    return _SANITIZE_RE.sub("_", name)


# Jev question text. Semantics sourced from skills/meta/do/SKILL.md: Phase 1
# (complexity/Trivial table), Phase 2 (SECTION-INTEGRITY, FORCE-ROUTE
# semantic-not-keyword matching, SPECIFICITY, agent-handles-domain/
# skill-handles-methodology, COMBINATION DOCTRINE/MULTI-AGENT RULE), Phase 3
# (signal table). Kept concise; token cost here is real but is not the
# optimized metric -- the optimization target is the orchestrator's own
# context, which never sees this payload.
#
# HAND-MAINTAINED COPY, NOT GENERATED: unlike routing-manifest.py (built from
# frontmatter, CI-staleness-checked), the strings below are a manual
# paraphrase of do/SKILL.md prose. There is no automated drift check today.
# If /do's semantics change, update these instructions by hand, or Jev's
# judgments silently diverge from /do's.
AGENT_ROLE_RULES = (
    " Agents named reviewer-* only read existing code and report findings; pick one only when the request asks "
    "for a review or assessment of existing code, never for building, fixing, investigating, or operating. Pick "
    "project-coordinator-engineer only when the request is a batch of unrelated deliverables in different parts "
    "of the system. Two features of one subsystem, or one task with a condition attached, is a single deliverable."
)
AGENT_INSTRUCTIONS_STAGE1 = (
    "Pick the single agent whose domain best fits this request's technical or functional area, from this full "
    "list of short descriptions. This is a cheap wide pass -- your full probability spread across candidates "
    "matters as much as the top pick, since a shortlist of your highest-probability candidates gets full detail "
    "and a second look next. The agent owns the domain (language, framework, infrastructure); a skill, asked "
    "separately, owns the methodology."
) + AGENT_ROLE_RULES
SKILL_INSTRUCTIONS_STAGE1 = (
    "Pick the single skill whose description best matches the methodology this request needs -- how the work "
    "should be done, not who does it -- from this full list of short descriptions. This is a cheap wide pass -- "
    "your full probability spread across candidates matters as much as the top pick, since a shortlist of your "
    "highest-probability candidates gets full detail next. A task verb in the request (review, debug, refactor, "
    "test) usually names the matching skill."
)
PIPELINE_INSTRUCTIONS_STAGE1 = (
    "Pick whether this work has real phases (3+ distinct steps, gather-then-synthesize, mixed script+LLM work, "
    'intermediate artifacts worth keeping), from this full list of short descriptions, including "none" as an '
    "option when one agent and one skill fully cover the whole request in a single step. This is a cheap wide "
    "pass -- your full probability spread matters as much as the top pick, since the highest-probability real "
    "candidate gets full detail next."
)
AGENT_INSTRUCTIONS_STAGE2 = (
    "Pick the single agent whose domain genuinely fits this request's technical or functional area, from this "
    "short list of finalists only. Read each full description AND any NOT/exclusion clause carefully -- this is "
    "the precise pick, not the wide skim. Prefer a specific domain agent over general-purpose; pick "
    "general-purpose only when no listed agent's domain genuinely covers the request."
) + AGENT_ROLE_RULES
SKILL_INSTRUCTIONS_STAGE2 = (
    "Pick the single skill whose description best matches the methodology this request needs, from this short "
    "list of finalists only. Read each full description AND any NOT/exclusion clause carefully -- this is the "
    "precise pick, not the wide skim. Genuine git/version-control operations (actually pushing code, "
    "committing, opening or merging a pull request) match pr-workflow; metaphorical uses ('commit to a "
    "decision', 'push back on a proposal', 'merge ideas') do not."
)
PIPELINE_INSTRUCTIONS_STAGE2 = (
    'Pick between this one real pipeline candidate and "none", reading the full description AND any '
    "NOT/exclusion clause carefully. Pick the pipeline only when it semantically matches and the work has real "
    'multi-phase structure. Pick "none" when one agent and one skill fully cover the whole request in a single '
    "step."
)
GATE_NEEDS_SKILL_INSTRUCTIONS = (
    "True when this request needs a specific skill (a documented methodology) to be done well -- not just "
    "conversation or a quick lookup, but real work with a right way and a wrong way to do it."
)
GATE_NEEDS_PIPELINE_INSTRUCTIONS = (
    "True when a documented multi-phase pipeline or procedure would genuinely apply to this request -- real "
    "phases, not just multiple sentences of work."
)
GATE_PROSE_SUFFICES_INSTRUCTIONS = (
    "True when plain prose alone fully answers or resolves this request -- no agent, skill, or pipeline "
    "dispatch needed at all. This matches /do's own Trivial classification: acting on a single user-named file "
    "by path, answering a direct question, or a one-line reply, with no agent or skill decision beyond that."
)
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

# Domain-attachment Nouls (stage 2, multi-select). The primary `skill` slot
# holds ONE methodology; these ask, one property each, whether a domain
# umbrella skill must ride along so its references load (Go patterns, UI
# design, Kubernetes, testing, Jev program design). Policy (threshold, cap,
# ordering) stays in `_attachments`. Keys are the manifest skill names.
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
# the skill's owning agent, mirroring /do's Agent-greediness table.
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
# pick. Every other force match is a hint that joins Jev's stage-2 shortlist.
SAFETY_FORCE_NAMES = frozenset({"pr-workflow", "pr-pipeline", "security"})

MAX_ATTACHMENTS = 3  # extra skills beyond the primary; keeps precision high

NOUL_INSTRUCTIONS = {
    "tests_requested": TESTS_REQUESTED_INSTRUCTIONS,
    "research_needed": RESEARCH_NEEDED_INSTRUCTIONS,
    "comprehensive_review": COMPREHENSIVE_REVIEW_INSTRUCTIONS,
    "local_only": LOCAL_ONLY_INSTRUCTIONS,
    "objective_loop_worthy": OBJECTIVE_LOOP_WORTHY_INSTRUCTIONS,
}
GATE_NOUL_INSTRUCTIONS = {
    "needs_skill": GATE_NEEDS_SKILL_INSTRUCTIONS,
    "needs_pipeline": GATE_NEEDS_PIPELINE_INSTRUCTIONS,
    "prose_suffices": GATE_PROSE_SUFFICES_INSTRUCTIONS,
}


def _fit_instructions(kind: str, name: str, criteria_text: str) -> str:
    """Per-candidate 'does this genuinely fit' Noul instructions (stage 2)."""
    return (
        f'True only when "{name}" genuinely and specifically fits this request as its {kind} pick -- not '
        f"merely plausible, but the right one. {name}'s full description: {criteria_text} False when a "
        "different candidate's domain fits better, or this description's NOT/exclusion text describes the "
        "request."
    )


def _fanout_instructions(name: str, criteria_text: str) -> str:
    """Per-candidate fan-out Noul instructions (stage 2, agents dimension only)."""
    return (
        f'True only when "{name}" should ALSO run in parallel alongside the primary agent pick, on a distinct, '
        "independent subtask or failure mode this request genuinely contains -- matching /do's own MULTI-AGENT "
        f"RULE (2+ independent failures or subtasks -> multiple Agent tools). {name}'s full description: "
        f"{criteria_text} False when one agent fully covers the request, or this would just be a second "
        "opinion rather than a distinct subtask."
    )


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

    Mirrors skills/meta/do/SKILL.md Phase 2 Step 1 exactly: a temp file holds
    the request so shell metacharacters in it can never break the subprocess
    call (no shell interpretation is involved at all), and the temp file is
    removed afterward.
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
        # to "no force-route match" so the request still reaches Jev instead
        # of crashing /d outright.
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


def _truncate_desc(desc: str, max_len: int = 100) -> str:
    """Truncate a description to max_len chars, adding '...' if truncated.

    Mirrors routing-manifest.py's truncate_desc() logic in code (not by
    import -- that function lives in a hyphenated file).
    """
    if not desc:
        return ""
    if len(desc) <= max_len:
        return desc
    return desc[: max_len - 3] + "..."


def _membership_sets(entries: list[dict]) -> tuple[set[str], set[str], set[str]]:
    """Live AGENTS:/SKILLS:/PIPELINES: name sets, shared by both criteria builders."""
    agent_names = {e["name"] for e in entries if e.get("type") == "agent"}
    agent_names.add("general-purpose")  # built-in fallback agent, absent from the manifest
    skill_names = {e["name"] for e in entries if e.get("type") == "skill"}
    pipeline_names = {e["name"] for e in entries if e.get("type") == "pipeline"}
    return agent_names, skill_names, pipeline_names


def _build_criteria_maps(
    entries: list[dict],
) -> tuple[dict[str, str], dict[str, str], dict[str, str], set[str], set[str], set[str]]:
    """Stage 1: truncated (~100 char) Jev `criteria` maps, cheap wide pass.

    Returns (agent_criteria, skill_criteria, pipeline_criteria, agent_names,
    skill_names, pipeline_names).
    """
    agent_names, skill_names, pipeline_names = _membership_sets(entries)

    agent_criteria = {
        e["name"]: _truncate_desc(e.get("description") or "") for e in entries if e.get("type") == "agent"
    }
    agent_criteria["general-purpose"] = (
        "Fallback generalist agent; pick only when no domain agent above genuinely fits."
    )

    skill_criteria = {
        e["name"]: _truncate_desc(e.get("description") or "") for e in entries if e.get("type") == "skill"
    }

    pipeline_criteria = {
        e["name"]: _truncate_desc(e.get("description") or "") for e in entries if e.get("type") == "pipeline"
    }
    pipeline_criteria["none"] = "No real multi-phase structure; one agent/skill covers the whole request."

    return agent_criteria, skill_criteria, pipeline_criteria, agent_names, skill_names, pipeline_names


def _build_full_criteria_maps(
    entries: list[dict],
) -> tuple[dict[str, str], dict[str, str], dict[str, str]]:
    """Stage 2: UNTRUNCATED `description` + (" NOT: " + `not_for`) per entry.

    Sourced straight from routing-manifest.py's live `load_entries()` output
    (already untruncated) -- no filesystem reads of SKILL.md/agent.md files.
    """

    def _full_text(e: dict) -> str:
        desc = e.get("description") or ""
        not_for = e.get("not_for")
        return f"{desc} NOT: {not_for}" if not_for else desc

    agent_full = {e["name"]: _full_text(e) for e in entries if e.get("type") == "agent"}
    agent_full["general-purpose"] = "Fallback generalist agent; pick only when no domain agent above genuinely fits."

    skill_full = {e["name"]: _full_text(e) for e in entries if e.get("type") == "skill"}

    pipeline_full = {e["name"]: _full_text(e) for e in entries if e.get("type") == "pipeline"}
    pipeline_full["none"] = "No real multi-phase structure; one agent/skill covers the whole request."

    return agent_full, skill_full, pipeline_full


def _top_names_by_probability(probabilities: dict | None, valid_names: set[str], top_n: int) -> list[str]:
    """Rank `probabilities` (name -> 0..1) restricted to `valid_names`, take top_n."""
    items = [(str(name), float(prob)) for name, prob in (probabilities or {}).items() if str(name) in valid_names]
    items.sort(key=lambda kv: kv[1], reverse=True)
    return [name for name, _ in items[:top_n]]


PROJECT_CONTEXT_INSTRUCTIONS = (
    " The state's `project` field lists the languages, frameworks, and datastores detected in the repository "
    "this request is about. When the request names no language or framework, use `project` to pick the domain."
)

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
    None when nothing is detected, so the caller sends the bare request.
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


def _with_project_note(instructions: str, project: dict | None) -> str:
    return instructions + PROJECT_CONTEXT_INSTRUCTIONS if project else instructions


def _build_stage1_payload(
    request_text: str,
    agent_criteria: dict[str, str],
    skill_criteria: dict[str, str],
    pipeline_criteria: dict[str, str],
    project: dict | None = None,
) -> dict:
    questions = {
        "agent": {
            "type": "choice",
            "instructions": _with_project_note(AGENT_INSTRUCTIONS_STAGE1, project),
            "criteria": agent_criteria,
        },
        "skill": {"type": "choice", "instructions": SKILL_INSTRUCTIONS_STAGE1, "criteria": skill_criteria},
        "pipeline": {"type": "choice", "instructions": PIPELINE_INSTRUCTIONS_STAGE1, "criteria": pipeline_criteria},
    }
    for key in GATE_NOUL_KEYS:
        questions[key] = {"type": "noul", "instructions": GATE_NOUL_INSTRUCTIONS[key]}
    return {"state": _state(request_text, project), "model": JEV_MODEL, "questions": questions}


def _build_stage2_payload(
    request_text: str,
    agent_shortlist: list[str],
    agent_full: dict[str, str],
    skill_shortlist: list[str],
    skill_full: dict[str, str],
    pipeline_top1: str | None,
    pipeline_full: dict[str, str],
    fanout_candidates: list[str],
    project: dict | None = None,
) -> dict:
    """Stage 2: shortlist rerank + per-candidate fits + stack signals + fan-out.

    Every dimension present here is a parallel `questions` entry in ONE HTTP
    call -- the cost model's second and final round trip.
    """
    questions: dict[str, dict] = {}

    agent_criteria = {name: agent_full[name] for name in agent_shortlist}
    questions["agent"] = {
        "type": "choice",
        "instructions": _with_project_note(AGENT_INSTRUCTIONS_STAGE2, project),
        "criteria": agent_criteria,
    }
    for name in agent_shortlist:
        questions[f"agent_fit__{_sanitize_key(name)}"] = {
            "type": "noul",
            "instructions": _fit_instructions("agent", name, agent_full[name]),
        }

    skill_criteria = {name: skill_full[name] for name in skill_shortlist}
    questions["skill"] = {"type": "choice", "instructions": SKILL_INSTRUCTIONS_STAGE2, "criteria": skill_criteria}
    for name in skill_shortlist:
        questions[f"skill_fit__{_sanitize_key(name)}"] = {
            "type": "noul",
            "instructions": _fit_instructions("skill", name, skill_full[name]),
        }

    if pipeline_top1 is not None:
        pipeline_criteria = {pipeline_top1: pipeline_full[pipeline_top1], "none": pipeline_full["none"]}
        questions["pipeline"] = {
            "type": "choice",
            "instructions": PIPELINE_INSTRUCTIONS_STAGE2,
            "criteria": pipeline_criteria,
        }
        questions[f"pipeline_fit__{_sanitize_key(pipeline_top1)}"] = {
            "type": "noul",
            "instructions": _fit_instructions("pipeline", pipeline_top1, pipeline_full[pipeline_top1]),
        }

    for key in NOUL_SIGNAL_KEYS:
        questions[key] = {"type": "noul", "instructions": NOUL_INSTRUCTIONS[key]}

    for name, instructions in DOMAIN_NOUL_INSTRUCTIONS.items():
        questions[f"{DOMAIN_NOUL_PREFIX}{_sanitize_key(name)}"] = {"type": "noul", "instructions": instructions}

    for name in fanout_candidates:
        questions[f"fanout__{_sanitize_key(name)}"] = {
            "type": "noul",
            "instructions": _fanout_instructions(name, agent_full.get(name, "")),
        }

    return {"state": _state(request_text, project), "model": JEV_MODEL, "questions": questions}


def _call_jev(payload: dict, timeout: float) -> tuple[dict, float]:
    """Evaluate one Jev payload through the selected transport.

    Both transports redact before sending. Transport failures retain safe
    receipts; callers still own fail-open routing behavior.
    """
    started = time.monotonic()
    # Packed: split at the reliable request size up front (jev-production-lessons
    # fact 2); stage 1's full candidate lists sit near the single-request limit.
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


def _build_result(
    *,
    available: bool,
    jev_called: bool,
    matched: bool,
    fallback: bool,
    fallback_reason: str | None,
    agent: str | None,
    skill: str | None,
    pipeline: str | None,
    complexity: str | None,
    confidence: str,
    match_type: str,
    reasoning: str,
    stack: list,
    signals: dict | None,
    signal_scores: dict | None,
    source: str,
    latency_ms: dict | None,
    usage: dict | None,
    agents: list | None = None,
    gate_score: float | None = None,
    fits_scores: dict | None = None,
    stage1_shortlist: dict | None = None,
) -> dict:
    return {
        "available": available,
        "jev_called": jev_called,
        "matched": matched,
        "fallback": fallback,
        "fallback_reason": fallback_reason,
        "agent": agent,
        "skill": skill,
        "pipeline": pipeline,
        "complexity": complexity,
        "confidence": confidence,
        "match_type": match_type,
        "reasoning": reasoning,
        "stack": stack,
        "signals": signals,
        "signal_scores": signal_scores,
        "source": source,
        "latency_ms": latency_ms,
        "usage": usage,
        "agents": agents if agents is not None else [],
        "gate_score": gate_score,
        "fits_scores": fits_scores,
        "stage1_shortlist": stage1_shortlist,
    }


def _force_route_result(pre_route: dict) -> dict:
    """Step 1 hit: the final answer. Jev is never called -- the safety invariant."""
    return _build_result(
        available=True,
        jev_called=False,
        matched=True,
        fallback=False,
        fallback_reason=None,
        agent=_norm(pre_route.get("agent")),
        skill=_norm(pre_route.get("skill")),
        pipeline=_norm(pre_route.get("pipeline")),
        complexity=None,
        confidence="high",
        match_type="force_route",
        reasoning=str(pre_route.get("reasoning", "")),
        stack=list(pre_route.get("stack") or []),
        signals=None,
        signal_scores=None,
        source="pre-route-force",
        latency_ms=None,
        usage=None,
    )


def _unavailable_result(reason: str) -> dict:
    return _build_result(
        available=False,
        jev_called=False,
        matched=False,
        fallback=True,
        fallback_reason=f"Jev unavailable: {reason}",
        agent=None,
        skill=None,
        pipeline=None,
        complexity=None,
        confidence="low",
        match_type="fallthrough",
        reasoning=reason,
        stack=[],
        signals=None,
        signal_scores=None,
        source="unavailable",
        latency_ms=None,
        usage=None,
    )


def _error_result(exc: Exception, jev_called: bool, reason_prefix: str) -> dict:
    reason = f"{reason_prefix}: {type(exc).__name__}: {str(exc)[:200]}"
    result = _build_result(
        available=True,
        jev_called=jev_called,
        matched=False,
        fallback=True,
        fallback_reason=reason,
        agent=None,
        skill=None,
        pipeline=None,
        complexity=None,
        confidence="low",
        match_type="fallthrough",
        reasoning=reason,
        stack=[],
        signals=None,
        signal_scores=None,
        source="error",
        latency_ms=None,
        usage=None,
    )
    telemetry = getattr(exc, "telemetry", None)
    if isinstance(telemetry, dict):
        result["transport_retry"] = telemetry
    return result


def _trivial_bypass_result(gate_score: float, stage1_shortlist: dict, latency_ms: dict, usage: dict | None) -> dict:
    """Stage 1's gate fired: no agent/skill/pipeline needed. Real terminal state,
    not a fallback -- /d's SKILL.md Phase 2 branches on `source` directly."""
    return _build_result(
        available=True,
        jev_called=True,
        matched=True,
        fallback=False,
        fallback_reason=None,
        agent=None,
        skill=None,
        pipeline=None,
        complexity="trivial",
        confidence="high",
        match_type="jev",
        reasoning=f"gate_score={gate_score:.3f} below threshold: prose alone suffices, no dispatch needed",
        stack=[],
        signals=None,
        signal_scores=None,
        source="jev-trivial-bypass",
        latency_ms=latency_ms,
        usage=usage,
        agents=[],
        gate_score=gate_score,
        fits_scores=None,
        stage1_shortlist=stage1_shortlist,
    )


def _parse_stage1(
    data: dict,
    agent_names: set[str],
    skill_names: set[str],
    pipeline_names: set[str],
    shortlist_n: int = STAGE1_SHORTLIST_N,
) -> dict:
    """Parse stage 1's answers into shortlists + gate_score. Raises on malformed shape."""
    answers = data["answers"]

    agent_probs = answers["agent"].get("probabilities") or {}
    skill_probs = answers["skill"].get("probabilities") or {}
    pipeline_probs = answers["pipeline"].get("probabilities") or {}

    agent_shortlist = _top_names_by_probability(agent_probs, agent_names, shortlist_n)
    skill_shortlist = _top_names_by_probability(skill_probs, skill_names, shortlist_n)
    # Pipeline: always forward the single highest-probability REAL (non-"none")
    # candidate into stage 2, regardless of whether "none" won stage 1's
    # truncated pass -- avoids the cheap pass prematurely foreclosing a real
    # pipeline pick before the full-detail rerank gets a chance (see design ref).
    pipeline_top = _top_names_by_probability(pipeline_probs, pipeline_names, 1)
    pipeline_top1 = pipeline_top[0] if pipeline_top else None

    needs_skill = float(answers["needs_skill"]["noul"])
    needs_pipeline = float(answers["needs_pipeline"]["noul"])
    prose_suffices = float(answers["prose_suffices"]["noul"])
    gate_score = (needs_skill + needs_pipeline + (1.0 - prose_suffices)) / 3.0

    return {
        "agent_shortlist": agent_shortlist,
        "skill_shortlist": skill_shortlist,
        "pipeline_top1": pipeline_top1,
        "agent_probs": agent_probs,
        "gate_score": gate_score,
        "gate_raw": {"needs_skill": needs_skill, "needs_pipeline": needs_pipeline, "prose_suffices": prose_suffices},
    }


def _select_fanout_candidates(
    agent_shortlist: list[str], agent_probs: dict, agent_names: set[str], gate_score: float
) -> list[str]:
    """Near-miss agents (ranks 4-6) worth a fan-out Noul, gated behind a cheap heuristic.

    Only asked when the request plausibly spans multiple domains: gate_score
    clears a higher bar than trivial-bypass (proxy for substantive/complex
    work) AND no single agent clearly dominates stage 1's ranking (proxy for
    "more than one plausible owner"). Both bounded, both documented in the
    design reference -- this is a cost-control heuristic, not a claim of
    precision.
    """
    if gate_score < FANOUT_GATE_SCORE_MIN:
        return []
    ranked = _top_names_by_probability(agent_probs, agent_names, len(agent_names))
    if not ranked:
        return []
    top_prob = float((agent_probs or {}).get(ranked[0], 0.0))
    if top_prob >= FANOUT_DOMINANCE_PROB:
        return []
    start = max(FANOUT_RANK_START, len(agent_shortlist))  # fan-out candidates rank just below the shortlist
    return ranked[start : start + FANOUT_MAX_CANDIDATES]


def _parse_stage2(
    data: dict,
    agent_shortlist: list[str],
    skill_shortlist: list[str],
    pipeline_top1: str | None,
    fanout_candidates: list[str],
    agent_names: set[str],
    skill_names: set[str],
    pipeline_names: set[str],
    fits_threshold: float,
) -> dict:
    """Parse stage 2's answers: final picks, signals, fan-out.

    Manifest-membership validation is a hard Python-side check here, same as
    v1 -- a name Jev returns that is not in the live manifest (or not in the
    shortlist actually offered) is never trusted. That is the ONLY thing that
    can invalidate a primary agent/skill/pipeline pick as of 2026-09-16: the
    owner removed the fits-threshold gate on primary selection ("it picks the
    most relevant option instead of having some .7 requirement... I don't
    want there to be any artificial limit") after finding it was bouncing ~26%
    of the v2 corpus back to a full /do manifest read AFTER a real Jev call
    had already happened -- the worst case for the token cost /d exists to
    avoid, for a threshold this project's own eval corpus was never validated
    as correlating with actual quality. `fits_threshold`/`--fits-threshold`
    stays alive for exactly one thing now: gating optional fan-out-candidate
    inclusion (a genuine "does this extra agent apply at all" yes/no
    decision, not a "which real option wins" decision) -- it no longer gates
    the primary agent/skill/pipeline picks below. `_build_result`'s
    `confidence` field is still derived from the fit scores for reporting
    visibility, but is informational only; it does not affect `fallback`.
    """
    answers = data["answers"]

    def _pick_and_fit(dimension: str, shortlist: list[str], valid_names: set[str]) -> tuple[str | None, float | None]:
        choice = _norm(answers[dimension]["choice"])
        if choice is None or choice not in valid_names or choice not in shortlist:
            return None, None
        fit_key = f"{dimension}_fit__{_sanitize_key(choice)}"
        fit = float(answers[fit_key]["noul"]) if fit_key in answers else None
        return choice, fit

    # agent_final/skill_final/pipeline_final always take the top Choice pick
    # once it clears manifest-membership validation (_pick_and_fit already
    # enforces that) -- no minimum fit score required. A None here means Jev's
    # answer was not a valid/shortlisted name, not "the pick scored too low."
    agent_choice, agent_fit = _pick_and_fit("agent", agent_shortlist, agent_names)
    agent_final = agent_choice

    skill_choice, skill_fit = _pick_and_fit("skill", skill_shortlist, skill_names)
    skill_final = skill_choice

    pipeline_final: str | None = None
    pipeline_fit: float | None = None
    if pipeline_top1 is not None and "pipeline" in answers:
        pipeline_choice = _norm(answers["pipeline"]["choice"])
        if pipeline_choice == pipeline_top1 and pipeline_choice in pipeline_names:
            pipeline_final = pipeline_top1
            fit_key = f"pipeline_fit__{_sanitize_key(pipeline_top1)}"
            if fit_key in answers:
                pipeline_fit = float(answers[fit_key]["noul"])
        # pipeline_choice == "none", or an off-shortlist name -> stays None:
        # Jev's own answer (genuinely no pipeline fits), not a threshold veto.

    signals: dict[str, bool] = {}
    signal_scores: dict[str, float] = {}
    for key in NOUL_SIGNAL_KEYS:
        score = float(answers[key]["noul"])
        signal_scores[key] = score
        signals[key] = score >= STACK_SIGNAL_THRESHOLD

    agents_fanout: list[str] = []
    for name in fanout_candidates:
        fit_key = f"fanout__{_sanitize_key(name)}"
        if fit_key in answers and float(answers[fit_key]["noul"]) >= fits_threshold:
            agents_fanout.append(name)

    fits_scores = {"agent": agent_fit, "skill": skill_fit, "pipeline": pipeline_fit}

    domain_scores: dict[str, float] = {}
    for name in DOMAIN_NOUL_INSTRUCTIONS:
        key = f"{DOMAIN_NOUL_PREFIX}{_sanitize_key(name)}"
        if key in answers:
            domain_scores[name] = float(answers[key]["noul"])

    # Fallback now means exactly one thing here: Jev's agent or skill answer
    # was not a valid manifest-member/shortlisted name (a real "nothing to
    # act on" condition, same class as TypeSafe-unavailable or a call error
    # -- see this function's docstring). It no longer means "a valid pick
    # scored below an unvalidated threshold" -- that gate was removed
    # 2026-09-16 per the owner's explicit instruction.
    fallback = agent_final is None or skill_final is None
    if fallback:
        reasoning = (
            f"invalid pick (not a manifest-member/shortlisted name): agent={agent_choice!r}, skill={skill_choice!r}"
        )
        source = "invalid-pick"
    else:
        reasoning = (
            f"jev pick: agent={agent_final!r}@{agent_fit}, skill={skill_final!r}@{skill_fit}, "
            f"pipeline={pipeline_final!r}@{pipeline_fit}, fanout={agents_fanout}"
        )
        source = "jev"

    if pipeline_final is not None or agents_fanout:
        complexity = "complex"
    elif any(signals.values()):
        complexity = "medium"
    else:
        complexity = "simple"

    best_fit_for_label = [v for v in (agent_fit, skill_fit) if v is not None]
    min_fit = min(best_fit_for_label) if best_fit_for_label else None
    if fallback or min_fit is None:
        confidence_label = "low"
    elif min_fit >= fits_threshold + 0.35:
        confidence_label = "high"
    elif min_fit >= fits_threshold:
        confidence_label = "medium"
    else:
        confidence_label = "low"

    return {
        "agent": agent_final,
        "skill": skill_final,
        "pipeline": pipeline_final,
        "agents": agents_fanout,
        "complexity": complexity,
        "confidence": confidence_label,
        "match_type": "jev",
        "reasoning": reasoning,
        "signals": signals,
        "signal_scores": signal_scores,
        "fits_scores": fits_scores,
        "domain_scores": domain_scores,
        "fallback": fallback,
        "fallback_reason": reasoning if fallback else None,
        "source": source,
    }


def _classify(
    request_text: str,
    gate_threshold: float,
    fits_threshold: float,
    timeout: float,
    project: dict | None,
    shortlist_n: int,
    hint_skill: str | None = None,
) -> tuple[dict, set[str]]:
    """Two-stage Jev classification. Returns (result, live skill names). Never raises.

    `hint_skill` is a non-safety pre-route force match: it joins the stage-2
    skill shortlist so Jev judges it with its full description, but it does
    not win by keyword alone.
    """
    available, reason = jev_transport.available()
    if not available:
        return _unavailable_result(reason), set()

    try:
        entries = _load_manifest_entries()
        # Exclude router entry points (d, do) from the candidate set at the
        # source, before either stage's criteria maps are built -- see
        # ROUTER_ENTRY_POINT_SKILLS. A filtered-out name never reaches
        # skill_criteria/skill_full/skill_names at either stage, so Jev is
        # structurally unable to rank or select it, not merely discouraged.
        entries = [e for e in entries if not (e.get("type") == "skill" and e.get("name") in ROUTER_ENTRY_POINT_SKILLS)]
        # Private (overlay) entries are candidates only when the request names
        # their domain, so a private domain skill cannot outrank a general one.
        entries = gate_private_entries(entries, request_text)
        agent_criteria, skill_criteria, pipeline_criteria, agent_names, skill_names, pipeline_names = (
            _build_criteria_maps(entries)
        )
        agent_full, skill_full, pipeline_full = _build_full_criteria_maps(entries)
    except Exception as exc:
        return _error_result(exc, jev_called=False, reason_prefix="manifest load failed"), set()

    try:
        stage1_payload = _build_stage1_payload(request_text, agent_criteria, skill_criteria, pipeline_criteria, project)
        data1, latency1 = _call_jev(stage1_payload, timeout)
        stage1 = _parse_stage1(data1, agent_names, skill_names, pipeline_names, shortlist_n)
        usage1 = _extract_usage(data1)
    except Exception as exc:
        return _error_result(exc, jev_called=True, reason_prefix="jev stage-1 call failed"), skill_names

    if hint_skill and hint_skill in skill_names and hint_skill not in stage1["skill_shortlist"]:
        stage1["skill_shortlist"].append(hint_skill)

    stage1_shortlist = {
        "agent": stage1["agent_shortlist"],
        "skill": stage1["skill_shortlist"],
        "pipeline": [stage1["pipeline_top1"]] if stage1["pipeline_top1"] else [],
    }

    if stage1["gate_score"] < gate_threshold:
        latency_ms = {"stage1_ms": latency1, "stage2_ms": None, "total_ms": latency1}
        usage = {"stage1": usage1, "stage2": None}
        return _trivial_bypass_result(stage1["gate_score"], stage1_shortlist, latency_ms, usage), skill_names

    fanout_candidates = _select_fanout_candidates(
        stage1["agent_shortlist"], stage1["agent_probs"], agent_names, stage1["gate_score"]
    )
    # Fan-out candidates must never overlap the primary shortlist -- they are
    # near-misses ranked below it, not alternates for the same slot.
    fanout_candidates = [n for n in fanout_candidates if n not in stage1["agent_shortlist"]]

    try:
        stage2_payload = _build_stage2_payload(
            request_text,
            stage1["agent_shortlist"],
            agent_full,
            stage1["skill_shortlist"],
            skill_full,
            stage1["pipeline_top1"],
            pipeline_full,
            fanout_candidates,
            project,
        )
        data2, latency2 = _call_jev(stage2_payload, timeout)
        decision = _parse_stage2(
            data2,
            stage1["agent_shortlist"],
            stage1["skill_shortlist"],
            stage1["pipeline_top1"],
            fanout_candidates,
            agent_names,
            skill_names,
            pipeline_names,
            fits_threshold,
        )
        usage2 = _extract_usage(data2)
    except Exception as exc:
        return _error_result(exc, jev_called=True, reason_prefix="jev stage-2 call failed"), skill_names

    latency_ms = {"stage1_ms": latency1, "stage2_ms": latency2, "total_ms": latency1 + latency2}
    usage = {"stage1": usage1, "stage2": usage2}

    result = _build_result(
        available=True,
        jev_called=True,
        matched=not decision["fallback"],
        fallback=decision["fallback"],
        fallback_reason=decision["fallback_reason"],
        agent=decision["agent"],
        skill=decision["skill"],
        pipeline=decision["pipeline"],
        complexity=decision["complexity"],
        confidence=decision["confidence"],
        match_type=decision["match_type"],
        reasoning=decision["reasoning"],
        stack=[],
        signals=decision["signals"],
        signal_scores=decision["signal_scores"],
        source=decision["source"],
        latency_ms=latency_ms,
        usage=usage,
        agents=decision["agents"],
        gate_score=stage1["gate_score"],
        fits_scores=decision["fits_scores"],
        stage1_shortlist=stage1_shortlist,
    )
    result["domain_scores"] = decision["domain_scores"]
    return result, skill_names


def _is_force(pre_route: dict) -> bool:
    return bool(
        pre_route.get("matched")
        and pre_route.get("confidence") == "high"
        and pre_route.get("match_type") == "force_route"
    )


def _is_suggestion(pre_route: dict) -> bool:
    """A pre-route suggest-only match: a skill named without a force route."""
    return bool(
        not pre_route.get("matched") and pre_route.get("skill") and pre_route.get("match_type") == "fallthrough"
    )


def _is_safety_force(forced: dict) -> bool:
    return forced.get("skill") in SAFETY_FORCE_NAMES or forced.get("pipeline") in SAFETY_FORCE_NAMES


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


def _merge_safety_force(forced: dict, classified: dict) -> dict:
    """Safety force route keeps its skill and pipeline; Jev supplies the agent and attachments."""
    merged = dict(forced)
    for key in ("agents", "signals", "signal_scores", "domain_scores", "gate_score", "fits_scores"):
        merged[key] = classified.get(key)
    merged["agents"] = classified.get("agents") or []
    merged["agent"] = forced.get("agent") or classified.get("agent")
    merged["jev_called"] = True
    merged["latency_ms"] = classified.get("latency_ms")
    merged["usage"] = classified.get("usage")
    merged["stage1_shortlist"] = classified.get("stage1_shortlist")
    merged["complexity"] = classified.get("complexity")
    merged["reasoning"] = (
        f"{forced.get('reasoning', '')}; agent and attachments from jev ({classified.get('reasoning')})"
    )
    return merged


def route(
    request_text: str,
    gate_threshold: float,
    fits_threshold: float,
    timeout: float,
    project: dict | None = None,
    shortlist_n: int = STAGE1_SHORTLIST_N,
) -> dict:
    """Guard, classify, and attach for one request string. Never raises.

    - Safety force route (pr-workflow, pr-pipeline, security): its skill and
      pipeline are final; Jev never overrides them. Jev still runs to pick the
      agent and attachments. If Jev fails, the force route stands alone.
    - Other force route: Jev classifies with the forced skill on its stage-2
      shortlist (a hint, matching /do Phase 2 Step 1(b)). If Jev fails or
      calls the request trivial, the force route stands, as before.
    - Pre-route suggestion (a suggest-only trigger such as "ship it"): the
      skill joins the stage-2 shortlist as a hint and never stands alone.
    - Every matched route then gets `attach` (extra skills that ride with the
      primary) and, when no domain agent was picked, a skill-owned agent.
    """
    pre_route = _run_pre_route(request_text)
    forced = _force_route_result(pre_route) if _is_force(pre_route) else None
    safety = forced is not None and _is_safety_force(forced)
    hint = forced.get("skill") if forced is not None and not safety else None
    if forced is None and _is_suggestion(pre_route):
        hint = _norm(pre_route.get("skill"))

    classified, skill_names = _classify(
        request_text, gate_threshold, fits_threshold, timeout, project, shortlist_n, hint_skill=hint
    )
    usable = not classified.get("fallback") and classified.get("source") == "jev"

    if forced is None:
        result = classified
    elif not usable:
        result = forced
        if classified.get("jev_called"):
            result["jev_called"] = True
            result["latency_ms"] = classified.get("latency_ms")
            result["usage"] = classified.get("usage")
    elif safety:
        result = _merge_safety_force(forced, classified)
    else:
        result = classified
        result["pre_route_hint"] = {
            "skill": forced.get("skill"),
            "pipeline": forced.get("pipeline"),
            "reasoning": forced.get("reasoning"),
        }

    if result.get("fallback") or result.get("source") == "jev-trivial-bypass":
        result["attach"] = []
        result["agent_source"] = None
        return result

    result["attach"] = _attachments(result, skill_names)
    result["agent_source"] = (
        "pre-route"
        if forced is not None and forced.get("agent") == result.get("agent") and result.get("agent")
        else "jev"
    )
    if result.get("agent") in (None, "general-purpose"):
        default = _default_agent(result)
        if default:
            result["agent"] = default
            result["agent_source"] = "skill-default"
    return result


def main() -> int:
    """CLI entry point."""
    parser = argparse.ArgumentParser(
        description="Merged deterministic-guard + two-stage Jev classifier for /d dispatch.",
    )
    req_group = parser.add_mutually_exclusive_group(required=True)
    req_group.add_argument(
        "--request",
        help="The user request string to route.",
    )
    req_group.add_argument(
        "--request-file",
        help="Path to a file containing the request string (avoids shell-splicing).",
    )
    parser.add_argument(
        "--json-compact",
        action="store_true",
        help="Output compact JSON (no indentation).",
    )
    parser.add_argument(
        "--confidence-floor",
        type=float,
        default=DEFAULT_CONFIDENCE_FLOOR,
        help=(
            f"SUPERSEDED, no effect on routing (default {DEFAULT_CONFIDENCE_FLOOR}); kept for CLI compatibility only."
        ),
    )
    parser.add_argument(
        "--gate-threshold",
        type=float,
        default=DEFAULT_GATE_THRESHOLD,
        help=f"Stage-1 trivial-bypass gate_score threshold (default {DEFAULT_GATE_THRESHOLD}). Unchanged by "
        "the 2026-09-16 fallback-threshold removal below -- this still decides whether routing happens at "
        "all, a different question from which candidate wins among real options.",
    )
    parser.add_argument(
        "--fits-threshold",
        type=float,
        default=DEFAULT_FITS_THRESHOLD,
        help=f"Fan-out-candidate inclusion threshold only (default {DEFAULT_FITS_THRESHOLD}). No longer gates "
        "primary agent/skill/pipeline acceptance as of 2026-09-16 (owner: 'no artificial limit') -- Jev's "
        "top-ranked pick is always used once it passes manifest-membership validation.",
    )
    parser.add_argument(
        "--timeout",
        type=float,
        default=DEFAULT_TIMEOUT,
        help=f"Jev HTTP call timeout in seconds, per stage (default {DEFAULT_TIMEOUT}).",
    )
    parser.add_argument(
        "--shortlist",
        type=int,
        default=STAGE1_SHORTLIST_N,
        help=f"How many stage-1 agent and skill candidates reach stage 2 (default {STAGE1_SHORTLIST_N}).",
    )
    parser.add_argument(
        "--cwd",
        default=None,
        help="Repository directory the request is about. Its languages and frameworks are detected from marker "
        "files and sent as state facts. Omit to send the bare request.",
    )
    parser.add_argument(
        "--project-json",
        default=None,
        help='Project facts as JSON, e.g. {"languages":["python"]}. Overrides --cwd detection (eval use).',
    )
    args = parser.parse_args()

    if args.confidence_floor != DEFAULT_CONFIDENCE_FLOOR:
        print(
            "[jev-route] --confidence-floor is superseded by --fits-threshold in the v2 two-stage design; "
            f"ignoring override value {args.confidence_floor} (kept for CLI compatibility only).",
            file=sys.stderr,
        )

    try:
        if args.request_file:
            request_text = Path(args.request_file).read_text(encoding="utf-8")
        else:
            request_text = args.request

        project = None
        if args.project_json:
            parsed = json.loads(args.project_json)
            project = parsed if isinstance(parsed, dict) and parsed else None
        elif args.cwd:
            project = detect_project_context(args.cwd)

        result = route(
            request_text, args.gate_threshold, args.fits_threshold, args.timeout, project, max(1, args.shortlist)
        )
        if result.get("fallback") and result.get("source") in {"unavailable", "error"}:
            # Preserve a hook-time receipt without multiplying a known gateway
            # outage by another full retry cycle. Runtime /d still validates its
            # actual PROPOSED_INTENT and fails open if the service remains down.
            result["intent_alignment"] = {
                "available": False,
                "source": jev_transport.select()[0] or "unavailable",
                "proposed_intent": jev_intent_align.proposed_intent(request_text, result),
                "alignment": "unavailable",
                "aligned": False,
                "clarification_needed": False,
                "issues": ["baseline intent alignment unavailable because classification transport failed"],
                "reason": result.get("fallback_reason"),
                "transport_retry": result.get("transport_retry"),
                "questions_version": jev_intent_align.QUESTIONS_VERSION,
            }
        else:
            # Validate the hook-owned literal restatement before the model gets
            # a token; Phase 2 cannot then be skipped by model behavior.
            candidate = jev_intent_align.proposed_intent(request_text, result)
            result["intent_alignment"] = jev_intent_align.evaluate_alignment(
                request_text, result, candidate, args.timeout
            )
    except Exception as exc:
        import traceback

        traceback.print_exc(file=sys.stderr)
        result = _error_result(exc, jev_called=False, reason_prefix="jev-route error")

    indent = None if args.json_compact else 2
    print(json.dumps(result, indent=indent))
    return 0


if __name__ == "__main__":
    sys.exit(main())
