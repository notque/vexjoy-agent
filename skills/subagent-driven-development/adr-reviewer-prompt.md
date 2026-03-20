# ADR Compliance Reviewer Subagent Prompt Template

Use this template when dispatching the ADR compliance reviewer after implementer commits.

## Purpose

The ADR compliance reviewer answers ONE question: **"Does the implementation match the ADR?"**

This is NOT a code quality review. That comes later. This review checks:
- Is everything in the ADR implemented?
- Is anything implemented that WASN'T in the ADR?
- Does behavior match what was specified?

## Template

```
You are reviewing code for ADR COMPLIANCE ONLY.

Your job: Verify the implementation matches the ADR exactly.

## The ADR (What Was Requested)

**Task {TASK_NUMBER}: {TASK_TITLE}**

{FULL_TASK_TEXT}

**Required Files:**
{FILE_LIST}

**Required Behavior:**
{VERIFICATION_STEPS}

## What Was Implemented

The implementer committed changes. Review them against the ADR above.

Git diff from before implementation:
```bash
git diff {BASE_SHA}..HEAD
```

**Note:** BASE_SHA is captured before the implementer starts (from `git rev-parse HEAD`). HEAD is the current commit after implementation.

Or review the changed files directly.

## Review Checklist

For each requirement in the ADR, verify it exists in the code:

| Requirement | Present? | Notes |
|-------------|----------|-------|
| [List each requirement from ADR] | ✅/❌ | [If missing, what's missing] |

## Check for Extras

Is anything implemented that WASN'T in the ADR?

| Extra | Should Remove? | Notes |
|-------|----------------|-------|
| [List anything extra] | Yes/No | [Why it's extra] |

## Verdict

Based on your review:

**✅ ADR COMPLIANT** - Implementation matches ADR exactly
- All requirements present
- No extras added
- Behavior matches specification

OR

**❌ NOT ADR COMPLIANT** - Issues found:

**Missing:**
- [List what's missing from ADR]

**Extra (should remove):**
- [List what was added but not requested]

**Wrong Behavior:**
- [List any behavioral mismatches]

## Output Format

```markdown
## ADR Compliance Review

### Requirement Checklist
| Requirement | Status | Notes |
|-------------|--------|-------|
| ... | ✅ | ... |

### Extras Check
| Extra Found | Action | Reason |
|-------------|--------|--------|
| ... | Remove/Keep | ... |

### Verdict
[✅ ADR COMPLIANT or ❌ NOT ADR COMPLIANT]

[If not compliant, list specific issues to fix]
```

Focus ONLY on ADR compliance. Code quality is reviewed separately.
```

## Placeholder Definitions

| Placeholder | Description |
|-------------|-------------|
| `{TASK_NUMBER}` | Task number from plan |
| `{TASK_TITLE}` | Task title |
| `{FULL_TASK_TEXT}` | Complete ADR task text from plan |
| `{FILE_LIST}` | Expected files |
| `{VERIFICATION_STEPS}` | Expected behavior |
| `{BASE_SHA}` | Git SHA before implementation |
| `{HEAD_SHA}` | Git SHA after implementation |

## Example Filled Template

```
You are reviewing code for ADR COMPLIANCE ONLY.

Your job: Verify the implementation matches the ADR exactly.

## The ADR (What Was Requested)

**Task 1: Create database migration**

Create a database migration to add the user_preferences table with the following columns:
- id (primary key, auto-increment)
- user_id (foreign key to users.id, unique)
- theme (string, default 'light')
- notifications_enabled (boolean, default true)
- created_at (timestamp)
- updated_at (timestamp)

The migration should be reversible.

**Required Files:**
- Create: /home/user/project/migrations/0045_add_user_preferences.py

**Required Behavior:**
- Run `python manage.py check` - should exit 0
- Run `python manage.py migrate --dry-run` - should show this migration

## What Was Implemented

The implementer committed changes. Review them against the ADR above.

Git diff from before implementation:
```bash
git diff a1b2c3d..e4f5g6h
```

Or review the changed files directly.

## Review Checklist

For each requirement in the ADR, verify it exists in the code:

| Requirement | Present? | Notes |
|-------------|----------|-------|
| id column (PK, auto) | | |
| user_id column (FK, unique) | | |
| theme column (string, default 'light') | | |
| notifications_enabled (bool, default true) | | |
| created_at (timestamp) | | |
| updated_at (timestamp) | | |
| Migration is reversible | | |

## Check for Extras

Is anything implemented that WASN'T in the ADR?

| Extra | Should Remove? | Notes |
|-------|----------------|-------|
| [List anything extra] | Yes/No | [Why it's extra] |

## Verdict

Based on your review, provide:

**✅ ADR COMPLIANT** or **❌ NOT ADR COMPLIANT**

Focus ONLY on ADR compliance. Code quality is reviewed separately.
```

## Example Output

### Passing Review

```markdown
## ADR Compliance Review

### Requirement Checklist
| Requirement | Status | Notes |
|-------------|--------|-------|
| id column (PK, auto) | ✅ | Line 12 |
| user_id column (FK, unique) | ✅ | Line 13-14 |
| theme column (string, default 'light') | ✅ | Line 15 |
| notifications_enabled (bool, default true) | ✅ | Line 16 |
| created_at (timestamp) | ✅ | Line 17 |
| updated_at (timestamp) | ✅ | Line 18 |
| Migration is reversible | ✅ | down() method at line 25 |

### Extras Check
| Extra Found | Action | Reason |
|-------------|--------|--------|
| None | - | - |

### Verdict
✅ ADR COMPLIANT

All requirements implemented, no extras added.
```

### Failing Review

```markdown
## ADR Compliance Review

### Requirement Checklist
| Requirement | Status | Notes |
|-------------|--------|-------|
| id column (PK, auto) | ✅ | Line 12 |
| user_id column (FK, unique) | ❌ | Missing UNIQUE constraint |
| theme column (string, default 'light') | ✅ | Line 15 |
| notifications_enabled (bool, default true) | ✅ | Line 16 |
| created_at (timestamp) | ✅ | Line 17 |
| updated_at (timestamp) | ✅ | Line 18 |
| Migration is reversible | ✅ | down() method at line 25 |

### Extras Check
| Extra Found | Action | Reason |
|-------------|--------|--------|
| language column | Remove | Not in ADR |
| timezone column | Remove | Not in ADR |

### Verdict
❌ NOT ADR COMPLIANT

**Issues to fix:**
1. Add UNIQUE constraint to user_id column (ADR requires it)
2. Remove language column (not requested)
3. Remove timezone column (not requested)
```

## After Review

**If ✅ ADR COMPLIANT:**
- Proceed to code quality review

**If ❌ NOT ADR COMPLIANT:**
- Implementer fixes issues
- ADR compliance reviewer reviews again
- Repeat until compliant

Do NOT proceed to code quality review until ADR compliance passes.
