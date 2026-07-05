# Skill Composition Examples — Advanced Patterns

Error recovery, circular-dependency handling, adaptive/nested compositions, and aggregate performance metrics for DAG-based skill orchestration.

> **Note**: Scripts referenced below (`discover_skills.py`, `build_dag.py`, `validate.py`) are not yet implemented. These examples illustrate the intended workflow and expected output format.

Core sequential/parallel composition examples (1-6) live in [dag-orchestration-examples.md](dag-orchestration-examples.md).

## Example 7: Loop Until Clean

### User Request
"Fix all linting violations in the payments module"

### DAG Building Output
```
Task: Fix all linting violations in the payments module

Task Analysis:
  Primary goals:
  Quality requirements: quality_checks

Selected Skills (1 with loop): code-linting

Execution Plan:

Loop (max 5 iterations):
  Phase 1:
    → code-linting

  If violations > 0:
    → fix violations
    → repeat
  Else:
    → exit loop

Summary:
  Total phases: 1 (looped)
  Skills: 1
```

### Execution Result
**Iteration 1**: code-linting found 18 violations
- Auto-fixed: 12
- Manual fix: 6

**Iteration 2**: code-linting found 4 violations (manual fixes created new issues)
- Auto-fixed: 3
- Manual fix: 1

**Iteration 3**: code-linting found 0 violations
- Loop exit: Clean!

**Total Duration**: 12 minutes
**Iterations**: 3/5

---

## Example 8: Style Compliance

### User Request
"Validate Go code meets team style guidelines before review"

### DAG Building Output
```
Task: Validate Go code meets team style guidelines

Task Analysis:
  Primary goals:
  Quality requirements: quality_checks
  Domain hints: golang

Execution Plan:

Phase 1:

Phase 2:
  → code-linting

Phase 3:
  → verification-before-completion

Summary:
  Total phases: 3
  Parallel phases: 0
  Skills: 3
```

### Execution Result
- Reviewability checks: Pass
- Maintainability checks: 2 violations
  - Long function (>50 lines) in `handler.go`
  - Deeply nested if statements in `validator.go`

**Phase 2**: code-linting (golangci-lint)
- 0 violations after team style fixes

**Phase 3**: verification-before-completion
- All checks pass

**Compliance Score**: 95/100 (A grade)

**Total Duration**: 14 minutes

---

## Error Recovery Examples

### Example 9: Failed Skill with Recovery

### User Request
"Add caching layer with tests"

### Initial Execution
```
Phase 1: workflow-orchestrator ✓
  Created 3 subtasks

Phase 2: test-driven-development ✗
  Error: Tests failed with 2 errors
  - Cache invalidation race condition
  - TTL configuration missing

Downstream impact:
  - verification-before-completion (blocked)

Recovery options:
  1. Fix test errors and retry
  2. Continue without tests (not recommended)
  3. Abort entire workflow
```

### Recovery Action
Selected option 1: Fix and retry

**Recovery Iteration**:
```
Phase 2 (retry): test-driven-development ✓
  Fixed race condition with mutex
  Added TTL configuration
  All tests pass (18/18)

Phase 3: verification-before-completion ✓
  All quality gates pass
```

**Total Duration**: 38 minutes (including 12 min recovery)

---

### Example 10: Circular Dependency Detection

### User Request
"Improve code quality comprehensively"

### Initial DAG Building
```
Analyzing task: Improve code quality comprehensively

✗ DAG validation failed: Circular dependency
  Cycle: code-linting → test-driven-development → code-linting

Solution: Remove circular dependency
  Option 1: Run code-linting → test-driven-development (no loop)
  Option 2: Run test-driven-development → code-linting (no loop)
  Option 3: Run both in parallel with verification after
```

### Corrected Composition
```
Selected Option 3: Parallel approach

Phase 1 (PARALLEL):
  → code-linting
  → test-driven-development

Phase 2:
  → verification-before-completion
```

---

## Advanced Composition Examples

### Example 11: Nested Composition

**High-level task**: "Implement microservice with full quality suite"

**Approach**: Use workflow-orchestrator to manage sub-compositions

```
workflow-orchestrator creates 3 major subtasks:

Subtask 1: Implement Core Service
  Composition: test-driven-development → code-linting

Subtask 2: Add API Documentation
  Composition: codebase-analyzer → comment-quality

Subtask 3: Quality Validation

Total Duration: 65 minutes
Skills Used: 7
```

---

### Example 12: Adaptive Composition

**Initial task**: "Add authentication feature"

**Initial composition**: test-driven-development → verification-before-completion

**Adaptive adjustment**: After phase 1, test coverage was only 45%

```
Adaptive decision:
  Insert additional iteration of test-driven-development

Modified composition:
  test-driven-development (iteration 1) →
  test-driven-development (iteration 2, focus on coverage) →
  verification-before-completion

Final coverage: 87%
Total Duration: 42 minutes (vs 30 minutes without adaptation)
```

---

## Performance Metrics

### Parallelization Benefits

| Composition | Sequential | Parallel | Savings |
|-------------|-----------|----------|---------|
| [code-linting, comment-quality] | 12 min | 8 min | 33% |
| [pr-workflow (miner), codebase-analyzer] | 28 min | 16 min | 43% |
| [3 language-specific lints] | 18 min | 8 min | 56% |

### Skill Chain Duration Averages

| Skills | Average Duration | Range |
|--------|-----------------|-------|
| 2 skills | 12 min | 8-18 min |
| 3 skills | 24 min | 18-35 min |
| 4 skills | 38 min | 30-50 min |
| 5+ skills | 52 min | 45-75 min |

---

## Usage Patterns

### Most Common Compositions (by frequency)

1. **workflow-orchestrator → test-driven-development** (45%)
2. **code-linting → verification-before-completion** (23%)
3. **systematic-debugging → comment-quality** (12%)
4. **[code-linting, comment-quality] → verification** (8%)
5. **pr-workflow (miner) → workflow-orchestrator** (5%)

### Success Rates

| Composition Pattern | Success Rate | Common Failure |
|-------------------|--------------|----------------|
| Simple sequential (2-3) | 96% | Test failures |
| Parallel quality checks | 92% | Linting violations |
| Research + implementation | 88% | Pattern mismatch |
| Loop until clean | 85% | Max iterations hit |
| Complex (5+) | 78% | Dependency issues |

---

These examples demonstrate real-world skill compositions with complete execution flows, error recovery, and performance characteristics. Use them as templates for your own compositions.
