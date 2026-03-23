# Canonical Chain Templates

Reference for Phase 2 (COMPOSE) of the chain-composer skill.
Load this file during composition to select the correct starting template for each subdomain's task type.

## How To Use This File

1. Look up the subdomain's `task_type` in the table below
2. Select the canonical chain as the starting template
3. Review the common variants to see if any apply to the subdomain
4. Adapt the template with domain-specific steps and operator profile gates (per Phase 2 Steps 2-4)

Do NOT compose chains from scratch. Always start from a canonical template.

---

## Generation

**Task type**: `generation`
**Use when**: The subdomain produces new artifacts -- code, configs, documentation, queries, templates.

### Canonical Chain
```
ADR -> RESEARCH -> COMPILE -> GENERATE -> VALIDATE -> OUTPUT
```

### Type Flow
```
decision-record -> research-artifact -> structured-corpus -> generation-artifact -> verdict -> pipeline-summary
```

### Common Variants

**With voice/audience targeting** (content that needs tone control):
```
ADR -> RESEARCH -> COMPILE -> GROUND -> GENERATE -> VALIDATE -> OUTPUT
```
When to use: Blog posts, user-facing documentation, content with a specific voice profile.

**With domain linting** (output has checkable syntax):
```
ADR -> RESEARCH -> COMPILE -> GENERATE -> LINT -> VALIDATE -> OUTPUT
```
When to use: PromQL, HCL, SQL, YAML, or any domain with deterministic syntax checking.
Note: LINT is transparent -- it produces a verdict as a side effect but primary data flow (generation-artifact) passes through.

**With spec conformance** (output must match external contract):
```
ADR -> RESEARCH -> COMPILE -> GENERATE -> CONFORM -> VALIDATE -> OUTPUT
```
When to use: OpenAPI specs, JSON Schema, protobuf definitions, domain schemas.
Note: CONFORM is transparent like LINT.

**With lint AND conformance**:
```
ADR -> RESEARCH -> COMPILE -> GENERATE -> LINT -> CONFORM -> VALIDATE -> OUTPUT
```
When to use: Domain artifacts that have both syntax rules (lint) and structural contracts (conform).

**With iterative refinement** (validation may fail):
```
ADR -> RESEARCH -> COMPILE -> GENERATE -> VALIDATE -> REFINE -> OUTPUT
```
When to use: When the validation script catches fixable issues (formatting, conventions) that the REFINE step can correct. REFINE has `max_refine_cycles: 3`.

**With template application** (boilerplate-heavy output):
```
ADR -> RESEARCH -> COMPILE -> TEMPLATE -> VALIDATE -> OUTPUT
```
When to use: When the output follows a rigid template (Helm charts, CI configs, Terraform modules). TEMPLATE replaces GENERATE when the output structure is more template-fill than free-form generation.

---

## Review

**Task type**: `review`
**Use when**: The subdomain evaluates existing work against criteria -- code review, architecture review, PR review, security audit.

### Canonical Chain
```
ADR -> RESEARCH -> ASSESS -> REVIEW (3+ parallel) -> AGGREGATE -> REPORT
```

### Type Flow
```
decision-record -> research-artifact -> decision-record -> verdict -> verdict -> pipeline-summary
```

### Common Variants

**Minimal review** (pre-research not needed):
```
ADR -> ASSESS -> REVIEW (3+ parallel) -> AGGREGATE -> REPORT
```
When to use: When the review target is already well-understood (e.g., reviewing a PR where the diff is the complete context).

**With execution** (review findings lead to fixes):
```
ADR -> RESEARCH -> ASSESS -> REVIEW (3+ parallel) -> AGGREGATE -> EXECUTE -> REPORT
```
When to use: When the review isn't just advisory -- findings should be applied as fixes (e.g., automated code fix after review).

**With pre-scan** (large codebase review):
```
ADR -> SCAN -> ASSESS -> REVIEW (3+ parallel) -> AGGREGATE -> REPORT
```
When to use: Architecture reviews, codebase health checks where structural exploration precedes evaluation.

### Review Step Configuration

The REVIEW step always runs 3+ parallel reviewers. Each reviewer gets a different lens:

```json
{
  "step": "REVIEW",
  "params": {
    "reviewers": 3,
    "lenses": ["lens-1", "lens-2", "lens-3"]
  }
}
```

Common lens sets by domain:

| Domain | Lens 1 | Lens 2 | Lens 3 | Lens 4 (optional) |
|--------|--------|--------|--------|-------------------|
| Code | Architecture | Security | Correctness | Performance |
| Documentation | Accuracy | Completeness | Clarity | Audience fit |
| Infrastructure | Security | Reliability | Cost | Compliance |
| API | Contract | Security | Usability | Versioning |

---

## Debugging

**Task type**: `debugging`
**Use when**: The subdomain diagnoses and fixes problems in running systems or code -- root cause analysis, error investigation, systematic debugging.

### Canonical Chain
```
ADR -> PROBE -> SEARCH -> ASSESS -> PLAN -> EXECUTE -> VERIFY -> OUTPUT
```

### Type Flow
```
decision-record -> research-artifact -> research-artifact -> decision-record -> decision-record -> execution-report -> verdict -> pipeline-summary
```

### Common Variants

**With distributed tracing** (multi-service issues):
```
ADR -> PROBE -> TRACE -> SEARCH -> ASSESS -> PLAN -> EXECUTE -> VERIFY -> OUTPUT
```
When to use: Debugging issues that span multiple services, where request flow needs tracing.

**With characterization** (capture before fix):
```
ADR -> CHARACTERIZE -> PROBE -> SEARCH -> ASSESS -> PLAN -> EXECUTE -> VERIFY -> OUTPUT
```
When to use: When you need to capture the current broken behavior as a test before fixing it, ensuring the fix actually changes the behavior.

**Investigation only** (diagnose but don't fix):
```
ADR -> PROBE -> SEARCH -> ASSESS -> SYNTHESIZE -> REPORT
```
When to use: When the subdomain only needs to identify the root cause, not fix it (e.g., post-mortem analysis, issue triage).

---

## Operations

**Task type**: `operations`
**Use when**: The subdomain manages infrastructure, deployments, cluster state -- scaling, storage management, federation setup, service management.

### Canonical Chain
```
ADR -> PROBE -> ASSESS -> PLAN -> GUARD -> EXECUTE -> VALIDATE -> OUTPUT
```

### Type Flow
```
decision-record -> research-artifact -> decision-record -> decision-record -> safety-record -> execution-report -> verdict -> pipeline-summary
```

Note: GUARD is transparent. EXECUTE consumes `decision-record` from PLAN (passing through GUARD).

### Common Variants

**With snapshot** (reversible operations):
```
ADR -> PROBE -> ASSESS -> PLAN -> GUARD -> SNAPSHOT -> EXECUTE -> VALIDATE -> OUTPUT
```
When to use: Operations that modify state and need a restore point (database changes, config modifications, scaling operations).

**With rollback** (operations that can fail):
```
ADR -> PROBE -> ASSESS -> PLAN -> GUARD -> SNAPSHOT -> EXECUTE -> VALIDATE -> OUTPUT
```
When to use: Same as with-snapshot. If VALIDATE fails, the ROLLBACK step is triggered manually (it's not part of the happy-path chain).

**With monitoring** (post-operation observation):
```
ADR -> PROBE -> ASSESS -> PLAN -> GUARD -> EXECUTE -> MONITOR -> VALIDATE -> OUTPUT
```
When to use: Operations where the effect isn't immediate -- deployment rollouts, scaling events, configuration propagation that needs observation time.

**Observation only** (no changes):
```
ADR -> PROBE -> MONITOR -> ASSESS -> REPORT
```
When to use: Health checks, monitoring dashboards, status reporting where no changes are made.

---

## Configuration

**Task type**: `configuration`
**Use when**: The subdomain produces configuration files, templates, or schema-conformant artifacts -- Helm values, Terraform configs, CI manifests, YAML configs.

### Canonical Chain
```
ADR -> RESEARCH -> COMPILE -> TEMPLATE -> CONFORM -> VALIDATE -> OUTPUT
```

### Type Flow
```
decision-record -> research-artifact -> structured-corpus -> generation-artifact -> verdict -> verdict -> pipeline-summary
```

Note: CONFORM is transparent. VALIDATE consumes `generation-artifact` from TEMPLATE (passing through CONFORM).

### Common Variants

**With multiple source compilation** (complex configs from many sources):
```
ADR -> GATHER -> COMPILE -> TEMPLATE -> CONFORM -> VALIDATE -> OUTPUT
```
When to use: When configuration requires broad research (GATHER with parallel agents) rather than targeted RESEARCH before template application.

**With iterative refinement** (conformance may fail):
```
ADR -> RESEARCH -> TEMPLATE -> CONFORM -> REFINE -> VALIDATE -> OUTPUT
```
When to use: When the generated config may not conform on the first attempt and needs iterative correction.

**Generation instead of template** (free-form config):
```
ADR -> RESEARCH -> COMPILE -> GENERATE -> CONFORM -> VALIDATE -> OUTPUT
```
When to use: When the configuration is not template-based but needs to be generated and then checked against a spec.

---

## Analysis

**Task type**: `analysis`
**Use when**: The subdomain performs research-heavy evaluation producing recommendations -- performance tuning, capacity planning, cost analysis, architecture assessment.

### Canonical Chain
```
ADR -> RESEARCH -> COMPILE -> ASSESS -> SYNTHESIZE -> REPORT
```

### Type Flow
```
decision-record -> research-artifact -> structured-corpus -> decision-record -> decision-record -> pipeline-summary
```

Note: SYNTHESIZE produces `decision-record` (it synthesizes findings into ranked recommendations). REPORT is the terminal step producing `pipeline-summary`.

### Common Variants

**With benchmarking** (quantitative analysis):
```
ADR -> RESEARCH -> BENCHMARK -> ASSESS -> PLAN -> EXECUTE -> BENCHMARK -> COMPARE -> REPORT
```
When to use: Performance tuning, optimization validation where before/after metrics are needed.

**With canary** (phased analysis):
```
ADR -> RESEARCH -> ASSESS -> PLAN -> CANARY -> BENCHMARK -> COMPARE -> REPORT
```
When to use: When the analysis involves testing changes on a subset before full assessment.

**Multi-perspective synthesis** (broad research):
```
ADR -> GATHER -> COMPILE -> ASSESS -> BRAINSTORM -> DECIDE -> SYNTHESIZE -> REPORT
```
When to use: Strategic analysis where multiple approaches need evaluation and a recommendation.

---

## Migration

**Task type**: `migration`
**Use when**: The subdomain moves from one state/schema/version to another -- database migrations, config format upgrades, API version transitions, schema evolution.

### Canonical Chain
```
ADR -> CHARACTERIZE -> PLAN -> GUARD -> SNAPSHOT -> EXECUTE -> VALIDATE -> OUTPUT
```

### Type Flow
```
decision-record -> verdict -> decision-record -> safety-record -> safety-record -> execution-report -> verdict -> pipeline-summary
```

Note: CHARACTERIZE produces a `verdict` (capturing current behavior). PLAN consumes it (decision-planning family accepts any). GUARD and SNAPSHOT are transparent. EXECUTE consumes `decision-record` from PLAN.

### Common Variants

**With simulation** (high-risk migrations):
```
ADR -> CHARACTERIZE -> PLAN -> SIMULATE -> APPROVE -> GUARD -> SNAPSHOT -> EXECUTE -> VALIDATE -> OUTPUT
```
When to use: Production database migrations, schema changes affecting live data, irreversible transformations.

**With canary** (phased migrations):
```
ADR -> CHARACTERIZE -> PLAN -> GUARD -> SNAPSHOT -> CANARY -> VALIDATE -> EXECUTE -> VALIDATE -> OUTPUT
```
When to use: Large-scale migrations where testing on a subset first reduces risk.

**With diff** (migration verification):
```
ADR -> CHARACTERIZE -> PLAN -> GUARD -> SNAPSHOT -> EXECUTE -> DIFF -> VALIDATE -> OUTPUT
```
When to use: When migration correctness is verified by comparing old vs. new state.

---

## Testing

**Task type**: `testing`
**Use when**: The subdomain generates or structures test suites -- test scaffolding, test data generation, test coverage analysis, fuzz testing.

### Canonical Chain
```
ADR -> RESEARCH -> COMPILE -> CHARACTERIZE -> GENERATE -> VALIDATE -> REPORT
```

### Type Flow
```
decision-record -> research-artifact -> structured-corpus -> [transparent: structured-corpus] -> generation-artifact -> verdict -> pipeline-summary
```

Note: COMPILE converts research findings into structured corpus. CHARACTERIZE is transparent (captures current behavior as verdict side-effect, passes structured-corpus through). GENERATE consumes the structured-corpus that flows through CHARACTERIZE.

### Common Variants

**With fuzzing** (robustness testing):
```
ADR -> RESEARCH -> COMPILE -> CHARACTERIZE -> FUZZ -> VALIDATE -> REPORT
```
When to use: Input validation testing, API boundary testing, configuration stress testing.

**With benchmarking** (performance test suites):
```
ADR -> RESEARCH -> COMPILE -> CHARACTERIZE -> GENERATE -> BENCHMARK -> COMPARE -> REPORT
```
When to use: Creating performance test suites that include baseline and comparison metrics.

**Exploration-first** (understanding before generating):
```
ADR -> SCAN -> COMPILE -> CHARACTERIZE -> GENERATE -> VALIDATE -> REPORT
```
When to use: When the codebase needs structural exploration before tests can be designed.

---

## Operator Profile Modifier Reference

After selecting and adapting a canonical chain, apply these modifiers based on the operator profile. This table summarizes what each profile adds or removes.

| Action | Personal | Work | CI | Production |
|--------|----------|------|-----|------------|
| Remove APPROVE | Yes | No | Yes | No |
| Remove PROMPT | Yes | No | Yes | No |
| Reduce GUARD | branch-check only | Full checks | dep/tool checks | Full + mandatory |
| Add CONFORM | No | Yes (after GENERATE) | No | No |
| Add NOTIFY | No | No | Yes (before terminal) | No |
| Add SIMULATE | No | No | No | Yes (before EXECUTE) |
| Add SNAPSHOT | No | If state changes | No | Yes (mandatory) |
| Add APPROVE | No | If production-affecting | No | Yes (mandatory) |
| Add PRESENT | No | No | No | Yes (before/after EXECUTE) |

### Profile Application Order

Apply profile modifiers in this order to avoid conflicts:

1. **Removals first**: Remove steps that the profile excludes (APPROVE, PROMPT for personal/CI)
2. **Reductions**: Reduce step params (GUARD checks for personal/CI)
3. **Additions**: Add steps the profile requires (CONFORM for work, NOTIFY for CI, safety steps for production)
4. **Set profile_gate**: For steps added by profile, set `profile_gate` to the profile that requires them
