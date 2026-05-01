# Output Schema Archetypes

Standardized output patterns for different agent types. Agents SHOULD use the appropriate schema for consistency.

## Implementation Schema

**For agents that write code/configs:**

```markdown
## Summary
[1-2 sentence overview of what was implemented]

## Implementation
[Description of approach and key decisions]

## Files Changed
| File | Change | Lines |
|------|--------|-------|
| `path/file.go:42` | [description] | +N/-M |

## Testing
- [x] Tests pass: [output]
- [x] Types check: [output]
- [x] Linting: [output]

## Next Steps
- [ ] [Follow-up if any]
```

**Used by:** golang-general-engineer, python-general-engineer, typescript-frontend-engineer, database-engineer, kubernetes-helm-engineer, ansible-automation-engineer, and other implementation agents

---

## Analysis Schema

**For agents that analyze and recommend:**

```markdown
## Analysis
[Methodology and scope of analysis]

## Findings
### Finding 1: [Title]
- **Location**: `file:line`
- **Issue**: [description]
- **Impact**: [severity and consequences]

## Recommendations
1. [Recommendation with priority]
2. [Recommendation with priority]

## Next Steps
- [ ] [Action item]
```

**Used by:** performance-optimization-engineer, codebase-analyzer, research-coordinator-engineer

---

## Reviewer Schema

**For code review agents:**

```markdown
## VERDICT: [PASS | NEEDS_CHANGES | BLOCK]

## Summary
[Brief overview of review findings]

## Issues Found

### CRITICAL (0)
[None or list]

### HIGH (N)
1. **[Issue Title]** - `file:line`
   - Issue: [description]
   - Recommendation: [fix]

### MEDIUM (N)
[List]

### LOW (N)
[List]

## What Was Done Well
- [Positive observation]

## Next Steps
- [ ] [Required action for merge]
```

**VERDICT Values:**
- **PASS**: No blocking issues, approve merge
- **NEEDS_CHANGES**: Issues found but not blocking, request changes
- **BLOCK**: Critical issues, do not merge until resolved

**Used by:** reviewer-security, reviewer-business-logic, systematic-code-review skill, all roaster agents

---

## Planning Schema

**For implementation planning agents:**

```markdown
**Goal:** [What we're trying to achieve]

**Architecture:** [High-level approach]

**Tech Stack:** [Technologies involved]

## Prerequisites
- [ ] [Required before starting]

## Implementation Tasks

### Phase 1: [Name]
- [ ] Task 1.1: [description] → `file1.go`
- [ ] Task 1.2: [description] → `file2.go`

### Phase 2: [Name]
- [ ] Task 2.1: [description]

## Verification
- [ ] [How to confirm success]

## Risks
- [Risk and mitigation]
```

**Used by:** workflow-orchestrator skill, project-coordinator-engineer

---

## Exploration Schema

**For deep codebase analysis:**

```markdown
## EXPLORATION SUMMARY
[Overview of what was explored and why]

## KEY FINDINGS
1. [Finding with file references]
2. [Finding with file references]

## ARCHITECTURE INSIGHTS
- [Pattern observed]
- [Design decision identified]

## RELEVANT FILES
| File | Purpose | Key Functions |
|------|---------|---------------|
| `path/file.go` | [purpose] | `func1`, `func2` |

## RECOMMENDATIONS
- [Recommendation based on findings]
```

**Used by:** codebase-overview skill, Explore agent

---

## Selecting the Right Schema

| Agent Type | Schema | Key Indicator |
|------------|--------|---------------|
| Writes code | Implementation | Creates/modifies files |
| Reviews code | Reviewer | Evaluates existing code |
| Plans work | Planning | Designs approach before implementation |
| Analyzes patterns | Analysis | Identifies issues without fixing |
| Explores codebase | Exploration | Maps and understands code |

## Extending Schemas

Domain-specific agents may extend base schemas:

```markdown
## [Base Schema Sections]

## Domain-Specific Section
[Additional content for this domain]
```

For example, `reviewer-security` extends Reviewer Schema with:
- OWASP Top 10 Coverage
- Compliance Status

---

## JSON Schema Validation

Review output structure is enforced by JSON Schemas in `skills/shared-patterns/schemas/`:

| Schema File | Review Type | Validates |
|-------------|------------|-----------|
| `review-output-base.schema.json` | base | Generic review validation: verdict, findings (critical/high/medium/low) with file:line locations, positives |
| `systematic-code-review.schema.json` | systematic-code-review | + risk_level, severity: blocking/should_fix/suggestions |
| `parallel-code-review.schema.json` | parallel-code-review | + severity_matrix, reviewer attribution per finding |
| `sapcc-review.schema.json` | sapcc-review | + 10-agent scorecard, quick_wins |
| `sapcc-audit.schema.json` | sapcc-audit | + package_summary, must_fix/should_fix/nit |

**Usage:**
```bash
python3 scripts/validate-review-output.py --type {type} output.md
```

Exit codes: 0 = valid, 1 = structural errors, 2 = parse error.

Schemas enforce Tier 1 (deterministic) validation per PHILOSOPHY.md. Content quality remains Tier 2 (LLM-judged).
