# Generated Skill Template

Template used by `pipeline-scaffolder` (Phase 3: SCAFFOLD) to produce one SKILL.md per
subdomain from a Pipeline Spec JSON. The scaffolder iterates over `spec.subdomains`,
fills `{{variables}}` from each subdomain object and the spec top-level, and writes the
result to `skills/{{skill_name}}/SKILL.md`.

This is a **reference file**, not a skill. It has no YAML frontmatter of its own.

---

## Variable Reference

All `{{variables}}` map to Pipeline Spec fields. See `pipeline-spec-format.md` for
authoritative field definitions.

### Direct Variables (read from spec)

| Variable | Source | Example |
|----------|--------|---------|
| `{{domain}}` | `spec.domain` | `prometheus` |
| `{{operator_profile}}` | `spec.operator_profile` | `personal` |
| `{{agent_name}}` | `spec.reuse_agent` or `spec.new_agent.name` | `prometheus-grafana-engineer` |
| `{{subdomain_name}}` | `subdomain.name` | `metrics-authoring` |
| `{{skill_name}}` | `subdomain.skill_name` | `prometheus-metrics` |
| `{{task_type}}` | `subdomain.task_type` | `generation` |
| `{{description}}` | `subdomain.description` | `Writing PromQL queries...` |
| `{{chain}}` | `subdomain.chain` | Array of Step objects |
| `{{references_needed}}` | `subdomain.references_needed` | `["promql-patterns.md"]` |
| `{{scripts_needed}}` | `subdomain.scripts_needed` | `["promql-validator.py"]` |
| `{{routing_triggers}}` | `subdomain.routing_triggers` | `["promql", "recording rule"]` |

### Derived Variables (computed by scaffolder)

| Variable | Derivation | Example |
|----------|------------|---------|
| `{{trigger_keywords}}` | Join `routing_triggers`, quote each | `"promql", "recording rule"` |
| `{{complexity}}` | Chain length: <=5 Simple, <=8 Medium, >8 Complex | `Medium` |
| `{{phase_count}}` | `len(chain)` including ADR | `7` |
| `{{skill_name_title}}` | Title-case of `skill_name` with hyphens to spaces | `Prometheus Metrics` |
| `{{subdomain_slug}}` | Kebab-case of `subdomain.name` | `metrics-authoring` |
| `{{generated_phases}}` | Chain[1..N] mapped to phase sections (see Phase Generation) | Markdown |
| `{{max_refine_cycles}}` | From REFINE step `params.max_refine_cycles`, default 3 | `3` |

---

## Template

Everything between `BEGIN TEMPLATE` and `END TEMPLATE` is the skeleton. The scaffolder
copies it verbatim, substitutes `{{variables}}`, and expands conditional blocks. Comments
in `<!-- -->` are scaffolder instructions and MUST be stripped from the final output.

<!-- BEGIN TEMPLATE -->

````markdown
---
name: {{skill_name}}
description: |
  {{description}} -- {{task_type}} pipeline for the {{domain}} domain.
  Use for {{trigger_keywords}}. Do NOT use for unrelated {{domain}} tasks
  outside the {{subdomain_name}} subdomain.
version: 1.0.0
user-invocable: true
agent: {{agent_name}}
model: opus
allowed-tools:
  - Read
  - Write
  - Bash
  - Grep
  - Glob
  - Edit
  - Task
routing:
  triggers: [{{trigger_keywords}}]
  pairs_with: [{{agent_name}}]
  complexity: {{complexity}}
  category: domain
---

# {{skill_name_title}}

## Operator Context

This skill operates as an operator for {{subdomain_name}} within the {{domain}} domain, configuring Claude's behavior for {{task_type}} workflows. It implements a **Pipeline** pattern with {{phase_count}} phases, deterministic validation gates, and dual-layer artifact output.

### Hardcoded Behaviors (Always Apply)
- **CLAUDE.md Compliance**: Read and follow repository CLAUDE.md files before execution. Project instructions override default skill behaviors.
- **Over-Engineering Prevention**: Produce only what the task requires. Do not add speculative features, optional enhancements, or content not grounded in research findings or source analysis.
- **Source-Grounded Output**: Every claim, example, or recommendation in the output must trace to research findings or direct source analysis. Hallucinated content undermines trust and misleads users.
- **ADR Mandate**: Phase 0 creates an ADR before any work begins. The ADR is re-read before every major decision to prevent context drift (Architecture Rule 10). WHY: Without a persistent reference, decisions made in Phase 1 are forgotten by Phase 5.
<!-- SCAFFOLDER: Include the next behavior ONLY if the chain contains a step with
     family "research-gathering". Check: chain.any(s => s.family == "research-gathering") -->
{{#if_has_research_step}}
- **Parallel Research Mandate**: The research phase MUST dispatch parallel agents. Sequential grep-based research is banned (Architecture Rule 12). WHY: A/B testing proved sequential research creates a 1.40-point quality gap vs parallel dispatch.
{{/if_has_research_step}}
<!-- SCAFFOLDER: Include the next behavior ONLY if any VALIDATE step has params.script.
     Check: chain.any(s => s.step == "VALIDATE" && s.params?.script) -->
{{#if_has_validation_script}}
- **Deterministic Validation**: Phase validation uses `scripts/{{validation_script}}` for machine verification. Output must pass validation before delivery. WHY: Self-assessment is unreliable; deterministic scripts catch what eyes miss.
{{/if_has_validation_script}}
<!-- SCAFFOLDER: Include operator profile behavior based on spec.operator_profile -->
{{#if operator_profile == "personal"}}
- **Operator Profile (Personal)**: Full autonomy. APPROVE and PROMPT steps are skipped. GUARD is limited to branch-check only. SIMULATE and SNAPSHOT are available but not mandatory.
{{/if}}
{{#if operator_profile == "work"}}
- **Operator Profile (Work)**: Convention-enforced. APPROVE gates for production-affecting changes. CONFORM added for organizational conventions. Full GUARD -> SNAPSHOT -> EXECUTE -> VALIDATE for state changes.
{{/if}}
{{#if operator_profile == "ci"}}
- **Operator Profile (CI)**: Fully autonomous, disposable environment. All interaction steps skipped. NOTIFY sends results to PR/Slack. GUARD checks dependencies exist, not permissions.
{{/if}}
{{#if operator_profile == "production"}}
- **Operator Profile (Production)**: Maximum gates. Full GUARD + SNAPSHOT + SIMULATE mandatory. APPROVE required before all state changes. PRESENT status before and after.
{{/if}}

### Default Behaviors (ON unless disabled)
- **Communication Style**: Report facts without self-congratulation. Show file paths, validation scores, and artifact locations.
- **Temporary File Cleanup**: Remove `/tmp/` artifacts after pipeline completion. Keep only the final output and ADR.
- **Dual-Layer Artifacts**: Every phase produces artifacts in dual-layer format: manifest.json for machine consumption, content.md for human reading.

### Optional Behaviors (OFF unless enabled)
- **Deep Mode** (`--deep`): Include extended analysis and internal architecture details
- **Quick Mode** (`--quick`): Skip research phase for draft-quality output

## What This Skill CAN Do
- Execute the full {{subdomain_name}} {{task_type}} pipeline from ADR through final output
<!-- SCAFFOLDER: For each unique step family in the chain, generate one capability line.
     Map family to capability description:
       research-gathering -> "Investigate the target via parallel multi-agent research dispatch"
       structuring -> "Structure raw findings into prioritized, cross-referenced hierarchies"
       generation -> "Produce domain-specific artifacts following templates and research"
       validation -> "Validate output deterministically against domain rules and scripts"
       review -> "Evaluate artifacts through multiple specialized review lenses"
       safety-guarding -> "Enforce safety gates with pre-condition checks and snapshots"
       decision-planning -> "Plan execution steps with dependencies, risks, and rollback procedures"
       observation -> "Probe and monitor live systems for health and behavior data"
       domain-extension -> "Apply domain-specific linting, conformance, and template rules"
       synthesis-reporting -> "Compile phase results into structured summaries and reports"
       git-release -> "Stage, commit, push, and create pull requests"
       learning-retro -> "Extract and persist learnings from pipeline execution"
       interaction -> "Gate on human approval or send notifications to external systems"
       orchestration -> "Decompose and delegate to sub-pipelines"
-->
{{#for_each_unique_family}}
- {{capability_description}}
{{/for_each_unique_family}}
- Produce dual-layer artifacts (manifest.json + content.md) at each phase
- Track progress via ADR updates at phase transitions

## What This Skill CANNOT Do
- **Handle other {{domain}} subdomains**: This skill covers {{subdomain_name}} only. Other subdomains have their own pipeline skills.
- **Replace domain expertise**: Produces structured output grounded in research, not expert judgment
- **Modify routing tables**: Use `routing-table-updater` for routing changes
- **Execute without ADR**: Phase 0 is mandatory; skipping it violates Architecture Rule 10

## Instructions

### Phase 0: ADR

**Goal**: Create a persistent reference document before work begins. WHY: The ADR prevents context drift across {{phase_count}} phases and provides a grading artifact for retrospectives.

**Step 1**: Create `adr/{{domain}}-{{subdomain_slug}}-{task-id}.md` with:
- **Context**: What task is being executed and why
- **Decision**: Which approach was chosen (include the pipeline chain: {{chain_step_names_csv}})
- **Constraints**: Operator profile is `{{operator_profile}}`. Domain rules from references apply.
- **Artifact Format**: Dual-layer (manifest.json + content.md) per phase
- **Test Plan**: How success will be verified
<!-- SCAFFOLDER: If a VALIDATE step has params.script, add the validation target:
     "Validation target: scripts/{{params.script}} must pass" -->

**Step 2**: Re-read the ADR before every major decision to prevent context drift.

**Gate**: ADR file exists at `adr/{{domain}}-{{subdomain_slug}}-{task-id}.md`. Proceed to Phase 1.

<!-- SCAFFOLDER: For each chain[i] where i > 0, generate a phase section using the
     family-specific template from the Phase Generation Rules section below.
     Phase numbering starts at 1. Skip chain[0] (the ADR step) since Phase 0
     is hardcoded above. -->

{{generated_phases}}

## Artifact Format

Every phase produces a dual-layer artifact in the pipeline working directory.

### manifest.json (Machine Layer)

```json
{
  "phase": "{{phase_name}}",
  "phase_number": {{N}},
  "skill": "{{skill_name}}",
  "domain": "{{domain}}",
  "subdomain": "{{subdomain_name}}",
  "timestamp": "ISO-8601",
  "input_schema": "{{step.consumes}}",
  "output_schema": "{{step.output_schema}}",
  "status": "complete | failed | skipped",
  "artifacts": [
    {"path": "/path/to/content.md", "type": "content", "size_bytes": 0}
  ],
  "metrics": {}
}
```

### content.md (Human Layer)

Structure varies by step family:

| Step Family | Content Structure |
|-------------|-------------------|
| research-gathering | Per-agent sections with findings and source quality notes |
| structuring | Organized hierarchy with cross-references and priorities |
| generation | Produced content with template attribution and grounding notes |
| validation | Pass/fail verdict, findings by severity, evidence citations |
| safety-guarding | Pre-conditions checked, snapshot references, simulation results |
| synthesis-reporting | Phases completed, artifacts produced, metrics, final verdict |

## Error Handling

### Error: Phase Failure
**Cause**: A phase fails to produce its expected output artifact
**Solution**: Check the phase gate criteria. If partial output exists, assess whether downstream phases can proceed with reduced input. Update the ADR with the failure and resolution. Maximum 2 retry attempts per phase before escalating to the user.

### Error: Validation Failure
**Cause**: The VALIDATE or REFINE phase produces a failing verdict
**Solution**: Enter a REFINE cycle (maximum {{max_refine_cycles}} iterations). Each cycle: (1) read the verdict to identify specific failures, (2) fix the generation artifact, (3) re-run validation. If all cycles exhausted, deliver the best-scoring output with the validation report attached. Note failures in the ADR.

### Error: Dependency Missing
**Cause**: A reference file (`references/*.md`) or script (`scripts/*.py`) does not exist
**Solution**: Check `skills/{{skill_name}}/references/` for reference files and `scripts/` for validation scripts. If a reference stub was not populated during domain research, report the gap and proceed without the missing resource. Skip validation steps that depend on a missing script.

<!-- SCAFFOLDER: Include ONLY if chain contains a research-gathering step -->
{{#if_has_research_step}}
### Error: Research Agent Timeout
**Cause**: One or more parallel research agents exceed the {{research_timeout}}-minute timeout
**Solution**: The gate requires at least {{min_research_agents}} of {{total_research_agents}} agents to complete. If fewer finish, fall back to single-agent sequential research for the missing aspects. Note reduced coverage in the output report and ADR.
{{/if_has_research_step}}

<!-- SCAFFOLDER: Include ONLY if chain contains a safety-guarding step -->
{{#if_has_safety_steps}}
### Error: Safety Gate Failure
**Cause**: A GUARD pre-condition check fails
**Solution**: Do NOT proceed past the safety gate. Report the specific check that failed, the current state, and what remediation is needed. The user must resolve the safety concern before the pipeline continues. This is non-negotiable.
{{/if_has_safety_steps}}

<!-- SCAFFOLDER: Include task-type-specific errors from the Task Type Default Errors table -->
{{#for_each_task_type_error}}
### Error: {{error_name}}
**Cause**: {{error_cause}}
**Solution**: {{error_solution}}
{{/for_each_task_type_error}}

## Anti-Patterns

### Anti-Pattern 1: Skipping the ADR
**What it looks like**: Jumping directly to Phase 1 without creating the ADR
**Why wrong**: Without the ADR, there is no persistent reference. Context drifts across phases, decisions become inconsistent, and retrospectives have no grading artifact. This violates Architecture Rule 10.
**Do instead**: Always execute Phase 0 first. The ADR is mandatory.

### Anti-Pattern 2: Delivering Without Validation
**What it looks like**: Producing output and delivering it without running the validation phase
**Why wrong**: Unvalidated output may contain errors, missing elements, or structural problems that a deterministic validation script would catch.
**Do instead**: Always run the validation phase. Fix issues found. Report the final score.

### Anti-Pattern 3: Hallucinated Content
**What it looks like**: Output contains claims, examples, or recommendations not grounded in research findings or source analysis
**Why wrong**: Hallucinated content misleads users and undermines trust in the pipeline
**Do instead**: Ground every output element in a specific research finding or source artifact. If information is unavailable, say so rather than fabricating.

<!-- SCAFFOLDER: Include ONLY if chain contains a research-gathering step -->
{{#if_has_research_step}}
### Anti-Pattern 4: Sequential Research
**What it looks like**: Running grep commands one at a time instead of dispatching parallel research agents
**Why wrong**: Sequential search produces tunnel vision. A/B testing proved parallel research eliminates a 1.40-point quality gap (Architecture Rule 12).
**Do instead**: Dispatch parallel research agents per the research phase instructions.
{{/if_has_research_step}}

<!-- SCAFFOLDER: Include task-type-specific anti-patterns from the Task Type Default
     Anti-Patterns table. Number them sequentially after the standard ones above. -->
{{#for_each_task_type_anti_pattern}}
### Anti-Pattern {{next_number}}: {{anti_pattern_name}}
**What it looks like**: {{anti_pattern_description}}
**Why wrong**: {{anti_pattern_reason}}
**Do instead**: {{anti_pattern_alternative}}
{{/for_each_task_type_anti_pattern}}

## Anti-Rationalization

These rationalizations are especially dangerous for {{task_type}} pipelines in the {{domain}} domain.

| Rationalization Attempt | Why It's Wrong | Required Action |
|------------------------|----------------|-----------------|
| "The ADR is boilerplate, I'll skip it" | ADRs prevent context drift across {{phase_count}} phases; skipping violates Rule 10 | Create the ADR. Re-read before every major decision. |
| "The output looks correct, skip validation" | Looking correct is not being correct; scripts catch what eyes miss | Run validation. Fix issues. Report the score. |
| "This is obvious, no need to research" | Obvious to whom? Research breadth determines quality | Run the research phase fully. |
| "One retry is enough" | Retry limits prevent loops, not effort | Use all allowed retries before escalating. |
| "The user wants it fast, skip the safety gate" | Safety gates exist because consequences of skipping > delay | Honor the gate. Report why it blocks. |
| "I'll fix manually instead of re-running" | Manual fixes bypass validation and artifact tracking | Re-run the phase with upstream corrections. |

## References

- **Architecture Rules**: `skills/workflow/references/pipeline-scaffolder/references/architecture-rules.md`
- **Step Menu**: `skills/workflow/references/pipeline-scaffolder/references/step-menu.md`
- **Anti-Rationalization Patterns**: `skills/shared-patterns/anti-rationalization-core.md`
<!-- SCAFFOLDER: For each file in references_needed + shared_references, add a reference line -->
{{#for_each_reference}}
- **{{reference_title}}**: `skills/{{skill_name}}/references/{{reference_file}}`
{{/for_each_reference}}
<!-- SCAFFOLDER: For each file in scripts_needed, add a reference line -->
{{#for_each_script}}
- **{{script_title}}**: `scripts/{{script_file}}`
{{/for_each_script}}
````

<!-- END TEMPLATE -->

---

## Phase Generation Rules

The scaffolder converts each Step object in `subdomain.chain` into one phase section.
Chain index 0 is always ADR (hardcoded as Phase 0 above). For `chain[1..N]`, apply the
family-specific template below.

### General Phase Structure

Every generated phase follows this skeleton:

```markdown
### Phase {{i}}: {{step.step}}

<!-- If step.profile_gate is non-null, insert a profile gate annotation -->

**Goal**: {{goal derived from step family and step name}}

{{body derived from step family, step params, and task context}}

**Gate**: {{completion criteria}}. Proceed to Phase {{i+1}}.
```

### Profile Gate Annotation

If `step.profile_gate` is non-null, insert before the Goal line:

```markdown
> **Profile Gate**: This phase activates when operator profile is `{{step.profile_gate}}`
> or more restrictive. Current profile: `{{operator_profile}}`.
> {{#if excluded}}This phase is SKIPPED for the current profile and included as
> documentation only. It activates when the profile changes.{{/if}}
> {{#if active}}This phase is ACTIVE for the current profile.{{/if}}
```

Profile restrictiveness order: `personal < work < ci < production`.
A step gated on `work` is active for `work`, `ci`, and `production` but skipped for `personal`.

---

### Family: research-gathering

Steps: RESEARCH, GATHER, SCAN, FETCH, SEARCH, SAMPLE

```markdown
### Phase {{i}}: {{step.step}} (Parallel Multi-Agent)

**Goal**: Investigate {{subdomain_name}} to build comprehensive understanding. Research breadth directly determines output quality.

**Default N = {{step.params.agents | default: 4}} agents.** Override with `--research-agents N` (minimum 2, maximum 6).

**Step 1: Prepare research context**
Assemble a shared context block from the ADR and prior phase artifacts.

**Step 2: Dispatch parallel research agents**
Launch all {{step.params.agents | default: 4}} agents simultaneously using the Task tool. Each agent:
- Receives the shared context block
- Investigates one specific aspect
- Saves findings to `/tmp/research-{aspect}.md`
- Has a {{step.params.timeout_minutes | default: 5}}-minute timeout

<!-- SCAFFOLDER: For each entry in step.params.aspects, generate an agent block.
     If aspects is absent, use task_type defaults:
       generation: [code-analysis, usage-patterns, ecosystem, examples]
       review: [architecture, security, correctness, test-coverage]
       debugging: [symptoms, history, dependencies, similar-issues]
       operations: [current-state, capacity, dependencies, runbooks]
       configuration: [schema-analysis, existing-configs, conventions, validation-rules]
       analysis: [primary-data, competing-approaches, historical-context, practical-impact]
       migration: [source-schema, target-schema, data-mapping, rollback-risk]
       testing: [existing-tests, coverage-gaps, edge-cases, integration-points] -->
{{#for_each_aspect}}
**Agent {{index}}: {{aspect_name}}** -- {{aspect_description}}
- {{investigation_instructions}}
- Save to `/tmp/research-{{aspect_slug}}.md`
{{/for_each_aspect}}

**Step 3: Collect and merge research artifacts**
After all agents complete, merge findings into `/tmp/research-compilation-{task-id}.md`.

**Gate**: At least {{ceil(agents * 0.75)}} of {{agents}} research agents completed. Research compilation saved. Proceed to Phase {{i+1}}.
```

### Family: structuring

Steps: COMPILE, MAP, OUTLINE, ASSESS, BRAINSTORM

Goal by step:
- COMPILE: "Structure raw research findings into a coherent, prioritized hierarchy."
- MAP: "Create a relationship map of components, dependencies, and interactions."
- OUTLINE: "Define the output structure before generation begins."
- ASSESS: "Evaluate candidates against criteria and identify risks."
- BRAINSTORM: "Generate 2-3 approaches, evaluate trade-offs, and select with rationale."

```markdown
### Phase {{i}}: {{step.step}}

**Goal**: {{goal_by_step_name}}

**Step 1**: Read all artifacts from Phase {{i-1}}.

**Step 2**: {{action_by_step_name}}
<!-- COMPILE: "Organize findings by theme. Cross-reference overlapping data. Prioritize by relevance."
     MAP: "Identify components and relationships. Draw dependency edges. Note orphans and cycles."
     OUTLINE: "Map every research element to an output section. Verify 100% coverage."
     ASSESS: "Define criteria. Score each candidate. Rank by weighted score. Document trade-offs."
     BRAINSTORM: "Generate 2+ approaches. For each: pros, cons, effort, risk. Select with rationale." -->

**Step 3**: Save structured output as dual-layer artifact (manifest.json + content.md).

**Gate**: Structured output covers all significant findings from prior phase. Output saved. Proceed to Phase {{i+1}}.
```

### Family: generation

Steps: GROUND, GENERATE, EXECUTE

Goal by step:
- GROUND: "Establish context (audience, constraints, mode) before generating output."
- GENERATE: "Produce the target artifact following the structured outline, grounded in research."
- EXECUTE: "Dispatch planned actions to domain agents or execute directly."

```markdown
### Phase {{i}}: {{step.step}}

**Goal**: {{goal_by_step_name}}

**Step 1**: Read the structured corpus or decision record from Phase {{i-1}}.
<!-- SCAFFOLDER: If step.params.template exists, add a template-loading step -->
{{#if step.params.template}}
**Step 2**: Read the output template from `{{step.params.template}}`.
{{/if}}

**Step {{next}}**: {{action_by_step_name}}
<!-- GROUND: "Define audience, tone, format constraints, and mode. Save grounding decisions to ADR."
     GENERATE: "Write output section by section following the outline. Ground every claim in research."
     EXECUTE: "Execute each action in dependency order. Record pre-state, action, post-state." -->

**Step {{next}}**: Save output as dual-layer artifact.

**Gate**: Output artifact produced and non-empty. Proceed to Phase {{i+1}}.
```

### Family: validation

Steps: VALIDATE, VERIFY, REFINE, CHARACTERIZE

Goal by step:
- VALIDATE: "Run deterministic validation against the generated output."
- VERIFY: "Execute tests or probes to confirm behavioral claims."
- REFINE: "Fix validation failures iteratively (maximum {{max_cycles}} cycles)."
- CHARACTERIZE: "Capture current behavior as a baseline before making changes."

```markdown
### Phase {{i}}: {{step.step}}

**Goal**: {{goal_by_step_name}}

<!-- SCAFFOLDER: If step.params.script exists, use script-based validation -->
{{#if step.params.script}}
**Step 1**: Run the validation script:
```bash
python3 scripts/{{step.params.script}} validate --input {artifact_path}
```

**Step 2**: Evaluate results:
- Pass: proceed to Phase {{i+1}}
- Fail: identify specific failures
{{/if}}

<!-- SCAFFOLDER: If step.step == "REFINE", use the refine loop -->
{{#if step_is_REFINE}}
**Step 1**: Read the verdict from the previous validation phase.

**Step 2**: For each failure:
1. Identify the failing element
2. Trace back to the generation artifact
3. Apply the correction

**Step 3**: Re-run validation. Maximum {{step.params.max_refine_cycles | default: 3}} cycles.

**Step 4**: If all cycles exhausted, deliver best-scoring output with validation report. Note failures in ADR.
{{/if}}

<!-- SCAFFOLDER: If step.step == "CHARACTERIZE" -->
{{#if step_is_CHARACTERIZE}}
**Step 1**: Analyze the current state of the target.

**Step 2**: Write characterization tests or capture behavioral snapshots.

**Step 3**: Save the baseline as a dual-layer artifact for comparison after changes.
{{/if}}

**Gate**: Validation passes OR max refine cycles exhausted (report final score). Proceed to Phase {{i+1}}.
```

### Family: review

Steps: REVIEW, AGGREGATE

```markdown
### Phase {{i}}: {{step.step}}

<!-- SCAFFOLDER: REVIEW with parallel reviewers -->
{{#if step_is_REVIEW}}
**Goal**: Evaluate the artifact through {{step.params.reviewers | default: 3}} specialized lenses in parallel.

**Step 1**: Dispatch {{step.params.reviewers | default: 3}} parallel reviewer agents:
{{#for_each_lens}}
- **Reviewer {{index}}: {{lens_name}}** -- Evaluates {{lens_focus}}
{{/for_each_lens}}

**Step 2**: Each reviewer produces a verdict with findings by severity.

**Step 3**: Collect all verdicts.

**Gate**: At least {{ceil(reviewers * 0.75)}} reviewers completed. Proceed to Phase {{i+1}}.
{{/if}}

{{#if step_is_AGGREGATE}}
**Goal**: Merge reviewer findings, deduplicate, and classify by severity.

**Step 1**: Read all reviewer verdicts.

**Step 2**: Deduplicate identical findings. Classify: critical, major, minor, nit.

**Step 3**: Produce unified verdict as dual-layer artifact.

**Gate**: Aggregated verdict produced. Proceed to Phase {{i+1}}.
{{/if}}
```

### Family: safety-guarding

Steps: GUARD, SIMULATE, SNAPSHOT, ROLLBACK, QUARANTINE

```markdown
### Phase {{i}}: {{step.step}}

{{#if step.profile_gate}}
> **Profile Gate**: This phase runs when operator profile is `{{step.profile_gate}}` or more restrictive.
{{/if}}

<!-- SCAFFOLDER: GUARD with pre-condition checks -->
{{#if step_is_GUARD}}
**Goal**: Verify all pre-conditions before proceeding with potentially dangerous operations.

**Step 1**: Run pre-condition checks:
{{#for_each step.params.checks}}
- [ ] {{check}}
{{/for_each}}

**Step 2**: {{#if step.params.block_on_failure}}If any check fails, STOP. Report which check failed and what remediation is needed. Do NOT proceed.{{else}}Log failures as warnings. Continue with caution.{{/if}}

**Gate**: All checks pass (or warnings logged). Proceed to Phase {{i+1}}.
{{/if}}

{{#if step_is_SNAPSHOT}}
**Goal**: Capture current state as a named restore point.

**Step 1**: Identify state to capture.
**Step 2**: Create snapshot: `snapshot-{{skill_name}}-{task-id}-{timestamp}`.
**Step 3**: Record snapshot reference in safety record artifact.

**Gate**: Snapshot created and recorded. Proceed to Phase {{i+1}}.
{{/if}}

{{#if step_is_SIMULATE}}
**Goal**: Dry-run the planned actions without committing changes.

**Step 1**: Execute the plan from the decision record in simulation mode.
**Step 2**: Record what would change, what would break, what side effects would occur.
**Step 3**: Save simulation results as safety record artifact.

**Gate**: Simulation complete. No blocking issues found (or issues reported for approval). Proceed to Phase {{i+1}}.
{{/if}}

{{#if step_is_ROLLBACK}}
**Goal**: Revert to the nearest snapshot.

**Step 1**: Identify the nearest SNAPSHOT artifact.
**Step 2**: Execute the rollback plan.
**Step 3**: Verify the rollback restored the expected state.

**Gate**: State restored to snapshot. Proceed to Phase {{i+1}}.
{{/if}}
```

### Family: domain-extension

Steps: LINT, TEMPLATE, MIGRATE, CONFORM, ADAPT

```markdown
### Phase {{i}}: {{step.step}}

{{#if step_is_LINT}}
**Goal**: Run domain-specific linting rules against the generated output.

**Step 1**: Run the linter:
```bash
{{step.params.linter}} {artifact_path}
```
{{#if step.params.rules}}
**Step 2**: Cross-check against rules in `references/{{step.params.rules | basename}}`.
{{/if}}
**Step {{next}}**: Record findings in a verdict artifact.

**Gate**: Lint passes or findings recorded. Proceed to Phase {{i+1}}.
{{/if}}

{{#if step_is_CONFORM}}
**Goal**: Verify output against domain schema, spec, or contract.

**Step 1**: Load the conformance spec.
**Step 2**: Validate each output element against the spec.
**Step 3**: Record conformance verdict.

**Gate**: Conformance passes or violations documented. Proceed to Phase {{i+1}}.
{{/if}}

{{#if step_is_TEMPLATE}}
**Goal**: Apply domain-specific templates with variable substitution.

**Step 1**: Load template from `{{step.params.template | default: "references/output-template.md"}}`.
**Step 2**: Substitute variables from the structured corpus or decision record.
**Step 3**: Save generation artifact.

**Gate**: Template applied. Output artifact saved. Proceed to Phase {{i+1}}.
{{/if}}

{{#if step_is_ADAPT}}
**Goal**: Modify generic output to fit domain-specific conventions.

**Step 1**: Read the generation artifact.
**Step 2**: Apply domain conventions (naming, formatting, idioms).
**Step 3**: Save adapted artifact.

**Gate**: Output conforms to domain conventions. Proceed to Phase {{i+1}}.
{{/if}}
```

### Family: synthesis-reporting

Steps: SYNTHESIZE, REPORT, OUTPUT, CLEANUP

```markdown
### Phase {{i}}: {{step.step}}

{{#if step_is_OUTPUT}}
**Goal**: Format and deliver final artifacts with validation report.

**Step 1**: Clean up temporary files:
- `/tmp/research-*.md`
- `/tmp/outline-*.md`
- Any other `/tmp/` artifacts from prior phases

**Step 2**: Verify final artifacts exist at expected paths.

**Step 3**: Update the ADR status to IMPLEMENTED.

**Step 4**: Report results:

```
## Pipeline Complete: {{skill_name}}

**Task**: {task-id}
**ADR**: adr/{{domain}}-{{subdomain_slug}}-{task-id}.md
**Output**: {output_path}

### Phase Summary
- Phase 0: ADR -- complete
{{#for_each_completed_phase}}
- Phase {{number}}: {{name}} -- {{status}}
{{/for_each_completed_phase}}

### Validation
- Score: {score}
- Issues: {count}

### Artifacts Produced
{{#for_each_artifact}}
- {{path}} ({{type}})
{{/for_each_artifact}}
```

**Gate**: Final artifacts delivered. ADR updated. Pipeline complete.
{{/if}}

{{#if step_is_REPORT}}
**Goal**: Generate a structured summary with metrics and verdicts.

**Step 1**: Compile metrics from all phase artifacts.
**Step 2**: Format the report with phase-by-phase summary.
**Step 3**: Save as pipeline-summary artifact.

**Gate**: Report produced. Pipeline complete.
{{/if}}

{{#if step_is_SYNTHESIZE}}
**Goal**: Unify findings from all prior phases into ranked recommendations.

**Step 1**: Read all phase artifacts.
**Step 2**: Cross-reference findings. Identify themes and conflicts.
**Step 3**: Rank recommendations by impact and confidence.
**Step 4**: Save synthesis as pipeline-summary artifact.

**Gate**: Synthesis complete. Proceed to Phase {{i+1}}.
{{/if}}

{{#if step_is_CLEANUP}}
**Goal**: Remove temporary files and verify final artifacts.

**Step 1**: Delete all `/tmp/` pipeline artifacts.
**Step 2**: Verify final output exists and is non-empty.
**Step 3**: Update ADR status.

**Gate**: Cleanup complete. Pipeline finished.
{{/if}}
```

### Family: decision-planning

Steps: PLAN, DECIDE, PRIME

```markdown
### Phase {{i}}: {{step.step}}

{{#if step_is_PLAN}}
**Goal**: Define execution steps with dependencies, risks, and rollback procedures.

**Step 1**: Read all available artifacts from prior phases.
**Step 2**: For each planned action, document:
  - What it does
  - What it depends on
  - What can go wrong
  - How to roll back
**Step 3**: Order actions by dependency. Save as decision record.

**Gate**: Plan produced with dependencies and rollback procedures. Proceed to Phase {{i+1}}.
{{/if}}

{{#if step_is_DECIDE}}
**Goal**: Evaluate options, filter by criteria, select the best approach.

**Step 1**: List all viable options.
**Step 2**: Define evaluation criteria with weights.
**Step 3**: Score each option. Select highest-scoring.
**Step 4**: Save decision with rationale. Update ADR.

**Gate**: Decision recorded with rationale. Proceed to Phase {{i+1}}.
{{/if}}

{{#if step_is_PRIME}}
**Goal**: Load prior artifacts, verify state, and capture context.

**Step 1**: Verify all required prior artifacts exist.
**Step 2**: Load context from ADR and prior phases.
**Step 3**: Capture current system state as baseline.

**Gate**: Context loaded. Baseline captured. Proceed to Phase {{i+1}}.
{{/if}}
```

### Family: observation

Steps: MONITOR, PROBE, TRACE, SAMPLE

```markdown
### Phase {{i}}: {{step.step}}

{{#if step_is_PROBE}}
**Goal**: Run active health or connectivity checks against the target.

**Step 1**: Execute probe commands against the target system.
**Step 2**: Record health status, response times, error rates.
**Step 3**: Save observations as research artifact.

**Gate**: Probe data collected. Proceed to Phase {{i+1}}.
{{/if}}

{{#if step_is_MONITOR}}
**Goal**: Observe runtime behavior or metrics over a defined time window.

**Step 1**: Define observation window and metrics to collect.
**Step 2**: Collect metrics over the window.
**Step 3**: Save as research artifact with baseline annotations.

**Gate**: Monitoring data collected. Proceed to Phase {{i+1}}.
{{/if}}

{{#if step_is_TRACE}}
**Goal**: Follow a request or data flow through the system.

**Step 1**: Identify the entry point and trace target.
**Step 2**: Follow the flow through each component.
**Step 3**: Document the complete trace path with timings.

**Gate**: Trace complete. Proceed to Phase {{i+1}}.
{{/if}}

{{#if step_is_SAMPLE}}
**Goal**: Collect representative examples from the target.

**Step 1**: Define sampling criteria and target count.
**Step 2**: Collect samples meeting criteria.
**Step 3**: Save as research artifact.

**Gate**: Samples collected. Proceed to Phase {{i+1}}.
{{/if}}
```

### Family: interaction

Steps: PROMPT, NOTIFY, APPROVE, PRESENT

```markdown
### Phase {{i}}: {{step.step}}

<!-- SCAFFOLDER: Interaction steps are profile-gated. Apply these rules:
     personal: REMOVE APPROVE and PROMPT entirely. NOTIFY and PRESENT are optional.
     ci: REMOVE APPROVE and PROMPT. Keep NOTIFY.
     work: Keep APPROVE for production-affecting changes. Remove PROMPT.
     production: Keep ALL interaction steps. -->

{{#if step_is_APPROVE}}
**Goal**: Gate on explicit human approval before proceeding.

**Step 1**: Present the current state and proposed action to the user.
**Step 2**: Wait for explicit approval. Do NOT proceed without it.
**Step 3**: Record approval in interaction record artifact.

**Gate**: User approval received. Proceed to Phase {{i+1}}.
{{/if}}

{{#if step_is_NOTIFY}}
**Goal**: Send pipeline status and results to external systems.

**Step 1**: Format notification with: pipeline status, key metrics, artifact locations.
**Step 2**: Send to configured target (PR comment, console, etc.).

**Gate**: Notification sent. Proceed to Phase {{i+1}}.
{{/if}}

{{#if step_is_PRESENT}}
**Goal**: Format intermediate results for human review without blocking.

**Step 1**: Format current state summary for readability.
**Step 2**: Display to user. Do NOT block -- proceed immediately.

**Gate**: Presentation displayed. Proceed to Phase {{i+1}}.
{{/if}}
```

### Family: git-release

Steps: STAGE, COMMIT, PUSH, CREATE_PR

```markdown
### Phase {{i}}: {{step.step}}

{{#if step_is_STAGE}}
**Goal**: Analyze and stage changes for commit, blocking sensitive files.

**Step 1**: Run `git status` to identify changes.
**Step 2**: Review changed files. Block `.env`, credentials, secrets.
**Step 3**: Stage appropriate files.

**Gate**: Changes staged. No sensitive files included. Proceed to Phase {{i+1}}.
{{/if}}

{{#if step_is_COMMIT}}
**Goal**: Create a commit with conventional format.

**Step 1**: Draft commit message summarizing the pipeline's output.
**Step 2**: Create commit.

**Gate**: Commit created. Proceed to Phase {{i+1}}.
{{/if}}

{{#if step_is_PUSH}}
**Goal**: Push to remote with branch setup.

**Step 1**: Ensure branch exists and tracks remote.
**Step 2**: Push with `-u` flag.

**Gate**: Push successful. Proceed to Phase {{i+1}}.
{{/if}}

{{#if step_is_CREATE_PR}}
**Goal**: Create a pull request with accumulated pipeline context.

**Step 1**: Gather context from all phase artifacts.
**Step 2**: Create PR with summary and test plan.

**Gate**: PR created. Proceed to Phase {{i+1}}.
{{/if}}
```

### Family: learning-retro

Steps: WALK, MERGE, GATE, APPLY, CHECKPOINT

```markdown
### Phase {{i}}: {{step.step}}

{{#if step_is_CHECKPOINT}}
**Goal**: Save phase artifact, invoke retro, and advance pipeline state.

**Step 1**: Save current phase artifacts to persistent storage.
**Step 2**: Invoke the retro system to extract learnings from this phase.
**Step 3**: Advance the pipeline state marker.

**Gate**: Checkpoint saved. Retro invoked. Proceed to Phase {{i+1}}.
{{/if}}

{{#if step_is_WALK}}
**Goal**: Launch parallel walkers to extract learnings from pipeline execution.

**Step 1**: Dispatch context walker and meta walker in parallel.
**Step 2**: Each walker analyzes the pipeline artifacts for patterns and improvements.
**Step 3**: Collect walker outputs.

**Gate**: Walker outputs collected. Proceed to Phase {{i+1}}.
{{/if}}

{{#if step_is_MERGE}}
**Goal**: Combine walker outputs and classify by hierarchy (L3/L2/L1).

**Step 1**: Read all walker outputs.
**Step 2**: Classify each learning: L3 (raw), L2 (per-feature), L1 (compact summary).
**Step 3**: Save merged learnings.

**Gate**: Learnings classified. Proceed to Phase {{i+1}}.
{{/if}}

{{#if step_is_APPLY}}
**Goal**: Write approved learnings to persistent storage.

**Step 1**: Read gated learnings from previous phase.
**Step 2**: Write to retro files (L1, L2 as appropriate).
**Step 3**: Confirm persistence.

**Gate**: Learnings persisted. Proceed to Phase {{i+1}}.
{{/if}}
```

---

## Task Type Defaults

### Default Errors by Task Type

| Task Type | Error Name | Cause | Solution |
|-----------|-----------|-------|----------|
| `generation` | Research Insufficient | Research agents returned sparse findings | Expand search scope or add more research agents |
| `generation` | Generation Off-Template | Output diverges from the specified template | Re-read template, re-generate following structure strictly |
| `generation` | Validation Loop Exceeded | Max refine cycles exhausted without passing | Deliver best output with report. Note in ADR. |
| `review` | Review Scope Unclear | Artifact boundaries not well-defined for reviewers | Clarify scope in ADR before dispatching reviewers |
| `review` | Reviewer Disagreement | Reviewers produce contradictory verdicts | Aggregate and classify; critical findings override |
| `debugging` | Reproduction Failed | Cannot reproduce the reported issue | Document what was tried. Probe for environmental differences. |
| `debugging` | Root Cause Ambiguous | Multiple potential causes identified | Rank by probability. Test each systematically. |
| `operations` | Pre-condition Check Failed | GUARD step blocked execution | Report which check failed. Do not bypass. |
| `operations` | Execution Timeout | Operation exceeded time limit | Check target system health. Retry with extended timeout. |
| `configuration` | Schema Violation | Generated config does not match spec | Re-run CONFORM step. Fix violations. |
| `configuration` | Template Variable Unresolved | Placeholder left in output | Check variable source. Fill or report as missing. |
| `analysis` | Data Insufficient | Not enough data for confident recommendations | Note confidence level. Recommend additional data collection. |
| `migration` | State Capture Failed | SNAPSHOT step could not capture current state | Check permissions and storage. Cannot proceed without snapshot. |
| `migration` | Rollback Incomplete | Rollback did not fully restore prior state | Manual intervention required. Report exact delta. |
| `testing` | Target Untestable | Target lacks testable interfaces | Report structural barriers. Suggest refactoring. |
| `testing` | Flaky Test Generated | Tests pass intermittently | Identify non-determinism source. Add stability guards. |

### Default Anti-Patterns by Task Type

| Task Type | Name | Description | Reason | Alternative |
|-----------|------|-------------|--------|-------------|
| `generation` | Generate Without Research | Producing output without the research phase | Unresearched output lacks grounding and examples | Always research first |
| `generation` | Skip Validation | Delivering without running validation | Unvalidated output may contain errors | Always validate |
| `generation` | Ignore Template | Writing freeform instead of following template | Template ensures structural consistency | Follow template |
| `review` | Single-Reviewer | Using one reviewer instead of parallel lenses | One lens misses what others catch | Use 3+ parallel reviewers |
| `review` | Review Without Criteria | Reviewing without defined evaluation criteria | Criteria-free reviews are subjective | Define criteria first |
| `debugging` | Fix Without Understanding | Applying fixes without understanding root cause | Fixes without understanding cause regressions | Diagnose first, fix second |
| `operations` | Execute Without Guard | Running operations without pre-condition checks | Ungated operations risk damage | Always GUARD before EXECUTE |
| `operations` | Skip Snapshot | Modifying state without a restore point | No snapshot means no rollback | Always SNAPSHOT before changes |
| `configuration` | Hardcode Values | Embedding environment-specific values | Configs must be portable | Use variables |
| `analysis` | Cherry-Pick Data | Selecting only supporting evidence | Biased analysis misleads | Include all findings |
| `migration` | Big Bang Migration | Migrating everything at once | All-or-nothing risks total failure | Migrate incrementally |
| `testing` | Test Happy Path Only | Testing only success scenarios | Edge cases cause production failures | Include edge cases and error paths |

---

## Scaffolder Checklist

Before writing the final SKILL.md, verify all of the following:

**Frontmatter**:
- [ ] `name` matches `subdomain.skill_name`
- [ ] `description` follows What+When formula with trigger keywords
- [ ] `agent` matches `spec.reuse_agent` or `spec.new_agent.name`
- [ ] `routing.triggers` matches `subdomain.routing_triggers`
- [ ] `routing.complexity` derived from chain length

**Structure**:
- [ ] Phase 0 is ADR (hardcoded, not from chain)
- [ ] Every `chain[1..N]` maps to exactly one phase
- [ ] Phase gates exist between every phase
- [ ] Profile-gated steps have conditional annotations
- [ ] Research steps use parallel multi-agent template (Rule 12)
- [ ] Validation steps reference correct script from `scripts_needed`

**Content**:
- [ ] Operator profile behaviors match `spec.operator_profile`
- [ ] Error handling covers: phase failure, validation failure, dependency missing
- [ ] Task-type-specific errors and anti-patterns included
- [ ] Anti-rationalization table populated
- [ ] Dual-layer artifact format documented
- [ ] References section lists all `references_needed`, `shared_references`, and `scripts_needed`

**Size**:
- [ ] Word count within complexity tier: Simple <=600, Medium <=1500, Complex <=2500
