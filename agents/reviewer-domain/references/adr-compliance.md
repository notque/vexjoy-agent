# ADR Compliance Domain

Verifies that implementations match Architecture Decision Records -- decision mapping, contradiction detection, and scope creep analysis.

## Expertise
- **ADR Discovery**: Auto-discovering ADRs from `adr/` directory and `.adr-session.json` files
- **Decision Mapping**: Mapping each ADR decision point to concrete implementation artifacts
- **Contradiction Detection**: Identifying code that directly contradicts an ADR decision
- **Scope Creep Analysis**: Detecting implementation that goes beyond what the ADR authorized
- **Compliance Verification**: Systematic pass/fail assessment of ADR adherence

## Review Methodology

### Step 1: ADR Discovery
Scan `adr/` directory and `.adr-session.json`. Build a decision registry mapping each ADR to its decision points and scope boundaries.

### Step 2: Decision-to-Implementation Mapping
For each decision point: search codebase for implementation evidence, read relevant code, mark as IMPLEMENTED / NOT IMPLEMENTED / PARTIALLY IMPLEMENTED / CONTRADICTED.

### Step 3: Contradiction Detection
Verify implementation matches ADR intent, not just keywords. Check for subtle contradictions and partial contradictions.

### Step 4: Scope Creep Detection
Map every change to an authorizing ADR decision. Flag changes that cannot be traced to any ADR decision point.

### Step 5: Compile Verdict
Aggregate into ADR COMPLIANT / NOT ADR COMPLIANT.

## Severity Classification

- **CRITICAL**: ADR contradiction -- implementation directly opposes a decision
- **HIGH**: Missing implementation -- ADR decision has no corresponding code
- **MEDIUM**: Scope creep -- changes outside ADR-authorized scope
- **LOW**: Minor drift -- small deviations from ADR intent

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
   - **Implementation**: [What code actually does]
   - **Recommendation**: [How to align]

### HIGH (missing implementation)
[Same format]

### MEDIUM (scope creep)
[Same format]

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
| "ADR is outdated" | Check compliance or flag ADR for update |
| "Close enough to the ADR" | Report the specific deviation |
| "ADR didn't anticipate this case" | Flag as scope creep, recommend ADR update |
| "Everyone agreed to this change" | Report as unauthorized until ADR is amended |
| "The spirit of the ADR is met" | Report the gap and recommend clarification |

## Error Handling

- **No ADRs Found**: Report "No ADRs discovered. Cannot perform compliance review." VERDICT: N/A
- **Ambiguous ADR Language**: Flag the ambiguity with both possible interpretations
- **ADR Conflicts**: Report as HIGH with both conflicting ADR references
- **Superseded ADRs**: Only check compliance against the latest active ADR
