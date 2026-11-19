---
description: "Scaffold pipeline components from a Pipeline Spec JSON."
user-invocable: false
allowed-tools:
  - Read
  - Write
  - Bash
  - Grep
  - Glob
  - Edit
  - Agent
routing:
  triggers:
    - scaffold pipeline
    - create pipeline components
    - generate pipeline from spec
  pairs_with:
    - chain-composer
    - pipeline-test-runner
  complexity: Medium
  category: meta
---

# Pipeline Scaffolder Skill

## Overview

This skill operates as the build engine of the self-improving pipeline generator. It consumes a Pipeline Spec JSON (produced by `chain-composer`) and scaffolds all components: one domain reference (bound or new), N skills (one per subdomain), N sets of reference files, optional scripts, optional hooks, and routing entries for all N skills. Repo agents are retired (plan 009), so the scaffolder writes no repo agent file; a dispatched phase runs on a fresh `general-purpose` worker told which skill reference to load. It implements a **Spec-Driven Fan-Out** pattern: parse the spec, validate it, fan out skill creation per subdomain, integrate into routing.

The skill MUST read and follow repository CLAUDE.md files before execution (project instructions override default behaviors). It ONLY accepts Pipeline Spec JSON as input—no freestyle scaffolding, no manual component manifests, no "just create a skill" requests. The spec is a validated, type-checked contract; freestyle scaffolding produces orphan components and type mismatches.

## Instructions

### Phase 1: LOAD (Parse Pipeline Spec)

**Goal**: Load the Pipeline Spec JSON, validate it against the format contract, and compute the full set of components to create.

**Step 1**: Read the Pipeline Spec JSON. This is typically saved by `chain-composer` at a known path (passed as input to this skill or found in the ADR).

**Step 2**: Validate the spec against `references/pipeline-spec-format.md`. The spec is the only valid input contract—pass invalid specs back to `chain-composer` for correction rather than fixing them here. Check:

Top-level:
- [ ] Exactly one of `new_agent` or `reuse_agent` is non-null; `reuse_agent` is `general-purpose` unless the owner named a private overlay agent
- [ ] `operator_profile` is a valid enum value (`personal`, `work`, `ci`, `production`)
- [ ] `subdomains` is non-empty
- [ ] `domain` is lowercase kebab-case

Per subdomain:
- [ ] Chain starts with ADR step (`family: "invariant"`) — every generated skill MUST include Phase 0: ADR as its first instruction phase to prevent context drift and provide grading artifacts
- [ ] Chain ends with terminal step (`output_schema: "pipeline-summary"`)
- [ ] Type compatibility holds for all adjacent steps
- [ ] `skill_name` matches pattern `^[a-z][a-z0-9]*(-[a-z][a-z0-9]*)+$`
- [ ] `pairs_with_agent` equals the top-level worker type (`reuse_agent` or `new_agent.name`)
- [ ] `routing_triggers` is non-empty
- [ ] Every `params.script` reference exists in `scripts_needed`
- [ ] Every `params.rules` / `params.template` reference exists in `references_needed` or `shared_references`

**Step 3**: Verify the worker type and the domain reference. `reuse_agent` must be a built-in agent type (`general-purpose` by default) or a private overlay agent listed in `agents/INDEX.local.json`; a retired repo agent name makes the spec invalid, so STOP. If `domain_reference` is non-null, verify the file exists under `skills/`; if it does not, STOP—the spec is invalid. Trust the spec: if `domain_reference` is set, upstream chain-composer already determined reuse is appropriate rather than fragmenting expertise across a new reference (Rule 9: Reuse Over Recreation).

**Step 4**: Compute build targets from the spec:

```
Skills to create    = spec.subdomains[*].skill_name
References to create = union(spec.shared_references, spec.subdomains[*].references_needed)
Scripts to create   = union(spec.subdomains[*].scripts_needed)
Domain reference    = spec.domain_reference (bind), else the new shared domain reference
Worker type         = spec.reuse_agent (general-purpose by default)
Overlay agent       = spec.new_agent (owner-requested private agent only)
Routing entries     = spec.subdomains[*].routing_triggers (per skill)
```

**Step 5**: Count and report planned components:
- N skills (one per subdomain)
- 1 domain reference (bound or new); 0 repo agents (0 or 1 overlay agent, owner-requested only)
- Total unique reference files
- Total unique scripts
- Total routing trigger entries

**Step 6: Verify ADR Integrity** (if spec contains `adr_hash` field)

If the spec has an `adr_hash` field:
```bash
python3 ~/.claude/scripts/adr-query.py verify \
  --adr {spec.adr_path} \
  --hash {spec.adr_hash}
```

- **Exit 0**: ADR matches—proceed with scaffolding
- **Exit 1**: ADR has changed since composition—STOP

If exit 1: Pause scaffolding. The ADR changed after this Pipeline Spec was composed, so the spec may now be inconsistent with the current ADR. Required action: Re-run `chain-composer` with the updated ADR to produce a fresh Pipeline Spec, then re-run scaffolder.

If `adr_hash` field is absent from the spec: Log a warning and continue (older pipeline specs may not have this field).

**Gate**: Pipeline Spec loaded and valid. All validation checks pass. ADR integrity verified (or hash absent—warning logged). Component count established. Proceed to Phase 2.

### Phase 2: BIND OR WRITE THE DOMAIN REFERENCE

**Goal**: Give every subdomain skill one home for the domain expertise. In the repo that home is a skill reference, never an agent.

**Decision logic**:
- If `domain_reference` is non-null: bind it. Log: "Binding domain reference: {domain_reference}". Each generated skill names it in its Reference Loading Table and lists its skill in `pairs_with`.
- If `domain_reference` is null: write the shared domain reference listed in `shared_references` (for example `{domain}-domain-knowledge.md`).
- If `new_agent` is non-null (the owner asked for a private overlay agent): also follow "Overlay agent (owner-requested only)" below.

**When writing a new domain reference**:

**Step 1**: Write the reference with the domain's description, expertise list (3-6 items), CAN / CANNOT table that names the owning skill or reference for out-of-scope work, error handling (3+ categories), preferred patterns, and blocker criteria. Keep it under the size limit that `python3 scripts/validate-references.py --check-size` enforces; move depth into a `references/{domain}/` subdirectory.

**Step 2**: Name the reference in each subdomain skill's Reference Loading Table, with signals drawn from the domain triggers.

**Overlay agent (owner-requested only)**: a private agent never ships in the repo. Write it at `private-agents/{new_agent.name}.md` and index it into `agents/INDEX.local.json` with `python3 scripts/generate-agent-index.py --include-private`. These steps apply only to that overlay agent:

**Step 1**: Read `skills/meta/toolkit/references/skill-creator/agent-template.md` for the structural template. Every overlay agent MUST follow this template to ensure structural consistency, which enables automated validation and routing integration.

**Step 2**: Generate the agent file with:
- YAML frontmatter: name, version, description (with 3 examples), color, routing metadata
- `routing.triggers` from `new_agent.triggers`
- `routing.pairs_with` listing ALL subdomain skill names from the spec—incomplete pairs_with means the agent can't be discovered for all subdomains
- `routing.complexity` from `new_agent.complexity`
- `routing.category` from `new_agent.category`
- Operator declaration with `new_agent.expertise` items
- Operator Context (Hardcoded, Default, Optional behaviors)
- Capabilities & Limitations
- Instructions section referencing the subdomain skills
- Error Handling (3+ categories)
- Blocker Criteria
- References section

**Step 3**: If `new_agent.complexity` is Medium or higher, create `private-agents/{new_agent.name}/references/` directory.

**Step 4**: Validate the overlay agent:
- [ ] All required agent-template sections present
- [ ] Main file under 10,000 words—no monolithic prompts. If content exceeds this limit, move detail to `references/` subdirectory
- [ ] `pairs_with` lists all N subdomain skill names
- [ ] Naming follows `{domain}-{function}-engineer` pattern
- [ ] Agent appears in `agents/INDEX.local.json`

**Gate**: Domain reference bound or written and validated (and the overlay agent indexed, when one was requested). Proceed to Phase 3.

### Phase 3: SCAFFOLD SKILLS (Fan-Out—one per subdomain)

**Goal**: Create all N subdomain skills using the generated-skill-template, plus their reference files and scripts. Template compliance ensures every skill MUST be generated from `references/generated-skill-template.md`.

**Step 0: Load the template**. Read `references/generated-skill-template.md` once. This contains:
- The SKILL.md template with `{{variable}}` placeholders
- The chain-to-phase mapping (how each step family becomes a phase section)
- Task type default errors and failure modes

**Fan-out strategy**:
- For simple chains (3-4 steps): batch 2-3 subdomain skills per sub-agent
- For complex chains (5+ steps): dispatch one sub-agent per subdomain
- Maximum 10 parallel sub-agents (system limit)
- Each sub-agent receives: the Pipeline Spec, the generated-skill-template, and architecture rules to enforce on every component before generation

**For each subdomain** (whether batched or individual):

**Step 1: Fill template variables** from the subdomain object:
- `{{skill_name}}` from `subdomain.skill_name`
- `{{domain}}` from top-level `domain`
- `{{subdomain_name}}` from `subdomain.name`
- `{{task_type}}` from `subdomain.task_type`
- `{{description}}` from `subdomain.description`
- `{{agent_name}}` from the worker type (`reuse_agent` or `new_agent.name`; `general-purpose` by default); not written to frontmatter
- `{{pairs_with}}` from the skill that holds the domain reference (`assemble-skill.py --pairs-with`)

After assembly, add a Reference Loading Table row to each generated skill that names the domain reference (`domain_reference`, or the new shared domain reference); the template has no placeholder for it.
- `{{routing_triggers_csv}}` from joining `subdomain.routing_triggers`
- `{{operator_profile_*}}` flags from top-level `operator_profile`—respect the profile field to include or exclude safety/interaction steps based on profile (personal profiles skip APPROVE gates; production profiles require them)

**Step 2: Convert chain steps to phases**. For each step in `subdomain.chain`:

Map from step family to phase implementation using the chain-to-phase mapping in the template:

| Step Family | Phase Template | Key Customizations |
|-------------|---------------|-------------------|
| `invariant` | Phase 0: ADR | Always first. Uses domain + subdomain in ADR path. |
| `research-gathering` | Parallel Multi-Agent | `params.agents` count, `params.aspects` labels, `params.timeout_minutes`. MANDATORY: Use parallel multi-agent dispatch per Rule 12, validated by A/B test (sequential research loses 1.40 points on Examples quality, 0.60 on Completeness). |
| `structuring` | Compile/Organize | Structures research into hierarchy |
| `decision-planning` | Plan/Decide | Options, criteria, selection rationale |
| `generation` | Generate | `params.template` reference, `params.voice` if applicable |
| `validation` | Validate | `params.script` name, `params.max_refine_cycles` limit |
| `review` | Parallel Reviewers | `params.reviewers` count, `params.lenses` focus areas |
| `domain-extension` | Lint/Conform/Template | `params.linter`, `params.rules` reference |
| `safety-guarding` | Guard/Snapshot | `params.checks` list, `params.block_on_failure`, `profile_gate` |
| `interaction` | Prompt/Approve/Notify | Only included when `profile_gate` matches `operator_profile` |
| `synthesis-reporting` | Output/Report | Always terminal. Produces pipeline-summary artifact. |
| `observation` | Monitor/Probe | Runtime checks against live systems |
| `orchestration` | Delegate/Converge | `params.target_pipeline`, `params.pass_artifacts` |
| `learning-retro` | Walk/Merge/Gate/Apply | Retro extraction phases |
| `comparison-evaluation` | Compare/Benchmark | A/B or before/after metrics |

For steps with `profile_gate` set: include the phase only if the gate matches the spec's `operator_profile` or is less restrictive. Annotate conditional phases with a profile gate notice.

**Step 3: Generate error handling**. Use the task type default errors from the template. Include at minimum 3 error entries per skill.

**Step 4: Create the skill file** at `skills/{skill_name}/SKILL.md`. All skills MUST use consistent naming: group-prefix (e.g., `voice-`, `go-`, `pr-`, `writing-`, `review-`) matching related existing skills. Before naming, check `ls skills/ | grep {domain}` to find the group. If no group exists, the new skill starts one. No naming convention violations.

**Step 5: Create reference files** for each entry in `subdomain.references_needed`:
- Create directory `skills/{skill_name}/references/` if it doesn't exist
- For each file in `references_needed`:
  - If it also appears in `shared_references`, copy from the shared source
  - If subdomain-specific, create a stub file with a header, purpose section, and placeholder content structure appropriate to the domain
- Symlink or reference `architecture-rules.md` from `pipeline-scaffolder/references/`

**Step 6: Create scripts** for each entry in `subdomain.scripts_needed`:
- Generate at `scripts/{filename}` with:
  - `#!/usr/bin/env python3` shebang
  - Module docstring with purpose, caller, usage
  - `argparse` CLI with relevant subcommands for the domain—all scripts use argparse for consistency and discoverability; this is not optional
  - JSON output format
  - Exit codes: 0 = success, 1 = error
  - Validation logic stubs appropriate to the artifact type
  - No LLM calls—scripts are deterministic operations

**Validation per skill** (before proceeding to next subdomain):
- [ ] YAML frontmatter has all required fields (name, description, version, user-invocable, allowed-tools; `agent` only when the skill sets `context: fork`)
- [ ] Phase 0 is ADR
- [ ] Phase gates exist between all phases
- [ ] The Reference Loading Table names the domain reference, and any dispatched phase tells its `general-purpose` worker which reference to load
- [ ] All `references_needed` files exist in `skills/{skill_name}/references/`
- [ ] Research-gathering phases use parallel multi-agent dispatch (Rule 12 is not negotiable—validated by A/B test)

**Gate**: All N skill files exist. All reference files exist. All scripts exist. Each skill passed per-skill validation. Proceed to Phase 4.

### Phase 4: INTEGRATE

**Goal**: Wire all components into routing and verify the full component dependency graph. Unroutable skills are dead code (Rule 7—not negotiable).

**Step 1: Routing integration**. Call the Skill tool with `toolkit` and run its Routing Tables mode. Use batch mode:
- Add all N skills to `skills/meta/do/references/routing-tables.md`
- For each skill: add trigger entries from `subdomain.routing_triggers`
- If the domain reference is new: add its triggers as signals in each skill's Reference Loading Table
- If an overlay agent was requested: regenerate `agents/INDEX.local.json` (`python3 scripts/generate-agent-index.py --include-private`)

**Step 2: Create domain manifest**. Write `commands/{domain}-pipeline.md` listing:
- Domain name and purpose
- Domain reference (bound or new) and worker type
- All N subdomain skills with their trigger keywords
- All reference files (shared and per-skill)
- All scripts
- Component dependency graph

**Step 3: Verify integration**. Check every component:

Domain reference verification:
- [ ] Domain reference file exists (bound or new)
- [ ] Every one of the N skills names it in its Reference Loading Table
- [ ] Overlay agent only: it appears in `agents/INDEX.local.json` and its `pairs_with` lists all N subdomain skill names

Skill verification (for each of N skills):
- [ ] Skill has routing entry in `skills/meta/do/references/routing-tables.md`
- [ ] Skill has no `agent` field, or `agent: general-purpose` (or the overlay agent) with `context: fork`
- [ ] Skill's description includes "Use for" with trigger keywords

Script verification (for each script):
- [ ] Script is syntactically valid Python (`python3 -c "import ast; ast.parse(open('{file}').read())"`)
- [ ] Script is referenced by at least one skill's chain (no dead scripts)

Cross-cutting:
- [ ] No orphan components (every component referenced by at least one other)
- [ ] No naming convention violations (group-prefix consistency, domain-function pattern)
- [ ] No dual-responsibility components

**Gate**: All components routable via `/do`. Integration verified. No orphans. Proceed to Phase 5.

### Phase 5: REPORT

**Goal**: Produce the scaffolding completion report as a dual-layer artifact.

**Step 1: Create manifest.json**:
```json
{
  "schema": "pipeline-summary",
  "step": "REPORT",
  "domain": "{domain}",
  "operator_profile": "{profile}",
  "components": {
    "domain_reference": "{path} (new|bound)",
    "agent": "{agent_name}",
    "skills": ["{skill_1}", "{skill_2}", ...],
    "references": ["{ref_1}", "{ref_2}", ...],
    "scripts": ["{script_1}", ...],
    "routing_entries": {total_count}
  },
  "validation": {
    "spec_valid": true,
    "all_skills_created": true,
    "all_references_created": true,
    "all_scripts_valid": true,
    "routing_integrated": true,
    "no_orphans": true
  }
}
```

**Step 2: Create content.md** with:

```markdown
# Scaffolding Report: {domain}

## Component Inventory

| Type | Count | Names |
|------|-------|-------|
| Domain reference | 1 | {path} ({new or bound}) |
| Worker type | 1 | {general-purpose, or overlay agent name} |
| Skills | {N} | {list} |
| References | {M} | {list} |
| Scripts | {J} | {list} |
| Routing entries | {K} | {count per skill} |

## Per-Subdomain Summary

### {subdomain_1.name}
- Skill: `{skill_name}`
- Chain: ADR -> {step_2} -> ... -> OUTPUT
- Triggers: {routing_triggers}
- References: {ref_list}
- Scripts: {script_list}

### {subdomain_2.name}
...

## Domain Reference Decision
{Rationale for binding an existing reference vs. writing a new one}

## Usage Examples

To invoke each generated skill:
- `/do {trigger_phrase_1}` -> routes to `{skill_1}` (loads `{domain_reference}`)
- `/do {trigger_phrase_2}` -> routes to `{skill_2}` (loads `{domain_reference}`)
```

**Gate**: Report artifacts exist. Scaffolding complete.

## Error Handling

### Error: Invalid Pipeline Spec
**Cause**: The spec fails validation in Phase 1—missing fields, type incompatibilities, invalid enums, or constraint violations. Specs are contracts; return them to `chain-composer` for correction rather than fixing during scaffolding.
**Solution**: Return the specific validation failure with the field path and expected value. This is `chain-composer`'s responsibility. Report the error to the orchestrator so it can re-invoke chain composition.

### Error: Worker or Domain Reference Not Found
**Cause**: `reuse_agent` names a retired repo agent or an overlay agent missing from `agents/INDEX.local.json`, or `domain_reference` names a file that does not exist.
**Solution**: STOP. This is a spec error. The worker type and the domain reference must resolve before the scaffolder can bind skills to them. Report to orchestrator. Either the name is wrong (typo or retired agent) or domain research missed the reference.

### Error: Template Section Missing
**Cause**: A generated skill is missing a required section (frontmatter field, Phase 0 ADR, gate between phases).
**Solution**: Re-read `references/generated-skill-template.md` and regenerate the skill. If the issue is in the chain-to-phase mapping (unsupported step family), add a mapping entry and regenerate.

### Error: Script Syntax Invalid
**Cause**: A generated Python script fails `ast.parse()`.
**Solution**: Re-generate the script skeleton. Scripts are simple argparse CLIs—syntax errors usually mean a template variable was not substituted. Check for remaining `{{variable}}` markers.

### Error: Naming Convention Violation
**Cause**: A component name doesn't follow group-prefix pattern (`{domain}-{function}` for skills, `{domain}-{function}-engineer` for overlay agents).
**Solution**: Rename the component. The `skill_name` field in the spec should already be validated, so this error usually means a manual override went wrong.

### Error: Orphan Component
**Cause**: A reference file or script exists but is not referenced by any skill's chain.
**Solution**: Either the spec has an unused entry in `references_needed`/`scripts_needed`, or the chain-to-phase mapping failed to include the reference. Check the spec for consistency (validation rules should have caught this in Phase 1).

### Error: Monolithic Single Skill Created
**Cause**: Creating one skill for the entire domain instead of N skills (one per subdomain).
**Solution**: This violates the spec. Monolithic skills dilute expertise, overload context, and can't be routed independently. Each subdomain has different task types needing different pipeline chains. Follow the spec—one skill per subdomain entry, same domain reference, different methodology.

### Error: Freestyle Scaffolding Attempted
**Cause**: Creating skills without a Pipeline Spec JSON—"just make a skill for X".
**Solution**: Without the spec, there is no validated chain, no type checking, no consistent structure. The result is skills that fail to integrate with the pipeline system. Always require a Pipeline Spec JSON. If one is missing, use this action: Call the Skill tool with `workflow`. Run the `chain-composer` pipeline first.

### Error: Routing Integration Skipped
**Cause**: All skill files exist but `routing-table-updater` was not run.
**Solution**: Unroutable skills are dead code (Rule 7—not negotiable). Users and the `/do` router can't discover them. Phase 4 integration is mandatory. Every skill must be routable before scaffolding is considered complete.

## References

- **Pipeline Spec Format**: [references/pipeline-spec-format.md](references/pipeline-spec-format.md)—the input contract
- **Generated Skill Template**: [references/generated-skill-template.md](references/generated-skill-template.md)—template for each subdomain skill
- **Architecture Rules**: [references/architecture-rules.md](references/architecture-rules.md)—rules to enforce on all components
- **Step Menu**: [references/step-menu.md](references/step-menu.md)—valid steps and type compatibility
- **Agent Template**: [../../../meta/toolkit/references/skill-creator/agent-template.md](../../../meta/toolkit/references/skill-creator/agent-template.md)—template for an owner-requested private overlay agent only
