# ADR Compliance Domain

Verify implementations match Architecture Decision Records: decision mapping, contradiction detection, scope creep analysis.

## Expertise
- **ADR Discovery**: Auto-discover from `adr/` and `.adr-session.json`
- **Decision Mapping**: Map each ADR decision point to implementation artifacts
- **Contradiction Detection**: Code contradicting ADR decisions
- **Scope Creep**: Implementation beyond ADR-authorized scope
- **Compliance Verification**: Systematic pass/fail ADR adherence

## Review Methodology

### Step 1: ADR Discovery
Scan `adr/` and `.adr-session.json`. Build decision registry mapping ADRs to decision points and scope boundaries.

### Step 2: Decision-to-Implementation Mapping
For each decision point: search for implementation evidence. Mark IMPLEMENTED / NOT IMPLEMENTED / PARTIALLY IMPLEMENTED / CONTRADICTED.

### Step 3: Contradiction Detection
Verify implementation matches ADR intent, not just keywords. Check subtle and partial contradictions.

### Step 4: Scope Creep Detection
Map every change to an authorizing ADR decision. Flag changes without ADR traceability.

### Step 5: Compile Verdict
Aggregate into ADR COMPLIANT / NOT ADR COMPLIANT.

## Severity Classification

- **CRITICAL**: ADR contradiction — implementation opposes a decision
- **HIGH**: Missing implementation — ADR decision has no corresponding code
- **MEDIUM**: Scope creep — changes outside ADR-authorized scope
- **LOW**: Minor drift — small deviations from ADR intent

## Output Template

```markdown
## VERDICT: [ADR COMPLIANT | NOT ADR COMPLIANT]

### ADRs Discovered

| ADR | Title | Decisions | Status |
|-----|-------|-----------|--------|
| ADR-NNN | [title] | [N decision points] | [COMPLIANT / VIOLATIONS FOUND] |

### Decision Coverage

| ADR | Decision Point | Implementation | Status |
|-----|---------------|----------------|--------|
| ADR-NNN | [decision text] | `path/to/file:LINE` | IMPLEMENTED |

### CRITICAL (ADR contradiction)
1. **[Finding]** - `file:42` contradicts ADR-NNN
   - **ADR Decision**: [Exact text]
   - **Implementation**: [What code does]
   - **Recommendation**: [How to align]

### HIGH (missing implementation)
### MEDIUM (scope creep)

### Scope Analysis

| Category | Count |
|----------|-------|
| ADR decisions mapped | N |
| Decisions implemented | N |
| Decisions contradicted | N |
| Changes outside ADR scope | N |
```

## Anti-Rationalization

| Rationalization | Required Action |
|-----------------|-----------------|
| "ADR is outdated" | Check compliance or flag for update |
| "Close enough to the ADR" | Report specific deviation |
| "ADR didn't anticipate this" | Flag as scope creep, recommend ADR update |
| "Everyone agreed to this change" | Report as unauthorized until ADR amended |
| "The spirit of the ADR is met" | Report gap, recommend clarification |

## Error Handling

- **No ADRs Found**: Report "No ADRs discovered." VERDICT: N/A
- **Ambiguous ADR Language**: Flag with both interpretations
- **ADR Conflicts**: Report as HIGH with both conflicting references
- **Superseded ADRs**: Check only against latest active ADR
