# Pipeline Step Menu

Reference for the Pipeline Architect when composing pipeline chains.
Load this file during chain composition (Phase 2 of pipeline generation).

## How To Use This File

1. For each subdomain, identify the task type (generation, review, debugging, operations, configuration, analysis)
2. Select steps from the appropriate families
3. Validate the chain using the Type Compatibility table
4. Apply Operator Profile gates to remove/add safety steps

---

## Steps By Family

### Research & Gathering

| Step | Output Schema | Consumes | Parallel | When To Use |
|------|--------------|----------|----------|-------------|
| GATHER | Research Artifact | (any) | Yes (3-5) | Broad investigation across codebase/ecosystem |
| SCAN | Research Artifact | (any) | Yes (3) | Structural exploration — file patterns, entry points, conventions |
| RESEARCH | Research Artifact | (any) | Yes (4) | Targeted investigation with domain-specific agent aspects |
| FETCH | Research Artifact | (any) | No | Retrieve content from URLs, files, or external sources |
| SEARCH | Research Artifact | (any) | No | Pattern-based codebase mining for references, callers, examples |

### Structuring

| Step | Output Schema | Consumes | Parallel | When To Use |
|------|--------------|----------|----------|-------------|
| COMPILE | Structured Corpus | Research Artifact | No | Structure raw findings into coherent hierarchy |
| MAP | Structured Corpus | Research Artifact | No | Create architecture/component relationship diagrams |
| OUTLINE | Structured Corpus | Research Artifact | No | Define document/output structure before writing |
| NORMALIZE | Structured Corpus | (any) | No | Standardize inconsistent inputs into canonical form |
| EXTRACT | Structured Corpus | (any) | No | Pull structured data from unstructured sources (logs, prose, HTML, PDFs) |

### Generation

| Step | Output Schema | Consumes | Parallel | When To Use |
|------|--------------|----------|----------|-------------|
| GROUND | Generation Artifact | Structured Corpus, Decision Record | No | Establish context (audience, emotion, mode) before generating |
| GENERATE | Generation Artifact | Structured Corpus, Decision Record | No | Produce content matching target patterns/templates |
| EXECUTE | Execution Report | Decision Record, Generation Artifact | No | Dispatch tasks to domain agents (wave-ordered) |

### Validation

| Step | Output Schema | Consumes | Parallel | When To Use |
|------|--------------|----------|----------|-------------|
| VALIDATE | Verdict | Generation Artifact, Execution Report | No | Run deterministic validation scripts against output |
| VERIFY | Verdict | Generation Artifact, Execution Report | No | Execute code/tests to confirm behavior claims |
| REFINE | Generation Artifact (improved) | Verdict (failing) + Generation Artifact | No | Fix validation failures iteratively (max 3 cycles) |
| CHARACTERIZE | Verdict | (any) | No | Write tests capturing current behavior before changes |

### Review

| Step | Output Schema | Consumes | Parallel | When To Use |
|------|--------------|----------|----------|-------------|
| REVIEW | Verdict | Generation Artifact, Execution Report | Yes (3+) | Launch 3+ specialized reviewers in parallel |
| AGGREGATE | Verdict | Verdict (multiple) | No | Merge reviewer findings, deduplicate, classify severity |

### Git & Release

| Step | Output Schema | Consumes | Parallel | When To Use |
|------|--------------|----------|----------|-------------|
| STAGE | Execution Report | Generation Artifact, Execution Report | No | Analyze and stage changes, block sensitive files |
| COMMIT | Execution Report | Execution Report | No | Create meaningful commit with conventional format |
| PUSH | Execution Report | Execution Report | No | Push to remote with branch setup |
| CREATE_PR | Execution Report | Execution Report | No | Generate PR with accumulated context |

### Learning & Retro

| Step | Output Schema | Consumes | Parallel | When To Use |
|------|--------------|----------|----------|-------------|
| WALK | Learning Record | (any) | Yes (2) | Launch parallel context + meta walkers to extract learnings |
| MERGE | Learning Record | Learning Record | No | Combine walker outputs, classify by hierarchy (L3/L2/L1) |
| GATE | Learning Record | Learning Record | No | Apply approval gates (bottom-up or phase) |
| APPLY | Learning Record | Learning Record | No | Write approved changes/learnings to persistent store |
| CHECKPOINT | Learning Record | (any) | Yes | Save phase artifact, invoke retro, advance state |

### Decision & Planning

| Step | Output Schema | Consumes | Parallel | When To Use |
|------|--------------|----------|----------|-------------|
| ASSESS | Decision Record | Research Artifact, Structured Corpus, Decision Record | No | Evaluate candidates against criteria, identify risks |
| BRAINSTORM | Decision Record | Research Artifact, Structured Corpus | No | Generate 2-3 approaches, select with rationale |
| PLAN | Decision Record | Research Artifact, Structured Corpus, Comparison Report | No | Define steps with dependencies, risks, rollback procedures |
| DECIDE | Decision Record | Research Artifact, Structured Corpus, Comparison Report | No | Evaluate options, filter by criteria, select best |
| PRIME | Decision Record | (any) | No | Load prior artifacts, verify state, capture context |
| SYNTHESIZE | Decision Record | (any) | No | Unify findings across perspectives into ranked recommendations |

### Synthesis & Reporting

| Step | Output Schema | Consumes | Parallel | When To Use |
|------|--------------|----------|----------|-------------|
| REPORT | Pipeline Summary | (any) | No | Generate structured summary with metrics and verdicts |
| OUTPUT | Pipeline Summary | (any) | No | Format and display final artifacts with validation report |
| CLEANUP | Pipeline Summary | Pipeline Summary | No | Remove temporary files, verify final artifacts exist |

### Safety & Guarding

| Step | Output Schema | Consumes | Parallel | When To Use |
|------|--------------|----------|----------|-------------|
| GUARD | Safety Record | (any) | No | Verify pre-conditions before dangerous operations (permissions, deps, disk, health) |
| SIMULATE | Safety Record | (any) | No | Dry-run pipeline steps without committing changes; preview full effect |
| SNAPSHOT | Safety Record | (any) | No | Capture current state as named restore point (db dump, config backup, git stash) |
| ROLLBACK | Safety Record | Safety Record | No | Define and execute undo plan using nearest SNAPSHOT |
| QUARANTINE | Safety Record | (any) | No | Isolate suspicious/failed artifacts without deleting them |

### Comparison & Evaluation

| Step | Output Schema | Consumes | Parallel | When To Use |
|------|--------------|----------|----------|-------------|
| COMPARE | Comparison Report | Two artifacts (same type) | Yes (2) | Side-by-side evaluation against shared criteria (A/B, old vs new) |
| DIFF | Comparison Report | Two artifacts (same type) | No | Compute structured semantic differences between two artifacts |
| BENCHMARK | Comparison Report | Two artifacts (same type) | Yes (N) | Measure quantitative metrics (latency, throughput, accuracy, cost) |
| RANK | Comparison Report | Two artifacts (same type) | No | Order candidates by weighted scoring criteria, produce ranked shortlist |

### Transformation

| Step | Output Schema | Consumes | Parallel | When To Use |
|------|--------------|----------|----------|-------------|
| TRANSFORM | (target type) | (any) | No | Convert data/artifacts from one format/schema to another |
| ENRICH | (same type, augmented) | (any) | No | Augment artifacts with external data, metadata, cross-references |

### Observation

| Step | Output Schema | Consumes | Parallel | When To Use |
|------|--------------|----------|----------|-------------|
| MONITOR | Research Artifact | Execution Report, Safety Record, Decision Record, Research Artifact | No | Observe runtime behavior/metrics over a defined time window |
| PROBE | Research Artifact | Execution Report, Safety Record, Decision Record, Research Artifact | No | Active health/connectivity checks against live systems or APIs |
| TRACE | Research Artifact | Execution Report, Safety Record, Decision Record, Research Artifact | No | Follow a request/event/data flow through multi-component system |
| SAMPLE | Research Artifact | (any) | No | Collect representative examples from large dataset or stream |

### Domain Extension

| Step | Output Schema | Consumes | Parallel | When To Use |
|------|--------------|----------|----------|-------------|
| LINT | Verdict | Generation Artifact | No | Run domain-specific linting rules (PromQL, HCL, YAML, SQL) |
| TEMPLATE | Generation Artifact | Structured Corpus, Decision Record | No | Apply domain-specific templates/boilerplate with variable substitution |
| MIGRATE | Execution Report | Decision Record | No | Incremental state transition from old format/schema to new with rollback |
| CONFORM | Verdict | Generation Artifact | No | Check output against domain schema/spec/contract (OpenAPI, JSON Schema, protobuf) |
| ADAPT | Generation Artifact | Generation Artifact | No | Modify generic output to fit domain-specific conventions or idioms |

### Interaction

| Step | Output Schema | Consumes | Parallel | When To Use |
|------|--------------|----------|----------|-------------|
| PROMPT | Interaction Record | (any) | No | Request human input at a decision point where pipeline lacks confidence |
| NOTIFY | Interaction Record | (any) | No | Send status/results/alerts to external systems (Slack, email, GitHub) |
| APPROVE | Interaction Record | (any) | No | Hard gate on explicit human approval before proceeding — blocks until received |
| PRESENT | Interaction Record | (any) | No | Format intermediate results for human consumption without blocking |

### Orchestration

| Step | Output Schema | Consumes | Parallel | When To Use |
|------|--------------|----------|----------|-------------|
| DECOMPOSE | Orchestration Manifest | Decision Record, Structured Corpus | No | Split complex task into independent sub-tasks, each gets own mini-chain |
| DELEGATE | Orchestration Manifest | Decision Record, Structured Corpus | Yes | Hand off sub-task to another complete pipeline (cross-domain invocation) |
| CONVERGE | Orchestration Manifest | Orchestration Manifest | No | Merge results from multiple sub-pipelines into unified artifact |
| SEQUENCE | Orchestration Manifest | Orchestration Manifest | No | Chain multiple pipelines end-to-end with output-to-input binding |
| RETRY | Orchestration Manifest | (any failed) | No | Re-execute a failed step/sub-chain with adjusted parameters (max N attempts) |

### State Management

| Step | Output Schema | Consumes | Parallel | When To Use |
|------|--------------|----------|----------|-------------|
| CACHE | State Record | (any) | No | Store expensive computation results for reuse by downstream steps or future runs |
| RESUME | State Record | State Record | No | Pick up from last successful CHECKPOINT after failure (skip completed phases) |
| HYDRATE | State Record | State Record | No | Load cached/persisted state into working memory from prior runs |
| PERSIST | State Record | (any) | No | Write pipeline state to durable storage for cross-session access |
| EXPIRE | State Record | State Record | No | Invalidate cached/persisted state that exceeded TTL or was superseded |

### Experimentation

| Step | Output Schema | Consumes | Parallel | When To Use |
|------|--------------|----------|----------|-------------|
| CANARY | Experiment Report | (any) | No | Apply changes to small subset first, validate, then proceed to full rollout |
| FUZZ | Experiment Report | (any) | No | Generate random/edge-case/adversarial inputs to test robustness |
| REPLAY | Experiment Report | (any) | No | Re-execute previous pipeline run with modified parameters or inputs |
| ABLATE | Comparison Report | (any) | No | Remove one component/step and re-run to measure its contribution |
| SHADOW | Comparison Report | (any) | No | Run new version of step alongside existing one without affecting output |

### Invariant

| Step | Output Schema | Consumes | Parallel | When To Use |
|------|--------------|----------|----------|-------------|
| ADR | Decision Record | (none) | No | **Every pipeline** — create persistent reference document before work begins |

---

## Type Compatibility Matrix

The Pipeline Architect validates chains by checking that each step's output schema is compatible with the next step's expected input.

| Step Family | Consumes | Produces |
|-------------|----------|----------|
| Research & Gathering | (any -- starts chains) | Research Artifact |
| Structuring | Research Artifact | Structured Corpus |
| Decision & Planning | Research Artifact, Structured Corpus, Comparison Report, (any for SYNTHESIZE) | Decision Record |
| Generation | Structured Corpus, Decision Record | Generation Artifact |
| Validation | Generation Artifact, Execution Report | Verdict |
| Review | Generation Artifact, Execution Report | Verdict |
| Refinement | Verdict (failing) + Generation Artifact | Generation Artifact (improved) |
| Git & Release | Generation Artifact, Execution Report | Execution Report |
| Safety & Guarding | (any -- wraps dangerous steps) | Safety Record |
| Comparison & Evaluation | Two artifacts of same type | Comparison Report |
| Transformation | Any artifact | Artifact of different type |
| Observation | Execution Report, Safety Record, Decision Record, Research Artifact | Research Artifact |
| Domain Extension | Generation Artifact | Verdict |
| Interaction | Any artifact | Interaction Record |
| Orchestration | Decision Record, Structured Corpus | Orchestration Manifest |
| State Management | Any artifact | State Record |
| Experimentation | Any two artifacts, Comparison Report | Experiment Report |
| Learning & Retro | Any artifact | Learning Record |
| Synthesis & Reporting | Any artifact(s) | Pipeline Summary |

---

## Composition Rules

### Structural Rules

**Rule: Every chain starts with ADR**
```
ADR -> [domain-specific steps] -> OUTPUT
```

**Rule: Research before Generation**
If the pipeline generates content/artifacts, it must research first.
```
ADR -> RESEARCH -> [structuring] -> GENERATE -> VALIDATE -> OUTPUT
```

**Rule: Validation after Generation**
If the pipeline produces output that can be verified deterministically.
```
... -> GENERATE -> VALIDATE -> REFINE (if needed) -> OUTPUT
```

**Rule: Characterize before Modification**
If the pipeline modifies existing code/state, capture current behavior first.
```
ADR -> CHARACTERIZE -> PLAN -> EXECUTE -> VALIDATE -> OUTPUT
```

**Rule: Review is parallel with 3+ lenses**
If the pipeline reviews work, use parallel specialized reviewers.
```
ADR -> ASSESS -> REVIEW (3+ parallel) -> AGGREGATE -> REPORT
```

**Rule: Retro at checkpoints**
If the pipeline has multiple stateful phases, each transition gets a retro.
```
... -> EXECUTE -> CHECKPOINT (retro) -> next phase -> CHECKPOINT (retro) -> ...
```

**Rule: Pipeline Summary is always terminal**
REPORT, OUTPUT, and CLEANUP produce Pipeline Summary, which is the final artifact. Nothing consumes it. SYNTHESIZE produces Decision Record (not Pipeline Summary) and can precede REPORT.

### Profile-Aware Rules

These rules are gated by Operator Profile. The Pipeline Architect adds or removes steps based on detected profile.

**Rule: Guard before Danger** *(Work, Production only -- skipped in Personal/CI)*
If the pipeline modifies production state, shared infrastructure, or irreversible resources.
```
... -> GUARD -> SNAPSHOT -> EXECUTE -> VALIDATE -> (ROLLBACK if failed) -> ...
```

**Rule: Simulate before Commit** *(Production only -- optional elsewhere)*
If the pipeline produces large-scale changes (bulk edits, migrations, infrastructure).
```
ADR -> PLAN -> SIMULATE -> APPROVE -> EXECUTE -> VALIDATE -> OUTPUT
```

**Rule: Human gates for irreversible actions** *(Production only -- skipped in Personal/CI)*
If the pipeline performs actions that cannot be undone.
```
... -> PRESENT -> APPROVE -> EXECUTE -> NOTIFY -> ...
```

### Optimization Rules

**Rule: Canary before Full Rollout**
If the pipeline deploys or applies changes to a large target set, test on subset first.
```
... -> CANARY (subset) -> VALIDATE -> EXECUTE (full) -> VALIDATE -> OUTPUT
```

**Rule: Conform after Generate**
If the pipeline produces artifacts that must match an external spec (API, schema, protocol).
```
... -> GENERATE -> CONFORM -> REFINE (if needed) -> OUTPUT
```

**Rule: Cache expensive research**
If the same research data is needed by multiple downstream steps or future runs.
```
... -> RESEARCH -> CACHE -> [multiple consumers read from cache] -> ...
```

### Delegation Rules

**Rule: Delegate for Cross-Domain**
If a pipeline step requires expertise from a different domain's pipeline.
```
... -> DELEGATE (sub-pipeline) -> CONVERGE -> ...
```

**Rule: Shadow before Replace**
If upgrading an existing pipeline step with a new implementation.
```
... -> SHADOW (old + new in parallel) -> COMPARE -> DECIDE -> [swap or keep] -> ...
```

### Type Rules

**Rule: Output must match input**
If step B expects a Structured Corpus, the preceding step must produce one. Reject chains where types don't align.

**Rule: Verdict gates block on failure**
Any step producing a Verdict can gate the next step. If Verdict is BLOCK/CRITICAL, the chain stops (or routes to REFINE/ROLLBACK).

**Rule: Comparison requires two artifacts of same schema type**
COMPARE, DIFF, BENCHMARK, ABLATE, and SHADOW require exactly two inputs of the same type.

**Rule: Safety steps wrap -- they don't replace**
GUARD, SIMULATE, SNAPSHOT produce Safety Records *alongside* the normal flow. The chain's primary data type passes through unchanged.

**Rule: Interaction steps are transparent**
PROMPT, APPROVE, PRESENT, NOTIFY produce Interaction Records as side effects. The primary artifact type passes through unchanged.

---

## Operator Profiles

The same logical chain produces different concrete chains depending on profile.

| Profile | Detection | Safety Steps | Interaction Steps |
|---------|-----------|-------------|-------------------|
| **Personal** | Not organizational/client repo, user's personal GitHub | GUARD: branch-check only. SIMULATE/SNAPSHOT: available, not mandatory | SKIP all (PROMPT, APPROVE removed; NOTIFY optional) |
| **Work** | Organizational repo, client repo, compliance markers | Full GUARD + SNAPSHOT for state changes. CONFORM added | APPROVE for production-affecting changes. PROMPT when conventions conflict |
| **CI** | `CI=true` env var, GitHub Actions, Docker | GUARD: checks deps/tools exist, not permissions | SKIP all. NOTIFY sends to PR/Slack |
| **Production** | `PRODUCTION=true`, production branch, deploy pipeline | Full GUARD + SNAPSHOT + SIMULATE mandatory. APPROVE required | APPROVE mandatory. PRESENT before and after |

### Profile Chain Examples

```
Logical:     ADR -> RESEARCH -> GENERATE -> VALIDATE -> EXECUTE -> OUTPUT

Personal:    ADR -> RESEARCH -> GENERATE -> VALIDATE -> EXECUTE -> OUTPUT
Work:        ADR -> RESEARCH -> GENERATE -> VALIDATE -> CONFORM -> EXECUTE -> OUTPUT
CI:          ADR -> RESEARCH -> GENERATE -> VALIDATE -> EXECUTE -> NOTIFY -> OUTPUT
Production:  ADR -> RESEARCH -> GENERATE -> VALIDATE -> APPROVE -> GUARD -> SNAPSHOT -> EXECUTE -> VALIDATE -> OUTPUT
```

---

## Quick Reference: Common Chain Patterns

### Generation Pipeline
Content creation: articles, documentation, configs, code.
```
ADR -> RESEARCH -> COMPILE -> GENERATE -> VALIDATE -> OUTPUT
```
Variants:
- With voice: `ADR -> RESEARCH -> COMPILE -> GROUND -> GENERATE -> VALIDATE -> OUTPUT`
- With domain lint: `ADR -> RESEARCH -> COMPILE -> GENERATE -> LINT -> CONFORM -> OUTPUT`
- With refinement: `ADR -> RESEARCH -> COMPILE -> GENERATE -> VALIDATE -> REFINE -> OUTPUT`

### Review Pipeline
Code review, architecture review, PR review.
```
ADR -> ASSESS -> REVIEW (3+ parallel) -> AGGREGATE -> REPORT
```
Variants:
- With pre-research: `ADR -> RESEARCH -> ASSESS -> REVIEW -> AGGREGATE -> REPORT`
- With execution: `ADR -> ASSESS -> REVIEW -> AGGREGATE -> EXECUTE -> REPORT`

### Debugging Pipeline
Systematic debugging, root cause analysis.
```
ADR -> PROBE -> SEARCH -> PLAN -> EXECUTE -> VERIFY -> OUTPUT
```
Variants:
- With tracing: `ADR -> PROBE -> TRACE -> SEARCH -> PLAN -> EXECUTE -> VERIFY -> OUTPUT`
- With characterization: `ADR -> CHARACTERIZE -> PROBE -> SEARCH -> PLAN -> EXECUTE -> VERIFY -> OUTPUT`

### Migration Pipeline
Format conversion, schema evolution, upgrades.
```
ADR -> CHARACTERIZE -> PLAN -> GUARD -> SNAPSHOT -> EXECUTE -> VALIDATE -> OUTPUT
```
Variants:
- With simulation: `ADR -> CHARACTERIZE -> PLAN -> SIMULATE -> APPROVE -> SNAPSHOT -> EXECUTE -> VALIDATE -> OUTPUT`
- With canary: `ADR -> CHARACTERIZE -> PLAN -> SNAPSHOT -> CANARY -> VALIDATE -> EXECUTE -> VALIDATE -> OUTPUT`

### Operations Pipeline
Cluster management, troubleshooting, deployments.
```
ADR -> PROBE -> ASSESS -> PLAN -> GUARD -> EXECUTE -> MONITOR -> OUTPUT
```
Variants:
- With snapshot: `ADR -> PROBE -> ASSESS -> PLAN -> GUARD -> SNAPSHOT -> EXECUTE -> MONITOR -> VALIDATE -> OUTPUT`
- With rollback: `ADR -> PROBE -> ASSESS -> PLAN -> GUARD -> SNAPSHOT -> EXECUTE -> VALIDATE -> (ROLLBACK if failed) -> OUTPUT`

### Analysis Pipeline
Performance tuning, benchmarking, optimization.
```
ADR -> RESEARCH -> BENCHMARK (baseline) -> ASSESS -> PLAN -> EXECUTE -> BENCHMARK (after) -> COMPARE -> OUTPUT
```
Variants:
- With canary: `ADR -> RESEARCH -> BENCHMARK -> ASSESS -> PLAN -> CANARY -> BENCHMARK -> COMPARE -> EXECUTE (full) -> OUTPUT`

### Learning Pipeline
Retro extraction, knowledge transfer, self-improvement.
```
ADR -> WALK (parallel) -> MERGE -> GATE -> APPLY -> OUTPUT
```
Variants:
- With checkpoints: `ADR -> EXECUTE -> CHECKPOINT -> WALK -> MERGE -> GATE -> APPLY -> OUTPUT`
