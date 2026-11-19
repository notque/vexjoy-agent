# Pipeline Architecture Rules

These rules are enforced by `pipeline-scaffolder` when generating pipeline components. Every scaffolded skill, skill reference, and hook MUST comply.

Repo agents are retired (plan 009). Domain expertise goes in a skill reference (or a new skill), and dispatched work runs on a fresh `general-purpose` worker told which reference to load. Rules below that name agents apply to the domain reference in the repo, and to an agent file only when the owner asks for a private overlay agent (`agents/INDEX.local.json`).

---

## Rule 1: Single-Purpose Components

**BANNED**: Monolithic agent prompts that handle discovery, execution, and integration in one file.

**REQUIRED**: Each component serves exactly one purpose.

| Component Type | Purpose | NOT Its Purpose |
|---------------|---------|-----------------|
| Hook | Detect environment, inject context | Execute logic, make decisions |
| Domain reference | Hold domain expertise that skills load | Define phases, manage routing |
| Overlay agent (owner-requested only) | Coordinate domain work | Scaffold other agents, manage routing |
| Skill | Define methodology and phases | Implement business logic directly |
| Script | Deterministic mechanical work | Interpret results, make judgments |

**Test**: If you can describe a component's purpose using "and", it's doing too much. Split it.

---

## Rule 2: Domain Reference and Agent Size Limits

A domain reference must pass `python3 scripts/validate-references.py --check-size`; move depth into a subdirectory it loads on demand. The rows below apply to the domain reference, and the YAML row only to an overlay agent.

| Constraint | Limit | Enforcement |
|-----------|-------|-------------|
| Main agent file (overlay) | 10,000 words max | Hard gate — move to references/ |
| YAML description (overlay agent) | 3 example blocks | Required by agent template |
| Hardcoded behaviors | 3-5 items | Excess indicates over-engineering |
| Capabilities list | 4-6 items | More suggests scope creep |
| Pattern coverage | 3+ items | Minimum for quality |
| Error categories | 3+ items | Minimum for robustness |

---

## Rule 3: Hook Design Constraints

All hooks MUST:
- Import from `hooks/lib/hook_utils.py`
- Exit 0 on ALL code paths (non-blocking)
- Target <50ms execution time
- Support `CLAUDE_HOOKS_DEBUG` environment variable
- Use `empty_output()` when no detection occurs
- Use `context_output()` to inject context
- Never call subprocesses unless absolutely necessary
- Never modify files or state (read-only detection)

All hooks MUST NOT:
- Block on network calls
- Import heavy libraries (no numpy, pandas, etc.)
- Write to stdout except via `hook_utils` output methods
- Raise unhandled exceptions (always catch and exit 0)

---

## Rule 4: Skill Phase Gates

Every skill MUST have:
- Numbered phases with clear goals
- A **Gate** statement between phases defining completion criteria
- Explicit inputs and outputs for each phase
- No phase may begin until the previous phase's gate is satisfied

**Template**:
```
### Phase N: NAME

**Goal**: [One sentence]

**Steps**: [Numbered list]

**Gate**: [Completion criteria]. Proceed to Phase N+1.
```

---

## Rule 5: Fan-Out/Fan-In Pattern

Pipelines are **component graphs**, not fixed triples. A pipeline may require multiple domain references, multiple skills, multiple hooks, multiple scripts, and reference documentation for each.

```
Phase 1: DISCOVER (sequential — needs full context)
    ↓
Phase 2: SCAFFOLD (fan-out — group by creator type)
    ├─ skill-creator:             Domain reference A, B, C (1..N)
    ├─ skill-creator:   Skill X, Skill Y (1..M)
    ├─ general-purpose + toolkit/references/hook-development.md: Hook 1, Hook 2 (1..K)
    └─ Direct:                    Script 1, Script 2 (1..J)
    ↓ (fan-in — wait for all)
Phase 3: INTEGRATE (sequential — wire component graph)
    ↓
Phase 4: VERIFY (sequential — validate all components + relationships)
```

**Rules**:
- Fan-out ONLY for genuinely independent work items
- Group by creator type: one sub-agent per type handles all components of that type
- For large pipelines, split further: one sub-agent per complex domain reference
- Each fan-out sub-agent receives the Discovery Report AND full Component Manifest
- Fan-in waits for ALL sub-agents before proceeding
- Maximum 10 parallel sub-agents (system limit)
- Reference docs are generated alongside their parent component (not as separate fan-out tasks)

---

## Rule 6: Routing Integration

Every pipeline MUST be routable via `/do`. This means:

1. Skill has `routing:` metadata in YAML frontmatter with `triggers`, `pairs_with`, `complexity`, `category`
2. Skill has trigger keywords in its description, and its Reference Loading Table names the domain reference
3. `routing-table-updater` is invoked to add entries to:
   - `skills/meta/do/SKILL.md` (main routing tables)
   - `skills/meta/do/references/routing-tables.md` (extended tables)
   - `skills/INDEX.json` (skill registry; `agents/INDEX.local.json` only for an owner-requested overlay agent)

**BANNED**: Creating a pipeline that requires manual routing table edits.

---

## Rule 7: No Dead Code

Every generated component must be:
- Referenced by at least one other component (skill loads domain reference, hook triggers skill)
- Routable via `/do` triggers
- Documented in a `commands/` manifest

**BANNED**: Orphan components that are scaffolded but never wired into the system.

---

## Rule 8: Naming Conventions

| Component | Pattern | Examples |
|-----------|---------|----------|
| Domain reference | `{domain}-domain-knowledge.md` or `{domain}-{function}.md` | `migration-domain-knowledge.md`, `prometheus-grafana.md` |
| Overlay agent (owner-requested only) | `{domain}-{function}-engineer` | `migration-safety-engineer`, `review-pipeline-engineer` |
| Skill | `{pipeline-name}` or `{domain}-{function}` | `pipeline-scaffolder`, `migration-validator` |
| Hook | `{pipeline-name}-detector.py` | `pipeline-context-detector.py`, `migration-detector.py` |
| Command | `{action}-{noun}.md` | `create-pipeline.md`, `run-migration.md` |
| References dir | `references/` under the skill (or under an overlay agent) | `skills/{name}/references/`, `private-agents/{name}/references/` |

---

## Rule 9: Reuse Over Recreation

Before creating any component, check:

1. Does a skill reference covering the same domain already exist?
2. Does a skill with the same methodology already exist?
3. Does a hook detecting the same environment already exist?

If YES to any: **bind the existing component** rather than creating a new one. Document the reuse decision in the Discovery Report.

**Threshold**: If an existing component covers 70%+ of the requirement, extend it rather than duplicating.

---

## Rule 10: ADR Enforcement

Every pipeline — both the Pipeline Creator itself and every pipeline it generates — MUST produce an Architectural Decision Record (ADR).

### Pipeline Creator ADR (Phase 0)
The pipeline orchestrator (`pipeline-orchestrator.md`) creates `adr/pipeline-{name}.md` BEFORE discovery. This ADR is a living document updated at each phase. It serves as the pipeline's single source of truth.

### Generated Pipeline ADR
Every pipeline created by the Pipeline Creator MUST include ADR creation as its own Phase 0. The generated skill's instructions MUST include:

```markdown
### Phase 0: ADR

**Goal**: Create a persistent reference document before work begins.

**Step 1**: Create `adr/{pipeline-name}-{task-id}.md` with:
- Context: Why this task is being executed
- Decision: Which approach was chosen and why
- Constraints: What limits apply
- Test Plan: How success will be verified

**Step 2**: Re-read the ADR before every major decision.

**Gate**: ADR file exists. Proceed to Phase 1.
```

**BANNED**: Pipelines that skip ADR creation. Every pipeline, no matter how simple, produces an ADR. The ADR prevents context drift across phases and provides a grading artifact for retrospectives.

---

## Rule 11: Anti-Rationalization Gate

Before finalizing any scaffolded component, check:

| Rationalization | Required Action |
|-----------------|-----------------|
| "This domain reference needs both X and Y responsibilities" | Split into two references |
| "The hook is too simple to create" | Create it anyway — hooks are the pipeline's eyes |
| "We can skip routing integration for now" | No — unroutable pipelines are dead code |
| "This skill doesn't need phase gates" | Yes it does — gates prevent runaway execution |
| "The template is overkill for this" | Follow it anyway — consistency enables tooling |
| "This pipeline doesn't need an ADR" | Yes it does — ADRs prevent context drift and enable retros |

---

## Rule 12: Parallel Research Phase

**Validated by A/B test** (10 trials, 20 outputs — see `adr/pipeline-creator-ab-test.md`).

Any generated pipeline that includes an information-gathering or research phase MUST dispatch parallel research agents rather than performing sequential searches. The A/B test showed that sequential grep-based research produces a **1.40-point gap in Examples quality** and **0.60-point gap in Completeness** compared to parallel multi-agent research.

### When This Rule Applies

A pipeline needs parallel research when it:
- Gathers context about a target (file, module, system, topic)
- Searches the codebase for usage patterns, callers, or integrations
- Needs to understand both the target AND its ecosystem

### Required Pattern

```
Phase N: RESEARCH (Parallel Multi-Agent)

Step 1: Prepare shared context block from prior phase artifacts
Step 2: Dispatch N parallel research agents (default 4, configurable 2-6)
Step 3: Collect and merge research artifacts after all agents complete

Default agents:
  Agent 1: Code Analysis     — internal architecture, data flow, algorithms
  Agent 2: Usage Patterns    — importers, callers, real-world invocation examples
  Agent 3: Context/Ecosystem — related modules, config, system role, tests
  Agent 4: Output/Examples   — return values, output shapes, concrete examples

Each agent:
  - Receives shared context block from prior phases
  - Saves findings to a separate artifact file (/tmp/research-{aspect}.md)
  - Has a 5-minute timeout
  - Operates independently (no inter-agent dependencies)
```

### Why This Matters

| Approach | Examples Score | Completeness Score | A/B Result |
|----------|--------------|-------------------|------------|
| Sequential grep (B v1.0) | 7.40 avg | 9.20 avg | Lost 10/10 |
| Parallel multi-agent (A) | 8.80 avg | 9.80 avg | Won 10/10 |

The gap is NOT in accuracy or structure (both tied within 0.10). It's entirely in research breadth — which directly feeds example richness and completeness.

### Preferred Pattern: Parallel Research

**BANNED**: Research phases that use sequential `grep` or `search` commands without dispatching parallel agents.

**Why wrong**: Sequential search is narrow by construction — each search informs the next, creating tunnel vision. Parallel agents explore independently, producing broader coverage.

**Exception**: If the pipeline's research phase takes <30 seconds total (e.g., single file lookup), sequential is acceptable. But any research involving "find all usages", "discover ecosystem", or "gather examples" MUST be parallel.

---

## Rule 13: Type Compatibility Must Cover All Canonical Chains

**Evidence**: E2E test 4C (Prometheus) found that `scripts/artifact-utils.py` rejected valid operations chains (`ADR → PROBE → ASSESS → PLAN → EXECUTE`). The observation family only accepted `execution-report` and `safety-record` as inputs, but PROBE after ADR requires `decision-record`. E2E test 4D (RabbitMQ) found MONITOR after PROBE was rejected because observation didn't accept `research-artifact`.

**REQUIRED**: The type compatibility matrix in `scripts/artifact-utils.py` must accept all canonical chain patterns from `references/canonical-chains.md`. When adding new canonical chains, run `validate-chain` against each to verify the type matrix supports it.

**Test**: For each canonical chain template in `canonical-chains.md`, create a test JSON and run `validate-chain`. All must pass.

---

## Rule 14: Layer 2 Fixes Only

**Evidence**: Three-Layer Pattern from A/B testing (`adr/pipeline-creator-ab-test.md`). Layer 1 (artifact fix) teaches the system nothing — the same error recurs next generation. Layer 2 (generator fix) propagates to all future pipelines.

**REQUIRED**: When a generated pipeline has a defect, fix the generator component that produced it (template, rule, step menu, or composition logic) — never the generated artifact directly. Then regenerate to validate the fix.

**BANNED**: Editing generated skill files directly to fix issues. Always trace back to the generation link that introduced the problem.

---

## Rule 15: Cross-Reference Before Create

**Evidence**: Post-mortem of self-improving pipeline generator build. Every specification inconsistency (ASSESS family, REFINE output type, canonical chain disagreements, observation consumes) had the same root cause: an agent created a component from a task summary instead of reading the authoritative source documents.

**REQUIRED**: Every agent creating or modifying a component MUST:

1. **Read the ADR** — the single source of truth for the pipeline being built
2. **Read every document the new component depends on** — not summaries, not descriptions, the actual files
3. **Cross-validate output against source documents** — verify that every type, family, step name, and schema reference matches the authoritative source
4. **Cite sources** — the component's ADR entry must list which documents were read during creation

**BANNED**: Creating a component from a task description or summary alone. Every component must be traceable to the authoritative source documents it references.

**BANNED**: Delegating component creation to an agent with "build X that does Y" instructions. Instead, provide the agent with explicit file paths to read and cross-reference requirements.

**Test**: After creating any component, grep it for step names, schema types, and family names. Every one must appear identically in the authoritative source (step-menu.md for steps, pipeline-spec-format.md for schemas).

---

## Rule 16: Single Source of Truth Chain

**Evidence**: Same post-mortem. Four documents defined step families (step-menu.md, pipeline-spec-format.md, canonical-chains.md, artifact-utils.py). They disagreed on ASSESS, BRAINSTORM, NORMALIZE, EXTRACT, and REFINE because each was written independently without cross-referencing the others.

**REQUIRED**: When the same concept appears in multiple documents, exactly one is the authoritative source. All others derive from it.

| Concept | Authoritative Source | Derived Locations |
|---------|---------------------|-------------------|
| Step definitions (name, family, output, consumes) | `step-menu.md` | `pipeline-spec-format.md` Step Name enum, `artifact-utils.py` STEP_FAMILIES |
| Type compatibility matrix | `step-menu.md` Type Compatibility Matrix | `pipeline-spec-format.md` Step Family table, `artifact-utils.py` TYPE_COMPAT |
| Canonical chain templates | `canonical-chains.md` | `pipeline-spec-format.md` Task Type table |
| Artifact schema definitions | `pipeline-spec-format.md` Output Schema enum | `artifact-utils.py` VALID_SCHEMAS |
| Architecture constraints | `architecture-rules.md` | All generated skills and domain references |
| Operator profiles | `pipeline-spec-format.md` Operator Profile enum | `hooks/operator-context-detector.py` |

**Process for updates**:
1. Update the authoritative source FIRST
2. Propagate to ALL derived locations in the SAME session
3. Run `validate-chain` against all canonical chains to confirm consistency
4. Never update a derived location without updating the authoritative source

**BANNED**: Updating a derived location (e.g., artifact-utils.py TYPE_COMPAT) without simultaneously updating the authoritative source (step-menu.md Type Compatibility Matrix).

---

## Rule 17: Mandatory Read List for Component Creation

**Evidence**: Same post-mortem. Agents that read the source documents produced correct output. Agents that worked from summaries produced inconsistencies.

**REQUIRED**: Before creating any component, the creating agent MUST read these files (not summaries — the actual files):

### For Skills
| File | Why |
|------|-----|
| The pipeline ADR | Single source of truth for this pipeline |
| `step-menu.md` | Authoritative step definitions — verify every step name and family |
| `pipeline-spec-format.md` | Contract for step objects, schema types, validation rules |
| `canonical-chains.md` | Canonical chain templates — verify chain matches template |
| `architecture-rules.md` | Constraints that apply to all generated components |
| Every existing component it references | Prevent drift from existing implementations |

### For Domain References
| File | Why |
|------|-----|
| The pipeline ADR | Context and decisions |
| The owning skill's `SKILL.md` and Reference Loading Table | Where the reference is loaded and which signals load it |
| `architecture-rules.md` | Constraints |
| Every skill that loads it | Verify skill references are accurate |

### For Overlay Agents (owner-requested only)
| File | Why |
|------|-----|
| The pipeline ADR | Context and decisions |
| `skills/meta/toolkit/references/skill-creator/agent-template.md` | Required structure |
| `architecture-rules.md` | Constraints |
| Every skill it pairs with | Verify skill references are accurate |

### For Scripts (validators, utilities)
| File | Why |
|------|-----|
| The pipeline ADR | Context |
| `step-menu.md` | Authoritative type definitions to encode |
| Every document that defines types/schemas the script validates | Ensure validator matches spec |

**BANNED**: "I'll create this from the task description" — every component requires reading the mandatory files above.

**Anti-Rationalization**: "The mandatory read list is overkill for a simple component" → The simple components are where inconsistencies hide. Follow the list regardless of perceived complexity.

---

## Rule 18: ADR Hash Required in Pipeline Specs

Every Pipeline Spec JSON produced by `chain-composer` MUST include:
- `adr_path`: path to the ADR that governs this pipeline (relative to repo root)
- `adr_hash`: sha256 hash of that ADR computed at composition time via `adr-query.py hash`

**Verification**: The `pipeline-scaffolder` Phase 1 gate runs:
```bash
python3 ~/.claude/scripts/adr-query.py verify --adr {spec.adr_path} --hash {spec.adr_hash}
```
If exit 1 (hash mismatch): STOP. The ADR changed after composition. Re-run `chain-composer` with the updated ADR before scaffolding.

**Compliance check**: After creating any component, verify against authoritative sources:
```bash
python3 ~/.claude/scripts/adr-compliance.py check --file {file} \
  --step-menu skills/process/workflow/references/pipeline-scaffolder/references/step-menu.md \
  --spec-format skills/process/workflow/references/pipeline-scaffolder/references/pipeline-spec-format.md
```

BANNED: Pipeline Specs without `adr_path` and `adr_hash` fields when generated via the self-improving pipeline generator.
