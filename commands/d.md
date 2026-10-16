---
description: "Jev-validated router: the session picks the route with /do's rules; Jev answers the attachment questions and checks the restated intent."
argument-hint: "[request]"
allowed-tools: ["Read", "Bash", "Grep", "Glob", "Skill", "Task"]
---

# /d - Jev-validated Router

Route user requests with `/do`'s rule text and manifest, then use Jev to
attach domain skills and check that the restated outcome survives the route.
Use `/d` to A/B-test against `/do`; use `/do` for normal work.

## Instructions

Call the Skill tool with `d`. Follow its classify, decide, enhance, and
execute phases.

```
Base directory: $CLAUDE_PROJECT_DIR or the current working directory
Skill file: skills/meta/d/SKILL.md
```

**Phase 1: CLASSIFY** — `scripts/jev-route.py` runs the force-route guard and
one Jev attachment evaluation. You pick the agent, skill, and pipeline with
`/do`'s rules (`scripts/print-route-rules.py`) and the routing manifest, then
`jev-route.py --finalize` validates the pick and adds the attachments.
**Phase 2: ALIGN INTENT** — MANDATORY before any banner or dispatch. Write
`PROPOSED_INTENT` for the finalized route, run `jev-intent-align.py` on it.
**Phase 3: DECIDE** — Show the finalized route. Display the routing banner
only after Phase 2 completes.
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
   -> Source: [session|pre-route-force] (confidence: [level])

 Invoking...
===================================================================
```

A banner printed without the `Intent` block means Phase 2 was skipped — that is not allowed.

For the full design (why `/d` exists as a separate command, the
request/response contract, measured eval results), read
`skills/meta/d/SKILL.md` and
`skills/meta/d/references/jev-classifier-design.md`.

ARGUMENTS: $ARGUMENTS
