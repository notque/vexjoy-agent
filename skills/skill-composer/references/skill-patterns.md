# Common Skill Composition Patterns

This document describes proven patterns for composing multiple skills into effective workflows.

## Pattern Catalog

### 1. Feature Development Pipeline

**Pattern**: `workflow-orchestrator → test-driven-development → verification-before-completion`

**When to Use**:
- Adding new features to codebase
- Need structured task breakdown
- Require comprehensive testing
- Want verification before completion

**Example Task**: "Add user authentication feature with tests"

**Execution Flow**:
1. **workflow-orchestrator**: Breaks feature into 2-5 minute subtasks with exact file paths
2. **test-driven-development**: Implements each subtask with RED-GREEN-REFACTOR cycle
3. **verification-before-completion**: Validates tests pass, code quality meets standards

**Expected Duration**: 20-40 minutes depending on feature complexity

**Success Criteria**:
- All subtasks completed
- Tests pass (RED → GREEN achieved)
- Code refactored for quality
- Verification gates passed

---

### 2. Debug and Document

**Pattern**: `systematic-debugging → comment-quality`

**When to Use**:
- Fixing bugs in production code
- Need root cause analysis
- Want proper documentation of fixes
- Prevent temporal references in comments

**Example Task**: "Debug authentication timeout and document the fix"

**Execution Flow**:
1. **systematic-debugging**: 4-phase root cause analysis (Reproduce → Isolate → Identify → Verify)
2. **comment-quality**: Reviews fix comments to ensure they explain WHAT/WHY, not WHEN

**Expected Duration**: 15-30 minutes

**Success Criteria**:
- Bug root cause identified
- Fix verified with tests
- Comments explain logic, not history
- No temporal references ("fixed bug", "TODO")

---

### 3. Parallel Quality Checks

**Pattern**: `[code-linting, comment-quality] → verification-before-completion`

**When to Use**:
- Improving existing code quality
- Pre-commit validation
- Preparing code for review
- Independent quality dimensions

**Example Task**: "Check code quality and documentation before PR"

**Execution Flow**:
1. **Phase 1 (Parallel)**:
   - `code-linting`: Run ruff (Python) or Biome (JS) linters
   - `comment-quality`: Check for temporal references in comments
2. **Phase 2 (Sequential)**:
   - `verification-before-completion`: Ensure all quality gates pass

**Expected Duration**: 5-10 minutes

**Parallelization Benefit**: ~50% time reduction compared to sequential

**Success Criteria**:
- Linting passes (or auto-fixed)
- Comments are timeless
- All verification checks pass

---

### 4. Research-Driven Implementation

**Pattern**: `pr-workflow (miner) → codebase-analyzer → workflow-orchestrator → test-driven-development`

**When to Use**:
- Implementing features in unfamiliar codebase
- Want to learn existing patterns first
- Need coding standards from PR reviews
- Building on established conventions

**Example Task**: "Add rate limiting following existing patterns"

**Execution Flow**:
1. **pr-workflow (miner)**: Mine GitHub PR review comments for tribal knowledge
2. **codebase-analyzer**: Extract implementation patterns from existing code
3. **workflow-orchestrator**: Plan implementation based on learned patterns
4. **test-driven-development**: Implement following discovered conventions

**Expected Duration**: 40-60 minutes

**Success Criteria**:
- Patterns extracted from existing code
- Implementation follows established conventions
- Tests validate behavior
- Code style matches project standards

---

### 5. Language-Specific Quality Gate

**Pattern**: `test-driven-development → (if Go: go-patterns, else: code-linting)`

**When to Use**:
- Multi-language projects
- Language-specific quality requirements
- Different validation tools per language

**Example Task**: "Implement feature with language-appropriate quality checks"

**Execution Flow**:
1. **test-driven-development**: Implement feature with tests
2. **Conditional Branch**:
   - If Go: `go-patterns` (golangci-lint, go test, go build)
   - Else: `code-linting` (ruff for Python, Biome for JS)

**Expected Duration**: 20-35 minutes

**Success Criteria**:
- Feature implemented with tests
- Language-specific linting passes
- Quality gates appropriate to language

---

### 6. Documentation Audit and Enhancement

**Pattern**: `codebase-analyzer → comment-quality → (generate docs)`

**When to Use**:
- Auditing documentation quality
- Preparing for external users
- Improving maintainability
- Removing outdated comments

**Example Task**: "Audit and improve documentation quality"

**Execution Flow**:
1. **codebase-analyzer**: Analyze code structure and patterns
2. **comment-quality**: Identify temporal references and poor documentation
3. **Generate docs**: Create/update documentation based on findings

**Expected Duration**: 25-40 minutes

**Success Criteria**:
- Code structure documented
- Temporal references removed
- Comments explain WHAT/WHY
- Documentation reflects current state

---

### 7. Comprehensive Quality Gate

**Pattern**: `test-driven-development → (language-specific-quality-gate) → verification-before-completion`

**When to Use**:
- Need comprehensive language-specific validation
- Running multiple quality tools in one step
- Want automated language detection for multi-language projects

**Example Task**: "Implement feature with comprehensive quality checks"

**Execution Flow**:
1. **test-driven-development**: Implement with RED-GREEN-REFACTOR
2. **Language-specific gate**:
   - Go projects: `go-patterns` (golangci-lint, tests, race detector, build)
   - Python projects: `python-quality-gate` (ruff, pytest, mypy, bandit)
   - Multi-language: `universal-quality-gate` (auto-detect and run appropriate tools)
3. **verification-before-completion**: Final validation

**Expected Duration**: 20-35 minutes

**Success Criteria**:
- All tests pass with good coverage
- Language-specific linting passes
- No security issues detected
- Type checking passes (where applicable)
- Code ready for production

---

### 8. Loop Until Clean

**Pattern**: `code-linting → (if violations: fix-violations → code-linting, else: done)`

**When to Use**:
- Iteratively fixing linting violations
- Auto-fix not sufficient alone
- Want guarantee of clean code

**Example Task**: "Fix all linting violations in module"

**Execution Flow**:
1. **code-linting**: Identify violations
2. **Loop Decision**:
   - If violations > 0: Fix violations and re-lint
   - Else: Exit loop
3. **Maximum iterations**: 5 (prevent infinite loops)

**Expected Duration**: 5-20 minutes depending on violations

**Success Criteria**:
- Zero linting violations
- Code follows style guidelines
- Loop completed in < 5 iterations

---

## Composition Guidelines

### Sequential vs Parallel Decision Tree

```
Can skills run independently?
│
├─ YES → Consider parallel execution
│   ├─ Do they share resources?
│   │   ├─ YES → Sequential (avoid conflicts)
│   │   └─ NO → Parallel (maximize speed)
│   └─ Is output needed by another skill?
│       ├─ YES → Sequential (dependency)
│       └─ NO → Parallel
│
└─ NO → Sequential execution required
    └─ What's the dependency order?
        └─ Use topological sort
```

### Conditional Execution Guidelines

**When to use conditionals**:
- Language-specific tooling (Go vs Python vs JS)
- Error recovery paths (if fails, try alternative)
- Optional enhancements (if time permits, add feature)
- Environment-specific (if production, extra validation)

**When NOT to use conditionals**:
- Core workflow steps (always run)
- Simple linear sequences (just chain them)
- Overly complex branching (split into separate compositions)

### Loop Composition Guidelines

**Safe loop patterns**:
```
loop until clean:
  - linting → fix → re-lint
  - test → fix failures → re-test
  - validate → improve → re-validate
```

**Required safeguards**:
- **Maximum iterations**: Always set (typically 3-5)
- **Progress check**: Ensure each iteration improves (fewer violations, fewer failures)
- **Exit condition**: Clear definition of "done"
- **Timeout**: Overall time limit for loop

**Avoid**:
- Infinite loops (always set max iterations)
- No progress detection (could loop forever)
- Complex multi-skill loops (too hard to debug)

---

## Anti-Patterns

### Anti-Pattern 1: Over-Composition
**Problem**: Chaining too many skills (6+) in single workflow
**Solution**: Break into multiple compositions or use workflow-orchestrator to manage complexity

### Anti-Pattern 2: Circular Dependencies
**Problem**: Skill A depends on B, B depends on C, C depends on A
**Solution**: Redesign to remove cycles, or split into independent workflows

### Anti-Pattern 3: False Parallelism
**Problem**: Running skills "in parallel" that actually share resources
**Solution**: Identify resource conflicts, make sequential

### Anti-Pattern 4: Missing Verification
**Problem**: Implementing features without verification step
**Solution**: Always end with verification-before-completion or equivalent

### Anti-Pattern 5: Premature Optimization
**Problem**: Forcing parallelism where sequential is clearer
**Solution**: Start sequential, parallelize only if bottleneck

---

## Pattern Selection Guide

| Task Type | Recommended Pattern | Duration | Complexity |
|-----------|---------------------|----------|------------|
| Add feature | Feature Development Pipeline | 20-40 min | Medium |
| Fix bug | Debug and Document | 15-30 min | Low |
| Quality check | Parallel Quality Checks | 5-10 min | Low |
| Learn codebase | Research-Driven Implementation | 40-60 min | High |
| Multi-language | Language-Specific Quality Gate | 20-35 min | Medium |
| Doc audit | Documentation Audit | 25-40 min | Medium |
| Style enforcement | Style Compliance | 10-15 min | Low |
| Fix violations | Loop Until Clean | 5-20 min | Low |

---

## Advanced Techniques

### Pattern Composition

Combine patterns for complex workflows:

```
Research-Driven Implementation + Style Compliance:
  pr-workflow (miner) → codebase-analyzer → workflow-orchestrator →
  verification-before-completion
```

### Adaptive Composition

Modify execution based on intermediate results:

```
Initial: test-driven-development
If tests reveal complexity: insert systematic-debugging before continue
If code quality low: insert code-linting after tests
```

### Nested Composition

Use workflow-orchestrator to manage sub-compositions:

```
workflow-orchestrator:
  Subtask 1: Feature Development Pipeline
  Subtask 2: Parallel Quality Checks
  Subtask 3: Documentation Audit
```

---

## Performance Optimization

### Parallelization Strategies

**Maximum Benefit**:
- Independent code analysis (linting + documentation)
- Multiple test suites (unit + integration)
- Different quality dimensions (style + security)

**Overhead Considerations**:
- Skill invocation: ~2-3 seconds per skill
- Context passing: ~0.5-1 second per transition
- Parallel coordination: ~10% overhead

**When to Parallelize**:
- Skills take > 30 seconds each
- No shared resource conflicts
- Independent outputs
- 2-4 skills in parallel (sweet spot)

**When to Stay Sequential**:
- Skills take < 10 seconds each
- Output needed by next skill
- Shared resource access
- Complex error recovery needed

---

## Troubleshooting Compositions

### Common Issues

**Issue**: "Skills selected don't match task"
**Cause**: Task analysis failed to identify goals
**Fix**: Make task description more explicit about goals

**Issue**: "Circular dependency detected"
**Cause**: Skills reference each other cyclically
**Fix**: Remove one dependency or split into separate compositions

**Issue**: "Skill outputs incompatible"
**Cause**: Output format doesn't match next skill's input
**Fix**: Add transformation step or choose different skills

**Issue**: "Parallel execution slower than expected"
**Cause**: Resource contention or coordination overhead
**Fix**: Make sequential or reduce parallel skill count

**Issue**: "Loop never terminates"
**Cause**: Exit condition never met or max iterations too high
**Fix**: Lower max iterations or fix exit condition logic

---

This pattern catalog provides proven compositions for common development workflows. Use these as starting points and adapt to your specific needs.
