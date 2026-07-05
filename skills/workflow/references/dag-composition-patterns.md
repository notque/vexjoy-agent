# Composition Patterns Reference

Proven patterns for composing multiple skills into effective workflows. This file is referenced by the skill-composer SKILL.md.

## Pattern Catalog

### Pattern 1: Feature Development Pipeline

```
workflow-orchestrator -> test-driven-development -> verification-before-completion
```

**When to use**: Adding new features with structured breakdown, comprehensive tests, and verification gates.

**Flow**:
1. workflow-orchestrator: Break feature into 2-5 minute subtasks with exact file paths
2. test-driven-development: Implement each subtask with RED-GREEN-REFACTOR
3. verification-before-completion: Validate tests pass, code quality meets standards

**Duration**: 20-40 minutes

---

### Pattern 2: Debug and Document

```
systematic-debugging -> comment-quality
```

**When to use**: Fixing bugs that need root cause analysis and proper documentation of the fix.

**Flow**:
1. systematic-debugging: 4-phase root cause analysis (Reproduce -> Isolate -> Identify -> Verify)
2. comment-quality: Review fix comments to ensure they explain WHAT/WHY, not WHEN

**Duration**: 15-30 minutes

---

### Pattern 3: Parallel Quality Checks

```
[code-linting, comment-quality] -> verification-before-completion
```

**When to use**: Pre-commit validation, code review preparation, or independent quality checks.

**Flow**:
1. Phase 1 (Parallel): code-linting + comment-quality (independent, no shared resources)
2. Phase 2 (Sequential): verification-before-completion merges results

**Duration**: 5-10 minutes (vs 12 minutes sequential)

---

### Pattern 4: Research-Driven Implementation

```
[pr-workflow (miner), codebase-analyzer] -> workflow-orchestrator -> test-driven-development
```

**When to use**: Implementing features in unfamiliar codebases where existing patterns should be followed.

**Flow**:
1. Phase 1 (Parallel): pr-workflow (miner) + codebase-analyzer discover conventions
2. Phase 2: workflow-orchestrator plans implementation based on learned patterns
3. Phase 3: test-driven-development implements following discovered conventions

**Duration**: 40-60 minutes

---

### Pattern 5: Language-Specific Quality Gate

```
test-driven-development -> (if Go: go-patterns, else: code-linting) -> verification-before-completion
```

**When to use**: Projects requiring language-appropriate quality validation tools.

**Conditional branches**:
- Go: go-patterns (golangci-lint, go test -race, go build)
- Python: python-quality-gate (ruff, pytest, mypy, bandit)
- Multi-language: universal-quality-gate (auto-detect)

**Duration**: 20-35 minutes

---

### Pattern 6: Loop Until Clean

```
code-linting -> (if violations > 0: fix -> re-lint, else: done) [max 5 iterations]
```

**When to use**: Iteratively fixing linting violations where auto-fix is insufficient.

**Required safeguards**:
- Maximum iterations: 3-5
- Progress check: Fewer violations each iteration
- Clear exit condition: Zero violations

**Duration**: 5-20 minutes

---

## Sequential vs Parallel Decision

```
Can skills run independently?
  YES -> Do they share resources (files, DB, network)?
    YES -> Sequential (avoid conflicts)
    NO  -> Parallel (maximize speed)
  NO  -> Sequential (dependency chain)
```

## Parallelization Benefits

| Composition | Sequential | Parallel | Savings |
|-------------|-----------|----------|---------|
| [code-linting, comment-quality] | 12 min | 8 min | 33% |
| [pr-workflow (miner), codebase-analyzer] | 28 min | 16 min | 43% |
| [3 language-specific lints] | 18 min | 8 min | 56% |

## Chain Length Guidelines

| Length | Best For | Duration | Risk |
|--------|----------|----------|------|
| 2-3 skills | Simple tasks, focused workflows | 5-15 min | Low |
| 4-5 skills | Feature development, quality enforcement | 20-40 min | Medium |
| 6+ skills | AVOID: Break into sub-compositions | 40-60+ min | High |

When chain length exceeds 5, use workflow-orchestrator to manage sub-compositions rather than creating a single long chain.

## Conditional Execution

**Use conditionals for**:
- Language-specific tooling (Go vs Python vs JS)
- Error recovery paths (if fails, try alternative)
- Environment-specific checks (production vs development)

**Avoid conditionals for**:
- Core workflow steps (always run these)
- Simple linear sequences (just chain them)
- Overly complex branching (split into separate compositions)

## Advanced Techniques

### Nested Composition
Use workflow-orchestrator to manage sub-compositions:
```
workflow-orchestrator:
  Subtask 1: Feature Development Pipeline
  Subtask 2: Parallel Quality Checks
  Subtask 3: Documentation Audit
```

### Adaptive Composition
Modify execution based on intermediate results:
```
test-driven-development
IF test_coverage < 80%: insert additional TDD pass
CONTINUE verification-before-completion
```

### Skill Parameter Binding
Pass parameters between skills:
```
skill: test-driven-development
inputs:
  feature_description: ${workflow-orchestrator.subtasks[0].description}
  file_path: ${workflow-orchestrator.subtasks[0].file_path}
```
