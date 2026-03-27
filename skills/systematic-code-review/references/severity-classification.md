# Severity Classification Rules

**Guiding principle**: When in doubt, classify UP. It's better to require a fix and have the author push back than to let a real issue slip through as "optional."

## BLOCKING (cannot merge without fixing)

These issues MUST be fixed. Never mark these as "needs discussion" or "optional":

| Category | Examples |
|----------|----------|
| **Security vulnerabilities** | Authentication bypass, injection (SQL/XSS/command), data exposure, secrets in code, missing authorization checks |
| **Test failures** | Any failing test, including pre-existing failures touched by the change |
| **Breaking changes** | API breaking without migration, backward incompatible changes without versioning |
| **Missing error handling** | Unhandled errors on network/filesystem/database operations, panics in production paths |
| **Race conditions** | Concurrent access without synchronization, data races |
| **Resource leaks** | Unclosed file handles, database connections, memory leaks in hot paths |
| **Logic errors** | Off-by-one errors, incorrect conditionals, wrong return values |

## SHOULD FIX (merge only if urgent, otherwise fix)

These issues should be fixed unless there's time pressure. Never mark as "suggestion":

| Category | Examples |
|----------|----------|
| **Missing tests** | New code paths without test coverage, untested error conditions |
| **Unhelpful error messages** | Errors that don't include context for debugging (missing IDs, states, inputs) |
| **Pattern violations** | Inconsistent with established codebase patterns (but still functional) |
| **Performance in hot paths** | N+1 queries, unnecessary allocations in loops, missing indexes for frequent queries |
| **Deprecated API usage** | Using APIs marked for removal, outdated patterns with better alternatives |
| **Poor encapsulation** | Exposing internal state unnecessarily, breaking abstraction boundaries |

## SUGGESTIONS (author's choice)

These are genuinely optional - author can reasonably decline:

| Category | Examples |
|----------|----------|
| **Naming preferences** | Variable/function names that are adequate but could be clearer |
| **Comment additions** | Places where a comment would help but code is understandable |
| **Alternative approaches** | Different implementation that isn't clearly better |
| **Style not in CLAUDE.md** | Formatting preferences not codified in project standards |
| **Micro-optimizations** | Performance improvements in cold paths with no measurable impact |

## Classification Decision Tree

```
Is there a security, correctness, or reliability risk?
|- YES -> BLOCKING
|- NO -> Does it violate established patterns or create maintenance burden?
          |- YES -> SHOULD FIX
          |- NO -> Is this purely stylistic or preferential?
                   |- YES -> SUGGESTION (or don't mention)
                   |- NO -> Re-evaluate: probably SHOULD FIX
```

## Common Misclassifications to Avoid

| Issue | Wrong | Correct | Why |
|-------|-------|---------|-----|
| Missing error check on `os.Open()` | SUGGESTION | BLOCKING | Resource leak + potential panic |
| No test for new endpoint | SUGGESTION | SHOULD FIX | Untested code is liability |
| Race condition in cache | NEEDS DISCUSSION | BLOCKING | Data corruption risk |
| Inconsistent naming | BLOCKING | SUGGESTION | No functional impact |
| Missing context in error | SUGGESTION | SHOULD FIX | Debugging nightmare |
| Unused import | BLOCKING | SHOULD FIX | Linter will catch, low impact |
