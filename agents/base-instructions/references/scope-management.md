# Scope Management: Over-Engineering Anti-Patterns

> **Scope**: Detecting and avoiding scope creep, premature abstraction, and unrequested
> additions in code changes. Covers code-level signals only; does not cover communication style
> (see `communication-anti-patterns.md`) or verification shortcuts (see anti-rationalization).
> **Version range**: all versions, language-agnostic
> **Generated**: 2026-05-10

---

## Overview

Agents operating in "be maximally helpful" mode drift toward adding unrequested features,
extracting premature abstractions, and introducing error handling for scenarios that cannot
occur. Each addition expands surface area, slows review, and adds maintenance burden — even
when individually well-intentioned. The constraint: do exactly what was asked, no more.

---

## Pattern Table: Scope Creep Signals

| Signal | Symptom | Correct Scope |
|--------|---------|---------------|
| New helper extracted from 2 call sites | Premature DRY | Leave duplicate; abstract at 3+ identical sites |
| Error handling for impossible inputs | Defensive over-coding | Trust caller contracts; validate only at system boundaries |
| New config flag "for flexibility" | Feature flag creep | Implement exactly the requested behavior; no flags |
| Backward compat shim for removed symbol | Cleanup pollution | Delete cleanly; callers own their migration |
| New test file for untouched module | Coverage scope creep | Test only what changed |
| Docstring/comment rewrite on untouched code | Cleanup beyond scope | Leave untouched files untouched |
| New interface for single concrete type | Interface-for-future | Implement the concrete type; don't extract interface |
| Utility function for one-time operation | Library thinking | Inline the operation; don't generalize |

---

## Pattern Catalog: Detection and Fixes

### Premature Abstraction (Helper Extracted from ≤ 2 Call Sites)

**Detection**:
```bash
# Find functions called only once in the codebase
rg "def (\w+)" --only-matching -r src/ | sort | uniq -c | sort -n | head -20
# Go: find single-use private helpers
rg "^func [a-z]\w+" --type go | awk -F: '{print $2}' | sort | uniq -c | sort -n | head -20
```

**Signal**:
```python
# BAD: extracted from one call site
def _build_user_display_name(first: str, last: str) -> str:
    return f"{first} {last}".strip()

# Used once:
display = _build_user_display_name(user.first, user.last)
```

**Why it matters**: A one-site helper adds indirection without reducing duplication.
The next reader must navigate to the helper definition to understand a trivial operation.
At two sites it's still marginal — the standard is three identical sites before extraction.

**Preferred action**:
```python
# GOOD: inline the operation
display = f"{user.first} {user.last}".strip()
```

---

### Error Handling for Impossible Scenarios

**Detection**:
```bash
# Find nil/null checks immediately after guaranteed-non-nil returns
rg "if \w+ == nil \{" --type go -A 3
# Find impossible type assertion guards
rg "if \w+, ok := \w+\.(\w+); !ok" --type go
# Python: unreachable else branches after exhaustive match
rg "else:\s*raise NotImplementedError" --type py
```

**Signal**:
```go
// BAD: cfg is always non-nil (NewConfig never returns nil)
cfg := NewConfig()
if cfg == nil {
    return fmt.Errorf("config is nil")
}
```

**Why it matters**: Adds dead code that confuses readers into thinking the nil case
is reachable. If it were, the code would never have worked. Dead branches also prevent
the compiler from flagging when the contract actually changes.

**Preferred action**:
```go
// GOOD: trust the contract
cfg := NewConfig()
cfg.Apply(opts)
```

**Version note**: Go 1.18+ generics can make nil-safety contracts explicit at the
type level; if the team has adopted generics, prefer typed constraints over runtime guards.

---

### Backward Compatibility Shims for Removed Code

**Detection**:
```bash
# Find type aliases and re-exports that exist only for compat
grep -rn "^type \w\+ = \w\+" --include="*.go" .
grep -rn "^var \w\+ = \w\+" --include="*.go" . | grep -v "test"
# Python: deprecated re-exports
grep -rn "^from .* import .* as " --include="*.py" . | grep -i "compat\|legacy\|deprecated"
# TypeScript: barrel re-exports of removed symbols
grep -rn "export { .* } from" --include="*.ts" . | grep -i "deprecated\|compat"
```

**Signal**:
```go
// BAD: compat shim after renaming UserManager → AccountManager
type UserManager = AccountManager  // "kept for backward compatibility"
var NewUserManager = NewAccountManager
```

**Why it matters**: "Backward compat" shims signal the agent rewrote more than requested
and then tried to soften the blast radius. If the task was to rename one symbol, update
all call sites. Don't leave shims — they silently delay callers from migrating and rot.

**Preferred action**: Update all call sites. Delete the old name. If callers in other
repos depend on it, that's a deployment concern, not a code concern.

---

### Feature Flags for Single-Implementation Behavior

**Detection**:
```bash
grep -rn "if.*flag\|if.*feature\|if.*enabled\|if.*config\." --include="*.go" . | \
  grep -v "_test.go" | head -20
grep -rn "feature_flag\|FEATURE_\|FLAGS\[" --include="*.py" -r . | grep -v test
```

**Signal**:
```python
# BAD: flag added "for flexibility" when only one behavior was requested
def process_order(order, *, use_new_pipeline: bool = False):
    if use_new_pipeline:
        return _new_pipeline(order)
    return _old_pipeline(order)
```

**Why it matters**: A flag that doesn't exist in any caller is dead code from day one.
It forces every future reader to determine which branch is active. It also signals the
agent was uncertain about the change and hedged rather than committing.

**Preferred action**: Implement the requested behavior directly. If the old behavior
needs to coexist during a transition, that's a deployment decision — model it as a
versioned endpoint or a migration script, not a runtime flag.

---

### New Tests for Untouched Modules

**Detection**:
```bash
# Files touched in the current branch
git diff --name-only origin/main...HEAD | grep -v test
# Test files added that test untouched modules
git diff --name-only origin/main...HEAD | grep test
```

**Why it matters**: Adding tests for code not in scope of the current task expands review
surface, risks introducing test-specific bugs, and can mask the actual change in the diff.
Test only what changed.

**Preferred action**: Scope tests to the changed code. If untouched code is visibly
under-tested, note it in a comment or open a follow-up issue — don't fix it inline.

---

### Docstring/Comment Rewrites on Untouched Code

**Detection**:
```bash
# Lines changed that are pure comment/docstring changes in unrelated files
git diff origin/main...HEAD -- '*.py' | grep "^+" | grep -E "^[+]#|^[+]\"\"\"|^[+]//|^[+]\s+#" | \
  grep -v "^+++" | head -20
```

**Why it matters**: Comment-only changes in files not part of the task clutter the diff
and trigger unnecessary reviewer attention on irrelevant sections.

**Preferred action**: Leave untouched files untouched. If a comment is genuinely wrong,
file a separate PR.

---

## Error-Fix Mappings

| Over-Engineering Signal | Root Cause | Correct Response |
|------------------------|------------|-----------------|
| New helper with one call site | Anticipating future reuse | Inline; extract when 3+ identical sites exist |
| `if x == nil` after guaranteed-non-nil | Defensive coding | Trust the contract; remove the guard |
| `type OldName = NewName` after rename | Softening blast radius | Update all call sites; delete old name |
| `bool` flag parameter with single behavioral path | Hedging on the change | Commit to one implementation |
| New test file for unchanged module | Coverage guilt | Scope to changed code only |
| Rewritten comments in unrelated file | Cleanup impulse | Leave untouched; file separate PR if needed |
| New interface for one concrete implementation | "Good design" overreach | Implement the concrete type; skip the interface |

---

## Scope Verification Checklist

Before submitting changes, verify:

```bash
# What files changed?
git diff --name-only origin/main...HEAD

# Are all changed files directly related to the task?
# If not: revert the unrelated changes.

# Did any new files appear that weren't requested?
git diff --name-only --diff-filter=A origin/main...HEAD

# Did line count grow significantly beyond the task description?
git diff --stat origin/main...HEAD
```

If a file changed but wasn't part of the stated task: revert it or open a separate PR.

---

## Detection Commands Reference

```bash
# Premature abstraction: single-use helpers
rg "def (\w+)" --only-matching -r src/ | sort | uniq -c | sort -n | head -20

# Impossible nil guards (Go)
rg "if \w+ == nil \{" --type go -A 3

# Compat shims (Go type aliases)
grep -rn "^type \w\+ = " --include="*.go" .

# Feature flags (Python)
grep -rn "feature_flag\|FEATURE_\|if.*enabled" --include="*.py" -r . | grep -v test

# Changed files not in task scope
git diff --name-only origin/main...HEAD

# New files added this branch
git diff --name-only --diff-filter=A origin/main...HEAD
```

---

## See Also

- `communication-anti-patterns.md` — output prose anti-patterns
- `skills/shared-patterns/anti-rationalization-core.md` — verification and completion protocols
- `agents/base-instructions.md` — over-engineering prevention rules (authoritative source)
