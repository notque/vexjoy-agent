---
name: roast
description: "Constructive critique via 5 HackerNews personas with claim validation."
user-invocable: false
argument-hint: "<target to critique>"
allowed-tools:
  - Read
  - Glob
  - Grep
  - Bash
  - Task
  - Skill
context: fork
routing:
  triggers:
    - "roast code"
    - "devil's advocate"
    - "stress test idea"
    - "roast this"
    - "stress test this idea"
    - "poke holes in this"
  category: analysis
  pairs_with:
    - multi-persona-critique
    - systematic-code-review
---

# Roast: Devil's Advocate Analysis

Evidence-based constructive critique through 5 HackerNews personas: Skeptical Senior, Well-Actually Pedant, Enthusiastic Newcomer, Contrarian Provocateur, Pragmatic Builder. Spawns personas in parallel, validates all claims against actual files/lines, synthesizes into improvement-focused report.

**Key constraints:**
- Read CLAUDE.md before analysis begins
- Read-only mode mandatory (no Write, Edit, destructive Bash) -- enforced via `read-only-ops` skill
- Every claim must reference specific file:line and be validated against evidence
- All 5 personas must complete before validation -- no partial analysis
- Final report includes both validated strengths and problems, prioritized by impact
- Unvalidated claims dismissed; unfounded critiques shown with evidence explaining why
- Sarcasm/mockery stripped during synthesis; technical accuracy and file references preserved

---

## Reference Loading Table

| Signal | Load These Files | Why |
|---|---|---|
| tasks related to this reference | `personas.md` | Loads detailed guidance from `personas.md`. |
| tasks related to this reference | `report-template.md` | Loads detailed guidance from `report-template.md`. |

## Instructions

### Phase 1: ACTIVATE READ-ONLY MODE

Invoke `read-only-ops` skill:

```
skill: read-only-ops
```

**Allowed**: Read, Glob, Grep, Bash (`ls`, `wc`, `du`, `git status/log/diff`)
**Forbidden**: Write, Edit, Bash (`rm`, `mv`, `cp`, `mkdir`, `touch`, `git add/commit/push`)

If read-only mode cannot activate, stop immediately.

**Gate**: Read-only mode active.

### Phase 2: GATHER CONTEXT

**Step 1: Identify target type**

| Input | Target | Action |
|-------|--------|--------|
| No argument | README.md + repo structure | Read README, survey layout |
| `@file.md` | Specific file | Read file, identify related files |
| Description | Described concept | Search repo for implementation |

**Step 2**: Read key files: README.md, main documentation, relevant implementation files.

**Step 3**: Survey structure via Glob: `**/*.md`, source organization, config/dependency files.

**Step 4**: Search via Grep for claims to verify, usage patterns, dependencies, tests.

**Step 5: Ground verbal descriptions** -- If user describes a concept, search repo for existing implementation. Critique grounded in actual code beats critique of a strawman. Never analyze a verbal description without confirming code exists.

**Gate**: Target identified, sufficient context gathered.

### Phase 3: SPAWN ROASTER AGENTS (Parallel)

Launch 5 agents in parallel via Task tool, each with full persona spec from its agent file:

1. **Skeptical Senior** (`agents/reviewer-code.md`, senior lens) -- sustainability, maintenance burden
2. **Well-Actually Pedant** (`agents/reviewer-code.md`, pedant lens) -- precision, terminological accuracy
3. **Enthusiastic Newcomer** (`agents/reviewer-perspectives.md`, newcomer lens) -- onboarding, documentation clarity
4. **Contrarian Provocateur** (`agents/reviewer-perspectives.md`, contrarian lens) -- fundamental assumptions, alternatives
5. **Pragmatic Builder** (`agents/reviewer-domain.md`, pragmatic-builder lens) -- production readiness, operational concerns

Each agent must:
- Invoke `read-only-ops` skill first
- Follow 5-step review process
- Tag ALL claims as `[CLAIM-N]` with specific `file:line` references
- Provide concrete evidence for every claim

See `references/personas.md` for full prompt template and claim format.

**CRITICAL**: Wait for all 5 agents before Phase 4. No partial results.

**Gate**: All 5 agents complete with tagged claims.

### Phase 4: COORDINATE (Validate Claims)

**Step 1: Collect all claims** -- Extract every `[CLAIM-N]`. Track: claim text, source persona, file:line.

**Step 2: Validate each claim** -- Read referenced file/line and assign verdict:

| Verdict | Meaning | Criteria |
|---------|---------|----------|
| VALID | Accurate | Evidence directly supports |
| PARTIAL | Overstated but has merit | Some truth, some exaggeration |
| UNFOUNDED | Not supported | Evidence contradicts or absent |
| SUBJECTIVE | Opinion, unverifiable | Preference/style |

You must read the file and check the line. "Obviously valid" is rationalization.

**Step 3: Cross-reference** -- Claims found by 3+ personas independently => escalate to HIGH.

**Step 4: Prioritize** -- Sort VALID/PARTIAL by impact: HIGH (core functionality, security, maintainability), MEDIUM (moderate impact), LOW (minor/polish).

**Gate**: All claims validated with evidence.

### Phase 5: SYNTHESIZE (Generate Report)

Follow template in `references/report-template.md`. Key rules:

1. **Filter**: Only VALID/PARTIAL in improvement opportunities
2. **Dismissed section**: UNFOUNDED claims with evidence showing why
3. **Subjective section**: SUBJECTIVE claims noted as opinion-based
4. **Strengths required**: Include "Validated Strengths" section
5. **Constructive tone**: Strip sarcasm/mockery, preserve technical accuracy and file references
6. **Implementation roadmap**: Group by immediacy (immediate / short-term / long-term)

**Validation Summary Table** (include in report):

```markdown
## Claim Validation Summary

| Claim | Agent | Verdict | Evidence |
|-------|-------|---------|----------|
| [CLAIM-1] | Senior | VALID | [file:line shows X] |
| [CLAIM-2] | Pedant | PARTIAL | [true that X, but Y mitigates] |
| [CLAIM-3] | Newcomer | UNFOUNDED | [code shows otherwise] |
```

**Gate**: Report complete with all sections. Analysis done.

---

## Error Handling

### Error: "Agent Returns Claims Without File References"
**Cause**: Persona skipped evidence-gathering.
**Solution**: Dismiss as UNFOUNDED. If majority lack references, re-run that agent with explicit file:line instruction. Never promote ungrounded claims.

### Error: "Read-Only Mode Not Activated"
**Cause**: Phase 1 skipped or `read-only-ops` failed.
**Solution**: Stop all analysis. Invoke `read-only-ops`. If unavailable, manually enforce: no Write, Edit, or destructive Bash.

### Error: "Agent Attempts to Fix Issues"
**Cause**: Persona crossed from analysis into implementation.
**Solution**: Discard modifications. Extract only analytical findings. This is read-only analysis.

### Error: "No Target Found or Empty Repository"
**Cause**: No target specified and no README.md.
**Solution**: Check CONTRIBUTING.md, docs/, main source files. If code but no docs, analyze code structure. If truly empty, ask user for specific target.

---

## References

### Reference Files
- `${CLAUDE_SKILL_DIR}/references/report-template.md`: Report template with tone transformation rules
- `${CLAUDE_SKILL_DIR}/references/personas.md`: Persona specifications, prompt template, claim format
- `agents/reviewer-code.md`: Code quality reviewer (senior and pedant lenses)
- `agents/reviewer-perspectives.md`: Perspectives reviewer (newcomer and contrarian lenses)
- `agents/reviewer-domain.md`: Domain reviewer (pragmatic-builder lens)

### Dependencies
- **read-only-ops skill**: Enforces no-modification guardrails during analysis
