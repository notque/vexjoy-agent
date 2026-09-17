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
**Phase 2: DECIDE** — Apply the Jev/force-route decision directly, display
the routing banner.
**Phase 3: ENHANCE** — Map stack signals to concrete stack entries.
**Phase 4: EXECUTE** — Same Task Spec + `build-dispatch.py` contract `/do`
uses, reused unmodified.

The routing banner MUST be the first visible output:
```
===================================================================
 ROUTING (/d): [brief summary]
===================================================================

 Selected:
   -> Agent: [name]
   -> Skill: [name]
   -> Source: [jev|pre-route-force] (confidence: [level])

 Invoking...
===================================================================
```

On fallback, the banner instead states `ROUTING (/d -> falling back to
/do): [reason]` and control passes entirely to `/do`'s own instructions.

For the full design (why `/d` exists as a separate command, the
request/response contract, fallback-condition reasoning, measured eval
results), read `skills/meta/d/SKILL.md` and
`skills/meta/d/references/jev-classifier-design.md`.

ARGUMENTS: $ARGUMENTS
