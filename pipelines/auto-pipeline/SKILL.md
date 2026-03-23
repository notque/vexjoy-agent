---
name: auto-pipeline
description: |
  Automatic pipeline generation for unrouted tasks. Two tiers: Tier 1 classifies
  the task type, selects a canonical chain (8-12 steps), and executes it inline
  with phase gates. Tier 2 auto-crystallizes the ephemeral pattern into a permanent
  pipeline when in the toolkit repo (immediate) or after 3+ runs elsewhere.
  Invoked automatically by /do when no existing route matches. Includes dedup gate
  to prevent creating pipelines that duplicate existing ones.
  Use when /do finds no matching route for a non-trivial request.
  Do NOT invoke directly — /do routes here automatically.
version: 1.0.0
user-invocable: false
allowed-tools:
  - Read
  - Write
  - Bash
  - Grep
  - Glob
  - Agent
  - Edit
context: fork
routing:
  triggers:
    - auto-pipeline
    - ephemeral pipeline
    - no route found
    - unrouted task
  pairs_with:
    - chain-composer
    - pipeline-scaffolder
    - domain-research
    - pipeline-test-runner
  complexity: Complex
  category: meta
---

# Auto-Pipeline

## Operator Context

This pipeline operates as the automatic fallback for `/do` when no existing route matches a non-trivial request. It classifies the task type, selects and adapts a canonical chain, executes it with phase gates, and optionally crystallizes the pattern into a permanent pipeline.

### Hardcoded Behaviors (Always Apply)
- **Dedup Gate**: ALWAYS check pipeline catalog before creating anything. If existing pipeline covers 70%+ of request, route to it instead.
- **8-12 Step Preference**: Prefer longer chains over minimal ones. More steps = more phase gates = higher quality. A 6-step chain that could be 10 steps is under-utilizing the infrastructure.
- **Phase Gates**: Every step must complete before the next begins. No skipping, no parallel steps unless the step explicitly supports parallelism (RESEARCH, REVIEW).
- **Artifact Persistence**: Save intermediate output at each phase to session-local files. Context is ephemeral; files are not.
- **Rule 12 Compliance**: RESEARCH steps MUST use parallel multi-agent dispatch (3-4 agents). Sequential grep-based research is banned.
- **Immediate Crystallization in Toolkit Repo**: If running in this repo (detected by `pipelines/auto-pipeline/` existing in CWD), crystallize on first encounter — don't wait for 3+ runs.
- **No Duplicate Pipelines**: The dedup gate is a HARD BLOCK. If an existing pipeline matches, route to it. Do not rationalize "this is slightly different."

### Default Behaviors (ON unless disabled)
- **Chain Adaptation**: Extend canonical chains with domain-appropriate steps from the step menu (EXTRACT, COMPILE, ASSESS, SYNTHESIZE, REFINE, COMPARE, LINT, CONFORM, MONITOR).
- **Operator Profile Gates**: Apply personal/work/CI/production gates per the step menu's profile rules.
- **Learning Recording**: After every ephemeral execution, record to learning.db for crystallization tracking.

### Optional Behaviors (OFF unless enabled)
- **Dry Run**: Show the proposed chain without executing it.
- **Force Ephemeral**: Skip crystallization even in toolkit repo (for testing).

## What This Pipeline CAN Do
- Classify any user request into one of 8 canonical task types
- Select and adapt canonical chains to 8-12 steps
- Execute chains inline with phase gates
- Auto-crystallize into permanent pipelines (toolkit repo: immediate; others: 3+ runs)
- Dedup against existing pipeline catalog

## What This Pipeline CANNOT Do
- Override existing pipeline routing (dedup gate prevents this)
- Create agents (crystallization uses existing agents or creates via pipeline-scaffolder)
- Bypass the creation gate hook (new pipelines go through proper creation flow)
- Execute without phase gates (every step is gated)

---

## Instructions

### Phase 0: DEDUP CHECK

**Goal**: Ensure we're not duplicating an existing pipeline.

**Step 1**: Run task type classification:
```bash
python3 scripts/task-type-classifier.py --request "{user_request}" --check-catalog pipelines/auto-pipeline/references/pipeline-catalog.md --json
```

**Step 2**: If the classifier returns `existing_pipeline`, STOP. Route to that pipeline instead. Display:
```
===================================================================
 ROUTING: Existing pipeline found
===================================================================
 Request matches: {pipeline_name} (coverage: {N}%)
 Routing to existing pipeline instead of creating new.
===================================================================
```

**Step 3**: If no existing pipeline matches, capture the classification result:
- `task_type`: one of 8 canonical types
- `chain`: the canonical chain for that type
- `steps`: step count
- `keywords_matched`: which keywords triggered this classification

**Gate**: Classification complete. No existing pipeline matches. Proceed to Phase 1.

### Phase 1: CHAIN SELECTION

**Goal**: Select the best canonical chain variant and extend to 8-12 steps.

**Step 1**: Read `pipelines/chain-composer/references/canonical-chains.md` for the full canonical chain and its variants.

**Step 2**: Select the best variant based on request analysis:
- Does the request involve unstructured input? → add EXTRACT
- Does the request need multi-source research? → add COMPILE or use GATHER variant
- Does the request need audience targeting? → add GROUND
- Does the request need iterative improvement? → add REFINE
- Does the request have verifiable syntax? → add LINT
- Does the request need spec conformance? → add CONFORM
- Does the request need post-execution observation? → add MONITOR
- Does the request involve state changes? → add CHARACTERIZE before, COMPARE after

**Step 3**: Verify chain has 8-12 steps. If fewer than 8:
- Add ASSESS before any generation/execution step
- Add COMPILE between research and generation
- Add REFINE after validation
- Add SYNTHESIZE before reporting

**Step 4**: Apply operator profile gates:
- Personal: remove APPROVE, PROMPT; reduce GUARD to branch-check only
- Work: add CONFORM after GENERATE; full GUARD
- CI: skip interaction steps; add NOTIFY
- Production: add SIMULATE, SNAPSHOT, APPROVE (mandatory)

**Gate**: Chain has 8-12 steps. All type compatibility rules satisfied. Proceed to Phase 2.

### Phase 2: CONTEXT CHECK (Toolkit Repo Detection)

**Goal**: Determine whether to crystallize immediately or run ephemeral.

**Step 1**: Check if `pipelines/auto-pipeline/SKILL.md` exists in CWD (indicates toolkit repo).

**Step 2**: If toolkit repo:
- Check learning.db for any prior ephemeral runs in this domain (informational only — crystallize regardless)
- Proceed to Phase 3 (CRYSTALLIZE) instead of Phase 4 (EPHEMERAL EXECUTE)

**Step 3**: If NOT toolkit repo:
- Query learning.db: `python3 scripts/learning-db.py search "ephemeral {task_type}" --json`
- Count matching entries for this domain
- If 3+ found: proceed to Phase 3 (CRYSTALLIZE)
- If <3 found: proceed to Phase 4 (EPHEMERAL EXECUTE)

**Gate**: Execution path determined (crystallize vs ephemeral). Proceed to appropriate phase.

### Phase 3: CRYSTALLIZE (Create Permanent Pipeline)

**Goal**: Create a permanent pipeline from the adapted chain and wire it into routing.

This phase IS a pipeline itself (10 steps):

**Step 1 — DETECT**: Confirm crystallization threshold is met (toolkit repo = always; other = 3+ prior runs).

**Step 2 — GATHER**: If prior ephemeral runs exist, collect their chain descriptions and outcomes from learning.db.

**Step 3 — RESEARCH**: Use accumulated evidence to inform pipeline design. Dispatch 3 parallel research agents:
- Agent 1: Analyze what steps worked in prior ephemeral runs
- Agent 2: Find similar existing pipelines to learn from
- Agent 3: Identify domain-specific references/scripts needed

**Step 4 — COMPOSE**: Build the final chain:
- Start from the adapted canonical chain (from Phase 1)
- Incorporate learnings from prior ephemeral runs (if any)
- Ensure 8-12 steps
- Validate type compatibility

**Step 5 — VALIDATE**: Run `python3 scripts/artifact-utils.py validate-chain` against the composed chain.

**Step 6 — SCAFFOLD**: Create the pipeline skill:
- Create `pipelines/{pipeline-name}/SKILL.md` with full operator context
- Create `pipelines/{pipeline-name}/references/` if domain references are needed
- Follow the existing pipeline SKILL.md format (frontmatter + operator context + phases)

**Step 7 — INTEGRATE**: Wire into routing:
- Run `python3 scripts/generate-skill-index.py` to update INDEX.json
- The routing-table-updater skill handles /do routing table updates

**Step 8 — VERIFY**: Confirm the new pipeline is discoverable:
- Check `skills/INDEX.json` contains the new pipeline
- Verify `pipelines/{name}/SKILL.md` exists and parses

**Step 9 — REGISTER**: Record in learning.db:
- Mark all contributing ephemeral learnings as graduated
- Record the crystallization event

**Step 10 — EXECUTE**: Route the original request through the newly created permanent pipeline.

**Gate**: Pipeline created, integrated, verified. Original request executing through permanent pipeline.

### Phase 4: EPHEMERAL EXECUTE

**Goal**: Execute the adapted chain inline with phase gates, without persistence.

**Step 1**: Display the ephemeral pipeline banner:
```
===================================================================
 ROUTING: [EPHEMERAL PIPELINE] {task_description}
===================================================================

 Task type: {task_type}
 Chain ({N} steps): {step1} → {step2} → ... → {stepN}
 Profile: {profile} ({profile_description})

 Note: No permanent pipeline exists for this domain.
       Running ephemeral chain with phase gates.

===================================================================
```

**Step 2**: Execute each step in sequence:
- For each step in the chain:
  1. Announce: `[Phase {N}/{total}: {STEP_NAME}]`
  2. Execute the step's action (research, compile, generate, validate, etc.)
  3. Save output to session-local file: `/tmp/ephemeral-pipeline/{step_name}.md`
  4. Verify gate condition is met
  5. Proceed to next step

**Step 3**: For RESEARCH steps (Rule 12): dispatch 3-4 parallel agents:
- Agent 1: Code/content analysis
- Agent 2: Usage patterns / ecosystem context
- Agent 3: Examples and reference material
- Agent 4 (optional): External documentation / API references

**Step 4**: For REVIEW steps: dispatch 3+ parallel reviewers with different lenses.

**Step 5**: For REFINE steps: iterate up to 3 times until validation passes.

**Step 6**: On completion, record learning:
```bash
python3 scripts/learning-db.py learn --skill auto-pipeline "ephemeral {task_type} for {domain}: {chain_description}"
```

**Gate**: All steps executed. Output delivered. Learning recorded.

---

## Error Handling

### Error: "Classification returns no matches"
Cause: Request doesn't match any task type keywords.
Solution: Default to `analysis` type (broadest applicability). Log a learning about the unclassifiable request.

### Error: "Dedup gate blocks but user insists"
Cause: Existing pipeline matches 70%+ but user says it doesn't serve their needs.
Solution: User can say "create new pipeline for X, existing one doesn't cover Y." The explicit override bypasses dedup.

### Error: "Chain validation fails"
Cause: Type compatibility error in adapted chain.
Solution: Fall back to the unmodified canonical chain for that task type. Log the adaptation that failed.

### Error: "Crystallization fails mid-scaffold"
Cause: Pipeline creation blocked by creation gate or ADR enforcement.
Solution: Fall back to ephemeral execution for the current request. Record the failure for investigation.

---

## Anti-Patterns

### Anti-Pattern 1: Creating Duplicate Pipelines
**What it looks like**: Auto-pipeline creates a new pipeline when an existing one covers the same domain.
**Why wrong**: Fragments routing, creates maintenance burden, confuses discovery.
**Do instead**: ALWAYS check the pipeline catalog first. 70%+ coverage = route to existing.

### Anti-Pattern 2: Minimal Chains
**What it looks like**: Creating a 4-5 step chain when 8-10 steps would be appropriate.
**Why wrong**: Fewer steps = fewer phase gates = fewer verification points = lower quality.
**Do instead**: Extend chains to 8-12 steps using the step menu. Add ASSESS, COMPILE, SYNTHESIZE, REFINE where appropriate.

### Anti-Pattern 3: Skipping Crystallization in Toolkit Repo
**What it looks like**: Running ephemeral in the toolkit repo instead of creating a permanent pipeline.
**Why wrong**: This repo IS the pipeline system. Every pipeline we create for ourselves becomes part of the toolkit.
**Do instead**: ALWAYS crystallize in the toolkit repo. Immediate, first encounter.

### Anti-Pattern 4: Sequential Research
**What it looks like**: Running grep/search commands one at a time in a RESEARCH step.
**Why wrong**: Rule 12 (validated by A/B test) — sequential research produces 1.40-point quality gap.
**Do instead**: Dispatch 3-4 parallel research agents. Always.

---

## References

- `pipelines/chain-composer/references/canonical-chains.md` — 8 canonical chain templates with variants
- `pipelines/pipeline-scaffolder/references/step-menu.md` — 23 step families, 150+ steps, type compatibility matrix
- `pipelines/auto-pipeline/references/pipeline-catalog.md` — auto-generated catalog of all existing pipelines (dedup reference)
