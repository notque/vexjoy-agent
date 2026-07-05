# Skill Composition Examples

Real-world examples of skill compositions with complete execution flows.

> **Note**: Scripts referenced below (`discover_skills.py`, `build_dag.py`, `validate.py`) are not yet implemented. These examples illustrate the intended workflow and expected output format.

For error-recovery patterns, adaptive/nested compositions, and aggregate performance metrics, see [dag-orchestration-advanced.md](dag-orchestration-advanced.md).

## Example 1: Feature Development with Tests

### User Request
"Add rate limiting middleware to the API server with comprehensive tests"

### Skill Discovery Output
```bash
$ python3 ~/.claude/scripts/discover_skills.py \
    --skills-dir ./skills \
    --output /tmp/skill-index.json
```

```
Discovering skills in ./skills...
Found 18 potential skills
  ✓ workflow-orchestrator
  ✓ test-driven-development
  ✓ verification-before-completion
  ✓ comment-quality
  ✓ code-linting
  ... (13 more skills)

Building skill index...
Index written to: /tmp/skill-index.json

============================================================
SKILL INDEX SUMMARY
============================================================
Total skills: 18

Categories:
  workflow: 2
  testing: 2
  quality: 5
  documentation: 2
  code-analysis: 3
  debugging: 2
  other: 2

Skills with dependencies: 4
============================================================
```

### DAG Building Output
```bash
$ python3 ~/.claude/scripts/build_dag.py \
    --task "Add rate limiting middleware with comprehensive tests" \
    --skill-index /tmp/skill-index.json \
    --output /tmp/execution-dag.json
```

```
Analyzing task: Add rate limiting middleware with comprehensive tests

DAG written to: /tmp/execution-dag.json

============================================================
EXECUTION DAG
============================================================

Task: Add rate limiting middleware with comprehensive tests

Task Analysis:
  Primary goals: implementation
  Quality requirements: testing

Selected Skills (3): workflow-orchestrator, test-driven-development, verification-before-completion

Execution Plan:

Phase 1:
  → workflow-orchestrator

Phase 2:
  → test-driven-development

Phase 3:
  → verification-before-completion

Summary:
  Total phases: 3
  Parallel phases: 0
  Skills: 3
============================================================
```

### Validation Output
```bash
$ python3 ~/.claude/scripts/validate.py \
    --dag /tmp/execution-dag.json \
    --skill-index /tmp/skill-index.json
```

```
============================================================
SKILL COMPOSITION VALIDATION
============================================================

DAG Structure:
------------------------------------------------------------
  ✓ PASS - DAG has required field: task
  ✓ PASS - DAG has required field: phases
  ✓ PASS - DAG has required field: dependencies
  ✓ PASS - DAG has required field: execution_order
  ✓ PASS - Phases is a list
  ✓ PASS - Phase 1 numbered correctly
  ✓ PASS - Phase 2 numbered correctly
  ✓ PASS - Phase 3 numbered correctly

Acyclic Check:
------------------------------------------------------------
  ✓ PASS - DAG is acyclic (no circular dependencies)

Skill Existence:
------------------------------------------------------------
  ✓ PASS - Skill exists: workflow-orchestrator
  ✓ PASS - Skill exists: test-driven-development
  ✓ PASS - Skill exists: verification-before-completion

I/O Compatibility:
------------------------------------------------------------
  ✓ PASS - Compatibility: workflow-orchestrator → test-driven-development
  ✓ PASS - Compatibility: test-driven-development → verification-before-completion

Topological Ordering:
------------------------------------------------------------
  ✓ PASS - Dependency ordering: workflow-orchestrator → test-driven-development
  ✓ PASS - Dependency ordering: test-driven-development → verification-before-completion
  ✓ PASS - Topological ordering valid

============================================================
SUMMARY: 17/17 checks passed
         Composition valid - ready for execution
============================================================
```

### Execution Result
**Phase 1**: workflow-orchestrator created 4 subtasks:
1. Create rate limiter interface in `middleware/ratelimit.go`
2. Implement token bucket algorithm in `middleware/tokenbucket.go`
3. Add middleware registration in `server/server.go`
4. Add configuration in `config/config.go`

**Phase 2**: test-driven-development implemented each subtask:
- RED: Wrote failing tests for each subtask
- GREEN: Implemented minimum code to pass
- REFACTOR: Improved code quality

**Phase 3**: verification-before-completion validated:
- All tests pass (24/24)
- Code coverage: 94%
- Linting: 0 violations

**Total Duration**: 32 minutes

---

## Example 2: Debug with Documentation

### User Request
"Fix the authentication timeout issue and properly document the root cause"

### DAG Building Output
```
Task: Fix the authentication timeout issue and properly document the root cause

Task Analysis:
  Primary goals: debugging, documentation
  Quality requirements:

Selected Skills (2): systematic-debugging, comment-quality

Execution Plan:

Phase 1:
  → systematic-debugging

Phase 2:
  → comment-quality

Summary:
  Total phases: 2
  Parallel phases: 0
  Skills: 2
```

### Execution Result
**Phase 1**: systematic-debugging:
1. **Reproduce**: Created minimal test case triggering timeout
2. **Isolate**: Identified token validation as bottleneck
3. **Identify**: Found blocking HTTP call in hot path
4. **Verify**: Confirmed fix resolves timeout

**Phase 2**: comment-quality reviewed fix comments:
- Removed: "Fixed timeout bug on 2025-11-30"
- Replaced with: "Token validation uses async HTTP call to prevent blocking"
- Validated: Comments explain WHAT/WHY, not WHEN

**Total Duration**: 18 minutes

---

## Example 3: Parallel Quality Checks

### User Request
"Check code quality and documentation before creating PR"

### DAG Building Output
```
Task: Check code quality and documentation before creating PR

Task Analysis:
  Primary goals:
  Quality requirements: quality_checks

Selected Skills (3): code-linting, comment-quality, verification-before-completion

Execution Plan:

Phase 1 (PARALLEL):
  → code-linting
  → comment-quality

Phase 2:
  → verification-before-completion

Summary:
  Total phases: 2
  Parallel phases: 1
  Skills: 3
```

### Execution Result
**Phase 1 (Parallel)**:
- `code-linting` (6 seconds): Found 3 violations, auto-fixed 2, manual fix needed for 1
- `comment-quality` (4 seconds): Found 2 temporal references ("TODO: fix later", "Bug fixed yesterday")

**Phase 2**:
- `verification-before-completion`: All checks pass after manual fixes

**Total Duration**: 8 minutes (vs 12 minutes sequential = 33% time savings)

---

## Example 4: Research-Driven Implementation

### User Request
"Implement pagination following existing patterns in the codebase"

### DAG Building Output
```
Task: Implement pagination following existing patterns in the codebase

Task Analysis:
  Primary goals: implementation, analysis
  Quality requirements:

Selected Skills (4): pr-workflow (miner), codebase-analyzer, workflow-orchestrator, test-driven-development

Execution Plan:

Phase 1 (PARALLEL):
  → pr-workflow (miner)
  → codebase-analyzer

Phase 2:
  → workflow-orchestrator

Phase 3:
  → test-driven-development

Summary:
  Total phases: 3
  Parallel phases: 1
  Skills: 4
```

### Execution Result
**Phase 1 (Parallel)**:
- `pr-workflow (miner)` (15 seconds): Found 12 PR comments about pagination patterns
  - Tribal knowledge: "Always use cursor-based for large datasets"
  - Standard: "Limit parameter max value: 100"
- `codebase-analyzer` (12 seconds): Extracted pagination patterns from 3 existing implementations
  - Pattern: `page`, `limit`, `cursor` query parameters
  - Helper function: `pkg/pagination/cursor.go`

**Phase 2**:
- `workflow-orchestrator` created subtasks based on learned patterns:
  1. Add cursor-based pagination to handler
  2. Reuse `pkg/pagination/cursor.go` helper
  3. Enforce `limit <= 100` constraint
  4. Add integration tests

**Phase 3**:
- `test-driven-development` implemented following discovered patterns

**Total Duration**: 42 minutes
**Pattern Compliance**: 100% (followed all discovered conventions)

---

## Example 5: Language-Specific Quality Gate

### User Request
"Implement user preferences feature with appropriate quality checks"

### DAG Building (Go Project)
```
Task: Implement user preferences feature with appropriate quality checks

Task Analysis:
  Primary goals: implementation
  Quality requirements: quality_checks
  Domain hints: golang

Selected Skills (3): test-driven-development, go-patterns, verification-before-completion

Execution Plan:

Phase 1:
  → test-driven-development

Phase 2:
  → go-patterns

Phase 3:
  → verification-before-completion
```

### Execution Result
**Phase 1**: test-driven-development
- Implemented feature with tests
- All tests pass (RED → GREEN → REFACTOR)

**Phase 2**: go-patterns (Go-specific)
- golangci-lint: 0 violations
- go test -race: No race conditions
- go build: Successful
- Coverage: 89%

**Phase 3**: verification-before-completion
- All quality gates pass

**Total Duration**: 28 minutes

---

### Alternative: Python Project

**DAG Building (Python Project)**:
```
Selected Skills (3): test-driven-development, python-quality-gate, verification-before-completion
```

**Execution Result (Python)**:
**Phase 2**: python-quality-gate (Python-specific)
- ruff: 0 violations
- pytest: 15/15 tests passed, 92% coverage
- mypy: Type checking passed
- bandit: No security issues

**Total Duration**: 26 minutes

---

### Alternative: Multi-Language Project

**DAG Building (Multi-Language)**:
```
Selected Skills (3): test-driven-development, universal-quality-gate, verification-before-completion
```

**Execution Result (Multi-Language)**:
**Phase 2**: universal-quality-gate (Auto-detected)
- Detected languages: Go, JavaScript
- Go checks: golangci-lint passed, tests passed
- JavaScript checks: Biome passed, jest tests passed

**Total Duration**: 35 minutes

---

## Example 6: Documentation Audit

### User Request
"Audit and improve documentation quality across the codebase"

### DAG Building Output
```
Task: Audit and improve documentation quality across the codebase

Task Analysis:
  Primary goals: documentation, analysis
  Quality requirements:

Selected Skills (2): codebase-analyzer, comment-quality

Execution Plan:

Phase 1:
  → codebase-analyzer

Phase 2:
  → comment-quality

Summary:
  Total phases: 2
  Parallel phases: 0
  Skills: 2
```

### Execution Result
**Phase 1**: codebase-analyzer
- Analyzed 156 files
- Found 42 functions without documentation
- Identified 18 complex functions needing better docs

**Phase 2**: comment-quality
- Reviewed all comments
- Found 23 temporal references
- Suggested improvements for 31 comments

**Generated Report**:
```markdown
# Documentation Audit Report

## Statistics
- Total files: 156
- Undocumented functions: 42 (27%)
- Temporal references: 23
- Poor quality comments: 31

## High Priority Issues
1. `auth/token.go`: No package documentation
2. `server/handler.go`: 8 temporal references
3. `db/query.go`: Complex logic without explanation

## Recommendations
- Add package-level documentation
- Replace temporal references with explanations
- Document complex algorithms
```

**Total Duration**: 35 minutes
