# Progressive Depth Routing: A/B Test Cases

## Test Design

**Variant S (skill)**: Progressive-depth reference loaded. Router starts at shallowest viable depth, escalates on evidence.
**Variant B (baseline)**: Standard `/do` routing without progressive-depth reference.

Each case is executed by both variants. Outputs are randomized to A/B labels before blind evaluation.

## Depth Levels (Reference)

| Level | Description | Typical Routing |
|-------|-------------|-----------------|
| 0 | Direct answer, no tools needed | Trivial: handle inline |
| 1 | Single agent, single skill | Simple: one agent dispatch |
| 2 | Agent + enhancement stack, or sequential agents | Medium: agent + skill + verification |
| 3 | Pipeline or parallel multi-agent coordination | Complex: full pipeline or subagent-driven-development |

---

## Case 1: Trivial -- Read a specific file (Expected: Level 0)

**Prompt**:
> Read the file at skills/roast/SKILL.md and tell me what version it is.

**Expected optimal depth**: Level 0 (Trivial -- direct file read, no routing needed)

**What good routing looks like**:
- Classifies as Trivial immediately (exact file path provided, single read)
- Does NOT spawn an agent or load a skill
- Reads the file, extracts the version from frontmatter, responds
- Total tool calls: 1 (Read)

**What bad routing looks like**:
- Spawns an explore agent to "understand the file"
- Loads verification-before-completion for a simple read
- Takes more than 2 tool calls

---

## Case 2: Trivial -- Check git status (Expected: Level 0-1)

**Prompt**:
> What branch am I on?

**Expected optimal depth**: Level 0 (single bash command, no routing needed)

**What good routing looks like**:
- Runs `git branch --show-current` or equivalent
- Returns the branch name
- No agent dispatch, no skill loading

**What bad routing looks like**:
- Routes to a git-related skill or agent
- Creates a task plan for a one-liner
- Asks clarifying questions

---

## Case 3: Moderate -- Fix a specific lint error (Expected: Level 1, may escalate to 2)

**Prompt**:
> The ruff linter says scripts/skill_eval/utils.py has an unused import on line 3. Fix it.

**Expected optimal depth**: Start at Level 1 (single agent, single skill). May escalate to Level 2 if the import removal breaks something downstream.

**What good routing looks like**:
- Starts shallow: dispatches a Python-domain agent with the specific fix
- Reads the file, removes the unused import
- Runs ruff to verify the fix
- If removing the import causes a NameError elsewhere, escalates to investigate usage
- If no downstream breakage, commits and stops at Level 1

**What bad routing looks like**:
- Immediately launches a full code review pipeline
- Loads parallel-code-review for a one-line fix
- Skips verification (removes import without running linter again)

---

## Case 4: Moderate -- Add a test for an existing function (Expected: Level 1-2)

**Prompt**:
> Write a test for the `calculate_stats` function in scripts/skill_eval/aggregate_benchmark.py. It should cover empty list, single value, and normal cases.

**Expected optimal depth**: Start at Level 1 (single agent writes tests). Escalate to Level 2 if the function has dependencies that need mocking or the test file structure needs setup.

**What good routing looks like**:
- Dispatches a Python agent with test-driven-development skill
- Reads the function to understand its signature and behavior
- Creates test file with 3 cases (empty, single, normal)
- Runs pytest to verify tests pass
- Stays at Level 1-2 (no pipeline needed)

**What bad routing looks like**:
- Routes to a full test pipeline with coverage analysis
- Loads research-coordinator to "investigate testing approaches"
- Creates tests without running them

---

## Case 5: Complex -- Refactor hook registration across the toolkit (Expected: Level 2-3)

**Prompt**:
> The hook registration in settings.json has 12 hooks that share the same timeout (3000ms). Refactor to use a shared constant or config, update all 12 entries, and verify nothing breaks.

**Expected optimal depth**: Start at Level 2 (agent + enhancement). Should escalate to Level 3 when the scope becomes clear (12 files, cross-cutting change, needs verification across all hooks).

**What good routing looks like**:
- Classifies as Medium-Complex initially
- Dispatches agent to survey the 12 hooks first
- Escalates to Level 3 when the scope reveals cross-cutting impact
- Uses subagent-driven-development or parallel agents for the refactor
- Runs verification across all affected hooks
- Creates a plan before executing

**What bad routing looks like**:
- Tries to handle as a simple find-and-replace (misses structural complexity)
- Stays at Level 1 despite 12-file scope
- Skips the survey step and starts editing immediately

---

## Case 6: Complex -- Design and implement a new evaluation metric (Expected: Level 3)

**Prompt**:
> Design a new metric for the skill-eval benchmark system that measures "explanation coherence" -- how well a skill's outputs explain their own reasoning. Implement it in aggregate_benchmark.py, add it to the viewer, write tests, and update the schema docs.

**Expected optimal depth**: Level 3 (pipeline -- design, implement, test, document across 4+ files)

**What good routing looks like**:
- Classifies as Complex immediately (multi-file, multi-phase, requires design decisions)
- Creates an ADR or design doc first
- Plans the implementation phases: design -> implement -> test -> document
- Uses a pipeline or subagent-driven-development
- Verifies each phase before proceeding to the next
- Updates schemas.md to reflect the new metric

**What bad routing looks like**:
- Dispatches a single agent to "just implement it"
- Skips the design phase
- Implements without tests
- Forgets to update the schema documentation

---

## Case 7: Ambiguous -- Investigate and maybe fix a routing misclassification (Expected: Depends on findings)

**Prompt**:
> Users report that "research best practices for Kubernetes RBAC" sometimes gets routed to the creation protocol instead of research-coordinator-engineer. Investigate why and fix it if you can identify the root cause.

**Expected optimal depth**: Ambiguous. Could be Level 1 (simple trigger overlap fix) or Level 3 (deep routing logic redesign) depending on what the investigation reveals.

**What good routing looks like**:
- Starts at Level 1: reads the routing tables and trigger lists to check for overlap
- If the fix is a trigger adjustment: stays at Level 1, makes the change, runs routing benchmark to verify
- If the root cause is deeper (e.g., complexity classifier interaction with creation scan): escalates to Level 2-3
- Makes the escalation decision based on evidence from the investigation, not assumptions
- The key signal: progressive depth should NOT pre-commit to a depth level -- it should explicitly say "starting shallow, will escalate if needed"

**What bad routing looks like**:
- Immediately launches a full routing redesign without investigating first
- Stays shallow even after discovering the root cause requires structural changes
- Pre-commits to Level 3 "just in case" (wasteful if the fix is a one-line trigger edit)

**Why this case is interesting**: It tests proportionality. The progressive-depth skill should demonstrate that it adapts depth to evidence, not to assumptions about complexity. The baseline (no progressive-depth) will likely either over- or under-commit to a depth level.
