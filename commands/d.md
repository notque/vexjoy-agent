---
description: "Jev-first router: A/B variant of /do. One TypeSafe call replaces the manifest read; falls back to /do when unavailable or unconfident."
argument-hint: "[request]"
allowed-tools: ["Read", "Bash", "Grep", "Glob", "Skill", "Task"]
---

# /d - Jev-first Router (A/B variant of /do)

Route user requests using a Jev classifier call instead of `/do`'s
in-context manifest read. Use `/d` to A/B-test against `/do`; use `/do` for
normal work.

## Instructions

Call the Skill tool with `d`. Follow its classify, decide, enhance, and
execute phases.

```
Base directory: $CLAUDE_PROJECT_DIR or the current working directory
Skill file: skills/meta/d/SKILL.md
```

**Phase 1: CLASSIFY** — One `scripts/jev-route.py` call: deterministic
force-route guard, then (if not force-routed) the merged Jev classification.
**Phase 1F: FALLBACK** — On `fallback: true` (TypeSafe unavailable, low
confidence, or error), read `skills/meta/do/SKILL.md` in full and run its
Phase 1-4 unmodified.
**Phase 2: ALIGN INTENT** — MANDATORY before any banner or dispatch. Write
`PROPOSED_INTENT`, run `jev-intent-align.py` on it. `JEV_RESULT.intent_alignment`
from the hook is the baseline only — it does NOT satisfy Phase 2.
**Phase 3: DECIDE** — Apply the Jev/force-route decision. Display the routing
banner only after Phase 2 completes.
**Phase 4: ENHANCE** — Map stack signals to concrete stack entries.
**Phase 5: EXECUTE** — Same Task Spec + `build-dispatch.py` contract `/do`
uses, reused unmodified.

The routing banner MUST include the Phase 2 intent alignment result:
```
===================================================================
 ROUTING (/d): [brief summary]
===================================================================

 Intent (/d):
   -> Restated: [PROPOSED_INTENT]
   -> Alignment: [aligned|review|unavailable] [— issues, if any]

 Selected:
   -> Agent: [name] - [reasoning]
   -> Skill: [name] - [reasoning]
   -> Source: [jev|pre-route-force] (confidence: [level])

 Invoking...
===================================================================
```

A banner printed without the `Intent` block means Phase 2 was skipped — that is not allowed.

On fallback, the banner instead states `ROUTING (/d -> falling back to
/do): [reason]` and control passes entirely to `/do`'s own instructions.

For the full design (why `/d` exists as a separate command, the
request/response contract, fallback-condition reasoning, measured eval
results), read `skills/meta/d/SKILL.md` and
`skills/meta/d/references/jev-classifier-design.md`.

ARGUMENTS: $ARGUMENTS
