---
name: feature-validate
description: |
  Run quality gates on implemented feature: tests, lint, type checks, and
  custom validation. Use after /feature-implement completes. Use for "validate
  feature", "run quality gates", "check feature", or "/feature-validate".
  Do NOT use for ad-hoc linting or debugging.
version: 2.0.0
user-invocable: true
command: /feature-validate
allowed-tools:
  - Read
  - Bash
  - Grep
  - Glob
routing:
  triggers:
    - feature validate
    - validate feature
    - run quality gates
    - check feature
    - feature-validate
  pairs_with:
    - feature-implement
    - feature-release
    - verification-before-completion
    - universal-quality-gate
  complexity: Medium
  category: process
---

# Feature Validate Skill

## Purpose

Run comprehensive quality gates on the implemented feature. Phase 4 of the feature lifecycle (design → plan → implement → **validate** → release).

## Operator Context

### Hardcoded Behaviors (Always Apply)
- **CLAUDE.md Compliance**: Read and follow repository CLAUDE.md
- **Implementation Required**: CANNOT validate without implementation artifacts
- **State Management via Script**: All state operations through `python3 scripts/feature-state.py`
- **Show Full Output**: NEVER summarize test results. Show actual command output.
- **All Gates Must Pass**: Cannot proceed to release with any gate failing
- **Existing Quality Gate Integration**: Use our existing quality gate skills (go-pr-quality-gate, python-quality-gate, universal-quality-gate)

### Default Behaviors (ON unless disabled)
- **Auto-detect Language**: Detect project language and run appropriate quality gate
- **Context Loading**: Read L0, L1, and implementation artifact at prime
- **Regression Check**: Verify existing tests still pass

### Optional Behaviors (OFF unless enabled)
- **Security scan**: Run security-focused review agent
- **Performance check**: Run benchmarks against baseline

## What This Skill CAN Do
- Run language-specific quality gates (tests, lint, type checks)
- Verify all planned files were created/modified
- Check for regressions
- Produce validation report

## What This Skill CANNOT Do
- Fix failing tests (route back to feature-implement)
- Skip validation gates
- Approve with failures

## Instructions

### Phase 0: PRIME

1. Verify feature state is `validate` and `implement` is completed.
2. Load implementation artifact from `.feature/state/implement/`.
3. Load L1 validate context.

**Gate**: Implementation artifact loaded. Proceed.

### Phase 1: EXECUTE (Quality Gates)

**Step 1: Language Detection**

Detect project language(s) from file extensions, build files, and implementation artifact.

**Step 2: Run Quality Gates**

For each detected language, run the appropriate quality gate:

| Language | Quality Gate | Command |
|----------|-------------|---------|
| Go | go-pr-quality-gate | `make check` or `go test ./... && go vet ./...` |
| Python | python-quality-gate | `ruff check && pytest && mypy` |
| TypeScript | universal-quality-gate | `npm run typecheck && npm run lint && npm test` |
| Other | universal-quality-gate | Detect and run project-specific checks |

**Step 3: Regression Check**

Run full test suite and compare against pre-implementation baseline:
- New test failures = regression
- Missing tests for new code = coverage gap

**Step 4: Custom Gates**

If the design document specified custom validation criteria, check those too.

**Gate**: All quality gates pass. Proceed.

### Phase 2: VALIDATE (Report)

Produce validation report:

```markdown
# Validation Report: [Feature Name]

## Quality Gates
- [ ] Tests: PASS/FAIL (X/Y passed)
- [ ] Lint: PASS/FAIL (N issues)
- [ ] Type Check: PASS/FAIL
- [ ] Regression: PASS/FAIL

## Coverage
- New files: X
- Modified files: Y
- Test coverage: Z%

## Issues Found
- [Issue 1]: [severity]
- [Issue 2]: [severity]

## Verdict: PASS / NEEDS_FIXES / BLOCK
```

If `NEEDS_FIXES`: suggest running `/feature-implement` with specific fix tasks.
If `BLOCK`: explain blocking issues.

**Gate**: Report produced. Proceed to Checkpoint.

### Phase 3: CHECKPOINT

1. Save validation artifact:
   ```bash
   echo "VALIDATION_REPORT" | python3 scripts/feature-state.py checkpoint FEATURE validate
   ```

2. **Record learnings** — if this phase produced non-obvious insights, record them:
   ```bash
   python3 scripts/learning-db.py record TOPIC KEY "VALUE" --category design
   ```

3. If validation passed, advance:
   ```bash
   python3 scripts/feature-state.py advance FEATURE
   ```

4. Suggest next step:
   ```
   Validation passed. Run /feature-release to merge and release.
   ```

## Error Handling

| Error | Cause | Solution |
|-------|-------|----------|
| Tests fail | Implementation bugs | Route back to /feature-implement with failure details |
| No test framework detected | Project setup incomplete | Report gap, suggest setup |
| Lint failures | Style issues | Auto-fix if trivial, otherwise route back |

## References

- [Verification Checklist](../shared-patterns/verification-checklist.md)
- [Retro Loop](../shared-patterns/retro-loop.md)
- [State Conventions](../_feature-shared/state-conventions.md)
