# Anti-Rationalization: Code Review

Review-specific patterns to prevent rationalized incomplete reviews.

## Base Patterns

See [anti-rationalization-core.md](./anti-rationalization-core.md) for universal patterns.

## Review-Specific Rationalizations

| Rationalization Attempt | Why It's Wrong | Required Action |
|------------------------|----------------|-----------------|
| "Author explained the logic" | Explanation ≠ Correctness | **Verify the code itself** |
| "Tests pass, must be fine" | Tests can be incomplete | **Review test coverage too** |
| "Small PR, quick review" | Small changes cause big bugs | **Full review regardless of size** |
| "Trusted author" | Everyone makes mistakes | **Same rigor for all authors** |
| "Just a refactor" | Refactors change behavior subtly | **Verify behavior preserved** |
| "Config change only" | Config affects runtime | **Review impact** |
| "Documentation change" | Docs must match code | **Verify accuracy** |
| "Already reviewed similar code" | Similar ≠ Same | **Review this specific code** |
| "Time pressure from author" | Quality > Speed | **Complete review** |
| "Nitpicks aren't worth it" | Small issues compound | **Report all findings** |

## Coverage Completeness Check

Before approving, verify you reviewed:

| Area | Checked? | Notes |
|------|----------|-------|
| Logic correctness | [ ] | Does code do what it should? |
| Edge cases | [ ] | Nulls, empty, boundaries? |
| Error handling | [ ] | All error paths covered? |
| Security | [ ] | Injection, auth, validation? |
| Performance | [ ] | O(n) concerns, queries, loops? |
| Naming | [ ] | Clear, accurate names? |
| Tests | [ ] | Adequate coverage? |
| Documentation | [ ] | Updated if behavior changed? |

## Severity Classification Honesty

Don't downgrade severity to avoid conflict:

| You Might Think | Actual Severity | Why |
|-----------------|-----------------|-----|
| "Minor issue, LOW" | Check if it could cause bugs | Logic issues are HIGH |
| "Style preference, skip" | Check if it affects readability | Readability is MEDIUM |
| "Author will be upset" | Severity is objective | Report truthfully |
| "Not my area of expertise" | Note uncertainty | "Potential issue, please verify" |

## Reviewer Boundaries

Reviewers REPORT, they do not FIX:

| Reviewer CAN | Reviewer CANNOT |
|--------------|-----------------|
| Read all files | Use Edit tool |
| Run read-only commands | Modify code |
| Report findings with file:line | Push commits |
| Recommend fixes with examples | Apply fixes directly |
| Classify severity | Dismiss findings to "help" author |

## Re-Review Protocol

After author makes changes:

1. Re-review ALL changed files (not just "addressed" comments)
2. Verify fixes actually fix the issues
3. Check for regressions from fixes
4. Don't assume "marked resolved" means "actually resolved"
