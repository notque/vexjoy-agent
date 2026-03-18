# Execution Report Format

Standardized output format for reporting completed work.

## Full Report Format

Use for significant changes or when requested:

```markdown
## Summary

[1-2 sentence overview of what was accomplished]

## Changes Made

| File | Change | Lines |
|------|--------|-------|
| `path/to/file.ts:42` | Added validation function | +15 |
| `path/to/other.ts:100` | Fixed null check | +3/-1 |
| `path/to/test.ts:50` | Added test coverage | +25 |

## Verification Performed

- [x] Tests pass
  ```
  [actual test output]
  ```
- [x] Types check
  ```
  [actual tsc output]
  ```
- [x] Linting passes
  ```
  [actual lint output]
  ```
- [x] Manual verification
  - [specific steps taken]
  - [result observed]

## Requirements Addressed

| Requirement | Status | Evidence |
|-------------|--------|----------|
| [Requirement 1] | Done | [how verified] |
| [Requirement 2] | Done | [how verified] |

## Remaining Items

- [ ] [If any follow-up needed]
- Or: None - all requirements complete

## How to Verify

Steps the user can take to confirm:

1. [Step 1]
2. [Step 2]
3. Expected result: [what they should see]
```

## Abbreviated Report Format

Use for minor changes:

```markdown
## Done

Changed `path/to/file.ts:42` - [brief description]

Verified: Tests pass, types check.

To verify: [quick step user can take]
```

## Review Finding Report Format

For code review findings:

```markdown
## Review Findings

### CRITICAL (0)
None found.

### HIGH (2)

1. **SQL Injection Risk** - `api/users.ts:45`
   - Issue: User input directly in query
   - Recommendation: Use parameterized query
   ```typescript
   // Instead of
   db.query(`SELECT * FROM users WHERE id = ${userId}`)
   // Use
   db.query('SELECT * FROM users WHERE id = ?', [userId])
   ```

2. **Missing Auth Check** - `api/admin.ts:20`
   - Issue: Admin endpoint lacks authorization
   - Recommendation: Add role check middleware

### MEDIUM (3)
[...]

### LOW (5)
[...]

## Summary

| Severity | Count |
|----------|-------|
| CRITICAL | 0 |
| HIGH | 2 |
| MEDIUM | 3 |
| LOW | 5 |

Recommendation: Address HIGH issues before merge.
```

## Error Report Format

When something goes wrong:

```markdown
## Error Report

### What Failed

[Brief description of failure]

### Error Output

```
[Actual error message/stack trace]
```

### Context

- File: `path/to/file.ts`
- Line: 42
- Action attempted: [what was being done]

### Attempted Resolution

1. [What was tried]
2. [Result]

### Current Status

- [ ] Resolved
- [x] Blocked - needs [specific help needed]

### Recommended Next Steps

1. [Action 1]
2. [Action 2]
```

## When to Use Each Format

| Situation | Format |
|-----------|--------|
| Feature implementation | Full |
| Bug fix | Full or Abbreviated |
| Minor change (<5 lines) | Abbreviated |
| Code review | Review Finding |
| Error during execution | Error Report |
| Documentation update | Abbreviated |
| Refactoring | Full |
