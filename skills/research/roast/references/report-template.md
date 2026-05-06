# Roast Report Template

Use this template for the final synthesized report output.

## Report Structure

```markdown
# Analysis Report: [Target Name]

**Generated:** [timestamp]
**Mode:** Read-only analysis via multi-agent review
**Target:** [what was analyzed]
**Methodology:** 5 specialized agents with evidence-based validation

---

## Executive Summary

[2-3 paragraph overview of analysis]
- What was analyzed and why
- Total claims generated vs. validated
- Key themes from agent findings
- Overall assessment (strengths + improvement areas)

---

## Files Examined

| File | Purpose | Agents Reviewing |
|------|---------|------------------|
| `path/to/file1` | [why examined] | Senior, Pedant, Builder |
| `path/to/file2` | [why examined] | All 5 agents |

---

## Agent Perspectives

### Sustainability & Maintenance (Senior Engineer Focus)

[Constructive summary of Senior agent findings]
**Key observations:**
- [Observation 1 with file:line]
- [Observation 2 with file:line]

**Improvement opportunities:** [Specific suggestions]

---

### Precision & Accuracy (Pedant Focus)

[Constructive summary of Pedant agent findings]
**Key observations:**
- [Terminology clarity at location]
- [Logic gaps at location]

**Improvement opportunities:** [Specific suggestions]

---

### Onboarding & Accessibility (Newcomer Focus)

[Constructive summary of Newcomer agent findings]
**Key observations:**
- [First-run experience issues]
- [Documentation gaps]

**Improvement opportunities:** [Specific suggestions]

---

### Assumptions & Alternatives (Contrarian Focus)

[Constructive summary of Contrarian agent findings]
**Key observations:**
- [Premise to consider]
- [Alternative approaches]

**Improvement opportunities:** [Specific suggestions]

---

### Production Readiness (Builder Focus)

[Constructive summary of Builder agent findings]
**Key observations:**
- [Operational concern at location]
- [Edge cases to handle]

**Improvement opportunities:** [Specific suggestions]

---

## Claim Validation Summary

**Total claims generated:** [N]
**Validation breakdown:**
- VALID: [N] claims (backed by evidence)
- PARTIAL: [N] claims (overstated but have merit)
- UNFOUNDED: [N] claims (disproven by evidence)
- SUBJECTIVE: [N] claims (opinion-based)

| Claim | Agent | Verdict | Evidence |
|-------|-------|---------|----------|
| [CLAIM-1] | Senior | VALID | [file:line shows X] |
| [CLAIM-2] | Pedant | PARTIAL | [true that X, but Y mitigates] |
| [CLAIM-3] | Newcomer | UNFOUNDED | [code shows otherwise] |

---

## Improvement Opportunities (Prioritized)

**Only VALID and PARTIAL findings, presented constructively:**

### High Priority

| Opportunity | Location | Evidence | Suggested Action | Agent |
|-------------|----------|----------|------------------|-------|
| [improvement] | file:line | [proof] | [specific action] | Senior |

### Medium Priority

| Opportunity | Location | Evidence | Suggested Action | Agent |
|-------------|----------|----------|------------------|-------|
| [improvement] | file:line | [proof] | [specific action] | Pedant |

### Low Priority

| Opportunity | Location | Evidence | Suggested Action | Agent |
|-------------|----------|----------|------------------|-------|
| [improvement] | file:line | [proof] | [specific action] | Newcomer |

---

## Validated Strengths

| Strength | Location | Evidence | Agent |
|----------|----------|----------|-------|
| [strength] | file:line | [proof] | Builder |

---

## Implementation Roadmap

**Immediate actions** (can be done now):
1. [Action from HIGH priority findings]
2. [Action from HIGH priority findings]

**Short-term improvements** (next sprint/iteration):
1. [Action from MEDIUM priority findings]
2. [Action from MEDIUM priority findings]

**Long-term considerations** (future planning):
1. [Action from LOW priority findings]
2. [Architectural considerations from Contrarian]

---

## Dismissed Claims (Transparency)

**UNFOUNDED:**

| Claim | Agent | Why Dismissed |
|-------|-------|---------------|
| [claim] | [agent] | [evidence showing it's wrong] |

**SUBJECTIVE:**

| Claim | Agent | Note |
|-------|-------|------|
| [claim] | [agent] | [opinion-based, your decision] |
```

## Tone Transformation

When synthesizing agent outputs into the report, apply these transformations:

| Instead of | Write |
|------------|-------|
| "This is broken" | "This could be improved by [specific action]" |
| "Obviously wrong approach" | "Alternative approach worth considering: [option]" |
| "Amateur mistake" | "Opportunity to enhance [aspect]" |
| "No one would use this" | "User adoption could be increased by [change]" |

**Remove from agent outputs:** Sarcasm, mockery, dismissive language ("obviously", "clearly"), personal attacks, exaggerated negativity.

**Preserve from agent outputs:** Specific file:line evidence, technical accuracy, concrete suggestions, priority categorization.
