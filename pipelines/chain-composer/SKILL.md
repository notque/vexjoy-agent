---
name: chain-composer
description: |
  Compose valid pipeline chains from the step menu for each subdomain in a
  Component Manifest. Validates type compatibility using artifact-utils.py.
  Produces Pipeline Spec JSON as the intermediate representation consumed by
  pipeline-scaffolder. Use when domain-research has completed and produced a
  Component Manifest with subdomains and task types. Do NOT use for scaffolding
  (that is pipeline-scaffolder), domain discovery (that is domain-research), or
  modifying existing pipelines.
version: 1.0.0
user-invocable: false
agent: pipeline-orchestrator-engineer
model: opus
allowed-tools:
  - Read
  - Write
  - Bash
  - Grep
  - Glob
  - Edit
routing:
  triggers:
    - compose chains
    - build pipeline chains
    - chain composition
    - pipeline spec
    - compose pipeline
  pairs_with:
    - pipeline-scaffolder
    - domain-research
  complexity: Medium
  category: meta
---

# Chain Composer Skill

## Operator Context

This skill operates as an operator for pipeline chain composition, configuring Claude's behavior for selecting, ordering, and validating pipeline steps into coherent chains. It implements a **Type-Safe Composition** pattern: read the step menu, select steps by task type, apply operator profile gates, validate type compatibility with a deterministic script, and produce a machine-readable Pipeline Spec.

### Hardcoded Behaviors (Always Apply)
- **CLAUDE.md Compliance**: Read and follow repository CLAUDE.md files before execution. Project instructions override default skill behaviors.
- **Over-Engineering Prevention**: Compose the simplest chain that satisfies the task type. Do not add steps "for completeness" or "in case they need it." Every step in a chain must have a concrete reason to be there. If a subdomain's task type maps to a 5-step canonical chain, don't pad it to 8 steps.
- **Deterministic Validation**: Chain correctness is verified by `python3 scripts/artifact-utils.py validate-chain`, not by LLM self-assessment. The script checks type compatibility, composition rules, ADR-first, and terminal steps. If the script says INVALID, the chain is invalid regardless of how logical it looks.
- **No Duplication**: The step menu lives in `pipelines/pipeline-scaffolder/references/step-menu.md`. The pipeline spec format lives in `pipelines/pipeline-scaffolder/references/pipeline-spec-format.md`. Reference them; do not copy their content into the Pipeline Spec or into this skill's output.
- **Operator Profile Enforcement**: Every chain must be modified by the operator profile from the Component Manifest. Personal chains are lean. Production chains have maximum gates. Skipping profile application produces chains that are unsafe (production) or bloated (personal).

### Default Behaviors (ON unless disabled)
- **Communication Style**: Report composition decisions concisely. Show chain visualizations (step arrows) rather than describing them in prose.
- **Temporary File Cleanup**: Remove `/tmp/pipeline-{run-id}/chain-*.json` validation fragments after Phase 3 completes. Keep only the final Pipeline Spec.
- **Canonical Chain Starting Point**: Always start from the canonical chain template for the task type (see `references/canonical-chains.md`), then adapt. Do not compose chains from scratch -- the canonical templates encode hard-won composition patterns.
- **Chain Visualization**: When reporting chains, use the arrow format: `ADR -> RESEARCH -> COMPILE -> GENERATE -> VALIDATE -> OUTPUT`.

### Optional Behaviors (OFF unless enabled)
- **Verbose Composition Log**: Show step-by-step reasoning for each composition decision (step selection, profile gate application, domain-specific additions)
- **Alternative Chain Generation**: Produce 2-3 alternative chains per subdomain with tradeoff analysis

## What This Skill CAN Do

- Compose valid pipeline chains for any task type in the step menu (generation, review, debugging, operations, configuration, analysis, migration, testing)
- Apply operator profile gates (personal, work, CI, production) to modify chains
- Add domain-specific steps (LINT, CONFORM, TEMPLATE, DELEGATE) when the subdomain requires them
- Validate all chains using `scripts/artifact-utils.py validate-chain` deterministically
- Produce a complete Pipeline Spec JSON following `pipeline-spec-format.md`
- Iterate on failed chains (max 3 attempts per chain) to fix type incompatibilities

## What This Skill CANNOT Do

- **Scaffold pipeline components**: That is `pipeline-scaffolder`. This skill only produces the Pipeline Spec; it does not create agents, skills, hooks, or scripts.
- **Discover subdomains**: That is `domain-research`. This skill consumes the Component Manifest; it does not research the domain.
- **Validate domain-specific content**: The type compatibility check is structural. Domain correctness (e.g., whether a PromQL pattern is valid) is the generated pipeline's responsibility, not this skill's.
- **Override the step menu**: All steps must come from `step-menu.md`. This skill composes from the menu; it does not invent new steps.

## Instructions

### Phase 1: LOAD (Prepare Context)

**Goal**: Load all inputs needed for composition. No composition happens in this phase -- only reading and verifying prerequisites.

**Why this phase exists**: Composition requires three inputs in context simultaneously: the Component Manifest (what to compose), the step menu (what to compose from), and the operator profile (how to modify). Loading them separately prevents context fragmentation.

**Step 1**: Read the Component Manifest from the domain-research output. This is the `content.md` from Phase 4 of the domain-research skill. Extract:
- The list of subdomains with their task types and descriptions
- The operator profile
- The agent decision (new_agent or reuse_agent)
- Per-subdomain metadata: references_needed, scripts_needed, routing_triggers

**Step 2**: Load `pipelines/pipeline-scaffolder/references/step-menu.md`. This file contains:
- Step families with output schemas and consumption rules
- The type compatibility matrix
- Composition rules (structural, profile-aware, optimization, delegation, type)
- Operator profile definitions and chain examples

**Step 3**: Load `pipelines/chain-composer/references/canonical-chains.md`. This contains the 8 canonical chain templates per task type, including common variants.

**Step 4**: Identify the operator profile from the Component Manifest. Valid profiles: `personal`, `work`, `ci`, `production`.

**Step 5**: Verify prerequisites:
- At least 2 subdomains exist (minimum from domain-research gate)
- Every subdomain has a task_type that maps to a canonical chain template
- Operator profile is one of the 4 valid values

**GATE**: Component Manifest loaded with 2+ subdomains. Step menu loaded. Canonical chains loaded. Operator profile identified and valid. Proceed to Phase 2.

---

### Phase 2: COMPOSE (Build Chains)

**Goal**: For each subdomain in the Component Manifest, compose a complete, valid pipeline chain by starting from the canonical template and adapting it.

**Why composition follows a template-then-adapt pattern**: Composing chains from scratch is error-prone -- the type compatibility matrix has 18 families with specific consumption rules, and getting the flow wrong is easy. The canonical templates encode the correct type flow for each task type. Starting from a template and adapting is more reliable than assembling step-by-step.

For each subdomain in the Component Manifest, execute Steps 1-5:

**Step 1: Select the canonical chain template**

Use the subdomain's `task_type` to select the starting template from `references/canonical-chains.md`:

| Task Type | Canonical Chain |
|-----------|----------------|
| `generation` | ADR -> RESEARCH -> COMPILE -> GENERATE -> VALIDATE -> OUTPUT |
| `review` | ADR -> RESEARCH -> ASSESS -> REVIEW (3+) -> AGGREGATE -> REPORT |
| `debugging` | ADR -> PROBE -> SEARCH -> ASSESS -> PLAN -> EXECUTE -> VERIFY -> OUTPUT |
| `operations` | ADR -> PROBE -> ASSESS -> PLAN -> GUARD -> EXECUTE -> VALIDATE -> OUTPUT |
| `configuration` | ADR -> RESEARCH -> TEMPLATE -> CONFORM -> VALIDATE -> OUTPUT |
| `analysis` | ADR -> RESEARCH -> COMPILE -> ASSESS -> SYNTHESIZE -> REPORT |
| `migration` | ADR -> CHARACTERIZE -> PLAN -> GUARD -> SNAPSHOT -> EXECUTE -> VALIDATE -> OUTPUT |
| `testing` | ADR -> RESEARCH -> CHARACTERIZE -> GENERATE -> VALIDATE -> REPORT |

**Step 2: Apply domain-specific adaptations**

Examine the subdomain's description, references_needed, and scripts_needed to determine if the canonical chain needs domain-specific steps:

- **If generating artifacts with checkable syntax** (e.g., PromQL, HCL, SQL): Insert `LINT` after `GENERATE` and before `VALIDATE`
- **If output must match an external spec** (e.g., OpenAPI, JSON Schema): Insert `CONFORM` after `GENERATE` (or after `LINT` if both apply)
- **If cross-domain expertise is needed**: Insert `DELEGATE` at the point where the other domain's pipeline is invoked
- **If the subdomain has a validation script** in `scripts_needed`: Ensure a `VALIDATE` step exists with `params.script` referencing that script
- **If a template/boilerplate is referenced** in `references_needed`: Consider replacing `GENERATE` with `TEMPLATE` or inserting `TEMPLATE` before `GENERATE`
- **If refinement is expected** (validation may fail iteratively): Insert `REFINE` after `VALIDATE` with `params.max_refine_cycles: 3`

**Step 3: Apply operator profile gates**

Modify the chain based on the operator profile from the Component Manifest. These rules come from `step-menu.md` Operator Profiles section:

**Personal profile**:
- Remove `APPROVE` and `PROMPT` steps (full autonomy)
- Reduce `GUARD` to `params.checks: ["branch-not-main"]` only
- `SIMULATE` and `SNAPSHOT` are available but not mandatory -- only include if the subdomain explicitly needs them

**Work profile**:
- Add `CONFORM` after `GENERATE` for convention checking (if not already present from domain adaptation)
- Full `GUARD -> SNAPSHOT -> EXECUTE -> VALIDATE` for any chain that modifies state
- Add `APPROVE` for production-affecting changes

**CI profile**:
- Remove all interaction steps (`PROMPT`, `APPROVE`, `PRESENT`)
- Add `NOTIFY` before `OUTPUT`/`REPORT` to send results to PR/Slack
- `GUARD` checks dependencies/tools exist, not permissions

**Production profile**:
- Add `GUARD -> SNAPSHOT` before every `EXECUTE`
- Add `SIMULATE` before `EXECUTE` for large-scale changes
- Add `APPROVE` before any dangerous operation
- Add `PRESENT` before and after `EXECUTE` for visibility

**Step 4: Construct Step objects**

For each step in the composed chain, construct the Step object per `pipeline-spec-format.md`:

```json
{
  "step": "RESEARCH",
  "family": "research-gathering",
  "output_schema": "research-artifact",
  "consumes": "decision-record",
  "params": { ... },
  "profile_gate": null
}
```

Rules for constructing Step objects:
- `family`: Look up the step in the Step Name enum in `pipeline-spec-format.md`
- `output_schema`: Look up the family in the Step Family table to find what it produces
- `consumes`: The first step (ADR) has `null`. Every other step's `consumes` is the `output_schema` of the previous substantive step. For steps after transparent steps (safety, interaction, validation), `consumes` references the last non-transparent step's output
- `params`: Populate based on the subdomain's references_needed and scripts_needed
- `profile_gate`: Set to the minimum profile required for this step (e.g., `"work"` for CONFORM added by work profile). Set to `null` for unconditional steps

**Step 5: Verify composition rules**

Before moving to the next subdomain, verify the chain satisfies the composition rules from `step-menu.md`:

- [ ] Chain starts with ADR
- [ ] Chain ends with OUTPUT, REPORT, or CLEANUP
- [ ] Research before Generation (if both present)
- [ ] Validation after Generation (if generation present)
- [ ] Characterize before Modification (if modifying existing state)
- [ ] Review is parallel with 3+ lenses (if review present)
- [ ] Pipeline Summary is terminal (nothing after OUTPUT/REPORT)
- [ ] No duplicate steps (except VALIDATE, VERIFY, CHECKPOINT)

**GATE**: Every subdomain has a complete chain. All chains follow composition rules. All Step objects have valid family, output_schema, and consumes fields. Proceed to Phase 3.

---

### Phase 3: VALIDATE (Deterministic Chain Checking)

**Goal**: Validate all chains using `scripts/artifact-utils.py validate-chain`. This is the critical quality gate -- it catches type incompatibilities that visual inspection misses.

**Why deterministic validation is mandatory**: The type compatibility matrix has complex rules: transparent steps pass through primary data flow, safety steps wrap rather than replace, and some steps appear in multiple families with different semantics (e.g., EXECUTE is in git-release, LINT is in both validation and domain-extension). The script handles all these edge cases correctly. LLM judgment is not sufficient -- it will rationalize subtle type mismatches as "close enough."

**Step 1**: Create a temporary directory for validation artifacts:
```bash
mkdir -p /tmp/pipeline-{run-id}
```

**Step 2**: For each subdomain chain, write a validation fragment. The `validate-chain` command expects a JSON array of `{"step": "...", "schema": "..."}` objects:

```bash
cat > /tmp/pipeline-{run-id}/chain-{subdomain-name}.json << 'EOF'
[
  {"step": "ADR", "schema": "decision-record"},
  {"step": "RESEARCH", "schema": "research-artifact"},
  {"step": "COMPILE", "schema": "structured-corpus"},
  {"step": "GENERATE", "schema": "generation-artifact"},
  {"step": "VALIDATE", "schema": "verdict"},
  {"step": "OUTPUT", "schema": "pipeline-summary"}
]
EOF
```

**Step 3**: Run the validator for each chain:
```bash
python3 scripts/artifact-utils.py validate-chain /tmp/pipeline-{run-id}/chain-{subdomain-name}.json
```

**Step 4**: Handle validation results:

- **If VALID**: Mark the chain as validated. Move to the next subdomain.
- **If INVALID**: Read the error output. Common failures:
  - Type incompatibility: step N expects input from {schemas}, but primary data flow is {schema}
  - Missing ADR start or terminal step
  - Schema mismatch: family produces X but declared schema is Y
  - Potential cycle: duplicate steps at unexpected positions

**Step 5**: If any chain fails validation, fix the composition error in Phase 2 and re-validate. Track the iteration count per chain.

- **Maximum 3 iterations per chain**. If a chain fails validation 3 times, STOP and report the persistent failure to the user with the specific type incompatibility. Do not guess at fixes beyond 3 attempts -- the chain template may need human review.

**Step 6**: After all chains pass, clean up temporary validation fragments:
```bash
rm -f /tmp/pipeline-{run-id}/chain-*.json
```

**GATE**: All chains pass `validate-chain` with exit code 0. Zero type incompatibilities. Proceed to Phase 4.

---

### Phase 4: PRODUCE (Pipeline Spec)

**Goal**: Produce the complete Pipeline Spec JSON and a human-readable summary. The Pipeline Spec is the contract that `pipeline-scaffolder` consumes.

**Why the Pipeline Spec is JSON, not markdown**: The scaffolder needs machine-readable data to derive build targets (skills, references, scripts, agents, routing). JSON is the contract format defined in `pipeline-spec-format.md`. The human-readable summary is a companion, not a replacement.

**Step 1**: Load `pipelines/pipeline-scaffolder/references/pipeline-spec-format.md` for the exact format contract. Verify every field requirement against what you will produce.

**Step 1a**: Compute the ADR hash for integrity binding:
```bash
python3 scripts/adr-query.py hash --adr {adr_path}
```
Record the output (e.g., `sha256:abc123...`). This value is included as `adr_hash` in the top-level Pipeline Spec to enable the scaffolder's ADR integrity check.

**Step 2**: For each subdomain, construct the subdomain object:

```json
{
  "name": "{subdomain-name}",
  "task_type": "{task_type}",
  "description": "{from Component Manifest}",
  "chain": [/* Step objects from Phase 2 */],
  "skill_name": "{domain}-{subdomain-function}",
  "pairs_with_agent": "{from Component Manifest}",
  "references_needed": [/* from Component Manifest */],
  "scripts_needed": [/* from Component Manifest */],
  "routing_triggers": [/* from Component Manifest */]
}
```

Naming rules:
- `skill_name` follows `{domain}-{function}` pattern per Rule 8 from architecture-rules.md
- Validate with regex: `^[a-z][a-z0-9]*(-[a-z][a-z0-9]*)+$`

**Step 3**: Construct the top-level Pipeline Spec:

```json
{
  "pipeline_name": "{domain}-pipeline",
  "domain": "{domain}",
  "adr_path": "{path_to_adr}",
  "adr_hash": "sha256:{hash_from_adr-query.py}",
  "subdomains": [/* subdomain objects from Step 2 */],
  "shared_references": [/* from Component Manifest */],
  "new_agent": {/* or null */},
  "reuse_agent": "{or null}",
  "operator_profile": "{profile}"
}
```

Top-level validation:
- Exactly one of `new_agent` or `reuse_agent` is non-null
- `operator_profile` is a valid profile enum value
- `subdomains` is non-empty

**Step 4**: Write the Pipeline Spec to the run directory:
```bash
cat > /tmp/pipeline-{run-id}/pipeline-spec.json << 'SPEC'
{json content}
SPEC
```

**Step 5**: Run a final validation pass on every subdomain chain within the spec. For each subdomain, extract its chain and validate:
```bash
python3 scripts/artifact-utils.py validate-chain /tmp/pipeline-{run-id}/final-chain-{name}.json
```

This redundant validation catches any errors introduced during the spec construction step (e.g., copy errors in Step object assembly).

**Step 6**: Produce the dual-layer artifact:

**Layer 1 (manifest.json)**:
```bash
python3 scripts/artifact-utils.py create-manifest \
  --schema generation-artifact --step PRODUCE --phase 4 --status complete \
  --outputs content.md pipeline-spec.json \
  --inputs component-manifest.md \
  --tags {domain} pipeline-spec chain-composition
```

**Layer 2 (content.md)**: Human-readable summary with:

```markdown
# Pipeline Spec: {domain}

## Operator Profile: {profile}

## Agent Decision
{Reuse/Create} agent: {agent-name}
Rationale: {from Component Manifest}

## Subdomain Chains

### {subdomain-1-name} ({task_type})
```
ADR -> STEP -> STEP -> ... -> OUTPUT
```
Steps: {count} | Profile gates: {count} | Domain-specific: {list}

### {subdomain-2-name} ({task_type})
```
ADR -> STEP -> STEP -> ... -> REPORT
```
Steps: {count} | Profile gates: {count} | Domain-specific: {list}

## Validation
All {N} chains passed `validate-chain`.
Total steps across all chains: {total}
```

**GATE**: Pipeline Spec JSON exists at `/tmp/pipeline-{run-id}/pipeline-spec.json`. All chains pass final `validate-chain`. Content summary generated. Handoff to `pipeline-scaffolder`.

## Error Handling

### Error: Type Incompatibility in Chain
**Cause**: A step's output schema does not match the next step's expected input. Common when inserting domain-specific steps (LINT, CONFORM) that change the type flow.
**Solution**: Check the type compatibility matrix. Transparent steps (GUARD, SNAPSHOT, VALIDATE, LINT, CONFORM, APPROVE) produce side-effect records but pass through the primary data type. The step *after* a transparent step consumes the same type as the step *before* it. Rebuild the `consumes` chain accounting for transparency.

### Error: Unknown Task Type
**Cause**: The Component Manifest contains a `task_type` that does not map to any canonical chain template.
**Solution**: Valid task types are: `generation`, `review`, `debugging`, `operations`, `configuration`, `analysis`, `migration`, `testing`. If the subdomain's workflow doesn't fit any of these, ask the user to classify it. Do not invent a new task type.

### Error: Validation Script Returns Exit Code 1 After 3 Iterations
**Cause**: The chain has a structural type incompatibility that iterative fixing cannot resolve. Usually happens when the canonical template itself needs modification for an unusual subdomain.
**Solution**: STOP. Report the specific `validate-chain` error output to the user. Include the chain visualization and the exact step where type incompatibility occurs. The user may need to provide guidance on the correct step ordering for this subdomain.

### Error: Component Manifest Missing Required Fields
**Cause**: The domain-research output is incomplete -- missing task_type, operator_profile, or subdomain list.
**Solution**: Do not proceed with partial data. Report which fields are missing and request that the domain-research phase be re-run or the manifest be completed manually.

### Error: Operator Profile Not Detected
**Cause**: The Component Manifest does not specify an operator_profile.
**Solution**: Default to `personal` profile (most permissive, fewest gates). Log a warning that profile was defaulted. This avoids blocking the pipeline but may produce under-gated chains for work/production environments.

## Anti-Patterns

### Hardcoding Chains Instead of Composing
**What it looks like**: Writing a fixed chain for a subdomain without consulting the canonical template or step menu.
**Why wrong**: Hardcoded chains bypass the type compatibility system. They work by coincidence until the step menu evolves and the hardcoded types no longer align. They also miss operator profile gates.
**Do instead**: Always start from the canonical chain template for the task type, then adapt with domain-specific steps and profile gates. The template encodes the correct type flow.

### Skipping Deterministic Validation
**What it looks like**: Composing chains in Phase 2 and proceeding directly to Phase 4 output without running `validate-chain`.
**Why wrong**: The type compatibility matrix has 18 families with specific rules. Transparent steps, primary data flow pass-through, and multi-family steps (LINT, EXECUTE, TEMPLATE) create subtle edge cases. LLM self-assessment will rationalize type mismatches as acceptable.
**Do instead**: Always run `python3 scripts/artifact-utils.py validate-chain` for every chain. The script is the source of truth.

### Padding Chains with Unnecessary Steps
**What it looks like**: A personal-profile `generation` chain that includes GUARD, SNAPSHOT, APPROVE, PRESENT, and CONFORM "for safety."
**Why wrong**: Over-gated chains waste execution time and context. Operator profiles exist precisely to prevent this -- personal profiles are lean by design. Adding production-grade gates to personal chains violates the profile contract.
**Do instead**: Apply exactly the gates specified by the operator profile. Personal = minimal gates. Production = maximum gates. No more, no less.

### Producing Markdown Instead of JSON
**What it looks like**: Writing the Pipeline Spec as a markdown document with chain visualizations but no JSON.
**Why wrong**: The scaffolder consumes JSON. It parses field names, iterates subdomain arrays, and extracts step objects programmatically. Markdown is for humans; JSON is the machine contract.
**Do instead**: Always produce `pipeline-spec.json` following `pipeline-spec-format.md` exactly. The `content.md` companion is for human readability, not for the scaffolder.

## Anti-Rationalization

| Rationalization Attempt | Why It's Wrong | Required Action |
|------------------------|----------------|-----------------|
| "The chain looks correct, no need to run validate-chain" | Visual inspection misses transparent step pass-through and multi-family step resolution | Run `validate-chain` for every chain, no exceptions |
| "This subdomain is simple, I can compose from scratch" | Even simple chains need correct type flow; canonical templates guarantee it | Start from canonical template, then adapt |
| "Adding extra safety steps won't hurt" | Extra steps bloat execution, waste context, and violate profile contracts | Apply only the gates specified by the operator profile |
| "The type mismatch is minor, the scaffolder can handle it" | The scaffolder rejects invalid specs; it does not fix them | Fix all type incompatibilities before producing the spec |
| "I'll fix the Pipeline Spec format later" | The spec is a contract; partial compliance means the scaffolder rejects it | Follow `pipeline-spec-format.md` exactly from the start |
| "Three validation failures means the template is wrong" | Three failures means your adaptation broke the type flow; re-examine your domain-specific insertions | Review each insertion point for type compatibility before retrying |

## Blocker Criteria

STOP and ask the user (do NOT proceed autonomously) when:

| Situation | Why Stop | Ask This |
|-----------|----------|----------|
| Component Manifest has fewer than 2 subdomains | Minimum subdomain count not met; domain-research may be incomplete | "The manifest has only {N} subdomain(s). Re-run domain-research or proceed with {N}?" |
| A subdomain's task_type has no canonical template | Cannot compose without a starting point | "Subdomain '{name}' has task_type '{type}' which has no canonical chain. How should I classify it?" |
| A chain fails validate-chain 3 times | Structural issue beyond iterative fixing | "Chain for '{subdomain}' fails validation after 3 attempts. Error: {error}. How should I restructure it?" |
| Operator profile conflicts with subdomain requirements | E.g., production subdomain under personal profile | "Subdomain '{name}' involves production state changes but profile is 'personal'. Override to 'work' or 'production'?" |

### Never Guess On
- Which operator profile to apply (must come from Component Manifest or user)
- Whether to create a new agent vs. reuse (must come from Component Manifest)
- The correct task_type for an ambiguous subdomain (ask the user)
- Whether a validation failure is a false positive (trust the script)

## References

- **Canonical Chains**: [references/canonical-chains.md](references/canonical-chains.md) -- 8 task-type templates with variants
- **Artifact Utils Script**: `scripts/artifact-utils.py validate-chain` -- Deterministic chain validator
