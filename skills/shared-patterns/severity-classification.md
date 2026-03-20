# Severity Classification

Standardized definitions for issue severity levels.

## Severity Levels

| Severity | Definition | Response | Color |
|----------|------------|----------|-------|
| **CRITICAL** | Security vulnerability, data loss risk, system down | Immediate - stop other work | Red |
| **HIGH** | Significant bug, broken feature, major performance issue | Same session - before completion | Orange |
| **MEDIUM** | Quality issue, suboptimal pattern, minor bug | Before merge - should address | Yellow |
| **LOW** | Style, suggestion, nice-to-have improvement | Optional - consider addressing | Blue |

## CRITICAL Criteria

Issue is CRITICAL if ANY of these apply:

| Criterion | Examples |
|-----------|----------|
| Security vulnerability | SQL injection, auth bypass, XSS, SSRF |
| Data loss possible | Unhandled delete, missing transaction |
| System unavailable | Crash on startup, infinite loop, resource exhaustion |
| Privacy breach | PII exposure, log leakage |
| Compliance violation | Regulatory requirement failure |

**Response:** Fix immediately. Do not merge with CRITICAL issues.

## HIGH Criteria

Issue is HIGH if ANY of these apply:

| Criterion | Examples |
|-----------|----------|
| Feature broken | Core functionality doesn't work |
| Significant bug | Wrong calculation, missing validation |
| Performance regression | 10x slower, memory leak |
| Race condition | Data corruption possible |
| Error handling missing | Unhandled exceptions in critical path |

**Response:** Address before marking complete.

## MEDIUM Criteria

Issue is MEDIUM if:

| Criterion | Examples |
|-----------|----------|
| Code quality issue | Missing error handling in non-critical path |
| Suboptimal pattern | Working but not ideal approach |
| Minor bug | Edge case not handled |
| Test coverage gap | Untested error path |
| Documentation mismatch | Docs don't match behavior |

**Response:** Should address. Acceptable to note and track if time-constrained.

## LOW Criteria

Issue is LOW if:

| Criterion | Examples |
|-----------|----------|
| Style preference | Naming could be clearer |
| Minor improvement | Could be slightly more efficient |
| Nice-to-have | Additional logging would help |
| Documentation enhancement | Example would be helpful |

**Response:** Consider addressing. OK to skip with justification.

## Classification Decision Tree

```
Is there a security risk?
├─ Yes → CRITICAL
└─ No → Can users lose data?
         ├─ Yes → CRITICAL
         └─ No → Is a feature broken?
                  ├─ Yes → HIGH
                  └─ No → Is behavior wrong?
                           ├─ Yes → HIGH
                           └─ No → Is it a code quality issue?
                                    ├─ Yes → MEDIUM
                                    └─ No → LOW
```

## Common Misclassifications

### Under-Classification (Don't Do This)

| Finding | Wrong | Correct | Why |
|---------|-------|---------|-----|
| SQL with user input | MEDIUM | CRITICAL | Security |
| Missing null check | LOW | HIGH | Can crash |
| No rate limiting | LOW | HIGH | DoS possible |
| Hardcoded secret | MEDIUM | CRITICAL | Security |

### Over-Classification (Also Wrong)

| Finding | Wrong | Correct | Why |
|---------|-------|---------|-----|
| Variable naming | HIGH | LOW | Style only |
| Missing comment | MEDIUM | LOW | Nice-to-have |
| Extra logging | HIGH | LOW | Not harmful |
| Formatting | MEDIUM | LOW | Cosmetic |

## Aggregation Rules

When reporting multiple findings:

```markdown
## Summary

| Severity | Count | Action Required |
|----------|-------|-----------------|
| CRITICAL | 0 | None |
| HIGH | 2 | Must fix before merge |
| MEDIUM | 5 | Should address |
| LOW | 3 | Optional |

**Recommendation:** [Based on findings]
```

## Escalation

When unsure about severity:

1. Default to HIGHER severity (safer)
2. Note uncertainty: "Potential CRITICAL - please verify"
3. Explain reasoning
4. Let reviewer/author make final call

## Extraction Severity Escalation

When a diff extracts inline code into a named helper function, **re-evaluate all defensive guards** that were previously rated LOW because "the caller handles it."

| Before extraction | After extraction | Action |
|---|---|---|
| Inline code, 1 caller | Named function, N potential callers | Escalate LOW → MEDIUM for any guard relying on caller discipline |
| "validateX catches it upstream" | Function callable without validateX | The guard must be self-contained |
| Missing defensive check rated LOW | Same check on reusable function | Rate as MEDIUM — "fix in this PR" |

**The rule**: inline code has exactly 1 caller (the enclosing function). An extracted helper has N potential callers. Guards that were safe as inline code may be unsafe as reusable functions.

**Trigger**: any diff that creates a new named function from code previously inline in another function.

*Graduated from hermez PR #338: empty-string guard rated LOW 3 times, then Copilot caught it post-extraction as the correct MEDIUM finding. The 2-line fix was trivial but severity classification delayed it.*
