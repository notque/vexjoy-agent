#!/usr/bin/env python3
"""Generate a compact routing manifest for the /do router (orchestrator self-route).

Reads skills/INDEX.json and pipeline-index.json, then outputs a compact text
manifest that an LLM can parse efficiently. The repo's specialist agents are
retired (plans/009): routing picks a skill, pipeline, and stack, and the worker
is the built-in general-purpose agent. The public manifest has no AGENTS:
section. Private overlay agents (routing_index_merge.overlay_agent_items: the
resolved agents index minus retired and built-in names) render in an
overlay-only AGENTS: section, and only with --request/--request-file, when the
request names their domain (the same private gate as overlay skills). With no
request no agent renders, so the session cache never holds one.

Usage:
    python3 scripts/routing-manifest.py
    python3 scripts/routing-manifest.py --json
    python3 scripts/routing-manifest.py --tiered
    python3 scripts/routing-manifest.py --request-file /tmp/request.txt

--request or --request-file gates private (overlay) entries on the request:
one stays only when the request names its domain
(routing_index_merge.gate_private_entries, the gate /d and pre-route.py
apply). With neither flag every entry renders, as the session cache holds it.

--tiered is REJECTED for production routing: two blind A/B runs failed
gates (c) safety misses and (d) stub-tier (verdicts in
scripts/routing-ab-results/tiered-v1|v2/VERDICT.md on PR #771's branch).
The flag stays for experimentation only; the /do router uses the full
manifest (no flag).

Line format (default/full manifest):

    AGENTS:            (overlay agents only; absent when none is gated in)
      name — description NOT: excluded t:phrase|phrase
    SKILLS:
      name FORCE (category) — description NOT: excluded t:phrase|phrase
    PIPELINES:
      name FORCE (category) — description NOT: excluded t:phrase|phrase

Pipeline lines share the skill grammar so the router reads one line format
across both sections: ``FORCE`` marks a force-route entry the router must
select, and the curated ``t:`` phrases carry the discriminating signal. Both
sections render in every mode — the /do section validator tokenizes the text
between the AGENTS:/SKILLS:/PIPELINES: headers, so the order and spelling of
those headers are load-bearing. AGENTS:, when present, always comes first.

The trailing ``t:`` field carries up to TRIGGER_CAP hand-curated trigger
phrases from INDEX.json — the discriminating signal the router needs to
tell two same-domain skills apart. Every FULL line carries it, in the
default manifest and on --tiered's FULL lines alike. --tiered stubs and
--compact skip it: both exist to shrink the manifest, so neither pays for
the field.

Exit codes:
    0 — Always (advisory)
"""

from __future__ import annotations

import argparse
import json
import os
import sqlite3
import sys
import time
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent

# Shared tracked+local INDEX merge — single source in routing_index_merge.py.
_SCRIPTS_DIR = Path(__file__).resolve().parent
if str(_SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS_DIR))
from routing_index_merge import canonical_agent_name as _canonical_agent_name
from routing_index_merge import detect_target as _detect_target
from routing_index_merge import gate_private_entries as _gate_private_entries
from routing_index_merge import load_index_items as _load_index_items
from routing_index_merge import load_items_for as _load_items_for
from routing_index_merge import overlay_agent_items as _overlay_agent_items
from routing_index_merge import private_names_for as _private_names_for
from routing_index_merge import resolve_pipeline_index as _resolve_pipeline_index

# Installed-index resolution (installer spec 7.2): $VEXJOY_INDEX_DIR, then
# ~/.<runtime>/vexjoy/index/<kind>.json, then the repo index + legacy local.
_INDEX_TARGET = _detect_target(__file__)

# Canonical DB-dir resolver (ADR-122 hardening lives there)
_HOOKS_LIB = Path(__file__).resolve().parent.parent / "hooks" / "lib"
if str(_HOOKS_LIB) not in sys.path:
    sys.path.insert(0, str(_HOOKS_LIB))
from learning_db_v2 import get_db_dir

# Tiered mode: how far back a route-events DECISION keeps a name in the
# working set, and how many description words a stub line keeps.
WORKING_SET_WINDOW_SECONDS = 30 * 86400
STUB_DESC_WORDS = 6

# Trigger phrases rendered per SKILLS/PIPELINES line. The manifest is injected on
# every routing decision, so this is a byte budget, not a preference: measured
# against the 37,367-byte no-trigger manifest, top-3 costs +19%, top-5 +29%,
# and all 1,791 curated phrases +80%. Top-5 is the chosen trade. Tune here.
TRIGGER_CAP = 5
TRIGGER_PREFIX = " t:"
TRIGGER_SEP = "|"


INDEX_PATHS = {
    "skills": (REPO_ROOT / "skills" / "INDEX.json", "INDEX.local.json"),
    "pipelines": (_resolve_pipeline_index(REPO_ROOT), None),
}


def load_entries() -> list[dict]:
    """Load all skill and pipeline INDEX entries into a flat list.

    No agent entries: the specialist agents are retired. A skill's legacy
    ``agent`` pairing is not carried, and ``pairs_with`` keeps only names that
    are skills or pipelines here, so a retired agent name never reaches the
    router through either field.
    """
    entries = []

    for index_type, (tracked, local_name) in INDEX_PATHS.items():
        items = _load_items_for(index_type, tracked, local_name, _INDEX_TARGET, REPO_ROOT)
        private = _private_names_for(index_type, tracked, local_name, _INDEX_TARGET, REPO_ROOT)

        for name, data in items.items():
            if not isinstance(data, dict):
                continue
            entry: dict = {
                "name": name,
                "type": "skill" if index_type == "skills" else index_type.rstrip("s"),
                "description": data.get("description") or data.get("short_description", ""),
                "triggers": data.get("triggers", []),
                "category": data.get("category", ""),
                "model": data.get("model"),
                "pairs_with": data.get("pairs_with", []),
                "force_route": bool(data.get("force_route", False)),
            }
            not_for = data.get("not_for")
            if isinstance(not_for, str):
                # Formatters below prepend "NOT: "; strip a source-side
                # prefix so a prefixed frontmatter value cannot render as
                # "NOT: NOT:".
                stripped = not_for.strip()
                if stripped.upper().startswith("NOT:"):
                    not_for = stripped[4:].lstrip()
            if not_for:
                entry["not_for"] = not_for
            if name in private:
                # Overlay-owned entry: routers gate it on a domain match
                # (routing_index_merge.gate_private_entries).
                entry["private"] = True
            entries.append(entry)

    known = {e["name"] for e in entries}
    for e in entries:
        e["pairs_with"] = [p for p in e["pairs_with"] if p in known]
    return entries


def load_overlay_agent_entries() -> list[dict]:
    """Private overlay agents as manifest entries, every one flagged ``private``.

    Retired repo agents never appear, even when a stale installed index lists
    them (routing_index_merge.overlay_agent_items subtracts RETIRED_AGENTS).
    The caller gates these on the request before rendering.
    """
    entries = []
    for name, data in sorted(_overlay_agent_items(_INDEX_TARGET, REPO_ROOT).items()):
        desc = data.get("description") or data.get("short_description") or ""
        not_for = data.get("not_for")
        entry: dict = {
            "name": name,
            "type": "agent",
            # Index descriptions can span lines; one manifest line per entry.
            "description": " ".join(str(desc).split()),
            "triggers": [t for t in data.get("triggers") or [] if isinstance(t, str)],
            "category": data.get("category", ""),
            "pairs_with": [],
            "force_route": False,
            "private": True,
        }
        if isinstance(not_for, str) and not_for.strip():
            entry["not_for"] = " ".join(not_for.split())
        entries.append(entry)
    return entries


def _learning_dir() -> Path:
    """Resolve the learning dir from CLAUDE_LEARNING_DIR (tests redirect it)."""
    return get_db_dir()


def _names_from_key(key: str, names: set[str]) -> None:
    """Add the agent and skill names from an `agent:skill` route key.

    A renamed agent's old name maps to its current name (AGENT_ALIASES).
    Agent names in the set are harmless: only skill names match an entry.
    """
    for i, part in enumerate(key.split(":", 1)):
        part = part.strip()
        if part and part != "-":
            names.add(_canonical_agent_name(part) if i == 0 else part)


def load_working_set(now: float | None = None) -> set[str]:
    """Names (agents and skills) with recorded routes.

    Union of: route-weight rows (n >= 1, test rows excluded) from learning.db,
    and DECISION events from route-events.jsonl in the last 30 days.
    Read-only. Any read failure yields a smaller set, never an error —
    a smaller working set only means more stub lines.
    """
    names: set[str] = set()
    base = _learning_dir()

    db_path = base / "learning.db"
    if db_path.exists():
        try:
            conn = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
            try:
                rows = conn.execute(
                    "SELECT key FROM learnings"
                    " WHERE topic = 'routing' AND category = 'effectiveness'"
                    " AND observation_count >= 1 AND source NOT LIKE 'test%'"
                ).fetchall()
            finally:
                conn.close()
            for (key,) in rows:
                _names_from_key(str(key), names)
        except sqlite3.Error:
            pass

    events_path = base / "route-events.jsonl"
    cutoff = (now if now is not None else time.time()) - WORKING_SET_WINDOW_SECONDS
    try:
        with open(events_path, encoding="utf-8") as f:
            for line in f:
                try:
                    event = json.loads(line)
                except json.JSONDecodeError:
                    continue
                if not isinstance(event, dict) or event.get("type") != "decision":
                    continue
                ts = event.get("ts")
                if not isinstance(ts, (int, float)) or ts < cutoff:
                    continue
                for field in ("agent", "skill"):
                    value = event.get(field)
                    if isinstance(value, str) and value and value != "-":
                        names.add(_canonical_agent_name(value) if field == "agent" else value)
    except OSError:
        pass

    return names


def section_names(entries: list[dict]) -> dict[str, set[str]]:
    """Names owned by each section, keyed by entry type."""
    names: dict[str, set[str]] = {"agent": set(), "skill": set(), "pipeline": set()}
    for e in entries:
        names.setdefault(e["type"], set()).add(e["name"])
    return names


def select_triggers(entry: dict, reserved: set[str], cap: int | None = None) -> list[str]:
    """Pick up to `cap` trigger phrases that add routing signal to this line.

    Two classes of phrase are dropped before the cap applies:

    - A phrase equal to a component name in the OTHER section. The /do section
      validator tokenizes the text between the SKILLS: and PIPELINES: headers,
      so a pipeline name printed inside a skill line (or the reverse) would
      validate in the wrong slot. Dropping them keeps trigger text out of that
      check. It does not make the check exact: descriptions can still print
      names from the other section.
    - A phrase already present verbatim in the description, which spends bytes
      to repeat a token the router can already read on the same line.
    """
    cap = TRIGGER_CAP if cap is None else cap
    desc = str(entry.get("description") or "").lower()
    picked: list[str] = []
    for raw in entry.get("triggers") or []:
        if len(picked) >= cap:
            break
        phrase = str(raw).strip()
        if not phrase or phrase in reserved or phrase.lower() in desc:
            continue
        picked.append(phrase)
    return picked


def format_triggers(entry: dict, reserved: set[str]) -> str:
    """Render the trailing ` t:a|b|c` field, or "" when nothing survives selection."""
    picked = select_triggers(entry, reserved)
    return TRIGGER_PREFIX + TRIGGER_SEP.join(picked) if picked else ""


def _stub_line(entry: dict) -> str:
    """One-line stub: name + router-critical metadata + first STUB_DESC_WORDS description words.

    Skill stubs keep not_for (tiered-v1 REJECT showed stubs need the router-
    critical fields).
    """
    desc = " ".join(str(entry["description"]).split()[:STUB_DESC_WORDS])
    if entry["type"] != "skill":
        return f"  {entry['name']} — {desc}"
    not_for = entry.get("not_for", "")
    not_for_str = f" NOT: {not_for}" if not_for else ""
    return f"  {entry['name']} — {desc}{not_for_str}"


def _skill_line(entry: dict, reserved: set[str] | None, truncate: bool = False) -> str:
    """Render one SKILLS line: ``name[ FORCE][ (category)] — desc[ NOT: x][ t:...]``.

    `reserved` holds the pipeline names; a trigger equal to one is dropped. Pass
    None to omit the trigger field (compact mode).
    """
    desc = entry["description"]
    not_for = entry.get("not_for", "")
    if truncate:
        desc = truncate_desc(desc)
        not_for = truncate_desc(not_for, 40) if not_for else ""
    force_str = " FORCE" if entry.get("force_route") else ""
    cat_str = f" ({entry['category']})" if entry.get("category") else ""
    not_for_str = f" NOT: {not_for}" if not_for else ""
    trig_str = format_triggers(entry, reserved) if reserved is not None else ""
    return f"  {entry['name']}{force_str}{cat_str} — {desc}{not_for_str}{trig_str}"


def _agent_line(entry: dict, reserved: set[str] | None, truncate: bool = False) -> str:
    """Render one AGENTS line (overlay agents only): ``name — desc[ NOT: x][ t:...]``.

    `reserved` holds the skill and pipeline names; a trigger equal to one is
    dropped so the section validator never reads it as an agent. Pass None to
    omit the trigger field (compact mode).
    """
    desc = entry["description"]
    not_for = entry.get("not_for", "")
    if truncate:
        desc = truncate_desc(desc)
        not_for = truncate_desc(not_for, 40) if not_for else ""
    not_for_str = f" NOT: {not_for}" if not_for else ""
    trig_str = format_triggers(entry, reserved) if reserved is not None else ""
    return f"  {entry['name']} — {desc}{not_for_str}{trig_str}"


def _pipeline_line(entry: dict, reserved: set[str] | None, truncate: bool = False) -> str:
    """Render one PIPELINES line: ``name[ FORCE][ (category)] — desc[ NOT: x][ t:...]``.

    Mirrors the skill line so every section speaks one grammar. Two fields are
    load-bearing and were previously dropped: ``FORCE`` is what lets the
    router's "manifest entries marked FORCE MUST be selected" rule fire on a
    pipeline at all, and the curated triggers are the only signal separating
    two pipelines whose descriptions read alike.

    `reserved` holds the names owned by the other sections; a trigger equal to
    one of them is dropped, because the section validator tokenizes between
    headers and would read that name as a pipeline. Pass None to omit the
    trigger field entirely — compact mode does, for the same byte budget that
    keeps triggers off its skill lines.
    """
    desc = entry["description"]
    not_for = entry.get("not_for", "")
    if truncate:
        desc = truncate_desc(desc)
        not_for = truncate_desc(not_for, 40) if not_for else ""
    force_str = " FORCE" if entry.get("force_route") else ""
    cat_str = f" ({entry['category']})" if entry.get("category") else ""
    not_for_str = f" NOT: {not_for}" if not_for else ""
    trig_str = format_triggers(entry, reserved) if reserved is not None else ""
    return f"  {entry['name']}{force_str}{cat_str} — {desc}{not_for_str}{trig_str}"


def format_tiered(entries: list[dict], working_set: set[str]) -> str:
    """Format entries with FULL lines for the working set, stubs for the rest.

    FULL: working-set names (recorded routes) and every force-route entry —
    force-route entries are never stubbed, and a FULL line here is the same
    line format_compact renders, triggers included. Stub: name + 6-word
    description, no triggers. Pipelines are few; they always render FULL.
    """
    agents = []
    skills = []
    pipelines = []
    names = section_names(entries)

    for e in entries:
        full = e["name"] in working_set or e.get("force_route", False)
        if e["type"] == "pipeline":
            pipelines.append(_pipeline_line(e, names["agent"] | names["skill"]))
        elif e["type"] == "skill":
            skills.append(_skill_line(e, names["agent"] | names["pipeline"]) if full else _stub_line(e))
        elif e["type"] == "agent":
            agents.append(_agent_line(e, names["skill"] | names["pipeline"]))

    sections = []
    if agents:
        sections.append("AGENTS:\n" + "\n".join(sorted(agents)))
    if skills:
        sections.append("SKILLS:\n" + "\n".join(sorted(skills)))
    if pipelines:
        sections.append("PIPELINES:\n" + "\n".join(sorted(pipelines)))

    return "\n\n".join(sections)


def format_compact(entries: list[dict]) -> str:
    """Format entries as a compact text manifest for LLM consumption.

    Two sections: skills and pipelines. Both carry a trailing ``t:`` trigger
    field — the curated phrases are what let the router tell two same-domain
    entries apart, so they render here even though they cost bytes. One line
    per entry.
    """
    agents = []
    skills = []
    pipelines = []
    names = section_names(entries)

    for e in entries:
        if e["type"] == "pipeline":
            pipelines.append(_pipeline_line(e, names["agent"] | names["skill"]))
        elif e["type"] == "skill":
            skills.append(_skill_line(e, names["agent"] | names["pipeline"]))
        elif e["type"] == "agent":
            agents.append(_agent_line(e, names["skill"] | names["pipeline"]))

    sections = []
    if agents:
        sections.append("AGENTS:\n" + "\n".join(sorted(agents)))
    if skills:
        sections.append("SKILLS:\n" + "\n".join(sorted(skills)))
    if pipelines:
        sections.append("PIPELINES:\n" + "\n".join(sorted(pipelines)))

    return "\n\n".join(sections)


def truncate_desc(desc: str, max_len: int = 60) -> str:
    """Truncate description to max_len chars, adding '...' if truncated."""
    if len(desc) <= max_len:
        return desc
    return desc[: max_len - 3] + "..."


def format_compact_mode(entries: list[dict], request_text: str = "") -> str:
    """Format entries in compact mode: truncated descriptions, all three sections.

    Every section renders here, PIPELINES included. The section is keyed to what
    exists, never to the request wording: a literal-substring gate hid every
    pipeline from "research X and write me an article", and it also removed the
    PIPELINES: header the /do section validator tokenizes the SKILLS: block
    against. `request_text` is accepted and unused here; main() applies the
    private-entry gate to `entries` before any formatter runs.

    Triggers stay off these lines, matching the skill lines above — compact
    mode exists to shrink the manifest.
    """
    agents = []
    skills = []
    pipelines = []

    for e in entries:
        if e["type"] == "pipeline":
            pipelines.append(_pipeline_line(e, None, truncate=True))
        elif e["type"] == "skill":
            skills.append(_skill_line(e, None, truncate=True))
        elif e["type"] == "agent":
            agents.append(_agent_line(e, None, truncate=True))

    sections = []
    if agents:
        sections.append("AGENTS:\n" + "\n".join(sorted(agents)))
    if skills:
        sections.append("SKILLS:\n" + "\n".join(sorted(skills)))
    if pipelines:
        sections.append("PIPELINES:\n" + "\n".join(sorted(pipelines)))

    return "\n\n".join(sections)


def _drop_gated_pairs(gated: list[dict], everything: list[dict]) -> list[dict]:
    """Remove the names the private gate dropped from every surviving entry's pairs_with.

    Without this a surviving entry's pairs_with (in --json output) still named
    a private skill the gate had hidden, so the name reached the router anyway.
    """
    removed = {e["name"] for e in everything} - {e["name"] for e in gated}
    if not removed:
        return gated
    out = []
    for e in gated:
        pairs = e.get("pairs_with") or []
        if any(p in removed for p in pairs):
            e = {**e, "pairs_with": [p for p in pairs if p not in removed]}
        out.append(e)
    return out


def main() -> int:
    parser = argparse.ArgumentParser(description="Generate routing manifest for the /do router.")
    parser.add_argument("--json", action="store_true", help="Output as JSON")
    parser.add_argument(
        "--compact",
        action="store_true",
        help="Compact mode: truncated descriptions, no trigger field; all three sections render",
    )
    parser.add_argument(
        "--request",
        type=str,
        default=None,
        help="Request text: private entries render only when it names their domain",
    )
    parser.add_argument(
        "--request-file",
        type=Path,
        default=None,
        help="Read the request text from this file (same gate as --request)",
    )
    parser.add_argument(
        "--tiered",
        action="store_true",
        help="Tiered mode (EXPERIMENT ONLY — rejected for production by two A/B runs, see module docstring): FULL lines for the live working set and force-route entries, one-line stubs otherwise",
    )
    args = parser.parse_args()

    try:
        entries = load_entries()
        request = args.request
        if args.request_file is not None:
            try:
                request = args.request_file.read_text(encoding="utf-8", errors="replace")
            except OSError:
                request = ""  # unreadable request: no domain named, so no private entry
        if request is not None:
            # Overlay agents join only for a request, so they always pass the
            # private gate and never reach the request-less session cache.
            entries = entries + load_overlay_agent_entries()
            entries = _drop_gated_pairs(_gate_private_entries(entries, request), entries)

        if args.json:
            print(json.dumps(entries, indent=2))
        elif args.compact:
            print(format_compact_mode(entries, request_text=request or ""))
        elif args.tiered:
            print(format_tiered(entries, load_working_set()))
        else:
            print(format_compact(entries))
    except Exception as exc:
        # Safe fallback: empty manifest so the router falls through gracefully.
        # Always print the cause so the failure is visible without debug flags.
        print(
            f"[routing-manifest] FALLBACK: {type(exc).__name__}: {exc}",
            file=sys.stderr,
        )
        print("SKILLS:\n\nPIPELINES:")

    return 0


if __name__ == "__main__":
    sys.exit(main())
