---
name: pipeline-scaffolder
description: |
  Scaffold pipeline components from a Pipeline Spec JSON: N subdomain skills,
  0-1 agents, reference files, scripts, hooks, and routing entries. Consumes
  output from chain-composer skill. Use for "scaffold pipeline", "create
  pipeline components", "generate pipeline from spec", or "build pipeline
  skills". Do NOT use for modifying existing pipelines, creating standalone
  agents, ad-hoc skill creation, or domain research.
version: 2.0.0
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
  - Agent
---

# Pipeline Scaffolder Skill

## Operator Context

This skill operates as the build engine of the self-improving pipeline generator. It consumes a Pipeline Spec JSON (produced by `chain-composer`) and scaffolds all components: 0-1 agents, N skills (one per subdomain), N sets of reference files, optional scripts, optional hooks, and routing entries for all N skills. It implements a **Spec-Driven Fan-Out** pattern -- parse the spec, validate it, fan out skill creation per subdomain, integrate into routing.

### Hardcoded Behaviors (Always Apply)
- **CLAUDE.md Compliance**: Read and follow repository CLAUDE.md files before execution. Project instructions override default skill behaviors.
- **Pipeline Spec Required**: The ONLY valid input is a Pipeline Spec JSON conforming to `references/pipeline-spec-format.md`. No freestyle scaffolding, no manual component manifests, no "just create a skill" requests. WHY: The spec is a validated, type-checked contract. Freestyle scaffolding produces orphan components and type mismatches.
- **Architecture Rules Enforcement**: Before generating any component, load and enforce all rules from `references/architecture-rules.md`. Every generated component must pass every rule.
- **Template Compliance**: Every agent MUST follow `AGENT_TEMPLATE_V2.md`. Every skill MUST be generated from `references/generated-skill-template.md`. WHY: Templates ensure structural consistency, which enables automated validation and routing integration.
- **No Monolithic Prompts**: Agent prompts MUST NOT exceed 10,000 words. If content exceeds this limit, move detail to `references/` subdirectory.
- **ADR Cascade**: Every generated skill MUST include Phase 0: ADR as its first instruction phase. WHY: ADRs prevent context drift across phases and provide grading artifacts for retrospectives. The ADR mandate cascades from generator to generated.
- **ADR Hash Verification**: Before scaffolding, verify the ADR has not been modified since session registration: `python3 scripts/adr-query.py verify --adr {adr_path} --hash {hash}`. If verification fails (exit 1), stop and re-register. Check `adr-query.py list` for related ADRs during discovery.
- **Parallel Research Enforcement**: When a generated skill's chain includes a research-gathering step, the generated phase MUST use parallel multi-agent dispatch per Rule 12. WHY: A/B testing proved sequential research loses 1.40 points on Examples quality versus parallel dispatch.

### Default Behaviors (ON unless disabled)
- **Communication Style**: Report facts without self-congratulation. Show generated file paths, component counts, and key decisions rather than describing them.
- **Temporary File Cleanup**: Remove any intermediate generation files. Keep only the final pipeline components.
- **Naming Convention**: Agents follow `{domain}-{function}-engineer` pattern. Skills use `{group}-{function}`. Hooks use `{pipeline-name}-detector.py`. Scripts use `{domain}-{function}.py`.
- **Group-Prefix Consistency**: New skills MUST use the same prefix as related existing skills. Before naming, check `ls skills/ | grep {domain}` to find the group. Examples: voice skills start with `voice-`, Go skills with `go-`, PR skills with `pr-`, writing/content skills with `writing-`, review skills with `review-`. If no group exists, the new skill starts one.
- **Profile-Aware Generation**: Respect the `operator_profile` field from the Pipeline Spec. Include or exclude safety/interaction steps based on the profile. WHY: Personal profiles don't need APPROVE gates; production profiles require them. Over-gating personal workflows adds friction; under-gating production workflows creates risk.

### Optional Behaviors (OFF unless enabled)
- **Reference File Generation**: Generate `references/anti-patterns.md` for new agents (ON for Complex agents, OFF for Simple).
- **Hook Test Generation**: Create a basic test script alongside any generated hook.
- **Dry Run Mode**: Parse and validate the spec, show planned components, but don't create files.

## What This Skill CAN Do
- Parse and validate Pipeline Spec JSON against the format contract
- Generate N subdomain skills (one per subdomain entry) from the generated-skill-template
- Generate 0-1 domain agents following AGENT_TEMPLATE_V2.md
- Generate Python scripts with argparse CLI skeletons for each `scripts_needed` entry
- Generate reference file stubs for each `references_needed` entry
- Copy or symlink shared references into each skill's references directory
- Convert chain steps to numbered skill phases using the chain-to-phase mapping
- Wire all components into routing via `routing-table-updater`
- Validate the full component dependency graph (no orphans, correct bindings)

## What This Skill CANNOT Do
- **Generate domain-specific business logic**: Scaffolded components are structural; domain logic comes from domain agents or the Pipeline Spec's chain definitions
- **Modify routing tables directly**: Routing updates are delegated to `routing-table-updater`
- **Compose pipeline chains**: Chain composition is handled by `chain-composer` upstream
- **Validate chain type compatibility**: Use `scripts/artifact-utils.py validate-chain` before invoking this skill

## Instructions

### Phase 1: LOAD (Parse Pipeline Spec)

**Goal**: Load the Pipeline Spec JSON, validate it against the format contract, and compute the full set of components to create.

**Step 1**: Read the Pipeline Spec JSON. This is typically saved by `chain-composer` at a known path (passed as input to this skill or found in the ADR).

**Step 2**: Validate the spec against `references/pipeline-spec-format.md`. Check:

Top-level:
- [ ] Exactly one of `new_agent` or `reuse_agent` is non-null
- [ ] `operator_profile` is a valid enum value (`personal`, `work`, `ci`, `production`)
- [ ] `subdomains` is non-empty
- [ ] `domain` is lowercase kebab-case

Per subdomain:
- [ ] Chain starts with ADR step (`family: "invariant"`)
- [ ] Chain ends with terminal step (`output_schema: "pipeline-summary"`)
- [ ] Type compatibility holds for all adjacent steps
- [ ] `skill_name` matches pattern `^[a-z][a-z0-9]*(-[a-z][a-z0-9]*)+$`
- [ ] `pairs_with_agent` references the correct agent
- [ ] `routing_triggers` is non-empty
- [ ] Every `params.script` reference exists in `scripts_needed`
- [ ] Every `params.rules` / `params.template` reference exists in `references_needed` or `shared_references`

**Step 3**: If `reuse_agent` is non-null, verify the agent exists in `agents/INDEX.json`. If it does not exist, STOP -- the spec is invalid.

**Step 4**: Compute build targets from the spec:

```
Skills to create    = spec.subdomains[*].skill_name
References to create = union(spec.shared_references, spec.subdomains[*].references_needed)
Scripts to create   = union(spec.subdomains[*].scripts_needed)
Agent to create     = spec.new_agent (if non-null)
Agent to bind       = spec.reuse_agent (if non-null)
Routing entries     = spec.subdomains[*].routing_triggers (per skill)
```

**Step 5**: Count and report planned components:
- N skills (one per subdomain)
- 0 or 1 agent
- Total unique reference files
- Total unique scripts
- Total routing trigger entries

**Step 6: Verify ADR Integrity** (if spec contains `adr_hash` field)

If the spec has an `adr_hash` field:
```bash
python3 scripts/adr-query.py verify \
  --adr {spec.adr_path} \
  --hash {spec.adr_hash}
```

- **Exit 0**: ADR matches — proceed with scaffolding
- **Exit 1**: ADR has changed since composition — STOP

If exit 1: Do NOT proceed. The ADR changed after this Pipeline Spec was composed. The spec may now be inconsistent with the current ADR. Required action: Re-run `chain-composer` with the updated ADR to produce a fresh Pipeline Spec, then re-run scaffolder.

If `adr_hash` field is absent from the spec: Log a warning and continue (older pipeline specs may not have this field).

**Gate**: Pipeline Spec loaded and valid. All validation checks pass. ADR integrity verified (or hash absent — warning logged). Component count established. Proceed to Phase 2.

### Phase 2: SCAFFOLD AGENT (if needed)

**Goal**: Create the domain agent if no existing agent covers the domain.

**Decision logic**:
- If `reuse_agent` is non-null: **SKIP this phase**. The existing agent is the executor. Log: "Reusing agent: {reuse_agent}".
- If `new_agent` is non-null: Create the agent.

**When creating a new agent**:

**Step 1**: Read `AGENT_TEMPLATE_V2.md` for the structural template.

**Step 2**: Generate the agent file at `agents/{new_agent.name}.md` with:
- YAML frontmatter: name, version, description (with 3 examples), color, routing metadata
- `routing.triggers` from `new_agent.triggers`
- `routing.pairs_with` listing ALL subdomain skill names from the spec
- `routing.complexity` from `new_agent.complexity`
- `routing.category` from `new_agent.category`
- Operator declaration with `new_agent.expertise` items
- Operator Context (Hardcoded, Default, Optional behaviors)
- Capabilities & Limitations
- Instructions section referencing the subdomain skills
- Error Handling (3+ categories)
- Anti-Patterns (3+ items)
- Anti-Rationalization table
- Blocker Criteria
- References section

**Step 3**: If `new_agent.complexity` is Medium or higher, create `agents/{new_agent.name}/references/` directory.

**Step 4**: Validate the agent:
- [ ] All 10 required AGENT_TEMPLATE_V2 sections present
- [ ] Main file under 10,000 words
- [ ] `pairs_with` lists all N subdomain skill names
- [ ] Naming follows `{domain}-{function}-engineer` pattern

**Gate**: Either existing agent confirmed in INDEX.json, or new agent file created and validated. Proceed to Phase 3.

### Phase 3: SCAFFOLD SKILLS (Fan-Out -- one per subdomain)

**Goal**: Create all N subdomain skills using the generated-skill-template, plus their reference files and scripts.

**Step 0: Load the template**. Read `references/generated-skill-template.md` once. This contains:
- The SKILL.md template with `{{variable}}` placeholders
- The chain-to-phase mapping (how each step family becomes a phase section)
- Task type default errors and anti-patterns

**Fan-out strategy**:
- For simple chains (3-4 steps): batch 2-3 subdomain skills per sub-agent
- For complex chains (5+ steps): dispatch one sub-agent per subdomain
- Maximum 10 parallel sub-agents (system limit)
- Each sub-agent receives: the Pipeline Spec, the generated-skill-template, and architecture rules

**For each subdomain** (whether batched or individual):

**Step 1: Fill template variables** from the subdomain object:
- `{{skill_name}}` from `subdomain.skill_name`
- `{{domain}}` from top-level `domain`
- `{{subdomain_name}}` from `subdomain.name`
- `{{task_type}}` from `subdomain.task_type`
- `{{description}}` from `subdomain.description`
- `{{agent_name}}` from the agent decision (`reuse_agent` or `new_agent.name`)
- `{{routing_triggers_csv}}` from joining `subdomain.routing_triggers`
- `{{operator_profile_*}}` flags from top-level `operator_profile`

**Step 2: Convert chain steps to phases**. For each step in `subdomain.chain`:

Map from step family to phase implementation using the chain-to-phase mapping in the template:

| Step Family | Phase Template | Key Customizations |
|-------------|---------------|-------------------|
| `invariant` | Phase 0: ADR | Always first. Uses domain + subdomain in ADR path. |
| `research-gathering` | Parallel Multi-Agent | `params.agents` count, `params.aspects` labels, `params.timeout_minutes` |
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

**Step 4: Generate anti-patterns**. Use the task type default anti-patterns from the template. Include at minimum 3 anti-pattern entries per skill.

**Step 5: Create the skill file** at `skills/{skill_name}/SKILL.md`.

**Step 6: Create reference files** for each entry in `subdomain.references_needed`:
- Create directory `skills/{skill_name}/references/` if it doesn't exist
- For each file in `references_needed`:
  - If it also appears in `shared_references`, copy from the shared source
  - If subdomain-specific, create a stub file with a header, purpose section, and placeholder content structure appropriate to the domain
- Symlink or reference `architecture-rules.md` from `pipeline-scaffolder/references/`

**Step 7: Create scripts** for each entry in `subdomain.scripts_needed`:
- Generate at `scripts/{filename}` with:
  - `#!/usr/bin/env python3` shebang
  - Module docstring with purpose, caller, usage
  - `argparse` CLI with relevant subcommands for the domain
  - JSON output format
  - Exit codes: 0 = success, 1 = error
  - Validation logic stubs appropriate to the artifact type
  - No LLM calls -- scripts are deterministic

**Validation per skill** (before proceeding to next subdomain):
- [ ] YAML frontmatter has all required fields (name, description, version, user-invocable, agent, allowed-tools)
- [ ] Phase 0 is ADR
- [ ] Phase gates exist between all phases
- [ ] `agent` field references the correct agent
- [ ] All `references_needed` files exist in `skills/{skill_name}/references/`
- [ ] Research-gathering phases use parallel multi-agent dispatch (Rule 12)

**Gate**: All N skill files exist. All reference files exist. All scripts exist. Each skill passed per-skill validation. Proceed to Phase 4.

### Phase 4: INTEGRATE

**Goal**: Wire all components into routing and verify the full component dependency graph.

**Step 1: Routing integration**. Invoke `routing-table-updater` in batch mode:
- Add all N skills to `skills/do/references/routing-tables.md`
- Add the agent (if new) to `agents/INDEX.json`
- For each skill: add trigger entries from `subdomain.routing_triggers`
- If the agent is new: add agent trigger entries from `new_agent.triggers`

**Step 2: Create domain manifest**. Write `commands/{domain}-pipeline.md` listing:
- Domain name and purpose
- Agent (new or reused) with trigger keywords
- All N subdomain skills with their trigger keywords
- All reference files (shared and per-skill)
- All scripts
- Component dependency graph

**Step 3: Verify integration**. Check every component:

Agent verification:
- [ ] Agent appears in `agents/INDEX.json` (new or existing)
- [ ] Agent's `pairs_with` lists all N subdomain skill names

Skill verification (for each of N skills):
- [ ] Skill has routing entry in `skills/do/references/routing-tables.md`
- [ ] Skill's `agent` field references the correct agent
- [ ] Skill's description includes "Use for" with trigger keywords

Script verification (for each script):
- [ ] Script is syntactically valid Python (`python3 -c "import ast; ast.parse(open('{file}').read())"`)
- [ ] Script is referenced by at least one skill's chain (no dead scripts)

Cross-cutting:
- [ ] No orphan components (every component referenced by at least one other)
- [ ] No naming convention violations (Rule 8)
- [ ] No dual-responsibility components (Rule 1)

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
    "agent": "{agent_name} (new|reused)",
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
| Agent | {0 or 1} | {name} ({new or reused}) |
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

## Agent Decision
{Rationale for reuse vs. new agent creation}

## Usage Examples

To invoke each generated skill:
- `/do {trigger_phrase_1}` -> routes to `{skill_1}` via `{agent_name}`
- `/do {trigger_phrase_2}` -> routes to `{skill_2}` via `{agent_name}`
```

**Gate**: Report artifacts exist. Scaffolding complete.

## Error Handling

### Error: Invalid Pipeline Spec
**Cause**: The spec fails validation in Phase 1 -- missing fields, type incompatibilities, invalid enums, or constraint violations.
**Solution**: Return the specific validation failure with the field path and expected value. Do NOT attempt to fix the spec -- that is `chain-composer`'s responsibility. Report the error to the orchestrator so it can re-invoke chain composition.

### Error: Agent Not Found
**Cause**: `reuse_agent` references an agent name not present in `agents/INDEX.json`.
**Solution**: STOP. This is a spec error. The agent must exist before the scaffolder can bind skills to it. Report to orchestrator. Either the agent name is wrong (typo) or domain research missed it.

### Error: Template Section Missing
**Cause**: A generated skill is missing a required section (frontmatter field, Phase 0 ADR, gate between phases).
**Solution**: Re-read `references/generated-skill-template.md` and regenerate the skill. If the issue is in the chain-to-phase mapping (unsupported step family), add a mapping entry and regenerate.

### Error: Script Syntax Invalid
**Cause**: A generated Python script fails `ast.parse()`.
**Solution**: Re-generate the script skeleton. Scripts are simple argparse CLIs -- syntax errors usually mean a template variable was not substituted. Check for remaining `{{variable}}` markers.

### Error: Naming Convention Violation
**Cause**: A component name doesn't follow the pattern from Rule 8 (`{domain}-{function}` for skills, `{domain}-{function}-engineer` for agents).
**Solution**: Rename the component. The `skill_name` field in the spec should already be validated, so this error usually means a manual override went wrong.

### Error: Orphan Component
**Cause**: A reference file or script exists but is not referenced by any skill's chain.
**Solution**: Either the spec has an unused entry in `references_needed` / `scripts_needed`, or the chain-to-phase mapping failed to include the reference. Check the spec for consistency (validation rules 10 and 11 should have caught this in Phase 1).

## Anti-Patterns

### Anti-Pattern 1: Monolithic Single Skill
**What it looks like**: Creating one skill for the entire domain instead of N skills (one per subdomain).
**Why wrong**: Monolithic skills dilute expertise, overload context, and can't be routed independently. Each subdomain has different task types needing different pipeline chains.
**Do instead**: Follow the spec -- one skill per subdomain entry. Same agent, different methodology.

### Anti-Pattern 2: Freestyle Scaffolding
**What it looks like**: Creating skills without a Pipeline Spec JSON -- "just make a skill for X".
**Why wrong**: Without the spec, there is no validated chain, no type checking, no consistent structure. The result is skills that don't integrate with the pipeline system.
**Do instead**: Always require a Pipeline Spec JSON. If one doesn't exist, route to `chain-composer` first.

### Anti-Pattern 3: Skip Routing Integration
**What it looks like**: Creating all skill files but not running `routing-table-updater`.
**Why wrong**: Unroutable skills are dead code (Rule 7). Users and the `/do` router can't discover them.
**Do instead**: Phase 4 integration is not optional. Every skill must be routable before scaffolding is considered complete.

### Anti-Pattern 4: Copy Agent When Reuse Works
**What it looks like**: Creating a new agent when `reuse_agent` is set -- "the new one will be more specialized".
**Why wrong**: Violates Rule 9 (Reuse Over Recreation). If an existing agent covers 70%+ of the domain, binding new skills to it is better than fragmenting expertise across agents.
**Do instead**: Trust the spec. If `reuse_agent` is non-null, the upstream chain-composer already determined reuse is appropriate.

### Anti-Pattern 5: Sequential Research in Generated Skills
**What it looks like**: Generating a skill whose research phase uses sequential grep/search instead of parallel agents.
**Why wrong**: A/B-tested loss: -1.40 points on Examples quality, -0.60 on Completeness (see `adr/pipeline-creator-ab-test.md`). Sequential research creates tunnel vision.
**Do instead**: Every research-gathering step in the chain MUST generate a parallel multi-agent phase. Use the template's chain-to-phase mapping for research families.

## Anti-Rationalization

| Rationalization Attempt | Why It's Wrong | Required Action |
|------------------------|----------------|-----------------|
| "This spec is close enough, I'll fix it during scaffolding" | Spec is the contract. Fixing it here means chain-composer has a bug. | Reject and return to chain-composer |
| "One skill can handle two subdomains" | Spec says N subdomains = N skills. Merging violates the design. | Follow the spec exactly |
| "This subdomain is too simple for a full skill" | Even simple subdomains need routing, ADR cascade, and phase gates. | Scaffold it anyway |
| "I'll add routing later" | Unroutable = dead code. Rule 7 is not negotiable. | Integrate in Phase 4 |
| "Sequential research is fine for this domain" | Rule 12 is validated by A/B test, not opinion. | Use parallel research |
| "The agent doesn't need all N skills in pairs_with" | Incomplete pairs_with means the agent can't be discovered for all subdomains. | List all N skills |
| "This script doesn't need argparse, it's simple" | All scripts use argparse for consistency and discoverability. | Add argparse CLI |

## References

- **Pipeline Spec Format**: [references/pipeline-spec-format.md](references/pipeline-spec-format.md) -- the input contract
- **Generated Skill Template**: [references/generated-skill-template.md](references/generated-skill-template.md) -- template for each subdomain skill
- **Architecture Rules**: [references/architecture-rules.md](references/architecture-rules.md) -- rules to enforce on all components
- **Step Menu**: [references/step-menu.md](references/step-menu.md) -- valid steps and type compatibility
- **Agent Template**: [../../AGENT_TEMPLATE_V2.md](../../AGENT_TEMPLATE_V2.md) -- template for new agents
