# File-backed plan contract

Use a saved plan only when work must survive context boundaries or coordinate
multiple owned surfaces. It records:

```markdown
# Task plan: <outcome>
## Phases
- [ ] <action> — owner/files — verification command and expected result
## Decisions
- <choice, source, consequence>
## Gaps and blockers
- <gap, owner, next evidence>
## Deviations
- <planned vs actual and why>
## Status
<current phase, last verified artifact, next action>
```

Update status after evidence-changing work, not every tool call. Never mark a
task complete from a worker assertion. If execution diverges, amend the plan
before continuing so resume state matches the repository.
