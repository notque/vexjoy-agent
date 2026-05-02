---
name: professional-communication
description: "Transform technical communication into structured business formats."
user-invocable: false
allowed-tools:
  - Read
  - Write
routing:
  triggers:
    - "business communication"
    - "structured format"
    - "clear writing"
    - "write email"
    - "draft memo"
    - "executive summary"
    - "summarize for management"
    - "status update"
  category: content-creation
  pairs_with:
    - voice-writer
    - pptx-generator
---

# Professional Communication Skill

Transform dense technical communication into structured business formats via proposition extraction and deterministic templates. Extract every detail, categorize by business relevance, apply template, verify completeness.

**Core principle**: Transformation, not creation. Restructure existing input for executive clarity with preserved technical accuracy.

---

## Reference Loading Table

| Signal | Load These Files | Why |
|---|---|---|
| example-driven tasks | `examples.md` | Loads detailed guidance from `examples.md`. |
| tasks related to this reference | `templates.md` | Loads detailed guidance from `templates.md`. |

## Instructions

### Phase 1: PARSE

**Goal**: Extract every proposition before structuring. Extract first, summarize never -- summarizing skips facts.

**Step 1: Classify input type** (determines Phase 2 categorization):
- Technical update, debugging narrative, status report, or dependency discussion

**Step 2: Extract all propositions** systematically:
1. **Facts**: All distinct statements of truth
2. **Implications**: Cause-effect relationships
3. **Temporal markers**: Past/present/future actions
4. **System references**: All mentioned components
5. **Blockers**: Hidden dependencies and constraints
6. **Emotional context**: Frustration/satisfaction/urgency (needed for tone transformation)

**Step 3: Document implicit context** -- surface assumptions the audience needs stated:
- Technical acronyms the audience may not know
- Timeline context relative to milestones
- Organizational context (teams, reporting)

**Step 4: Count and validate**

```markdown
## Parsing Result
Input type: [technical update | debugging narrative | status report | dependency discussion]
Proposition count: [N distinct facts/claims]
Emotional markers: [frustration | satisfaction | urgency | neutral]

Extracted Propositions:
1. [Fact/claim 1]
2. [Fact/claim 2]
... (ALL propositions - NO information loss)

Implicit Context:
- [Assumption 1]
- [Assumption 2]
```

**Gate**: ALL propositions extracted with zero information loss.

### Phase 2: STRUCTURE

**Goal**: Categorize and prioritize propositions by business relevance.

**Step 1: Categorize** (determines template placement):

```markdown
Status:   [items with current state]
Actions:  [completed, in-progress, planned]
Impacts:  [business and technical consequences]
Blockers: [dependencies, constraints]
Next:     [required actions]
```

**Step 2: Priority order** (by executive decision impact):
1. Business Impact (revenue, customer, strategic)
2. Technical Functionality (core operation)
3. Project Timeline (schedule implications)
4. Resource Requirements (personnel, infrastructure)
5. Risk Management (potential issues)

Highest-priority categories go in output. Lower-priority items preserved in Technical Details.

**Step 3: Identify information gaps** -- ask only when:
- Severity ambiguous (GREEN vs YELLOW -- default YELLOW)
- Missing action item ownership (block until clarified)
- Undefined terms critical to business impact

**Gate**: All propositions categorized and prioritized.

### Phase 3: TRANSFORM

**Goal**: Apply standard template with professional tone. Use ONLY this structure:

```markdown
**STATUS**: [GREEN|YELLOW|RED]
**KEY POINT**: [Single most important business takeaway]

**Summary**:
- [Primary accomplishment/issue]: [Business impact]
- [Current focus/blocker]: [Expected outcome/resolution need]
- [Secondary consideration]: [Implications]

**Technical Details**:
[2-3 sentences maximum preserving technical accuracy]

**Next Steps**:
1. [Specific action with timeline if available]
2. [Secondary action with ownership implications]
3. [Follow-up considerations]
```

**Step 2: Tone adjustment** (apply all deterministically):
- Strip hedging: "I think we might need to..." → "Deploy X to address Y"
- Neutralize defensive tone: "We had to rollback because..." → "Rolled back to [version] due to [root cause]"
- Preserve urgency markers and severity indicators
- Keep technical terms intact -- oversimplification loses information
- Maintain causal chains and specific metrics

**Step 3: Status classification** (document reasoning always):
- **GREEN**: Fully complete, no follow-up, verification done
- **YELLOW**: Resolved with follow-up needed, blocked, partial completion
- **RED**: Active critical issues, production impact, urgent intervention

Format: "Status: YELLOW (deployment successful but monitoring pending)"

**Step 4: Action item specificity**

Every next step MUST include: specific verb (investigate/deploy/coordinate -- not "fix"), scope, ownership, timeline (IMMEDIATE/EOW/this sprint).

**Gate**: Template applied, tone transformed, action items specific.

### Phase 4: VERIFY

**Goal**: Confirm transformation quality. All checks must pass.

1. Compare output against Phase 1 propositions -- zero information loss. Missing facts go in Technical Details.
2. Verify technical accuracy -- exact terms, metrics, causal chains. "Database issues" for "Redis cluster failover" fails.
3. Confirm status matches severity criteria.
4. Validate action items: each must have (verb, scope, owner, timeline). "Fix the issue" fails; "Complete Redis failover testing in staging (DevOps, by EOW)" passes.
5. Check detail level for audience. Non-technical: bridge jargon with plain explanations.
6. Document transformation summary:

```markdown
## Transformation Summary
Input type: [type]
Propositions extracted: [N]
Status assigned: [GREEN|YELLOW|RED] ([reasoning])
Information loss: None
Template applied: standard
```

**Gate**: All verification checks pass. Transformation is complete. Complete all 6 steps before delivering.

---

## Examples

### Example 1: Multi-Propositional Sentence
User says: "I fixed the database issue but then the API started failing so I had to rollback and now we're investigating the connection pool settings which might be related to the recent Kubernetes upgrade."
Actions:
1. Extract 5 propositions: DB fix, API failure, rollback, pool investigation, K8s link (PARSE)
2. Categorize: Status=rollback done, Blockers=pool+K8s, Actions=investigating (STRUCTURE)
3. Apply template with YELLOW status, specific next steps (TRANSFORM)
4. Verify no facts lost, technical terms preserved (VERIFY)
Result: Structured update with clear status and actionable next steps

### Example 2: Defensive Blocker Communication
User says: "I can't make progress because the API team hasn't responded in 3 days and my sprint is at risk"
Actions:
1. Extract urgency, duration, dependency, impact propositions (PARSE)
2. Categorize: Blocker=API spec, Impact=sprint risk, Timeline=3 days (STRUCTURE)
3. Apply template with YELLOW status, escalation-focused next steps (TRANSFORM)
4. Verify urgency preserved, defensive tone neutralized (VERIFY)
Result: Neutral status report with clear escalation path

### Example 3: Crisis Communication
User says: "The latest deploy broke checkout completely, users are getting 500 errors, we rolled back but some orders might be lost"
Actions:
1. Extract severity, system affected, user impact, rollback status, data risk (PARSE)
2. Categorize: Status=rolled back, Impact=orders lost, Blocker=data recovery (STRUCTURE)
3. Apply template with RED status, IMMEDIATE/URGENT tiered next steps (TRANSFORM)
4. Verify crisis severity reflected, no false reassurance in tone (VERIFY)
Result: RED status report with tiered emergency response actions

---

## Error Handling

### Error: "Missing Context in Input"
**Cause**: Technical terms or acronyms critical to business impact are undefined.

**Solution**:
1. Ask user for clarification on terms critical to status classification — speculation causes wrong status assignments
2. Make reasonable inferences only for minor details; flag all assumptions explicitly in Technical Details section
3. Complete transformation while waiting — provide output with a note: "Status classification assumed X because Y was undefined"

### Error: "Ambiguous Status Classification"
**Cause**: Input contains mixed signals (e.g., issue resolved but monitoring incomplete).

**Solution**:
1. Default to YELLOW when unclear between GREEN/YELLOW — YELLOW preserves urgency for follow-up without false reassurance
2. Default to RED only with clear critical indicators: production impact (users affected), data loss (unrecoverable), or ongoing crisis (not yet mitigated)
3. Document reasoning in parenthetical: "Status: YELLOW (deployment successful but monitoring pending)" — transparency prevents misinterpretation

### Error: "Multi-Thread Update Contamination"
**Cause**: Input contains multiple unrelated topics that could cross-contaminate status classifications.

**Solution**:
1. Process each thread as separate proposition set (Phase 1 extraction per thread)
2. Apply template independently to each thread (Phase 2-3 per thread)
3. Combine with clear thread identification in final output (use headers: "Thread A: Deployment", "Thread B: Data Recovery")
4. Ensure status indicators are thread-specific (Thread A may be GREEN while Thread B is RED) — separate outcomes, separate classifications

---

## Error Handling Principles

- Summarizing before extracting = loses facts. Complete Phase 1 fully first.
- Status is never "obvious". Apply criteria, document reasoning.
- Always include Technical Details even for non-technical audiences -- bridge jargon.
- Action items must be explicit (verb, scope, owner, timeline). Implied work cannot be executed.
- Apply ALL tone rules. "Close enough" means defensive language is still embedded.

---

## References

- `${CLAUDE_SKILL_DIR}/references/templates.md`: Status templates, section formats, phrase transformations
- `${CLAUDE_SKILL_DIR}/references/examples.md`: Complete transformation examples with proposition extraction
