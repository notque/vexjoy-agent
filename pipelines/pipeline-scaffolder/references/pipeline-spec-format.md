# Pipeline Spec Format

The pipeline spec is the intermediate representation between the Pipeline Architect (chain-composer) and the Pipeline Scaffolder. When chain-composer produces a pipeline design, it outputs this format. When pipeline-scaffolder consumes it, this is the contract it reads.

This is a **machine-readable contract**. Both sides must agree on every field.

---

## Top-Level Structure

```json
{
  "domain": "prometheus",
  "adr_path": "adr/pipeline-prometheus.md",
  "adr_hash": "sha256:3a7f9b2c...",
  "subdomains": [ ... ],
  "shared_references": ["prometheus-domain-knowledge.md"],
  "new_agent": null,
  "reuse_agent": "prometheus-grafana-engineer",
  "operator_profile": "personal"
}
```

### Top-Level Field Definitions

| Field | Type | Required | Valid Values | Purpose |
|-------|------|----------|--------------|---------|
| `domain` | string | Yes | Lowercase kebab-case identifier | The top-level domain this pipeline covers. Used as prefix in naming conventions. |
| `adr_path` | string | Required if pipeline was generated via self-improving-pipeline-generator | Relative path from repo root (e.g., `adr/pipeline-prometheus.md`) | Path to the ADR that governs this pipeline. Used by `pipeline-scaffolder` Phase 1 gate to verify hash integrity before scaffolding. |
| `adr_hash` | string | Required if `adr_path` is set | Format: `sha256:hexdigest` (e.g., `sha256:3a7f9b2c...`) | SHA-256 hash of the ADR file content, computed at chain-composition time. The scaffolder verifies this hash before proceeding to detect ADR changes since composition. |
| `subdomains` | array\<Subdomain\> | Yes | Non-empty array of Subdomain objects | Each subdomain becomes one skill. The scaffolder creates one skill per subdomain entry. |
| `shared_references` | array\<string\> | No | Filenames (no path — placed in skill's `references/`) | Reference files shared across all subdomains. Created once, symlinked or copied into each skill's references directory. |
| `new_agent` | object\|null | Conditional | Agent object (see below) or `null` | If no existing agent covers the domain, define the new agent here. Mutually exclusive with `reuse_agent` — exactly one must be non-null. |
| `reuse_agent` | string\|null | Conditional | Existing agent name from `agents/INDEX.json` | If an existing agent covers 70%+ of the domain (Rule 9: Reuse Over Recreation), reference it here instead of creating a new one. |
| `operator_profile` | string | Yes | See Operator Profile enum | The detected or overridden operator profile. Determines which safety/interaction steps are injected into chains. |

**Note on `adr_hash`**: Computed via `python3 scripts/adr-query.py hash --adr {path}` at the time `chain-composer` produces the spec. The `pipeline-scaffolder` Phase 1 gate runs `python3 scripts/adr-query.py verify --adr {spec.adr_path} --hash {spec.adr_hash}` before proceeding. If exit 1 (hash mismatch), the scaffolder stops — the ADR changed after composition and `chain-composer` must be re-run with the updated ADR before scaffolding.

**Constraint**: Exactly one of `new_agent` or `reuse_agent` must be non-null. The scaffolder rejects specs where both are null (no executor) or both are non-null (ambiguous executor).

---

## Subdomain Object

Each subdomain represents one pipeline skill to scaffold.

```json
{
  "name": "metrics-authoring",
  "task_type": "generation",
  "description": "Writing PromQL queries, recording rules, metric naming conventions",
  "chain": [ ... ],
  "skill_name": "prometheus-metrics",
  "pairs_with_agent": "prometheus-grafana-engineer",
  "references_needed": ["promql-patterns.md", "metric-naming-conventions.md"],
  "scripts_needed": ["promql-validator.py"],
  "routing_triggers": ["promql", "recording rule", "metric naming", "prometheus metrics"]
}
```

### Subdomain Field Definitions

| Field | Type | Required | Valid Values | Purpose |
|-------|------|----------|--------------|---------|
| `name` | string | Yes | Lowercase kebab-case, descriptive | Human-readable subdomain identifier. Used in logs and ADR references. Not used for file naming — that is `skill_name`. |
| `task_type` | string | Yes | See Task Type enum | Classifies the subdomain's primary workflow pattern. Determines which chain template is used as a starting point. |
| `description` | string | Yes | 1-2 sentences | What this subdomain covers. Becomes the basis for the generated skill's YAML description field. |
| `chain` | array\<Step\> | Yes | Non-empty array of Step objects, validated by chain rules | The ordered sequence of pipeline steps. The scaffolder converts this into numbered phases in the generated SKILL.md. |
| `skill_name` | string | Yes | `{domain}-{function}` pattern per Rule 8 | The name for the generated skill. Becomes the directory name under `skills/` and the `name:` in YAML frontmatter. |
| `pairs_with_agent` | string | Yes | Must match `reuse_agent` or `new_agent.name` at top level, OR an existing agent | The agent that executes this skill. Written to the skill's `agent:` frontmatter field. |
| `references_needed` | array\<string\> | No | Filenames (placed in `skills/{skill_name}/references/`) | Domain-specific reference files the skill needs. The scaffolder creates stub files with headers; domain content is populated by research. |
| `scripts_needed` | array\<string\> | No | Filenames matching `{domain}-{function}.py` pattern | Deterministic Python scripts the skill invokes. The scaffolder creates skeleton scripts with argparse CLI. |
| `routing_triggers` | array\<string\> | Yes | Non-empty array of lowercase trigger phrases | Keywords and phrases that cause `/do` to route to this skill. Written to the skill description's "Use for" clause and to routing tables. |

---

## Step Object

Each step in a chain represents one phase in the generated skill.

```json
{
  "step": "RESEARCH",
  "family": "research-gathering",
  "output_schema": "research-artifact",
  "consumes": "decision-record",
  "params": {
    "agents": 4,
    "aspects": ["code-analysis", "usage-patterns", "ecosystem", "examples"]
  },
  "profile_gate": null
}
```

### Step Field Definitions

| Field | Type | Required | Valid Values | Purpose |
|-------|------|----------|--------------|---------|
| `step` | string | Yes | See Step Name enum | The pipeline step from the step menu. Determines the phase template the scaffolder uses. |
| `family` | string | Yes | See Step Family enum | The step's category in the step menu. Used for type compatibility validation. |
| `output_schema` | string | Yes | See Output Schema enum | The artifact schema this step produces. The next step's `consumes` must be type-compatible with this value. |
| `consumes` | string\|null | Conditional | An output schema name, or `null` for chain-starting steps | The artifact schema this step expects as input. Must match the previous step's `output_schema` per the type compatibility matrix. `null` only for the first step in a chain (ADR). |
| `params` | object | No | Step-specific key-value pairs (see Params by Step) | Configuration for the step. The scaffolder uses these to customize the generated phase template. |
| `profile_gate` | string\|null | No | See Operator Profile enum, or `null` | If non-null, this step is only included in the chain when the operator profile matches. `null` means the step runs unconditionally. |

---

## Enums

### Task Type

Defines the primary workflow pattern for a subdomain. Each task type has a canonical chain template that the Pipeline Architect uses as a starting point, then customizes with domain-specific steps.

| Value | Description | Canonical Chain Template |
|-------|-------------|------------------------|
| `generation` | Producing new artifacts: code, configs, documentation, queries | ADR -> RESEARCH -> [structuring] -> GENERATE -> VALIDATE -> OUTPUT |
| `review` | Evaluating existing work against criteria | ADR -> RESEARCH -> ASSESS -> REVIEW -> AGGREGATE -> REPORT |
| `debugging` | Diagnosing and fixing problems in running systems or code | ADR -> PROBE -> SEARCH -> ASSESS -> PLAN -> EXECUTE -> VERIFY -> OUTPUT |
| `operations` | Managing infrastructure, deployments, cluster state | ADR -> PROBE -> ASSESS -> PLAN -> GUARD -> EXECUTE -> VALIDATE -> OUTPUT |
| `configuration` | Templating, schema conformance, config file generation | ADR -> RESEARCH -> COMPILE -> TEMPLATE -> CONFORM -> VALIDATE -> OUTPUT |
| `analysis` | Research-heavy evaluation producing recommendations | ADR -> RESEARCH -> COMPILE -> ASSESS -> SYNTHESIZE -> REPORT |
| `migration` | Moving from one state/schema/version to another | ADR -> CHARACTERIZE -> PLAN -> GUARD -> SNAPSHOT -> EXECUTE -> VALIDATE -> OUTPUT |
| `testing` | Generating or structuring test suites | ADR -> RESEARCH -> COMPILE -> CHARACTERIZE -> GENERATE -> VALIDATE -> REPORT |

**Usage**: The canonical chain is a starting point. The Pipeline Architect modifies it by:
- Adding domain-specific steps (LINT, CONFORM, TEMPLATE, etc.)
- Inserting safety steps based on operator profile (GUARD, SNAPSHOT, APPROVE)
- Adding interaction steps for production profiles (PRESENT, APPROVE, NOTIFY)
- Removing steps that don't apply to the specific subdomain

### Step Name

All valid step names from the pipeline step menu. Grouped by family.

| Family | Valid Steps |
|--------|------------|
| research-gathering | `GATHER`, `SCAN`, `RESEARCH`, `FETCH`, `SEARCH`, `SAMPLE` |
| structuring | `COMPILE`, `MAP`, `OUTLINE`, `NORMALIZE`, `EXTRACT` |
| generation | `GROUND`, `GENERATE`, `EXECUTE` |
| validation | `VALIDATE`, `VERIFY`, `REFINE`, `CHARACTERIZE` |
| review | `REVIEW`, `AGGREGATE` |
| git-release | `STAGE`, `COMMIT`, `PUSH`, `CREATE_PR` |
| learning-retro | `WALK`, `MERGE`, `GATE`, `APPLY`, `CHECKPOINT` |
| decision-planning | `ASSESS`, `BRAINSTORM`, `PLAN`, `DECIDE`, `PRIME`, `SYNTHESIZE` |
| synthesis-reporting | `REPORT`, `OUTPUT`, `CLEANUP` |
| safety-guarding | `GUARD`, `SIMULATE`, `SNAPSHOT`, `ROLLBACK`, `QUARANTINE` |
| comparison-evaluation | `COMPARE`, `DIFF`, `BENCHMARK`, `RANK`, `ABLATE`, `SHADOW` |
| transformation | `TRANSFORM`, `ENRICH` |
| observation | `MONITOR`, `PROBE`, `TRACE`, `SAMPLE` |
| domain-extension | `LINT`, `TEMPLATE`, `MIGRATE`, `CONFORM`, `ADAPT` |
| interaction | `PROMPT`, `NOTIFY`, `APPROVE`, `PRESENT` |
| orchestration | `DECOMPOSE`, `DELEGATE`, `CONVERGE`, `SEQUENCE`, `RETRY` |
| state-management | `CACHE`, `RESUME`, `HYDRATE`, `PERSIST`, `EXPIRE` |
| experimentation | `CANARY`, `FUZZ`, `REPLAY`, `ABLATE`, `SHADOW` |
| invariant | `ADR` |

### Step Family

Maps to the type compatibility matrix. The family determines what schema types a step can consume and produce.

| Family | Consumes | Produces |
|--------|----------|----------|
| `invariant` | (none -- starts every chain) | `decision-record` |
| `research-gathering` | (any -- can start sub-chains) | `research-artifact` |
| `structuring` | `research-artifact` | `structured-corpus` |
| `decision-planning` | `research-artifact`, `structured-corpus`, `comparison-report`, any (SYNTHESIZE) | `decision-record` |
| `generation` | `structured-corpus`, `decision-record` | `generation-artifact` |
| `validation` | `generation-artifact`, `execution-report` | `verdict` |
| `review` | `generation-artifact`, `execution-report` | `verdict` |
| `git-release` | `generation-artifact`, `execution-report` | `execution-report` |
| `safety-guarding` | (any -- wraps dangerous steps) | `safety-record` |
| `comparison-evaluation` | any two artifacts of same type | `comparison-report` |
| `transformation` | any artifact | artifact of different type |
| `observation` | `execution-report`, `safety-record`, `decision-record`, `research-artifact` | `research-artifact` |
| `domain-extension` | `generation-artifact` | `verdict` |
| `interaction` | any artifact | `interaction-record` |
| `orchestration` | `decision-record`, `structured-corpus` | `orchestration-manifest` |
| `state-management` | any artifact | `state-record` |
| `experimentation` | any two artifacts, `comparison-report` | `experiment-report` |
| `learning-retro` | any artifact | `learning-record` |
| `synthesis-reporting` | any artifact(s) | `pipeline-summary` |

**Type compatibility note**: "any" in the Consumes column means the step can accept whatever the previous step produced. The scaffolder still records the concrete schema in the step's `consumes` field for traceability.

### Output Schema

All valid artifact schema types. Each corresponds to a dual-layer artifact (manifest.json + content.md).

| Value | Description | Typical Producers |
|-------|-------------|-------------------|
| `research-artifact` | Raw findings from investigation, per-agent sections, source quality | GATHER, SCAN, RESEARCH, FETCH, SEARCH, SAMPLE |
| `structured-corpus` | Organized hierarchy, cross-references, prioritized items | COMPILE, MAP, OUTLINE, NORMALIZE, EXTRACT (structuring family) |
| `decision-record` | Options evaluated, criteria, selection with rationale | ADR, ASSESS, BRAINSTORM, DECIDE, RANK, SYNTHESIZE (decision-planning family) |
| `generation-artifact` | Produced content/code/config, template used, validation checklist | GROUND, GENERATE, TEMPLATE, ADAPT, REFINE |
| `execution-report` | Changes made, commands run, pre/post state, rollback instructions | EXECUTE, MIGRATE, STAGE, COMMIT, PUSH, CREATE_PR |
| `verdict` | Pass/fail/block verdict, findings by severity, evidence | VALIDATE, VERIFY, CONFORM, LINT, REVIEW, AGGREGATE |
| `refinement-log` | Iteration tracking: attempt number, what failed, what changed, per-iteration results | (tracking sub-artifact within REFINE iterations, not a primary step output) |
| `comparison-report` | Subjects compared, dimensions, per-dimension scores, delta table | COMPARE, DIFF, BENCHMARK, ABLATE, SHADOW |
| `safety-record` | Pre-conditions checked, snapshot reference, simulation results, rollback plan | GUARD, SIMULATE, SNAPSHOT, ROLLBACK, QUARANTINE |
| `interaction-record` | Question posed, response received, decision made, notification sent | PROMPT, NOTIFY, APPROVE, PRESENT |
| `orchestration-manifest` | Sub-tasks created, delegation targets, convergence status | DECOMPOSE, DELEGATE, CONVERGE, SEQUENCE |
| `state-record` | Key, value, TTL, storage location, cache hit/miss | CACHE, RESUME, HYDRATE, PERSIST, EXPIRE |
| `experiment-report` | Hypothesis, control metrics, treatment metrics, conclusion | CANARY, FUZZ, REPLAY |
| `learning-record` | Observations, classifications, promotions, approval status | WALK, MERGE, GATE, APPLY, CHECKPOINT |
| `pipeline-summary` | Phases completed, artifacts produced, metrics, final verdict | REPORT, OUTPUT, CLEANUP |

### Operator Profile

Determines which safety/interaction steps are injected into or removed from chains.

| Value | Detection | Step Behavior |
|-------|-----------|---------------|
| `personal` | Not an organizational/client repo. User's personal GitHub. | Full autonomy. APPROVE, PROMPT removed from chain. GUARD reduced to branch-check only. SIMULATE, SNAPSHOT available but not mandatory. |
| `work` | Organizational repo, client repo, or repo with compliance markers. | Convention-enforced. APPROVE for production-affecting changes. CONFORM added for org conventions. Full GUARD -> SNAPSHOT -> EXECUTE -> VALIDATE for state changes. |
| `ci` | `CI=true` env var, GitHub Actions runner, Docker container. | Fully autonomous, disposable environment. All interaction steps skipped. NOTIFY sends results to PR/Slack. GUARD checks dependencies exist, not permissions. |
| `production` | `PRODUCTION=true` env var, production branch, deployment pipelines. | Maximum gates. Full GUARD + SNAPSHOT + SIMULATE before any EXECUTE. APPROVE mandatory. PRESENT status before and after. |

---

## Step Params

Step-specific parameters that customize the generated phase template. All params are optional -- the scaffolder uses defaults when omitted.

### Research & Gathering Params

```json
{
  "step": "RESEARCH",
  "params": {
    "agents": 4,
    "aspects": ["code-analysis", "usage-patterns", "ecosystem", "examples"],
    "timeout_minutes": 5
  }
}
```

| Param | Type | Default | Valid Range | Purpose |
|-------|------|---------|-------------|---------|
| `agents` | number | 4 | 2-6 | Number of parallel research agents to dispatch (Rule 12). |
| `aspects` | array\<string\> | Based on task_type | Non-empty, length must equal `agents` | The investigation focus for each agent. |
| `timeout_minutes` | number | 5 | 1-10 | Per-agent timeout in minutes. |

### Validation Params

```json
{
  "step": "VALIDATE",
  "params": {
    "script": "promql-validator.py",
    "max_refine_cycles": 3
  }
}
```

| Param | Type | Default | Purpose |
|-------|------|---------|---------|
| `script` | string | null | Deterministic validation script to invoke. Must exist in `scripts_needed`. |
| `max_refine_cycles` | number | 3 | Maximum REFINE iterations if validation fails. |

### Domain Extension Params

```json
{
  "step": "LINT",
  "params": {
    "linter": "promql-check",
    "rules": "references/promql-rules.md"
  }
}
```

| Param | Type | Default | Purpose |
|-------|------|---------|---------|
| `linter` | string | null | Name or path of the domain-specific linter tool. |
| `rules` | string | null | Reference file containing linting rules. Must exist in `references_needed`. |

### Review Params

```json
{
  "step": "REVIEW",
  "params": {
    "reviewers": 3,
    "lenses": ["architecture", "security", "correctness"]
  }
}
```

| Param | Type | Default | Valid Range | Purpose |
|-------|------|---------|-------------|---------|
| `reviewers` | number | 3 | 3-5 | Number of parallel reviewer agents. |
| `lenses` | array\<string\> | Based on domain | Length must equal `reviewers` | Specialized review focus for each reviewer. |

### Safety & Guarding Params

```json
{
  "step": "GUARD",
  "params": {
    "checks": ["branch-not-main", "dependencies-installed", "service-healthy"],
    "block_on_failure": true
  }
}
```

| Param | Type | Default | Purpose |
|-------|------|---------|---------|
| `checks` | array\<string\> | `["branch-not-main"]` for personal, full list for work/production | Pre-conditions to verify before proceeding. |
| `block_on_failure` | boolean | true | If true, chain stops when any check fails. If false, failures are warnings. |

### Generation Params

```json
{
  "step": "GENERATE",
  "params": {
    "template": "references/output-template.md",
    "voice": null
  }
}
```

| Param | Type | Default | Purpose |
|-------|------|---------|---------|
| `template` | string | null | Reference file containing the output template or structure guide. |
| `voice` | string\|null | null | Voice profile to apply (if content is voice-validated). |

### Orchestration Params

```json
{
  "step": "DELEGATE",
  "params": {
    "target_pipeline": "grafana-validation",
    "pass_artifacts": ["generation-artifact"]
  }
}
```

| Param | Type | Default | Purpose |
|-------|------|---------|---------|
| `target_pipeline` | string | (required) | The skill name of the sub-pipeline to invoke. |
| `pass_artifacts` | array\<string\> | All artifacts from current phase | Which artifact schemas to forward to the sub-pipeline. |

---

## New Agent Object

When no existing agent covers the domain (`reuse_agent` is null), define the new agent.

```json
{
  "new_agent": {
    "name": "prometheus-pipeline-engineer",
    "description": "Domain expert for Prometheus monitoring stack. Coordinates PromQL authoring, alerting rules, cluster operations, dashboard design, and performance tuning pipelines.",
    "triggers": ["prometheus", "promql", "alertmanager", "recording rule"],
    "category": "devops",
    "complexity": "Medium",
    "expertise": [
      "PromQL query language and recording rules",
      "Alertmanager routing and inhibition",
      "Prometheus federation and remote write",
      "Metric naming conventions and cardinality management"
    ]
  }
}
```

### New Agent Field Definitions

| Field | Type | Required | Valid Values | Purpose |
|-------|------|----------|--------------|---------|
| `name` | string | Yes | `{domain}-{function}-engineer` per Rule 8 | Agent filename (without `.md`). |
| `description` | string | Yes | 2-4 sentences | Agent purpose. Written to YAML frontmatter description field. |
| `triggers` | array\<string\> | Yes | Non-empty, lowercase keywords | Routing triggers for `/do`. Written to `routing.triggers` in YAML frontmatter. |
| `category` | string | Yes | `language`, `infrastructure`, `devops`, `review`, `meta`, `content` | Routing category. Written to `routing.category` in YAML frontmatter. |
| `complexity` | string | Yes | `Simple`, `Medium`, `Medium-Complex`, `Complex` | Agent complexity tier. Determines whether `references/` directory is created (Medium+). |
| `expertise` | array\<string\> | Yes | 3-6 items | Domain expertise areas. Written to the agent's expertise list in its Operator declaration. |

---

## Validation Rules

The pipeline spec must satisfy all of the following rules. The scaffolder rejects specs that violate any rule and returns the specific violation.

### Chain Structure Rules

**Rule 1: ADR First**
Every chain must start with a step where `step` is `"ADR"` and `family` is `"invariant"`. No exceptions -- this is Rule 10 from architecture-rules.md.

**Rule 2: Terminal Step**
Every chain must end with a step whose `output_schema` is `"pipeline-summary"`. Valid terminal steps: `OUTPUT`, `REPORT`, `CLEANUP`. The pipeline must produce a summary artifact for the user.

**Rule 3: Type Compatibility**
For every pair of adjacent steps (step[i], step[i+1]):
- `step[i+1].consumes` must be type-compatible with `step[i].output_schema`
- Type compatibility is defined by the Step Family table's Consumes column
- If the family says "any", any schema is compatible
- If the family lists specific schemas, the consumed schema must be in that list

```
Valid:   RESEARCH (produces research-artifact) -> COMPILE (consumes research-artifact)
Valid:   GENERATE (produces generation-artifact) -> VALIDATE (consumes generation-artifact)
Invalid: RESEARCH (produces research-artifact) -> GENERATE (consumes structured-corpus)
         ^ Missing COMPILE step to structure the research first
```

**Rule 4: No Orphan Consumes**
The first step's `consumes` must be `null`. Every subsequent step's `consumes` must not be `null`.

### Safety & Profile Rules

**Rule 5: Profile Gate Validity**
Every `profile_gate` value must be a valid operator profile (`"personal"`, `"work"`, `"ci"`, `"production"`) or `null`.

**Rule 6: Profile Consistency**
Steps with `profile_gate` set to a profile that is less restrictive than the spec's `operator_profile` are permitted (they run). Steps gated on a more restrictive profile than the spec's are excluded from the generated skill (they are conditional annotations, not errors).

### Component Reference Rules

**Rule 7: Agent Reference**
`pairs_with_agent` must reference either:
- The value of `reuse_agent` at the top level, OR
- The value of `new_agent.name` at the top level, OR
- An agent that exists in `agents/INDEX.json`

**Rule 8: Skill Naming**
`skill_name` must follow the `{domain}-{function}` pattern (Rule 8 from architecture-rules.md). Validated by regex: `^[a-z][a-z0-9]*(-[a-z][a-z0-9]*)+$`

**Rule 9: Routing Triggers Non-Empty**
`routing_triggers` must contain at least one entry. Skills without triggers are dead code (Rule 7: No Dead Code).

**Rule 10: Script References**
Every script referenced in step `params` (e.g., `params.script` in VALIDATE steps) must appear in the subdomain's `scripts_needed` array.

**Rule 11: Reference References**
Every reference file referenced in step `params` (e.g., `params.rules` in LINT steps) must appear in the subdomain's `references_needed` array or in the top-level `shared_references` array.

---

## Component Manifest

The pipeline spec doubles as the component manifest -- it contains everything the scaffolder needs to determine what to build.

### Deriving Build Targets from the Spec

The scaffolder reads the spec and computes the full set of components to create:

```
FROM spec:
  Skills to create    = spec.subdomains[*].skill_name
  References to create = union(
                           spec.shared_references,
                           spec.subdomains[*].references_needed
                         )
  Scripts to create   = union(spec.subdomains[*].scripts_needed)
  Agent to create     = spec.new_agent (if non-null)
  Agent to bind       = spec.reuse_agent (if non-null)
  Routing entries     = spec.subdomains[*].routing_triggers (per skill)
```

### Build Target Table

| Component Type | Source Field | Output Location | Naming Convention |
|---------------|-------------|-----------------|-------------------|
| Skill | `subdomains[i].skill_name` | `skills/{skill_name}/SKILL.md` | `{domain}-{function}` |
| Skill references | `subdomains[i].references_needed` | `skills/{skill_name}/references/{filename}` | Domain-descriptive |
| Shared references | `shared_references` | `skills/{skill_name}/references/{filename}` (copied per skill) | Domain-descriptive |
| Script | `subdomains[i].scripts_needed` | `scripts/{filename}` | `{domain}-{function}.py` |
| Agent | `new_agent.name` | `agents/{name}.md` | `{domain}-{function}-engineer` |
| Agent references | (created if `new_agent.complexity` is Medium+) | `agents/{name}/references/` | Per architecture-rules.md |
| Routing entries | `subdomains[i].routing_triggers` | `skills/do/references/routing-tables.md`, `agents/INDEX.json` | N/A (data, not files) |

### Component Dependency Graph

The scaffolder also validates that no component is orphaned (Rule 7: No Dead Code):

```
agent (new or reused)
  ├── bound to skill_1 (via pairs_with_agent)
  │     ├── references: ref_a.md, ref_b.md
  │     ├── invokes: script_x.py (via VALIDATE step params)
  │     └── routing: triggers registered in /do
  ├── bound to skill_2
  │     ├── references: ref_c.md, shared_ref.md
  │     └── routing: triggers registered in /do
  └── ...
```

Every skill must have a `pairs_with_agent`. Every script in `scripts_needed` must be referenced by at least one step's `params`. Every reference in `references_needed` must be referenced by at least one step's `params` or loaded explicitly in a phase.

---

## Complete Example

A full pipeline spec for the Prometheus domain with two subdomains:

```json
{
  "domain": "prometheus",
  "adr_path": "adr/pipeline-prometheus.md",
  "adr_hash": "sha256:3a7f9b2c...",
  "subdomains": [
    {
      "name": "metrics-authoring",
      "task_type": "generation",
      "description": "Writing PromQL queries, recording rules, metric naming conventions",
      "chain": [
        {
          "step": "ADR",
          "family": "invariant",
          "output_schema": "decision-record",
          "consumes": null,
          "params": {},
          "profile_gate": null
        },
        {
          "step": "RESEARCH",
          "family": "research-gathering",
          "output_schema": "research-artifact",
          "consumes": "decision-record",
          "params": {
            "agents": 4,
            "aspects": ["code-analysis", "usage-patterns", "ecosystem", "examples"],
            "timeout_minutes": 5
          },
          "profile_gate": null
        },
        {
          "step": "COMPILE",
          "family": "structuring",
          "output_schema": "structured-corpus",
          "consumes": "research-artifact",
          "params": {},
          "profile_gate": null
        },
        {
          "step": "GENERATE",
          "family": "generation",
          "output_schema": "generation-artifact",
          "consumes": "structured-corpus",
          "params": {
            "template": "references/promql-patterns.md"
          },
          "profile_gate": null
        },
        {
          "step": "LINT",
          "family": "domain-extension",
          "output_schema": "verdict",
          "consumes": "generation-artifact",
          "params": {
            "linter": "promql-check",
            "rules": "references/metric-naming-conventions.md"
          },
          "profile_gate": null
        },
        {
          "step": "REFINE",
          "family": "validation",
          "output_schema": "generation-artifact",
          "consumes": "verdict",
          "params": {
            "max_refine_cycles": 3
          },
          "profile_gate": null
        },
        {
          "step": "OUTPUT",
          "family": "synthesis-reporting",
          "output_schema": "pipeline-summary",
          "consumes": "generation-artifact",
          "params": {},
          "profile_gate": null
        }
      ],
      "skill_name": "prometheus-metrics",
      "pairs_with_agent": "prometheus-grafana-engineer",
      "references_needed": ["promql-patterns.md", "metric-naming-conventions.md"],
      "scripts_needed": ["promql-validator.py"],
      "routing_triggers": ["promql", "recording rule", "metric naming", "prometheus metrics"]
    },
    {
      "name": "cluster-operations",
      "task_type": "operations",
      "description": "Scaling, storage management, federation setup, pod troubleshooting for Prometheus clusters",
      "chain": [
        {
          "step": "ADR",
          "family": "invariant",
          "output_schema": "decision-record",
          "consumes": null,
          "params": {},
          "profile_gate": null
        },
        {
          "step": "PROBE",
          "family": "observation",
          "output_schema": "research-artifact",
          "consumes": "decision-record",
          "params": {},
          "profile_gate": null
        },
        {
          "step": "ASSESS",
          "family": "decision-planning",
          "output_schema": "decision-record",
          "consumes": "research-artifact",
          "params": {},
          "profile_gate": null
        },
        {
          "step": "PLAN",
          "family": "decision-planning",
          "output_schema": "decision-record",
          "consumes": "decision-record",
          "params": {},
          "profile_gate": null
        },
        {
          "step": "GUARD",
          "family": "safety-guarding",
          "output_schema": "safety-record",
          "consumes": "decision-record",
          "params": {
            "checks": ["cluster-accessible", "permissions-sufficient", "backup-recent"],
            "block_on_failure": true
          },
          "profile_gate": "work"
        },
        {
          "step": "SNAPSHOT",
          "family": "safety-guarding",
          "output_schema": "safety-record",
          "consumes": "decision-record",
          "params": {},
          "profile_gate": "work"
        },
        {
          "step": "EXECUTE",
          "family": "generation",
          "output_schema": "execution-report",
          "consumes": "decision-record",
          "params": {},
          "profile_gate": null
        },
        {
          "step": "VALIDATE",
          "family": "validation",
          "output_schema": "verdict",
          "consumes": "execution-report",
          "params": {
            "script": "prometheus-health-check.py"
          },
          "profile_gate": null
        },
        {
          "step": "OUTPUT",
          "family": "synthesis-reporting",
          "output_schema": "pipeline-summary",
          "consumes": "verdict",
          "params": {},
          "profile_gate": null
        }
      ],
      "skill_name": "prometheus-operations",
      "pairs_with_agent": "prometheus-grafana-engineer",
      "references_needed": ["prometheus-cluster-patterns.md", "federation-topology.md"],
      "scripts_needed": ["prometheus-health-check.py"],
      "routing_triggers": ["prometheus scaling", "prometheus storage", "prometheus federation", "prometheus pod", "prometheus troubleshoot"]
    }
  ],
  "shared_references": ["prometheus-domain-knowledge.md"],
  "new_agent": null,
  "reuse_agent": "prometheus-grafana-engineer",
  "operator_profile": "personal"
}
```

### Validation Trace for the Example

The scaffolder validates this spec as follows:

```
Top-level checks:
  [PASS] adr_path "adr/pipeline-prometheus.md" present
  [PASS] adr_hash "sha256:3a7f9b2c..." present and format valid
  [PASS] adr-query.py verify --adr adr/pipeline-prometheus.md --hash sha256:3a7f9b2c... → exit 0
  [PASS] reuse_agent is non-null, new_agent is null -- exactly one executor
  [PASS] operator_profile "personal" is valid
  [PASS] reuse_agent "prometheus-grafana-engineer" exists in agents/INDEX.json

Subdomain 1: metrics-authoring
  [PASS] Chain starts with ADR (invariant)
  [PASS] Chain ends with OUTPUT (pipeline-summary)
  [PASS] Type chain: decision-record -> research-artifact -> structured-corpus
           -> generation-artifact -> verdict -> generation-artifact -> pipeline-summary
  [PASS] All consumes match previous output_schema per family compatibility
  [PASS] skill_name "prometheus-metrics" matches ^[a-z][a-z0-9]*(-[a-z][a-z0-9]*)+$
  [PASS] pairs_with_agent matches reuse_agent
  [PASS] routing_triggers is non-empty (4 triggers)
  [PASS] LINT params.rules "references/metric-naming-conventions.md"
           -> "metric-naming-conventions.md" in references_needed
  [PASS] All profile_gate values are null (valid)

Subdomain 2: cluster-operations
  [PASS] Chain starts with ADR (invariant)
  [PASS] Chain ends with OUTPUT (pipeline-summary)
  [PASS] Type chain: decision-record -> research-artifact -> structured-corpus
           -> decision-record -> safety-record -> safety-record
           -> execution-report -> verdict -> pipeline-summary
  [PASS] GUARD and SNAPSHOT gated on "work" -- valid profile
  [PASS] VALIDATE params.script "prometheus-health-check.py"
           -> in scripts_needed
  [PASS] skill_name "prometheus-operations" matches naming pattern
  [PASS] routing_triggers is non-empty (5 triggers)

Component manifest:
  Skills: prometheus-metrics, prometheus-operations
  References: promql-patterns.md, metric-naming-conventions.md,
              prometheus-cluster-patterns.md, federation-topology.md,
              prometheus-domain-knowledge.md (shared)
  Scripts: promql-validator.py, prometheus-health-check.py
  Agent: reuse prometheus-grafana-engineer (no new agent)
  Routing: 9 trigger phrases across 2 skills

Result: VALID -- proceed to scaffolding
```

---

## Notes on Type Flow Through Safety and Interaction Steps

Safety steps (GUARD, SNAPSHOT, SIMULATE) and interaction steps (PROMPT, APPROVE, PRESENT, NOTIFY) are **transparent** in the type chain. They produce their own artifact types (safety-record, interaction-record) as side effects, but the primary data type passes through unchanged.

In practice, this means the `consumes` field of the step *after* a safety/interaction step should reference the output of the step *before* the safety/interaction step, not the safety/interaction step's own output.

However, for chain serialization simplicity, the spec encodes safety/interaction steps as regular chain members. The scaffolder handles the pass-through semantics internally: when it sees a safety or interaction step, it knows the next non-safety/non-interaction step consumes the artifact from the last substantive step.

This is why in the cluster-operations example above, EXECUTE consumes `decision-record` (from PLAN) even though GUARD and SNAPSHOT sit between them. The safety steps produce safety-records as side effects but don't transform the primary data flow.
