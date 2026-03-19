---
name: skill-composer
description: |
  DAG-based multi-skill orchestration: Discover, Plan, Validate, Execute.
  Builds execution graphs for tasks requiring multiple skills in sequence
  or parallel with dependency resolution and context passing. Use when a
  task requires 2+ skills chained together, parallel skill execution, or
  conditional branching between skills. Use for "compose skills", "chain
  workflow", "multi-skill", or "orchestrate skills". Do NOT use when a
  single skill can handle the request, or for simple sequential invocation
  that needs no dependency management.
version: 2.0.0
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
---

# Skill Composer

## Purpose

Orchestrate complex workflows by chaining multiple skills into validated execution DAGs. Discovers applicable skills, resolves dependencies, validates compatibility, presents execution plans, and manages skill-to-skill context passing.

## Operator Context

This skill operates as an operator for multi-skill orchestration, configuring Claude's behavior for DAG-based workflow composition with dependency resolution and context passing between skills.

### Hardcoded Behaviors (Always Apply)
- **CLAUDE.md Compliance**: Read and follow repository CLAUDE.md files before composing any workflow
- **Over-Engineering Prevention**: Only compose skills that are directly requested. Prefer simple 2-3 skill chains over complex orchestrations. Do not add speculative skills or "nice to have" additions without explicit user request
- **Dry Run First**: ALWAYS show execution plan and get user confirmation before running skills
- **DAG Validation**: ALWAYS validate execution graph is acyclic before execution
- **Context Validation**: ALWAYS verify output/input compatibility between chained skills
- **Error Isolation**: ALWAYS catch skill failures and determine if remaining chain can continue
- **Skill Discovery**: Scan skills/*/SKILL.md for available skills before building any DAG

### Default Behaviors (ON unless disabled)
- **Communication Style**: Report facts without self-congratulation. Show command output rather than describing it. Be concise but informative.
- **Temporary File Cleanup**: Remove temporary files (skill index, DAG files, intermediate outputs) at task completion. Keep only files explicitly needed for final output.
- **Parallel Optimization**: Execute independent skills concurrently when no shared resources or dependencies exist
- **Verbose Logging**: Show skill selection reasoning and execution progress for each phase
- **Compatibility Checks**: Validate skill input/output formats match before execution using `references/compatibility-matrix.md`
- **Pattern Recognition**: Suggest known composition patterns from `references/composition-patterns.md` when applicable

### Optional Behaviors (OFF unless enabled)
- **Auto-retry Failed Skills**: Retry failed skills with adjusted parameters (max 2 retries)
- **Adaptive Composition**: Modify execution plan based on intermediate results
- **Skill Suggestion**: Proactively suggest additional skills that might help

## What This Skill CAN Do
- Discover available skills and build execution DAGs with dependency resolution
- Chain skills sequentially, in parallel, or with conditional branching
- Validate composition compatibility (acyclic, type-safe, ordered)
- Pass context between skills with output/input transformation
- Handle partial failures with isolation and recovery options
- Present dry-run execution plans before committing to execution

## What This Skill CANNOT Do
- Execute skills without showing the plan first (dry run is mandatory)
- Compose workflows with circular dependencies
- Chain skills with incompatible input/output types without transformation
- Replace single-skill invocation (if one skill suffices, use it directly)
- Skip DAG validation to save time

---

## Instructions

### Phase 1: DISCOVER

**Goal**: Analyze the task and find applicable skills.

**Step 1: Analyze the user's request**

Identify:
- Primary goals (what needs to be accomplished)
- Quality requirements (testing, verification, documentation)
- Domain constraints (language, framework, standards)
- Execution constraints (sequential vs parallel, conditionals)

**Step 2: Discover available skills**

```bash
# TODO: scripts/discover_skills.py not yet implemented
# Manual alternative: scan skills directory for SKILL.md files
find ./skills -name "SKILL.md" -exec grep -l "^name:" {} \; | sort
```

Review the discovered skills. Categorize by type (workflow, testing, quality, documentation, code-analysis, debugging) with dependency metadata.

**Step 3: Select skills**

Choose only skills directly needed for the stated goals. Apply the minimum-skills principle:

- Can a single skill handle this? If yes, do NOT compose. Invoke it directly.
- Can 2 skills handle this? Prefer that over 3+.
- Is a skill being added "for quality" or "just in case"? Remove it.

Cross-reference selections against `references/compatibility-matrix.md` to confirm chaining is valid before proceeding.

**Gate**: Task goals identified. Available skills indexed. Selected skills directly address stated goals with no extras. Proceed only when gate passes.

### Phase 2: PLAN

**Goal**: Build a validated execution DAG.

**Step 1: Build the DAG**

```bash
# TODO: scripts/build_dag.py not yet implemented
# Manual alternative: construct the execution DAG as a JSON structure
# with nodes (skills) and edges (dependencies) based on the task analysis
```

**Step 2: Validate the DAG**

Validate the execution DAG manually by checking:
- No circular dependencies exist between skills
- Output types from each skill match input requirements of downstream skills
- All referenced skills exist in the skill index
- Dependencies satisfy topological ordering

Validation checks:
- **Acyclic**: No circular dependencies
- **Compatibility**: Output types match input requirements (consult `references/compatibility-matrix.md`)
- **Availability**: All referenced skills exist in the index
- **Ordering**: Dependencies satisfy topological ordering

If validation fails, fix the issue and re-validate. Common fixes:
- Circular dependency: Remove one edge or split into two independent compositions
- Type mismatch: Choose different skill or add transformation step
- Missing skill: Check spelling, re-run discovery
- Ordering violation: Reorder phases to satisfy dependencies

**Step 3: Present the execution plan**

```
=== Execution Plan ===

Phase 1 (Sequential):
  -> skill-name
    Purpose: [what it does in this context]
    Output: [what it produces]

Phase 2 (Parallel):
  -> skill-a
    Purpose: [what it does]
    Input: [from Phase 1]
  -> skill-b
    Purpose: [what it does]
    Input: [from Phase 1]

Phase 3 (Sequential):
  -> skill-c
    Purpose: [what it does]
    Input: [from Phase 2]

Skills: N | Phases: N | Parallel phases: N

Proceed? [Y/n]
```

**Gate**: DAG is acyclic. All skills exist. Input/output types are compatible. Topological ordering is valid. User has seen the plan. Proceed only when gate passes.

### Phase 3: EXECUTE

**Goal**: Run skills in topological order, passing context between them.

**Step 1: Execute each phase**

For sequential phases:
1. Invoke skill with context from previous phases
2. Capture output
3. Verify output matches expected type
4. Proceed to next phase

For parallel phases:
1. Launch all independent skills using Task tool
2. Wait for all to complete
3. Aggregate results for next phase

**Step 2: Pass context between skills**

For each skill transition:
1. Capture output from completed skill
2. Transform to format expected by next skill
3. Inject as context when invoking next skill
4. Verify transformation succeeded

**Step 3: Report progress**

After each phase completes, report:
- Phase number and skills completed
- Output summary
- Overall progress (e.g., "Phase 2/3 complete")

**Step 4: Handle failures during execution**

If a skill fails mid-chain:

1. **Assess impact**: Does this block downstream skills?
   - Critical (blocks all downstream): Stop chain, report what completed
   - Isolated (blocks one branch): Continue other branches
   - Recoverable (transient failure): Retry with adjusted parameters (max 2 attempts)

2. **Report failure context**:
```
Skill failed: [skill-name]
  Phase: N
  Error: [error message]
  Downstream impact: [list blocked skills]
  Continuing branches: [list unaffected skills]
  Recovery options:
    1. Fix error and retry
    2. Skip skill and continue (if non-critical)
    3. Abort entire workflow
```

3. **Execute recovery**: Based on user selection or automatic policy (if auto-retry enabled)

**Gate**: All phases executed. All skill outputs captured. Context passed successfully between all transitions. Proceed only when gate passes.

### Phase 4: REPORT

**Goal**: Collect results and clean up.

**Step 1: Generate results summary**

```
=== Composition Results ===

Execution Summary:
  Total phases: N
  Skills executed: N
  Duration: X minutes

Phase Results:
  Phase 1: [skill-name] - [status]
    Output: [summary]
  Phase 2: [skill-a] - [status]
           [skill-b] - [status]
    Output: [summary]
  Phase 3: [skill-c] - [status]
    Output: [summary]

Final Output:
  [Key deliverables with file paths]
```

**Step 2: Clean up temporary files**

Remove: `/tmp/skill-index.json`, `/tmp/execution-dag.json`, and any intermediate output files created during composition.

**Gate**: Results reported. Temporary files cleaned up. Composition complete.

---

## Examples

### Example 1: Feature with Tests
User says: "Add rate limiting middleware with comprehensive tests"
Actions:
1. DISCOVER: Identify implementation + testing goals. Select workflow-orchestrator, test-driven-development, verification-before-completion
2. PLAN: Build 3-phase sequential DAG. Validate compatibility. Show plan.
3. EXECUTE: Phase 1 creates subtasks, Phase 2 implements with TDD, Phase 3 verifies
4. REPORT: All phases complete, 24 tests pass, 94% coverage
Result: 3-skill chain, 32 minutes, no failures

### Example 2: Parallel Quality Checks
User says: "Check code quality and documentation before PR"
Actions:
1. DISCOVER: Identify quality + documentation goals. Select code-linting, comment-quality, verification-before-completion
2. PLAN: Phase 1 runs code-linting and comment-quality in parallel (no shared resources). Phase 2 runs verification sequentially.
3. EXECUTE: Parallel phase completes in ~6 seconds (vs 10 sequential). Verification merges results.
4. REPORT: 33% time savings from parallelization, all checks pass
Result: 3-skill chain with 1 parallel phase, 8 minutes

### Example 3: Research Before Implementation
User says: "Implement pagination following existing patterns"
Actions:
1. DISCOVER: Identify research + implementation goals. Select pr-miner, codebase-analyzer, workflow-orchestrator, test-driven-development
2. PLAN: Phase 1 runs pr-miner and codebase-analyzer in parallel. Phase 2 plans with orchestrator. Phase 3 implements with TDD.
3. EXECUTE: Research discovers cursor-based pagination convention. Plan follows it. Implementation matches.
4. REPORT: Pattern compliance 100%, all tests pass
Result: 4-skill chain with 1 parallel phase, 42 minutes

---

## Error Handling

### Error: "Circular dependency detected"
Cause: Skills reference each other cyclically in the DAG
Solution:
1. Review dependency graph for cycles
2. Remove or reorder the problematic dependency
3. Consider splitting into independent compositions
4. Re-validate DAG before proceeding

### Error: "Skill output incompatible with next skill input"
Cause: Output type from one skill does not match expected input of the next
Solution:
1. Consult `references/compatibility-matrix.md` for valid chains
2. Add an intermediate transformation skill if one exists
3. Choose a different skill combination that has compatible types
4. Re-validate after changes

### Error: "Skill failed during execution"
Cause: A skill in the chain encountered an error
Solution:
1. Determine failure impact: critical (blocks downstream), isolated (one branch), or recoverable
2. If isolated: continue other branches, report partial results
3. If recoverable: retry with adjusted parameters (max 2 attempts)
4. If critical: abort chain, report what completed, suggest recovery options

### Error: "Skill not found in index"
Cause: Referenced skill does not exist or name is misspelled
Solution:
1. Check spelling against skill index output
2. Re-run discovery script to refresh the index
3. Verify the skill directory exists under skills/
4. Use the suggested alternative from the discovery output if the name was close

---

## Anti-Patterns

### Anti-Pattern 1: Over-Composition
**What it looks like**: User asks "Add a login feature" and response chains 6 skills: workflow-orchestrator, TDD, code-linting, comment-quality, code-review, verification
**Why wrong**: Adds unnecessary overhead. Most skills don't add value for a simple feature request. 2-3 skills would suffice.
**Do instead**: Use test-driven-development directly. Only compose multiple skills when the task explicitly requires orchestration.

### Anti-Pattern 2: Skipping the Dry Run
**What it looks like**: Immediately executing skills without showing the plan
**Why wrong**: User cannot catch composition errors early. No opportunity to adjust before wasting time. Violates the "Dry Run First" hardcoded behavior.
**Do instead**: Always present the execution plan and wait for confirmation before proceeding.

### Anti-Pattern 3: Sequential When Parallel Is Safe
**What it looks like**: Running code-linting, then comment-quality, then go-pr-quality-gate in sequence when all three are independent
**Why wrong**: Forces ~15 minutes of sequential execution when ~5 minutes parallel would work. No dependencies exist between them.
**Do instead**: Analyze dependencies carefully. Independent skills with no shared resources run in parallel.

### Anti-Pattern 4: Incompatible Skill Chaining
**What it looks like**: Chaining test-driven-development (outputs: Go source files) into pr-miner (expects: Git repository URL)
**Why wrong**: Output type does not match input type. Will fail at runtime with a compatibility error.
**Do instead**: Consult `references/compatibility-matrix.md` during planning. Only chain skills with compatible interfaces.

### Anti-Pattern 5: Forgetting Cleanup
**What it looks like**: After composition completes, /tmp/ contains skill-index.json, execution-dag.json, and multiple intermediate output files
**Why wrong**: Temporary files accumulate across sessions, may contain sensitive data, and clutter the filesystem.
**Do instead**: Always execute cleanup in the REPORT phase. Remove all temporary files created during composition. Keep only files explicitly needed for the final output.

---

## References

This skill uses these shared patterns:
- [Anti-Rationalization](../shared-patterns/anti-rationalization-core.md) - Prevents shortcut rationalizations
- [Verification Checklist](../shared-patterns/verification-checklist.md) - Pre-completion checks

### Domain-Specific Anti-Rationalization

| Rationalization | Why It's Wrong | Required Action |
|-----------------|----------------|-----------------|
| "One skill can probably handle all of this" | Complex tasks need specialized skills | Discover applicable skills, compose what's needed |
| "No need to validate the DAG, it's simple" | Simple DAGs can still have type mismatches | Run validation script every time |
| "User doesn't need to see the plan" | Skipping dry run violates hardcoded behavior | Present plan, wait for confirmation |
| "I'll add a few extra skills for quality" | Over-composition wastes time and adds failure points | Only compose skills explicitly needed |

### Reference Files
- `${CLAUDE_SKILL_DIR}/references/composition-patterns.md`: Proven multi-skill composition patterns with duration estimates
- `${CLAUDE_SKILL_DIR}/references/compatibility-matrix.md`: Skill input/output compatibility and valid chains
- `${CLAUDE_SKILL_DIR}/references/skill-patterns.md`: Common skill patterns with sequential/parallel decision trees
- `${CLAUDE_SKILL_DIR}/references/examples.md`: Real-world composition examples with execution output
