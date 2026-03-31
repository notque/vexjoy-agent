---
name: chain-composer
description: "Compose valid pipeline chains from the step menu per subdomain."
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

## Overview

This skill composes valid pipeline chains for each subdomain in a Component Manifest. It reads the step menu, selects and orders steps by task type, applies operator profile gates (personal, work, CI, production), validates type compatibility using a deterministic script (`artifact-utils.py validate-chain`), and produces a machine-readable Pipeline Spec JSON consumed by `pipeline-scaffolder`.

**Core pattern**: template-then-adapt. Start from a canonical chain template for the task type (which encodes correct type flow), then inject domain-specific steps and operator profile gates. This is more reliable than composing from scratch because the type compatibility matrix has 18 families with specific consumption rules, and the canonical templates already encode the correct flow.

---

## Instructions

### Phase 1: LOAD (Prepare Context)

**Goal**: Load all inputs needed for composition. No composition happens in this phase -- only reading and verifying prerequisites.

**Why this phase exists**: Composition requires three inputs in context simultaneously: the Component Manifest (what to compose), the step menu (what to compose from), and the operator profile (how to modify). Loading them separately prevents context fragmentation.

**Step 1**: Read the Component Manifest from the domain-research output. This is the `content.md` from Phase 4 of the domain-research skill. Extract:
- The list of subdomains with their task types and descriptions
- The operator profile
- The agent decision (new_agent or reuse_agent)
- Per-subdomain metadata: references_needed, scripts_needed, routing_triggers

**Step 2**: Load `skills/workflow/references/pipeline-scaffolder/references/step-menu.md`. This file contains:
- Step families with output schemas and consumption rules
- The type compatibility matrix
- Composition rules (structural, profile-aware, optimization, delegation, type)
- Operator profile definitions and chain examples

**Step 3**: Load `skills/workflow/references/chain-composer/references/canonical-chains.md`. This contains the 8 canonical chain templates per task type, including common variants.

**Step 4**: Identify the operator profile from the Component Manifest. Valid profiles: `personal`, `work`, `ci`, `production`.

**Step 5**: Verify prerequisites:
- At least 2 subdomains exist (minimum from domain-research gate)
- Every subdomain has a task_type that maps to a canonical chain template
- Operator profile is one of the 4 valid values

**Gate**: Component Manifest loaded with 2+ subdomains. Step menu loaded. Canonical chains loaded. Operator profile identified and valid. Proceed to Phase 2.

---

### Phase 2: COMPOSE (Build Chains)

**Goal**: For each subdomain in the Component Manifest, compose a complete, valid pipeline chain by starting from the canonical template and adapting it.

**Why composition follows a template-then-adapt pattern**: Composing chains from scratch is error-prone. The canonical templates encode the correct type flow for each task type. Starting from a template and adapting is more reliable than assembling step-by-step. *Constraint: Always start from the canonical chain template for the task type, then adapt. Do not compose chains from scratch.*

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

**Constraint: Unknown task_type is a blocker.** If the Component Manifest contains a `task_type` that does not map to any canonical chain template, STOP and ask the user to classify it. Valid task types are the 8 listed above. Do not invent a new task type.

**Step 2: Apply domain-specific adaptations**

Examine the subdomain's description, references_needed, and scripts_needed to determine if the canonical chain needs domain-specific steps:

- **If generating artifacts with checkable syntax** (e.g., PromQL, HCL, SQL): Insert `LINT` after `GENERATE` and before `VALIDATE`. *Reason: syntax errors must be caught before validation.*
- **If output must match an external spec** (e.g., OpenAPI, JSON Schema): Insert `CONFORM` after `GENERATE` (or after `LINT` if both apply). *Reason: conformance to spec is a prerequisite to validation.*
- **If cross-domain expertise is needed**: Insert `DELEGATE` at the point where the other domain's pipeline is invoked. *Reason: enables sequential execution across domain boundaries.*
- **If the subdomain has a validation script** in `scripts_needed`: Ensure a `VALIDATE` step exists with `params.script` referencing that script. *Reason: ties generated artifacts to deterministic validation.*
- **If a template/boilerplate is referenced** in `references_needed`: Consider replacing `GENERATE` with `TEMPLATE` or inserting `TEMPLATE` before `GENERATE`. *Reason: templates encode domain knowledge that should run before generation.*
- **If refinement is expected** (validation may fail iteratively): Insert `REFINE` after `VALIDATE` with `params.max_refine_cycles: 3`. *Reason: limits iteration cost while permitting recovery from validation failures.*

*Constraint: Compose the simplest chain that satisfies the task type. Do not add steps "for completeness" or "in case they need it." Every step in a chain must have a concrete reason to be there.* If the subdomain doesn't explicitly require a step, don't add it.

**Step 3: Apply operator profile gates**

Modify the chain based on the operator profile from the Component Manifest. These rules come from `step-menu.md` Operator Profiles section:

**Personal profile** (most permissive, fewest gates):
- Remove `APPROVE` and `PROMPT` steps (full autonomy)
- Reduce `GUARD` to `params.checks: ["branch-not-main"]` only
- `SIMULATE` and `SNAPSHOT` are available but not mandatory -- only include if the subdomain explicitly needs them

**Work profile** (moderate gates):
- Add `CONFORM` after `GENERATE` for convention checking (if not already present from domain adaptation)
- Full `GUARD -> SNAPSHOT -> EXECUTE -> VALIDATE` for any chain that modifies state
- Add `APPROVE` for production-affecting changes

**CI profile** (automated, no interaction):
- Remove all interaction steps (`PROMPT`, `APPROVE`, `PRESENT`)
- Add `NOTIFY` before `OUTPUT`/`REPORT` to send results to PR/Slack
- `GUARD` checks dependencies/tools exist, not permissions

**Production profile** (maximum gates):
- Add `GUARD -> SNAPSHOT` before every `EXECUTE`
- Add `SIMULATE` before `EXECUTE` for large-scale changes
- Add `APPROVE` before any dangerous operation
- Add `PRESENT` before and after `EXECUTE` for visibility

*Constraint: Apply exactly the gates specified by the operator profile. Personal = minimal gates. Production = maximum gates. No more, no less. Do NOT add production-grade gates to personal chains or vice versa.*

**Constraint: Operator profile must come from Component Manifest or user.** If the Component Manifest does not specify an operator_profile, default to `personal` profile (most permissive, fewest gates) and log a warning that profile was defaulted.

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
- `consumes`: The first step (ADR) has `null`. Every other step's `consumes` is the `output_schema` of the previous substantive step. *Constraint: For steps after transparent steps (safety, interaction, validation), `consumes` references the last non-transparent step's output.* This is because transparent steps pass through the primary data flow.
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

*Constraint: Chain correctness is verified by `python3 ~/.claude/scripts/artifact-utils.py validate-chain`, not by LLM self-assessment. The script checks type compatibility, composition rules, ADR-first, and terminal steps. If the script says INVALID, the chain is invalid regardless of how logical it looks.*

**Gate**: Every subdomain has a complete chain. All chains follow composition rules. All Step objects have valid family, output_schema, and consumes fields. Proceed to Phase 3.

---

### Phase 3: VALIDATE (Deterministic Chain Checking)

**Goal**: Validate all chains using `scripts/artifact-utils.py validate-chain`. This is the critical quality gate -- it catches type incompatibilities that visual inspection misses.

**Why deterministic validation is mandatory**: The type compatibility matrix has complex rules: transparent steps pass through primary data flow, safety steps wrap rather than replace, and some steps appear in multiple families with different semantics (e.g., EXECUTE is in git-release, LINT is in both validation and domain-extension). The script handles all these edge cases correctly. *Constraint: LLM judgment is not sufficient. The script is the source of truth. Trust the script over visual inspection.*

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
python3 ~/.claude/scripts/artifact-utils.py validate-chain /tmp/pipeline-{run-id}/chain-{subdomain-name}.json
```

**Step 4**: Handle validation results:

- **If VALID**: Mark the chain as validated. Move to the next subdomain.
- **If INVALID**: Read the error output. Common failures:
  - Type incompatibility: step N expects input from {schemas}, but primary data flow is {schema}
  - Missing ADR start or terminal step
  - Schema mismatch: family produces X but declared schema is Y
  - Potential cycle: duplicate steps at unexpected positions

**Step 5**: If any chain fails validation, fix the composition error in Phase 2 and re-validate. Track the iteration count per chain.

*Constraint: Maximum 3 iterations per chain.* If a chain fails validation 3 times, STOP and report the persistent failure to the user with the specific type incompatibility. Do not guess at fixes beyond 3 attempts -- the chain template may need human review.

**Step 6**: After all chains pass, clean up temporary validation fragments:
```bash
rm -f /tmp/pipeline-{run-id}/chain-*.json
```

**Gate**: All chains pass `validate-chain` with exit code 0. Zero type incompatibilities. Proceed to Phase 4.

---

### Phase 4: PRODUCE (Pipeline Spec)

**Goal**: Produce the complete Pipeline Spec JSON and a human-readable summary. The Pipeline Spec is the contract that `pipeline-scaffolder` consumes.

**Why the Pipeline Spec is JSON, not markdown**: *Constraint: The scaffolder needs machine-readable data to derive build targets (skills, references, scripts, agents, routing). JSON is the contract format defined in `pipeline-spec-format.md`.* The human-readable summary is a companion, not a replacement. *Constraint: Do NOT produce markdown instead of JSON. The scaffolder consumes JSON. It parses field names, iterates subdomain arrays, and extracts step objects programmatically.*

**Step 1**: Load `skills/workflow/references/pipeline-scaffolder/references/pipeline-spec-format.md` for the exact format contract. Verify every field requirement against what you will produce.

**Step 1a**: Compute the ADR hash for integrity binding:
```bash
python3 ~/.claude/scripts/adr-query.py hash --adr {adr_path}
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
- Exactly one of `new_agent` or `reuse_agent` is non-null. *Constraint: Whether to create a new agent vs. reuse must come from Component Manifest or user. Do NOT guess.*
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
python3 ~/.claude/scripts/artifact-utils.py validate-chain /tmp/pipeline-{run-id}/final-chain-{name}.json
```

This redundant validation catches any errors introduced during the spec construction step (e.g., copy errors in Step object assembly).

**Step 6**: Produce the dual-layer artifact:

**Layer 1 (manifest.json)**:
```bash
python3 ~/.claude/scripts/artifact-utils.py create-manifest \
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

**Gate**: Pipeline Spec JSON exists at `/tmp/pipeline-{run-id}/pipeline-spec.json`. All chains pass final `validate-chain`. Content summary generated. Handoff to `pipeline-scaffolder`.

---

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

## References

- **Canonical Chains**: [references/canonical-chains.md](references/canonical-chains.md) -- 8 task-type templates with variants
- **Artifact Utils Script**: `scripts/artifact-utils.py validate-chain` -- Deterministic chain validator
- **Step Menu**: [../pipeline-scaffolder/references/step-menu.md](../pipeline-scaffolder/references/step-menu.md) -- Step families, type compatibility matrix, composition rules, operator profiles
- **Pipeline Spec Format**: [../pipeline-scaffolder/references/pipeline-spec-format.md](../pipeline-scaffolder/references/pipeline-spec-format.md) -- Machine-readable contract format
- **Domain Research**: [./domain-research.md](./domain-research.md) -- Input skill that produces Component Manifest
