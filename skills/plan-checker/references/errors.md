# Plan Checker Error Handling

Verbatim error matrix.

| Error | Cause | Solution |
|-------|-------|----------|
| No plan found | No plan file at expected locations | Provide explicit path, or run /feature-lifecycle (plan phase) first |
| No goal found | Plan lacks ## Goal or ## Success Criteria | Add a goal section to the plan before checking |
| File verification fails | Referenced file doesn't exist in codebase | Fix the file path in the plan, or create the file first |
| CLAUDE.md not found | No CLAUDE.md in target repo | Dimension 9 passes automatically; note in findings |
| Revision loop exhausted | 3 iterations couldn't resolve all blockers | Proceed with known risks documented |
| Plan is inline text | User pasted plan instead of file path | Parse inline text; warn that revisions won't persist to file |
