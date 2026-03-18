# ADR-003: ADR System Remediation

**Status**: APPROVED
**Date**: 2026-03-18
**Decision**: Close all gaps between the ADR system's design intent and its implementation

---

## Context

The ADR system was designed as the foundation for agent-to-agent communication during creation tasks. The /do router's Creation Protocol declares: "For any create or new request, automatically sequence: (1) ADR, (2) task plan, (3) implementation." Two hooks (`adr-context-injector`, `adr-enforcement`) exist to inject ADR context into sub-agents and check compliance after writes.

An audit found 10 gaps. The Creation Protocol is declared but not implemented in the router's execution phases. Creation agents don't register ADR sessions. The context injector's keyword filter is too narrow. The compliance checker only validates pipeline specs.

## Decision

### Fix 1: /do router Phase 4 implements Creation Protocol

Add explicit instructions to Phase 4 (EXECUTE) in `skills/do/SKILL.md`:

- Detect creation requests ("create", "new", "scaffold", "build pipeline/agent/skill/hook")
- Write ADR to `adr/{name}.md` with decision, context, and component list
- Register session: `python3 scripts/adr-query.py register --adr adr/{name}.md`
- Proceed to task plan, then implementation

### Fix 2: skill-creator-engineer registers ADR sessions

Add to `agents/skill-creator-engineer.md`:

- Check for active ADR session (`.adr-session.json`)
- If none and creating a new skill, call `adr-query.py register`
- Read ADR context via `adr-query.py context --role skill-creator`

### Fix 3: skill-creation-pipeline references ADR in DISCOVER phase

Add to `skills/skill-creation-pipeline/SKILL.md` Phase 1:

- Check `adr-query.py list` for related ADRs
- If active session, read ADR sections relevant to skill creation

### Fix 4: hook-development-pipeline references ADR

Add to `skills/hook-development-pipeline/SKILL.md`:

- Check for active ADR session in SPEC phase
- Read relevant ADR sections for hook requirements

### Fix 5: Widen adr-context-injector keyword filter

Add keywords to `hooks/adr-context-injector.py` RELEVANCE_KEYWORDS:

- "create", "new", "build", "implement", "design", "feature", "component", "write", "add"

### Fix 6: feature-design creates ADR for features

Add to `skills/feature-design/SKILL.md`:

- Write ADR documenting design decisions during exploration
- Register session for sub-phase skills

### Fix 7: adr-compliance.py handles non-pipeline components

Update `scripts/adr-compliance.py` to check:

- Agent files against architecture-rules section
- Skill files against step-menu section (existing) AND general structure rules
- Hook files against hook requirements from ADR

### Fix 8: adr-query.py list called during DISCOVER phases

Add `adr-query.py list` call to:

- skill-creation-pipeline Phase 1 (DISCOVER)
- hook-development-pipeline Phase 1 (SPEC)
- pipeline-scaffolder Phase 1

### Fix 9: Pipeline scaffolder verifies ADR hash before scaffolding

Add gate to `skills/pipeline-scaffolder/SKILL.md`:

- Call `adr-query.py verify --adr {path} --hash {hash}` before Phase 2
- Fail if hash mismatch (ADR was modified after session registration)

### Fix 10: precompact-archive ADR anchor already works (verify only)

Confirm `hooks/precompact-archive.py` inject_adr_anchor function fires during compaction.

## Consequences

- Creation requests through /do produce ADRs automatically
- Sub-agents receive architectural context via hook injection
- Compliance checking covers agents, skills, and hooks (not only pipeline specs)
- Feature design decisions are documented in ADRs
- ADR hash verification prevents stale-ADR scaffolding
