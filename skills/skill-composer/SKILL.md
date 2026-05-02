---
name: skill-composer
description: "DAG-based multi-skill orchestration with dependency resolution."
user-invocable: false
allowed-tools:
  - Read
  - Write
  - Bash
  - Grep
  - Glob
  - Edit
  - Task
  - Skill
routing:
  triggers:
    - "compose skills"
    - "DAG orchestration"
    - "multi-skill chain"
    - "skill pipeline"
    - "combine skills"
  category: meta-tooling
  pairs_with:
    - workflow
    - feature-lifecycle
---

# Skill Composer

Orchestrate workflows by chaining multiple skills into validated execution DAGs. Discovers applicable skills, resolves dependencies, validates compatibility, presents execution plans, and manages skill-to-skill context passing.

Use when a task requires 2+ skills chained together, parallel execution, or conditional branching. Invoke single skills directly when they suffice.

Minimize composition overhead. Prefer 2-3 skill chains. Add only skills directly needed.

## Reference Loading Table

| Signal | Load These Files | Why |
|---|---|---|
| tasks related to this reference | `compatibility-matrix.md` | Loads detailed guidance from `compatibility-matrix.md`. |
| implementation patterns | `composition-patterns.md` | Loads detailed guidance from `composition-patterns.md`. |
| example-driven tasks | `examples.md` | Loads detailed guidance from `examples.md`. |
| implementation patterns | `skill-patterns.md` | Loads detailed guidance from `skill-patterns.md`. |

## Instructions

### Phase 1: DISCOVER

**Goal**: Analyze the task and find applicable skills.

**Step 1: Analyze request**

Identify: primary goals, quality requirements, domain constraints, execution constraints (sequential vs parallel).

**Step 2: Discover available skills**

```bash
python3 ${CLAUDE_SKILL_DIR}/scripts/discover_skills.py ./skills
```

Categorize by type (workflow, testing, quality, documentation, code-analysis, debugging) with dependency metadata.

**Step 3: Select skills (minimum-skills principle)**

- Single skill handles it? Invoke directly.
- 2 skills sufficient? Prefer over 3+.
- Skill added "for quality" or "just in case"? Remove it.

Cross-reference against `references/compatibility-matrix.md` before proceeding.

**Gate**: Goals identified. Skills indexed. Selected skills directly address stated goals with no extras.

### Phase 2: PLAN

**Goal**: Build a validated execution DAG.

**Step 1: Build DAG**

```bash
python3 ${CLAUDE_SKILL_DIR}/scripts/build_dag.py skill-index.json task-description.json
```

**Step 2: Validate DAG (mandatory before execution)**

Checks:
- **Acyclic**: No circular dependencies
- **Compatible**: Output types match downstream input requirements (consult `references/compatibility-matrix.md`)
- **Available**: All referenced skills exist
- **Ordered**: Dependencies satisfy topological ordering

Fixes: circular -> remove edge or split; type mismatch -> different skill or transformation step; missing -> check spelling, re-run discovery; ordering -> reorder phases.

**Step 3: Present execution plan (mandatory dry run)**

Show plan and get user confirmation before running:

```
=== Execution Plan ===

Phase 1 (Sequential):
  -> skill-name
    Purpose: [what it does]
    Output: [what it produces]

Phase 2 (Parallel):
  -> skill-a | Purpose: [...] | Input: [from Phase 1]
  -> skill-b | Purpose: [...] | Input: [from Phase 1]

Skills: N | Phases: N | Parallel phases: N
Proceed? [Y/n]
```

**Gate**: DAG acyclic. All skills exist. Types compatible. Topological order valid. User saw plan.

### Phase 3: EXECUTE

**Goal**: Run skills in topological order, passing context between them.

**Step 1: Execute phases**

Sequential: invoke skill -> capture output -> verify compatibility -> proceed.
Parallel: launch independent skills via Task tool -> wait for all -> aggregate.

**Step 2: Pass context**

Verify output/input compatibility between chained skills before passing. Capture output -> transform to expected format -> inject -> verify.

**Step 3: Report progress**

After each phase: phase number, output summary, overall progress.

**Step 4: Handle failures**

If a skill fails mid-chain:
1. **Assess impact**: Critical (blocks all downstream) -> stop, report. Isolated (one branch) -> continue others. Recoverable -> retry (max 2 attempts).
2. **Report**: skill name, phase, error, downstream impact, continuing branches, recovery options.
3. **Execute recovery** per user selection or auto-policy.

**Gate**: All phases executed. Outputs captured. Context passed successfully.

### Phase 4: REPORT

**Goal**: Collect results and clean up.

**Step 1: Generate summary**

```
=== Composition Results ===
Total phases: N | Skills executed: N | Duration: X min

Phase Results:
  Phase 1: [skill] - [status] | Output: [summary]
  Phase 2: [skill-a] - [status], [skill-b] - [status]

Final Output: [deliverables with file paths]
```

**Step 2: Clean up**

Remove temporary files (`/tmp/skill-index.json`, `/tmp/execution-dag.json`, intermediate outputs). Keep only final output files.

**Gate**: Results reported. Temp files cleaned. Composition complete.

---

## Error Handling

### Circular dependency detected
Cause: Skills reference each other cyclically.
Solution: Review graph, remove/reorder problematic dependency, consider splitting into independent compositions. Re-validate.

### Output incompatible with next skill input
Cause: Type mismatch between chained skills.
Solution: Consult `references/compatibility-matrix.md`. Add intermediate transformation skill or choose compatible combination. Re-validate.

### Skill failed during execution
Cause: Error mid-chain.
Solution: Assess impact (critical/isolated/recoverable). Continue other branches if isolated. Retry if recoverable (max 2). Abort if critical, report completed work.

### Skill not found in index
Cause: Missing or misspelled skill name.
Solution: Check spelling. Re-run discovery. Verify directory exists under `skills/`.

## References

- `${CLAUDE_SKILL_DIR}/references/composition-patterns.md`: Multi-skill composition patterns with duration estimates
- `${CLAUDE_SKILL_DIR}/references/compatibility-matrix.md`: Skill input/output compatibility and valid chains
- `${CLAUDE_SKILL_DIR}/references/skill-patterns.md`: Common patterns with sequential/parallel decision trees
