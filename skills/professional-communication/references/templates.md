# Communication Template Library

## Standard Business Communication Template

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

## Status Indicator Guidelines

### GREEN Status Template
Use when: Successful completion, positive progress, resolved issues

```markdown
**STATUS**: GREEN
**KEY POINT**: [Positive achievement or resolution]

**Summary**:
- Success: [What was accomplished]
- Impact: [Positive business or technical outcome]
- Quality: [Performance or reliability improvement]

**Technical Details**:
[Brief technical implementation or resolution details]

**Next Steps**:
1. [Monitoring or validation actions]
2. [Documentation or knowledge sharing]
3. [Potential follow-up enhancements]
```

### YELLOW Status Template
Use when: In progress with blockers, partial completion, external dependencies

```markdown
**STATUS**: YELLOW
**KEY POINT**: [Current state and primary blocker]

**Summary**:
- Progress: [What has been completed]
- Blocker: [Specific constraint or dependency]
- Workaround: [Temporary solution if available, or "None available"]

**Technical Details**:
[Technical explanation of constraint or dependency]

**Next Steps**:
1. [Action to address blocker or coordinate with stakeholders]
2. [Continue work on unblocked components]
3. [Document or escalate if appropriate]
```

### RED Status Template
Use when: Critical issues, project-affecting problems, urgent intervention needed

```markdown
**STATUS**: RED
**KEY POINT**: [Critical issue and business impact]

**Summary**:
- Critical issue: [Specific problem and severity]
- Impact scope: [Who/what is affected]
- Workaround: [Emergency mitigation if available]

**Technical Details**:
[Root cause and technical explanation for resolution teams]

**Next Steps**:
1. IMMEDIATE: [Emergency action to mitigate impact]
2. URGENT: [Coordination or escalation action]
3. [Root cause resolution and prevention]
```

## Section Templates

### Summary Section Structure

```markdown
**Summary**:
- [Most critical item]: [Business or technical impact]
- [Second priority item]: [Expected outcome or resolution timeline]
- [Supporting information]: [Implications for stakeholders]
```

**Rules**:
- Maximum 3 bullet points for executive summary
- Each bullet: [Subject]: [Impact or outcome]
- Order by business impact priority
- Keep each bullet to one line if possible

### Technical Details Section

```markdown
**Technical Details**:
[System or component name] [specific behavior or issue description]. [Root cause or implementation approach]. [Performance or reliability implications if relevant].
```

**Rules**:
- 2-3 sentences maximum for business stakeholders
- Can expand to 1 paragraph for technical audiences
- Preserve exact technical terminology
- Maintain cause-effect relationships
- Include metrics or measurements if relevant

### Next Steps Section

```markdown
**Next Steps**:
1. [Action verb] [specific task] [with timeline marker if available]
2. [Action verb] [specific task] [with ownership implication if present]
3. [Action verb] [follow-up consideration]
```

**Action Verb Examples**:
- Investigate, analyze, determine (for discovery)
- Implement, deploy, configure (for execution)
- Coordinate, escalate, communicate (for stakeholder actions)
- Document, validate, test (for quality assurance)
- Monitor, track, measure (for ongoing activities)

**Timeline Markers**:
- IMMEDIATE (within hours)
- URGENT (within 1-2 days)
- This week, Next sprint, This month
- After [dependency], When [condition met]

## Proposition Extraction Templates

### Fact Extraction Pattern
```
ORIGINAL: [Dense sentence]

FACTS:
- [Fact 1]: [What is stated]
- [Fact 2]: [What is stated]
- [Fact 3]: [What is stated]

IMPLICATIONS:
- [Fact 1] → [Consequence]
- [Fact 2] → [Consequence]
```

### Temporal Extraction Pattern
```
PAST ACTIONS:
- [What was done]

CURRENT STATE:
- [What is happening now]

FUTURE INTENTIONS:
- [What will be done]
```

### System Reference Pattern
```
SYSTEMS/COMPONENTS:
- [Component 1]: [Current state or behavior]
- [Component 2]: [Relationship to Component 1]
- [Component 3]: [External dependency or constraint]
```

## Multi-Stakeholder Templates

### Executive Summary (C-Level)
```markdown
**STATUS**: [COLOR]
**BUSINESS IMPACT**: [Revenue/customer/strategic implication]

**Summary**:
[1-2 sentences maximum covering what happened and what it means for business]

**Required Action**:
[What executive needs to know or approve]
```

### Technical Manager Summary
```markdown
**STATUS**: [COLOR]
**KEY POINT**: [Technical achievement or issue]

**Summary**:
- Technical: [What was implemented or discovered]
- Team impact: [Resource or timeline implications]
- Dependencies: [What's needed from other teams]

**Technical Details**:
[1 paragraph with sufficient detail for technical understanding]

**Next Steps**:
[3-5 specific actions with ownership]
```

### External Partner Communication
```markdown
**STATUS**: [COLOR]
**KEY POINT**: [Partnership or integration impact]

**Summary**:
- Integration status: [Current state of joint work]
- Dependencies: [What's needed from partner]
- Timeline: [Expected milestones or delivery dates]

**Technical Details**:
[API, integration, or interface specifics]

**Next Steps**:
[Coordinated actions with clear ownership split]
```

## Specialized Patterns

### Bug Report Translation
```markdown
**STATUS**: [YELLOW or RED based on severity]
**KEY POINT**: [Bug impact on functionality or users]

**Summary**:
- Bug: [Specific behavior that's broken]
- Impact: [Who/what is affected]
- Root cause: [Technical explanation if known, or "Under investigation"]

**Technical Details**:
[Reproduction steps, error messages, system state]

**Next Steps**:
1. [Immediate mitigation or workaround]
2. [Investigation or fix implementation]
3. [Testing and validation]
```

### Feature Request Translation
```markdown
**STATUS**: YELLOW
**KEY POINT**: [Feature request and business justification]

**Summary**:
- Request: [What functionality is needed]
- Business value: [Why it's important]
- Technical feasibility: [High/Medium/Low with brief explanation]

**Technical Details**:
[Implementation approach or architectural considerations]

**Next Steps**:
1. [Prioritization or stakeholder decision]
2. [Design or planning phase]
3. [Implementation timeline if approved]
```

### Performance Analysis Translation
```markdown
**STATUS**: [GREEN if acceptable, YELLOW if degraded, RED if critical]
**KEY POINT**: [Performance metric and business impact]

**Summary**:
- Current performance: [Metric with comparison to baseline or target]
- Impact: [User experience or system reliability effect]
- Root cause: [What's causing the performance characteristic]

**Technical Details**:
[Profiling data, bottlenecks, resource utilization]

**Next Steps**:
1. [Optimization approach or investigation]
2. [Performance testing validation]
3. [Monitoring and ongoing measurement]
```

## Quality Checklist Template

```markdown
TRANSFORMATION QUALITY CHECKLIST:
✓ Single, clear key point identified
✓ No information loss from original communication
✓ Technical accuracy maintained throughout
✓ Business impact clearly highlighted
✓ Action items specific and appropriately assigned
✓ Professional formatting and tone consistency
✓ Appropriate detail level for target audience
✓ Status indicator matches severity
✓ Next steps are actionable and owned
```

## Common Phrase Transformations

### Defensive → Neutral
- "I can't do X unless Y" → "X is blocked by dependency on Y"
- "That's not my fault" → "Root cause is in [system/team] scope"
- "I told you this would happen" → "As previously documented, [issue] occurred"

### Technical → Business
- "The algorithm is broken" → "System producing incorrect results"
- "Performance is terrible" → "Response time exceeds acceptable thresholds"
- "It won't work" → "Implementation not feasible with current constraints"

### Casual → Professional
- "This is awesome" → "Substantial improvement achieved"
- "Totally broken" → "Complete system failure"
- "Pretty good" → "Acceptable performance within parameters"
- "Kinda works" → "Partial functionality with known limitations"
