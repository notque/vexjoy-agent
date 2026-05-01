# ADR Template

General-purpose template for Architecture Decision Records in the VexJoy Agent.
Copy the block below for each new ADR.

---

## File Naming

```
adr/NNN-short-descriptive-slug.md
```

Where `NNN` is the next available number:

```bash
ls adr/ | grep -E '^[0-9]' | sort | tail -1
# then increment by 1
```

Also create `adr/short-descriptive-slug.md` as a one-line redirect to the numbered file.
This satisfies any hooks that look for `adr/{component-name}.md`.

ADR files go in `adr/` (gitignored — they are local development artifacts, not shipped
with the toolkit).

---

## Template

```markdown
# ADR-NNN: [Title]

## Status
Proposed

## Date
YYYY-MM-DD

## Context

[2–4 paragraphs describing the problem. Include:]
- What was found and where — with file:line references for every claim
- Why it matters in practice — concrete scenario, not theoretical risk
- Any relevant system background (architecture, existing behavior, prior ADRs)

[Example of concrete evidence:]

`hooks/userprompt-datetime-inject.py:16` outputs `%H:%M:%S`, which changes every
second. The `additionalContext` field places content in the system prompt prefix —
the cache-sensitive region Claude Code otherwise keeps byte-stable via alphabetical
tool sorting (`src/utils/toolResultStorage.ts`) and content-hash settings paths.
Result: every prompt misses the cache, costing 12.5× more than a cache hit.

## Decision

[Specific implementation plan. Not "improve X" but "replace X with Y in file Z
because reason W".]

[Include before/after code snippets for non-trivial changes:]

```python
# Before (hooks/userprompt-datetime-inject.py:16)
print(f"[datetime] {now.strftime('%Y-%m-%d %H:%M:%S %Z')}")

# After
print(f"[datetime] {now.strftime('%Y-%m-%d %Z')}")
```

[For multi-part decisions, use numbered subsections:]

### 1. [First change]
[Description and code]

### 2. [Second change]
[Description and code]

## Alternatives Considered

### A. [Alternative name]
[Description of the approach]

**Rejected because**: [specific reason — cost, complexity, unavailability, etc.]

### B. [Another alternative]
[Description]

**Deferred because**: [reason — follow-on ADR, future version, etc.]

[Include every alternative that was seriously considered. Showing rejected paths
demonstrates the decision was not arbitrary and prevents future re-litigation.]

## Affected Files

| File | Action | Change |
|------|--------|--------|
| `hooks/your-hook.py` | Create | New hook for [purpose] |
| `.claude/settings.json` | Modify | Register hook in `[EventType]` handlers |

[List every file the implementing agent will touch. Files not listed here will not
be modified. Make the table complete.]

## Consequences

### Positive
- [Concrete improvement with measurable or observable evidence]
- [Another improvement]

### Negative / Risks
- [Tradeoff accepted by this decision]
- [Risk introduced, with mitigation if applicable]

## Implementation Notes

[Specific implementation guidance for the domain agent executing this ADR:]
- [File paths and line numbers]
- [Code patterns to follow or avoid]
- [Sequencing constraints between changes]

**Deploy order for hooks** (per established protocol — deploy file BEFORE registering
in settings.json, or a startup crash will deadlock the session):

1. Create the hook file in the repo
2. Run `python3 scripts/sync-to-user-claude.py` to sync to `~/.claude/hooks/`
3. Verify the hook exits 0 with expected output (see Testing Commands below)
4. Only after verification passes, register in `.claude/settings.json`

## System Integration

[HOW this component plugs into the toolkit. This section is MANDATORY for any ADR
that creates a new component (hook, skill, agent, pipeline). For modification-only
ADRs it may be omitted or shortened.]

### Hook Registration (if applicable)

Add to the appropriate event group in `.claude/settings.json`:

```json
{
  "type": "command",
  "command": "python3 \"$HOME/.claude/hooks/your-hook.py\"",
  "description": "One-line description of what the hook does",
  "timeout": 1000
}
```

[Specify which event type (`UserPromptSubmit`, `PreToolUse`, `PostToolUse`, etc.),
position within the group, and timeout budget.]

### Skill/Agent Registration (if applicable)

Add to `skills/INDEX.json` or `agents/INDEX.json`:

```json
{
  "name": "your-skill",
  "path": "skills/your-skill/SKILL.md",
  "description": "...",
  "triggers": ["trigger phrase", "another phrase"],
  "category": "domain"
}
```

[Include the YAML frontmatter for the new component:]

```yaml
---
name: your-skill
description: "..."
routing:
  triggers:
    - trigger phrase
  category: domain
---
```

### /do Routing (if applicable)

Add to `skills/do/references/routing-tables.md`:

```
| your-skill | trigger phrase, another phrase | domain | description |
```

[Specify triggers, category, and any `pairs_with` entries.]

### Deploy Order

1. [Step with verification gate]
2. [Step with verification gate]
3. Regenerate INDEX: `python3 scripts/generate-skill-index.py` (or agent equivalent)
4. Verify routing: `python3 scripts/routing-benchmark.py --verbose`
5. Register in settings.json (hooks only — after file is deployed and verified)

**CRITICAL**: deploy hook files BEFORE registering in settings.json. Registration of
a broken hook deadlocks every subsequent user prompt.

### Interaction with Other Components

[How this component interacts with existing hooks, skills, agents, or ADRs:]

- **`existing-hook.py`** — [Independent / depends on / must run before/after]
- **ADR-NNN** — [Builds on / supersedes / must be implemented before this]

[If no interactions exist, write "Self-contained — no interactions with existing components."]

### Testing Commands

```bash
# [Describe what this tests]
[exact bash command]

# [Describe what this tests]
[exact bash command]

# Performance check
time [command] <<< '{}'
```

[All commands must be runnable as-is. Include expected output or exit code where
it is not obvious.]

## Router Integration Checklist

[Required for any ADR that creates or modifies a skill, pipeline, or agent.
For hook-only ADRs, write "N/A — no routing changes" and skip this section.]

- [ ] Frontmatter triggers added/updated in component YAML
- [ ] INDEX.json regenerated (`generate-skill-index.py` or `generate-agent-index.py`)
- [ ] Entry added to `skills/do/references/routing-tables.md`
- [ ] Trigger collision check passed (no duplicate triggers across force-routed entries)
- [ ] Pipeline companion map updated (if component pairs with existing pipelines)
- [ ] Quick-reference examples added to routing tables
- [ ] `python3 scripts/routing-benchmark.py --verbose` passes

## Validation Requirements

[What must be demonstrably true before this ADR is considered implemented:]

1. [Specific, runnable verification — exact command with expected output]
2. [Another verification]
3. [Performance check if applicable — e.g., execution time under 50ms]
4. [Edge case — malformed input, missing env var, etc.]

[These requirements become the PR acceptance criteria. Write them so that a domain
agent can execute them mechanically and report pass/fail.]

## References

- [`path/to/file.py`] — [What this file is and why it is relevant]
- [ADR-NNN] — [What that ADR decided and how it relates]
- [`research/topic.md`] — [What the research found]
```

---

## Notes for ADR Writers

**Context must cite file:line.** Every claim about code behavior needs a location.
"The hook outputs the wrong format" is not verifiable. "The hook outputs `%H:%M:%S`
at `hooks/userprompt-datetime-inject.py:16`" is verifiable.

**Decision must be implementable by a domain agent.** The agent reads the Decision
section and executes it. "Improve error handling" is not implementable. "Replace bare
`except:` on line 47 of `hooks/foo.py` with `except (json.JSONDecodeError, OSError) as e:`
and log the error to stderr" is implementable.

**Alternatives Considered is not optional.** Every seriously-considered path that was
not taken should appear here with a reason. This prevents relitigating the decision
later and shows the operator the decision was not arbitrary.

**System Integration is MANDATORY for new components.** Any ADR that creates a hook,
skill, agent, or pipeline must include the System Integration section with all
applicable subsections filled in. Skipping it produces a component that exists on disk
but is invisible to `/do` and not registered in settings.json.

**Router Integration Checklist is MANDATORY for new routable components.** Any ADR
creating a skill, agent, or pipeline must complete all checklist items before the PR
merges. A routable component without routing table entries is effectively invisible
to the toolkit.

**Sections marked "(if applicable)" can be removed entirely.** If this ADR creates
no hooks, delete the Hook Registration subsection. If it creates no skills, delete
Skill/Agent Registration. Do not leave empty subsections with placeholder text.

**The Affected Files table is the implementing agent's scope boundary.** The agent
only touches files listed there. If a file is missing from the table, the agent will
not modify it. Make the table complete before approving the ADR for implementation.

**Keep the Execution Plan optional.** For most ADRs, the Implementation Notes and
Affected Files table are sufficient. An elaborate 7-phase Execution Plan with parallel
worktrees and skill-eval gates is only warranted for ADRs that create multiple
interdependent new components. If the change is a one-line fix, the Implementation
Notes section is enough.
