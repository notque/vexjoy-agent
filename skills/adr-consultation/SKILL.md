---
name: adr-consultation
description: "Multi-agent consultation for architecture decisions."
user-invocable: false
allowed-tools:
  - Read
  - Write
  - Glob
  - Grep
  - Bash
  - Task
routing:
  triggers:
    - "consult on ADR"
    - "challenge this design"
    - "review before implementing"
    - "multi-agent consultation"
    - "architecture consultation"
    - "should we proceed"
    - "adr consultation"
  pairs_with:
    - feature-lifecycle
  complexity: Medium
  category: meta
---

# ADR Consultation Skill

Dispatches 3 specialized reviewers in parallel against an ADR, synthesizes findings into a PROCEED or BLOCKED verdict. Gate between feature-lifecycle plan and implement phases for Medium+ decisions.

## Reference Loading Table

| Signal | Load These Files | Why |
|---|---|---|
| tasks related to this reference | `agent-prompts.md` | Loads detailed guidance from `agent-prompts.md`. |
| implementation patterns | `consultation-preferred-patterns.md` | Loads detailed guidance from `consultation-preferred-patterns.md`. |
| implementation patterns | `consultation-patterns.md` | Loads detailed guidance from `consultation-patterns.md`. |
| errors, error handling | `error-handling.md` | Loads detailed guidance from `error-handling.md`. |

## Instructions

### Phase 1: DISCOVER

**Goal**: Locate the ADR and prepare the consultation directory.

**Step 1: Locate the ADR**

Check in order:
1. User-provided path (e.g., `adr/intent-based-routing.md`)
2. Active session context from adr-system hook (`.adr-session.json`)
3. Ask the user

Do not guess -- an incorrect guess wastes a full consultation cycle.

```bash
cat .adr-session.json 2>/dev/null
ls adr/*.md
```

Even if discussed informally, run the formal consultation -- undocumented discussion produces no persistent artifacts.

**Step 2: Check for prior consultation**

Scan `adr/{adr-name}/` for existing files before dispatching -- silently overwriting destroys the audit trail.

```bash
ls adr/{adr-name}/ 2>/dev/null
```

If files exist, report them with timestamps. Ask whether to overwrite or reuse.

**Step 3: Read the ADR**

Read full ADR content. Extract: decision, proposed changes, stated risks, ADR name (filename without `.md`).

**Step 4: Create consultation directory**

```bash
mkdir -p adr/{adr-name}
```

**Gate**: ADR read, directory created, ADR name confirmed. Dispatch only after gate passes.

---

### Phase 2: DISPATCH

**Goal**: Launch all consultation agents in a single message for true parallel execution.

All three Task calls MUST appear in ONE response -- sequential dispatch triples wall-clock time. The value is simultaneous independent judgment.

Dispatch all 3 agents even if the ADR "seems simple" -- partial consultation gives false confidence. Let agents report "no concerns" if clean.

Do not skip consultation under time pressure -- blocking concerns found post-implementation cost far more.

**Standard mode (3 agents)**: Always dispatch all three. See `references/agent-prompts.md` for prompt templates.

**Complex mode (5 agents)**: For Complex decisions (new subsystem, major API change), add `reviewer-system` and a second domain expert. Enable with "complex consultation" or "full consultation". See `references/agent-prompts.md` SS Complex Mode.

Each agent receives:
1. Full ADR content
2. Its specific lens and focus
3. Output path: `adr/{adr-name}/{agent-name}.md`
4. Structured output format from `references/agent-prompts.md`

**Gate**: All Task calls dispatched in one message. Proceed to Phase 3 only when all agents return and write files to `adr/{adr-name}/`.

---

### Phase 3: SYNTHESIZE

**Goal**: Read all agent responses and produce a synthesis.

**Step 1: Read agent responses from files**

Read from disk, not Task return context -- files persist across sessions; context does not.

```bash
cat adr/{adr-name}/reviewer-perspectives-contrarian.md
cat adr/{adr-name}/reviewer-perspectives-user-advocate.md
cat adr/{adr-name}/reviewer-perspectives-meta-process.md
```

**Step 2: Extract all concerns**

Track every concern in `adr/{adr-name}/concerns.md`. See `references/consultation-patterns.md` SS Phase 3 Artifact Templates for format.

**Step 3: Identify verdict agreement**

Do not treat NEEDS_CHANGES as PROCEED. Multiple NEEDS_CHANGES aggregates to higher concern, not softer approval.

| Pattern | Meaning |
|---------|---------|
| All 3 PROCEED | Strong consensus -- proceed |
| 2 PROCEED, 1 NEEDS_CHANGES | Soft consensus -- address changes, then proceed |
| Any BLOCK | Hard block -- must resolve first |
| Mixed NEEDS_CHANGES | Significant concerns -- address first |

Document any cross-cutting concerns the synthesizer identifies in concerns.md.

**Step 4: Write synthesis**

Write `adr/{adr-name}/synthesis.md` using template from `references/consultation-patterns.md` SS Phase 3 Artifact Templates.

**Gate**: concerns.md and synthesis.md both exist in `adr/{adr-name}/`.

---

### Phase 4: GATE

**Goal**: Issue final PROCEED or BLOCKED verdict.

**Step 1: Check for blocking concerns**

Read `adr/{adr-name}/concerns.md`. If any concern has `**Severity**: blocking`, verdict is BLOCKED. Hard gate, not advisory.

Do not rationalize blocking concerns as "theoretical" -- the gate exists to prevent proceeding with unresolved issues.

**Step 2: Issue verdict**

Use verdict display format from `references/consultation-patterns.md` SS Phase 4 Verdict Display.

**Gate**: Verdict issued, artifacts on disk. Consultation complete.

---

### Phase 5: LIFECYCLE (optional -- after ADR implementation merges)

**Goal**: Clean up consultation artifacts.

1. **Keep**: `adr/{name}/synthesis.md`, `adr/{name}/concerns.md`
2. **Delete**: `adr/{name}/reviewer-*.md` (value extracted into synthesis)
3. **Update**: ADR status to reflect completion

```bash
rm adr/{name}/reviewer-*.md
ls adr/{name}/synthesis.md adr/{name}/concerns.md
```

No `.gitkeep` needed -- `adr/` is gitignored.

---

## Error Handling

> See `references/error-handling.md` for full recovery procedures.

| Error | Resolution |
|-------|-----------|
| No ADR found | `ls adr/*.md`, ask user to specify |
| Agent times out or fails to write file | Re-run failed agents individually; do not synthesize until all 3 files exist |
| All agents PROCEED but synthesizer detects deeper issue | Document as orchestrator-level concern in concerns.md; factor into verdict |
| Consultation directory already exists | Report timestamps; ask whether to overwrite or reuse |

---

## Reference Loading

| Signal | Load |
|--------|------|
| Dispatching agents, structuring Task calls | `references/agent-prompts.md` |
| Complex mode (5-agent) dispatch | `references/agent-prompts.md` |
| Synthesizing verdicts, aggregating PROCEED/BLOCK/NEEDS_CHANGES | `references/consultation-patterns.md` |
| Classifying concern severity, writing concerns.md or synthesis.md | `references/consultation-patterns.md` |
| Issuing BLOCKED or PROCEED verdict display | `references/consultation-patterns.md` |
| Agent file missing, consultation incomplete, prior work overwritten | `references/consultation-preferred-patterns.md` |
| Rationalizing a blocking concern, treating NEEDS_CHANGES as PROCEED | `references/consultation-preferred-patterns.md` |
| Agent times out, empty file, output written to wrong path | `references/error-handling.md` |
| concerns.md has blocking severity but synthesis says PROCEED | `references/error-handling.md` |

## References

- [ADR: Multi-Agent Consultation](../../adr/multi-agent-consultation.md) -- The architecture decision this skill implements
- [parallel-code-review](../parallel-code-review/SKILL.md) -- Fan-out/fan-in pattern this skill adapts
- [reviewer-perspectives](../../agents/reviewer-perspectives.md) -- Perspectives agent (contrarian, user-advocate, meta-process lenses)
- `references/agent-prompts.md` -- Full prompt templates for all 3 standard agents + complex mode
- `references/consultation-patterns.md` -- Correct patterns, artifact templates, verdict display formats
- `references/consultation-preferred-patterns.md` -- Anti-patterns with detection commands
- `references/error-handling.md` -- Error recovery by phase
