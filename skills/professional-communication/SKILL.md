---
name: professional-communication
description: |
  Transform dense technical communication into clear, structured business
  formats using proposition extraction and deterministic templates. Use when
  user needs to convert technical updates, debugging narratives, status
  reports, or dependency discussions into executive-ready summaries. Use for
  "transform this update", "make this executive-ready", "summarize for my
  manager", "professional format", or "status report". Do NOT use for
  writing new content from scratch, creative writing, or generating
  documentation that doesn't transform an existing input.
version: 2.0.0
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
---

# Professional Communication Skill

## Operator Context

This skill operates as an operator for technical communication transformation, configuring Claude's behavior for structured information extraction and business formatting. It implements the **Deterministic Template** architectural pattern -- extract all propositions, categorize by type, apply structured template -- with **Domain Intelligence** embedded in the status classification and tone transformation methodology.

### Hardcoded Behaviors (Always Apply)
- **CLAUDE.md Compliance**: Read and follow repository CLAUDE.md before transformation
- **Over-Engineering Prevention**: Only transform what's directly requested. No speculative sections, no "nice to have" formatting not asked for
- **Complete Proposition Extraction**: NEVER lose technical details during transformation
- **Status Indicators**: Always use GREEN/YELLOW/RED in output (non-negotiable for executive readability)
- **Template Structure**: Always follow "Status -> Key Point -> Summary -> Technical Details -> Next Steps" format
- **Four-Phase Process**: PARSE -> STRUCTURE -> TRANSFORM -> VERIFY (mandatory workflow)

### Default Behaviors (ON unless disabled)
- **Communication Style**: Report transformation results factually without self-congratulation
- **Executive Summary**: Include executive-friendly overview by default
- **Action Item Extraction**: Extract and list next steps with ownership implications
- **Context Bridging**: Make implicit knowledge explicit for non-technical audiences
- **Professional Tone**: Transform casual/defensive language into neutral business language
- **Temporary File Cleanup**: Remove intermediate analysis files at completion

### Optional Behaviors (OFF unless enabled)
- **Technical Deep Dive**: Include extended technical details beyond 2-3 sentence summary
- **Comparative Analysis**: Add historical comparison sections
- **Multi-Stakeholder Variants**: Generate multiple versions for different audiences

## What This Skill CAN Do
- Extract all propositions from dense technical communication without information loss
- Apply deterministic templates that produce consistent business-formatted output
- Classify status indicators (GREEN/YELLOW/RED) based on objective severity criteria
- Transform defensive or emotional language into neutral business language
- Generate specific, actionable next steps with ownership and timeline markers

## What This Skill CANNOT Do
- Write new content from scratch (use appropriate writing skill instead)
- Generate documentation that doesn't transform an existing input
- Skip proposition extraction and jump straight to formatting
- Create multi-stakeholder variants by default (enable optional behavior first)
- Transform without verifying information completeness in Phase 4

---

## Instructions

### Phase 1: PARSE

**Goal**: Extract every proposition from the input before structuring anything.

**Step 1: Classify input type**

Identify the communication type:
- Technical update (progress report with embedded facts)
- Debugging narrative (stream-of-consciousness problem-solving)
- Status report (project state with blockers/dependencies)
- Dependency discussion (constraints buried in defensive language)

**Step 2: Extract all propositions**

Parse each sentence systematically:
1. **Facts**: All distinct statements of truth
2. **Implications**: Cause-effect relationships
3. **Temporal markers**: Past/present/future actions
4. **System references**: All mentioned components
5. **Blockers**: Hidden dependencies and constraints
6. **Emotional context**: Frustration/satisfaction/urgency indicators

**Step 3: Document implicit context**

Surface assumptions the author takes for granted but the audience needs stated:
- Technical acronyms or project names the audience may not know
- Timeline context (when things happened relative to milestones)
- Organizational context (team relationships, reporting structures)

**Step 4: Count and validate propositions**

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

**Gate**: ALL propositions extracted with zero information loss. Proceed only when gate passes.

### Phase 2: STRUCTURE

**Goal**: Categorize and prioritize all extracted propositions.

**Step 1: Categorize propositions**

```markdown
Status:   [items with current state]
Actions:  [completed, in-progress, planned]
Impacts:  [business and technical consequences]
Blockers: [dependencies, constraints]
Next:     [required actions]
```

**Step 2: Priority order**

1. Business Impact (revenue, customer, strategic)
2. Technical Functionality (core operation)
3. Project Timeline (schedule implications)
4. Resource Requirements (personnel, infrastructure)
5. Risk Management (potential issues)

**Step 3: Identify information gaps**

Flag any propositions that need clarification before transformation:
- Ambiguous severity (could be GREEN or YELLOW)
- Missing ownership for action items
- Undefined technical terms critical to business impact

**Gate**: All propositions categorized and prioritized. Proceed only when gate passes.

### Phase 3: TRANSFORM

**Goal**: Apply output template with professional tone.

**Step 1: Apply standard template**

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

**Step 2: Tone adjustment**

- Strip hedging, defensive language, and filler
- Preserve urgency markers and severity indicators
- Keep technical terms intact (do NOT oversimplify)
- Maintain causal chains and specific metrics

**Step 3: Status classification**

- **GREEN**: Fully complete with no follow-up, all verification done
- **YELLOW**: Resolved with follow-up needed, blocked on dependencies, partial completion
- **RED**: Active critical issues, production impact, urgent intervention needed
- Document reasoning: "Status: YELLOW (deployment successful but monitoring pending)"

**Step 4: Action item specificity**

Every next step MUST include:
- Specific action verb (investigate, deploy, coordinate, document)
- Clear scope (what exactly needs doing)
- Ownership implication (who or which team)
- Timeline marker when available (IMMEDIATE, by EOW, this sprint)

**Gate**: Output follows template structure with professional tone. Proceed only when gate passes.

### Phase 4: VERIFY

**Goal**: Confirm transformation quality before delivery.

**Step 1**: Compare output against extracted propositions -- NO information loss

**Step 2**: Verify technical accuracy -- terms, metrics, causal chains preserved

**Step 3**: Confirm status indicator matches actual severity

**Step 4**: Validate action items are specific (who, what, when) not vague

**Step 5**: Check appropriate detail level for target audience

**Step 6**: Document transformation summary

```markdown
## Transformation Summary
Input type: [type]
Propositions extracted: [N]
Status assigned: [GREEN|YELLOW|RED] ([reasoning])
Information loss: None
Template applied: [standard | executive | technical manager]
```

**Gate**: All verification checks pass. Transformation is complete.

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
Cause: Technical terms or acronyms critical to business impact are undefined
Solution:
1. Ask user for clarification on terms critical to status classification
2. Make reasonable inferences for minor details
3. Note all assumptions explicitly in Technical Details section

### Error: "Ambiguous Status Classification"
Cause: Input contains mixed signals (e.g., issue resolved but monitoring incomplete)
Solution:
1. Default to YELLOW when unclear between GREEN/YELLOW
2. Default to RED only with clear critical indicators (production impact, data loss)
3. Document reasoning in parenthetical after status indicator

### Error: "Multi-Thread Update Contamination"
Cause: Input contains multiple unrelated topics that could cross-contaminate
Solution:
1. Process each thread as separate proposition set
2. Apply template independently to each thread
3. Combine with clear thread identification in final output
4. Ensure status indicators are thread-specific

---

## Anti-Patterns

### Anti-Pattern 1: Skipping Proposition Extraction
**What it looks like**: Jumping straight to template formatting without parsing all embedded facts
**Why wrong**: Loses technical details, misses causal relationships, assigns wrong status
**Do instead**: Complete Phase 1 fully. Extract ALL propositions before any formatting.

### Anti-Pattern 2: Adding Unsolicited Sections
**What it looks like**: Adding "Risk Assessment", "Mitigation Strategies", "Historical Context" not in the original
**Why wrong**: Over-engineering that changes meaning, increases length, violates hardcoded behavior
**Do instead**: Apply ONLY the standard template. Let user request additional analysis.

### Anti-Pattern 3: Losing Technical Accuracy for Simplicity
**What it looks like**: "Redis cluster failover with 15-second timeout" becomes "database problems caused delays"
**Why wrong**: Strips specificity needed for technical teams to act. Violates complete proposition extraction.
**Do instead**: Keep technical terms, preserve metrics, maintain causal chains in Technical Details section.

### Anti-Pattern 4: Vague Action Items
**What it looks like**: "Fix the issue", "Follow up on dependencies", "Improve the system"
**Why wrong**: No ownership, no timeline, no scope. Stakeholders cannot act on vague items.
**Do instead**: "Complete Redis failover testing in staging (DevOps team, by EOW)"

### Anti-Pattern 5: Inconsistent Status Indicators
**What it looks like**: 2-hour outage marked GREEN, successful deploy with incomplete monitoring marked GREEN
**Why wrong**: Inconsistency confuses stakeholders and erodes trust in the status system
**Do instead**: Apply status criteria consistently. Document reasoning in parenthetical.

---

## References

This skill uses these shared patterns:
- [Anti-Rationalization](../shared-patterns/anti-rationalization-core.md) - Prevents shortcut rationalizations
- [Verification Checklist](../shared-patterns/verification-checklist.md) - Pre-completion checks

### Domain-Specific Anti-Rationalization

| Rationalization | Why It's Wrong | Required Action |
|-----------------|----------------|-----------------|
| "I can summarize without extracting first" | Summarizing skips propositions, loses facts | Complete Phase 1 extraction |
| "Status is obviously GREEN" | Obvious ≠ verified against criteria | Apply status classification rules |
| "Technical details aren't needed here" | Non-technical audience ≠ no technical section | Include Technical Details section always |
| "Action items are implied" | Implied ≠ actionable for stakeholders | Write explicit next steps with ownership |
| "Close enough tone" | Professional tone requires specific transformations | Apply defensive->neutral, casual->professional rules |

### Reference Files
- `${CLAUDE_SKILL_DIR}/references/templates.md`: Status-specific templates, section formats, phrase transformations
- `${CLAUDE_SKILL_DIR}/references/examples.md`: Complete transformation examples with proposition extraction
