# Skill Compatibility Matrix

This document maps which skills work well together, common input/output types, and known incompatibilities.

## Skill Input/Output Types

### Workflow & Orchestration Skills

**workflow-orchestrator**
- Inputs: `task_description`, `repository`
- Outputs: `task_breakdown`, `subtasks`, `file_paths`, `verification_steps`
- Compatible with: Almost all implementation skills
- Notes: Excellent starting point for complex tasks

**skill-composer** (this skill)
- Inputs: `task_description`, `skill_index`
- Outputs: `execution_dag`, `skill_chain`
- Compatible with: All skills (meta-skill)
- Notes: Orchestrates other skills

---

### Testing & Quality Skills

**test-driven-development**
- Inputs: `feature_description`, `file_path`, `task_breakdown`
- Outputs: `tested_code`, `test_suite`, `test_results`
- Compatible with: workflow-orchestrator, verification-before-completion, comment-quality
- Notes: RED-GREEN-REFACTOR cycle

**verification-before-completion**
- Inputs: `code_changes`, `test_results`, `implementation`
- Outputs: `verification_report`, `quality_status`
- Compatible with: Any implementation skill, all quality skills
- Notes: Excellent endpoint for workflows

**code-linting**
- Inputs: `file_path`, `directory`, `language`
- Outputs: `lint_results`, `violations`, `auto_fixes`
- Compatible with: All code-producing skills
- Notes: Language-specific (ruff for Python, Biome for JS)

**go-patterns**
- Inputs: `repository`, `directory` (Go projects only)
- Outputs: `quality_report`, `lint_results`, `test_results`, `build_status`
- Compatible with: Go-specific skills, verification-before-completion
- Notes: Go-only, comprehensive quality checks

**python-quality-gate**
- Inputs: `repository`, `directory` (Python projects only)
- Outputs: `quality_report`, `lint_results`, `test_results`, `type_check_results`
- Compatible with: Python skills, code-linting, verification-before-completion
- Notes: Python-only, runs ruff, pytest, mypy, bandit

**universal-quality-gate**
- Inputs: `repository`, `directory`
- Outputs: `quality_report`, `detected_languages`, `results_by_language`
- Compatible with: All language projects, verification-before-completion
- Notes: Auto-detects languages and runs appropriate linters

---

### Code Analysis Skills

**codebase-analyzer**
- Inputs: `repository`, `directory`, `language`
- Outputs: `code_patterns`, `statistics`, `analysis_report`
- Compatible with: pr-workflow (miner), workflow-orchestrator, comment-quality
- Notes: Statistical analysis of implementation patterns

**pr-workflow (miner)**
- Inputs: `repository_url`, `organization`, `repo_name`
- Outputs: `review_comments`, `tribal_knowledge`, `coding_standards`
- Compatible with: codebase-analyzer, workflow-orchestrator
- Notes: Mines GitHub PR review comments

**comment-quality**
- Inputs: `file_path`, `directory`, `code_changes`
- Outputs: `documentation_review`, `temporal_references`, `quality_score`
- Compatible with: All code-producing skills
- Notes: Reviews for temporal references (WHEN vs WHAT/WHY)

---

### Debugging Skills

**systematic-debugging**
- Inputs: `bug_description`, `error_message`, `file_path`
- Outputs: `root_cause`, `fix_implementation`, `test_cases`
- Compatible with: comment-quality, verification-before-completion
- Notes: 4-phase process (Reproduce → Isolate → Identify → Verify)

---

## Compatibility Matrix

### Excellent Combinations (⭐⭐⭐)

| Skill A | → | Skill B | Notes |
|---------|---|---------|-------|
| workflow-orchestrator | → | test-driven-development | Perfect: breakdown feeds into TDD |
| test-driven-development | → | verification-before-completion | Perfect: tests validate verification |
| systematic-debugging | → | comment-quality | Perfect: fix docs need quality check |
| pr-workflow (miner) | → | codebase-analyzer | Perfect: PR knowledge + code patterns |
| code-linting | ‖ | comment-quality | Perfect parallel: independent checks |
| codebase-analyzer | → | workflow-orchestrator | Good: patterns inform planning |
| test-driven-development | → | go-patterns | Perfect for Go: tests then gate |
| test-driven-development | → | python-quality-gate | Perfect for Python: tests then gate |
| test-driven-development | → | universal-quality-gate | Perfect: tests then multi-language gate |

**Legend**: `→` = sequential, `‖` = parallel

---

### Good Combinations (⭐⭐)

| Skill A | → | Skill B | Notes |
|---------|---|---------|-------|
| workflow-orchestrator | → | systematic-debugging | Good if bug is complex |
| pr-workflow (miner) | → | test-driven-development | Good: learn then implement |
| code-linting | → | verification-before-completion | Good: lint then verify |
| codebase-analyzer | → | comment-quality | Good: analyze then doc |
| go-patterns | → | verification-before-completion | Good: gate then verify |
| python-quality-gate | → | verification-before-completion | Good: gate then verify |
| universal-quality-gate | → | verification-before-completion | Good: gate then verify |
| systematic-debugging | → | test-driven-development | Good: debug then add tests |
| pr-workflow (miner) | → | codebase-analyzer | Good: mine patterns then analyze code |

---

### Weak Combinations (⭐)

| Skill A | → | Skill B | Notes |
|---------|---|---------|-------|
| verification-before-completion | → | test-driven-development | Backwards: verify should come last |
| comment-quality | → | code-linting | Backwards: lint finds code issues first |
| pr-workflow (miner) | → | verification-before-completion | Skip step: need implementation in between |
| test-driven-development | → | workflow-orchestrator | Backwards: plan before implement |

---

### Incompatible Combinations (❌)

| Skill A | → | Skill B | Reason |
|---------|---|---------|--------|
| pr-miner | → | comment-quality | Type mismatch: PR data ≠ code files |
| go-patterns | → | code-linting | Redundant: gate includes linting |
| python-quality-gate | → | code-linting | Redundant: gate includes linting |
| universal-quality-gate | → | code-linting | Redundant: gate includes linting |
| workflow-orchestrator | → | skill-composer | Circular: composer should call orchestrator |
| pr-workflow (miner) | → | pr-workflow (miner) | Redundant: coordinator calls pr-workflow (miner) internally |

---

## Parallel Execution Compatibility

### Safe Parallel Combinations

**Independent Quality Checks**:
```
[code-linting, comment-quality]
```
- No shared resources
- Different quality dimensions
- Can merge results

**Multi-Language Linting**:
```
[code-linting (Python), code-linting (JS)]
```
- Different file sets
- Independent execution
- Parallel speedup: ~50%

**Code Analysis**:
```
[codebase-analyzer, pr-workflow (miner)]
```
- Different data sources (local files vs GitHub)
- Independent outputs
- Can run simultaneously

---

### Unsafe Parallel Combinations

**Shared File Modification**:
```
[code-linting (auto-fix), test-driven-development]
```
- Both modify same files
- Race conditions possible
- Must run sequentially

**Dependent Data**:
```
[workflow-orchestrator, test-driven-development]
```
- TDD needs orchestrator output
- Cannot run in parallel
- Dependency chain

---

## Input/Output Type Matching

### Common Input Types

| Type | Description | Skills That Accept |
|------|-------------|-------------------|
| `file_path` | Path to single file | code-linting, comment-quality, test-driven-development |
| `directory` | Path to directory | code-linting, codebase-analyzer, go-patterns |
| `repository` | Git repository path/URL | pr-miner, codebase-analyzer, workflow-orchestrator |
| `task_description` | Natural language task | workflow-orchestrator, skill-composer |
| `code_changes` | Modified code | verification-before-completion, comment-quality |
| `configuration` | Config file/object | code-linting, go-patterns |

### Common Output Types

| Type | Description | Skills That Produce |
|------|-------------|-------------------|
| `test_results` | Test execution results | test-driven-development, go-patterns |
| `report` | Analysis report | All quality/analysis skills |
| `task_breakdown` | Subtask list | workflow-orchestrator |
| `code_patterns` | Implementation patterns | codebase-analyzer |
| `validation_result` | Pass/fail status | verification-before-completion |

---

## Transformation Rules

### Type Conversions

**task_breakdown → feature_description**:
```
workflow-orchestrator output can feed test-driven-development
Transformation: Extract first subtask as feature description
```

**test_results → validation_result**:
```
test-driven-development output feeds verification-before-completion
Transformation: Pass test results directly
```

**code_patterns → task_description**:
```
codebase-analyzer output can inform workflow-orchestrator
Transformation: Summarize patterns as context for planning
```

---

## Language-Specific Compatibility

### Go Projects

**Recommended Stack**:
```
workflow-orchestrator →
test-driven-development →
go-patterns →
verification-before-completion
```

**Avoid**:
- Using generic code-linting (use go-patterns instead)
- Using Python-specific skills with Go code

### Python Projects

**Recommended Stack**:
```
workflow-orchestrator →
test-driven-development →
python-quality-gate →
verification-before-completion
```

**Alternative** (more granular):
```
workflow-orchestrator →
test-driven-development →
[code-linting (ruff), comment-quality] →
verification-before-completion
```

**Avoid**:
- Using Go-specific skills with Python code

### JavaScript/TypeScript Projects

**Recommended Stack**:
```
workflow-orchestrator →
test-driven-development →
[code-linting (Biome), comment-quality] →
verification-before-completion
```

**Avoid**:
- Language-specific Go/Python skills

---

## Skill Chain Length Guidelines

### Optimal Chain Lengths

**Short Chain (2-3 skills)**:
- Best for: Simple tasks, focused workflows
- Example: `code-linting → verification-before-completion`
- Duration: 5-15 minutes
- Risk: Low

**Medium Chain (4-5 skills)**:
- Best for: Feature development, quality enforcement
- Example: `workflow-orchestrator → test-driven-development → code-linting → verification-before-completion`
- Duration: 20-40 minutes
- Risk: Medium

**Long Chain (6+ skills)**:
- Best for: Complex workflows, research + implementation
- Duration: 40-60+ minutes
- Risk: High (more failure points)

### When to Break Into Multiple Chains

**Indicators**:
- Chain length > 6 skills
- Multiple independent branches
- Long duration (> 60 minutes)
- Complex error recovery needed
- Different user roles involved

**Solution**: Use workflow-orchestrator to manage sub-compositions

---

## Compatibility Validation Checklist

Before composing skills, verify:

1. **Input/Output Match**:
   - [ ] Previous skill's outputs include types next skill needs
   - [ ] Or transformation is straightforward

2. **Language Compatibility**:
   - [ ] Language-specific skills match project language
   - [ ] No Go skills for Python projects (and vice versa)

3. **Resource Conflicts**:
   - [ ] Skills don't modify same files simultaneously
   - [ ] Database/network resources not shared unsafely

4. **Dependency Order**:
   - [ ] Skills with dependencies come after their dependencies
   - [ ] No circular dependencies

5. **Parallelization Safety**:
   - [ ] Parallel skills truly independent
   - [ ] No shared state between parallel skills

6. **Semantic Coherence**:
   - [ ] Skill sequence makes logical sense
   - [ ] Not testing before implementing
   - [ ] Not verifying before testing

---

## Advanced Compatibility Patterns

### Conditional Compatibility

**Pattern**: Language-based skill selection
```
IF language == "go":
  → go-patterns
ELSE IF language == "python":
  → code-linting (ruff)
ELSE:
  → code-linting (Biome)
```

### Fallback Compatibility

**Pattern**: Try preferred, fall back to generic
```
IF FAIL (not Go project):
  FALLBACK TO code-linting
```

### Adaptive Compatibility

**Pattern**: Adjust chain based on intermediate results
```
test-driven-development
IF test_coverage < 80%:
  INSERT additional test-driven-development pass
CONTINUE verification-before-completion
```

---

## Troubleshooting Compatibility Issues

### Issue: "Output type mismatch"

**Symptoms**:
- Skill B expects `file_path`, Skill A outputs `repository`
- Type error in validation

**Solutions**:
1. Add intermediate transformation
2. Choose different Skill B that accepts `repository`
3. Extract file paths from repository output

### Issue: "Circular dependency"

**Symptoms**:
- Skill A depends on B, B depends on C, C depends on A
- DAG validation fails

**Solutions**:
1. Remove one dependency
2. Split into two independent compositions
3. Reorder to break cycle

### Issue: "Parallel resource conflict"

**Symptoms**:
- Both skills modify same files
- Race conditions or corruption

**Solutions**:
1. Make sequential instead of parallel
2. Partition files between skills
3. Use locking mechanism

---

This compatibility matrix helps select skills that work well together and avoid problematic combinations. Use it during composition design to ensure smooth execution.
