## Error Handling

### Error: "Cannot Determine if Pattern is a Quality Issue"

Cause: Context-dependent — pattern may be valid in specific situations

Solution:
1. Check if the test has a comment explaining the unusual approach
2. Consider the testing layer (unit vs integration vs E2E)
3. If mock-heavy test is for a unit with many dependencies, suggest integration test instead
4. When in doubt, flag as MEDIUM and explain trade-offs

### Error: "Fix Changes Test Behavior"

Cause: Anti-pattern was masking an actual test gap or testing wrong thing

Solution:
1. Identify what the test was originally trying to verify
2. Write the correct assertion for that behavior
3. If original behavior was wrong, note it as a separate finding
4. Preserve what each test covers

### Error: "Suite Has Hundreds of Quality Issues"

Cause: Systemic test quality issues, not individual mistakes

Solution:
1. Fix issues incrementally, focusing on highest severity first
2. Focus on HIGH severity items only (flaky, order-dependent)
3. Recommend adopting TDD going forward to prevent new quality issues
4. Suggest incremental cleanup strategy (fix on touch, not bulk rewrite)
