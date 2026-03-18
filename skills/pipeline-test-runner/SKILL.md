---
name: pipeline-test-runner
description: |
  Test generated pipeline skills against real targets. Discovers test targets
  (fixtures, codebase files, or synthetic inputs), runs each subdomain skill
  in parallel, validates dual-layer artifacts, and produces a pass/fail report
  with failure traces. Use after pipeline-scaffolder completes, for "test
  generated pipelines", "run pipeline tests", "validate scaffolded skills".
  Do NOT use for testing hand-written skills, unit testing scripts, or
  evaluating voice/content quality.
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
  - Agent
routing:
  triggers:
    - test generated pipelines
    - run pipeline tests
    - validate scaffolded skills
    - pipeline test runner
  pairs_with:
    - pipeline-scaffolder
    - pipeline-retro
    - chain-composer
  complexity: Medium
  category: meta
---

# Pipeline Test Runner

## Purpose

Validate that generated pipeline skills actually work by running them against real targets. Chain validation (done by `chain-composer` and `scripts/artifact-utils.py validate-chain`) checks type compatibility between steps. This skill checks **execution** -- does the skill produce valid artifacts when given real input? The distinction matters because a chain can be type-valid but produce empty content, crash on domain-specific inputs, or timeout due to overly complex research phases.

This skill is Phase 5 of the pipeline orchestrator's 7-phase flow. Its output feeds directly into `pipeline-retro` (Phase 6), which traces failures back to the generator using the Three-Layer Pattern.

## Operator Context

### Hardcoded Behaviors (Always Apply)
- **CLAUDE.md Compliance**: Read and follow repository CLAUDE.md files before execution. Project instructions override default skill behaviors.
- **Pipeline Spec Required**: Input MUST include the Pipeline Spec JSON (same spec consumed by `pipeline-scaffolder`). The spec defines what subdomains exist, what skills were generated, and what scripts/references each skill expects. WHY: Without the spec, the test runner doesn't know what to test or what "success" looks like.
- **Per-Subdomain Results**: Every subdomain gets its own result (PASS/PARTIAL/FAIL/TIMEOUT). Never aggregate into a single pass/fail that hides individual failures. WHY: The retro skill (Phase 6) needs per-subdomain failure traces to fix the correct generator component. A blanket "FAIL" tells the retro nothing about which subdomain or which chain step broke.
- **No Production Targets**: Test against repo files, fixtures, or synthetic inputs only. Never invoke skills against live/external systems. WHY: Test runs happen during pipeline generation -- they must be safe, repeatable, and free of side effects.
- **Artifact Validation via Script**: Always use `scripts/artifact-utils.py validate-manifest` for manifest validation rather than manual JSON inspection. WHY: The script implements the canonical validation rules from the ADR. Manual checks will drift from the spec over time.

### Default Behaviors (ON unless disabled)
- **Communication Style**: Report facts without self-congratulation. Show per-subdomain results table, not narrative descriptions.
- **Temporary File Cleanup**: Remove `/tmp/pipeline-test-*` directories after the report is produced. Keep only the final report artifacts.
- **Parallel Execution**: Fan out skill runs up to 5 in parallel. Batch larger sets into groups of 5. WHY: Parallel execution matches the pipeline architecture's "parallel over sequential" principle, but unbounded parallelism risks context exhaustion.
- **Timeout Enforcement**: 5 minutes per skill run. Skills that exceed this are classified as TIMEOUT rather than left to run indefinitely.

### Optional Behaviors (OFF unless enabled)
- **Verbose Traces**: Include full skill output in the report (default: summary + failure traces only)
- **Skip Synthetic**: Disable synthetic target generation -- only test subdomains with real targets
- **Extended Timeout**: Increase per-skill timeout to 10 minutes (for complex chains with 7+ steps)

## What This Skill CAN Do
- Discover appropriate test targets for each subdomain (fixtures, codebase files, synthetic)
- Run N subdomain skills in parallel batches of up to 5
- Validate dual-layer artifacts (manifest.json + content.md) using `scripts/artifact-utils.py`
- Produce per-subdomain PASS/PARTIAL/FAIL/TIMEOUT classifications
- Generate failure traces linking failures to specific chain steps
- Produce a dual-layer report artifact for consumption by `pipeline-retro`

## What This Skill CANNOT Do
- **Fix failed skills**: Fixing is `pipeline-retro`'s job (Three-Layer Pattern: Layer 2 fixes the generator, not the artifact)
- **Test against external systems**: Only repo files, fixtures, and synthetic targets
- **Evaluate content quality**: Tests structural validity (manifest exists, content non-empty, status complete) not semantic quality (is the generated PromQL correct?)
- **Run more than 10 subdomain tests per batch**: System limit on parallel agents

When asked to perform unavailable actions, explain the limitation and suggest the appropriate skill.

---

## Instructions

### Input

This skill requires:
- **Pipeline Spec JSON**: The validated spec from `chain-composer` / `pipeline-scaffolder` (path or inline)
- **Scaffolding Report** (optional): The report from `pipeline-scaffolder` Phase 5, confirming all components exist

The spec provides:
- `spec.subdomains[*].skill_name` -- what skills to test
- `spec.subdomains[*].routing_triggers` -- how to invoke each skill
- `spec.subdomains[*].scripts_needed` -- what validation scripts exist
- `spec.subdomains[*].references_needed` -- what domain references are available
- `spec.domain` -- the target domain (used for fixture/codebase search)
- `spec.reuse_agent` or `spec.new_agent.name` -- the executing agent

### Phase 1: DISCOVER TARGETS

**Goal**: For each subdomain skill, identify a suitable test target that exercises the skill's pipeline chain.

**Why this phase exists**: A skill that passes chain validation (types match) can still fail when given real input. The research phase might find nothing relevant, the generation phase might produce empty content, or the validation script might reject the output. Testing against real targets catches these failures before the pipeline ships.

**Step 1: Load the Pipeline Spec**

Read the spec and extract the subdomain list:
```
subdomains = spec.subdomains
domain = spec.domain
agent = spec.reuse_agent or spec.new_agent.name
```

**Step 2: For each subdomain, find a test target**

Search in priority order. Stop at the first match:

**Priority 1 -- Test fixtures**:
```bash
ls tests/fixtures/{domain}/ 2>/dev/null
ls tests/fixtures/{subdomain.name}/ 2>/dev/null
```
Fixture files are purpose-built for testing and are the most reliable targets.

**Priority 2 -- Codebase files**:
Search the repo for files matching the subdomain's domain. The search strategy depends on the subdomain's task type:

| Task Type | Search Strategy |
|-----------|----------------|
| `generation` | Find existing examples of the output type (configs, queries, code) |
| `review` | Find existing code/config that could be reviewed |
| `debugging` | Find log files, error reports, or test failure output |
| `operations` | Find infrastructure configs, deployment files |
| `configuration` | Find existing config files in the target format |
| `analysis` | Find existing reports, metrics, or data files |
| `migration` | Find files in the "old" format |
| `testing` | Find existing code that needs test generation |

Use Glob and Grep to search. Examples:
```bash
# For prometheus-metrics (generation, PromQL):
# Search for existing .rules files, prometheus configs, PromQL expressions
```

**Priority 3 -- Synthetic targets**:
If no real targets exist, create a minimal synthetic target that exercises the skill's chain. The synthetic target should be:
- Small enough to process quickly (under 50 lines)
- Representative of the subdomain's input type
- Valid input that the skill's chain can actually consume

Save synthetic targets to `/tmp/pipeline-test-{run-id}/targets/{subdomain.name}/`.

**Step 3: Record target metadata**

For each subdomain, record:
```json
{
  "subdomain": "{name}",
  "skill_name": "{skill_name}",
  "target_type": "fixture|codebase|synthetic",
  "target_path": "/path/to/target",
  "expected_output": {
    "has_manifest": true,
    "has_content": true,
    "status": "complete",
    "schema": "pipeline-summary"
  },
  "validation_criteria": {
    "manifest_valid": "scripts/artifact-utils.py validate-manifest passes",
    "content_nonempty": "content.md exists and has >0 bytes",
    "domain_script": "{scripts_needed[0]} if applicable"
  }
}
```

**GATE**: Every subdomain has a test target (fixture, codebase file, or synthetic). Target metadata recorded. Proceed to Phase 2.

### Phase 2: EXECUTE (Parallel Skill Runs)

**Goal**: Run each subdomain skill against its test target and capture output artifacts.

**Why parallel**: Subdomain skills are independent -- `prometheus-metrics` has no dependency on `prometheus-alerting`. Sequential execution wastes time proportional to the number of subdomains. The A/B test validated that parallel execution produces equivalent quality to sequential (and the test runner cares about structural validity, not content quality).

**Step 1: Create run directory**

```bash
mkdir -p /tmp/pipeline-test-{run-id}/runs/
```

Use a timestamp-based run-id: `$(date +%Y%m%d-%H%M%S)`.

**Step 2: Prepare invocation prompts**

For each subdomain, construct the prompt that will invoke the skill:

```
Run the {skill_name} skill against this test target:

Target: {target_path}
Target content: [include content for synthetic targets, path for real targets]

Produce output as dual-layer artifacts in:
  /tmp/pipeline-test-{run-id}/runs/{subdomain.name}/

Requirements:
- manifest.json must conform to the artifact envelope format
- content.md must contain the skill's output
- Follow the full pipeline chain -- do not skip phases
```

**Step 3: Fan-out execution**

Dispatch skill runs in parallel batches:
- If N <= 5 subdomains: run all in parallel using the Agent tool
- If N > 5: batch into groups of 5, run each batch sequentially (each batch's skills run in parallel)

For each skill run:
1. Invoke using the Agent tool with the subdomain's bound agent (`spec.reuse_agent` or `spec.new_agent.name`)
2. Pass the invocation prompt from Step 2
3. Set timeout: 5 minutes (300,000ms)
4. On completion, record: exit status, execution time, output path
5. On timeout: record TIMEOUT status, note which phase was running when timeout hit (if determinable)

**Step 4: Collect results**

After all runs complete (or timeout), collect:
```json
{
  "subdomain": "{name}",
  "skill_name": "{skill_name}",
  "status": "completed|timeout|error",
  "execution_time_seconds": N,
  "output_path": "/tmp/pipeline-test-{run-id}/runs/{subdomain.name}/",
  "manifest_exists": true|false,
  "content_exists": true|false,
  "error_output": "..." // if error
}
```

**GATE**: All skill runs completed (success, timeout, or error). Results collected for every subdomain. Proceed to Phase 3.

### Phase 3: VALIDATE OUTPUTS

**Goal**: Classify each skill's output as PASS, PARTIAL, FAIL, or TIMEOUT based on structural validity.

**Why structural validation, not semantic**: This skill checks "did the pipeline produce valid artifacts?" not "is the content correct?" Content quality evaluation requires domain expertise and is subjective. Structural validation is deterministic and catches the failures that matter for generator improvement -- missing manifests, empty content, broken chains.

**Step 1: For each completed run, validate the manifest**

```bash
python3 scripts/artifact-utils.py validate-manifest \
  /tmp/pipeline-test-{run-id}/runs/{subdomain.name}/manifest.json
```

Check the output:
- Exit 0: manifest is valid
- Exit 1: manifest has validation errors (capture error message)
- File not found: manifest was not produced

**Step 2: Validate content**

Check `content.md`:
- Exists and is non-empty (> 0 bytes)
- Contains actual content (not just headers or template placeholders)
- Check for `{{variable}}` markers that indicate template substitution failure

```bash
# Check for unsubstituted template variables
grep -c '{{' /tmp/pipeline-test-{run-id}/runs/{subdomain.name}/content.md
```

**Step 3: Check manifest status**

If the manifest exists and is valid, read the `status` field:
- `"complete"`: the skill reports it finished successfully
- `"partial"`: the skill reports incomplete results (some phases ran, some didn't)
- `"failed"`: the skill reports explicit failure
- `"blocked"`: the skill was blocked by a gate

**Step 4: Run domain-specific validation (if applicable)**

If the subdomain's `scripts_needed` includes a validation script, run it against the output:

```bash
python3 scripts/{domain-validator}.py validate \
  /tmp/pipeline-test-{run-id}/runs/{subdomain.name}/content.md
```

Domain scripts provide deeper validation than manifest checks (e.g., `promql-validator.py` checks PromQL syntax). Not all subdomains have domain scripts -- this step is optional.

**Step 5: Classify each subdomain**

Apply the classification matrix:

| Condition | Classification |
|-----------|---------------|
| Skill didn't complete within timeout | **TIMEOUT** |
| Skill errored (crash, unhandled exception) | **FAIL** |
| Manifest missing or invalid | **FAIL** |
| Content missing or empty | **FAIL** |
| Unsubstituted `{{variable}}` markers in content | **FAIL** |
| Manifest status is `"failed"` or `"blocked"` | **FAIL** |
| Manifest valid, content exists, but status is `"partial"` | **PARTIAL** |
| Manifest valid, content exists, domain validation has warnings | **PARTIAL** |
| Manifest valid, content non-empty, status `"complete"`, domain validation passes | **PASS** |

For each FAIL or PARTIAL classification, record the failure trace:
```json
{
  "subdomain": "{name}",
  "classification": "FAIL|PARTIAL",
  "reason": "manifest_invalid|content_empty|status_failed|timeout|domain_validation_failed|template_markers",
  "detail": "Specific error message or validation output",
  "chain_step_hint": "Best guess at which chain step failed (e.g., GENERATE produced empty content, VALIDATE script not found)"
}
```

**GATE**: All outputs classified. Failure traces recorded for every non-PASS result. Proceed to Phase 4.

### Phase 4: REPORT

**Goal**: Produce the test run report as a dual-layer artifact for consumption by `pipeline-retro`.

**Why dual-layer**: The manifest enables `pipeline-retro` to programmatically determine the overall verdict and iterate over per-subdomain results. The content.md provides human-readable detail for debugging. Both layers are needed -- the retro skill reads the manifest to decide what to fix, and the human reads the content to understand what went wrong.

**Step 1: Compute overall verdict**

| Condition | Overall Verdict |
|-----------|----------------|
| All subdomains PASS | **PASS** |
| Majority (>50%) PASS, remainder PARTIAL or FAIL | **PARTIAL** |
| Majority (>50%) FAIL or TIMEOUT | **FAIL** |

**Step 2: Create manifest.json**

Save to `/tmp/pipeline-test-{run-id}/report/manifest.json`:

```json
{
  "schema": "verdict",
  "step": "REPORT",
  "phase": 5,
  "status": "complete",
  "verdict": "PASS|PARTIAL|FAIL",
  "metrics": {
    "subdomains_tested": N,
    "pass_count": N,
    "partial_count": N,
    "fail_count": N,
    "timeout_count": N,
    "total_execution_seconds": N
  },
  "inputs": ["pipeline-spec.json"],
  "outputs": ["content.md"],
  "timestamp": "ISO-8601",
  "tags": ["{domain}", "pipeline-test", "phase-5"],
  "per_subdomain": [
    {
      "subdomain": "{name}",
      "skill_name": "{skill_name}",
      "classification": "PASS|PARTIAL|FAIL|TIMEOUT",
      "target_type": "fixture|codebase|synthetic",
      "execution_time_seconds": N,
      "failure_reason": null | "{reason}",
      "chain_step_hint": null | "{step}"
    }
  ]
}
```

**Step 3: Create content.md**

Save to `/tmp/pipeline-test-{run-id}/report/content.md`:

```markdown
# Pipeline Test Report: {domain}

## Overall Verdict: {PASS|PARTIAL|FAIL}

Tested {N} subdomain skills generated from pipeline spec.

## Results

| Subdomain | Skill | Target Type | Result | Time | Failure Reason |
|-----------|-------|-------------|--------|------|----------------|
| {name} | {skill_name} | fixture | PASS | 45s | -- |
| {name} | {skill_name} | synthetic | FAIL | 120s | manifest_invalid |
| {name} | {skill_name} | codebase | TIMEOUT | 300s | exceeded 5min |

## Failure Traces

### {subdomain_name} -- FAIL

**Reason**: {classification reason}
**Detail**: {specific error message}
**Chain Step Hint**: {which step likely failed and why}
**Target Used**: {target_path} ({target_type})

Full error output:
\```
{error output or validation failure text}
\```

### {subdomain_name} -- PARTIAL

**Reason**: {classification reason}
**Detail**: {specific detail}
**Chain Step Hint**: {hint}

## Recommendations

For each failure, classify the likely root cause:

| Failure | Likely Cause | Recommended Fix Layer |
|---------|-------------|----------------------|
| manifest_invalid | Scaffolder template bug | Generator (Layer 2) |
| content_empty | Research phase found nothing | Test target (redo discovery) |
| template_markers | Variable substitution missed | Scaffolder (Layer 2) |
| domain_validation_failed | Generated code has syntax errors | Generator rules (Layer 2) |
| timeout | Chain too complex or research too broad | Chain composition (Layer 2) |
| status_failed | Skill hit an error gate | Skill logic (Layer 2) |

The "Recommended Fix Layer" column tells pipeline-retro WHERE to apply the fix:
- **Generator (Layer 2)**: Fix the scaffolder template or generation logic
- **Test target**: The target was bad, not the skill -- redo discovery
- **Chain composition**: The chain design needs adjustment (too many steps, wrong step order)
```

**Step 4: Display summary**

Output the results table and overall verdict to the user. Include the report path for `pipeline-retro` to consume.

**GATE**: Report artifacts exist at `/tmp/pipeline-test-{run-id}/report/`. Pipeline test run complete.

---

## Error Handling

### Error: Pipeline Spec Not Found
**Cause**: The spec path provided doesn't exist or the spec wasn't passed as input.
**Solution**: Check the ADR for the spec path (usually saved by `chain-composer`). If the spec was consumed by `pipeline-scaffolder` but not saved, re-run chain composition or read the spec from the scaffolder's input artifacts.

### Error: Skill File Not Found
**Cause**: A subdomain's `skill_name` in the spec references a skill that doesn't exist at `skills/{skill_name}/SKILL.md`.
**Solution**: The scaffolder didn't create this skill. Check the scaffolding report for errors. This subdomain gets an automatic FAIL classification with reason `skill_not_found`.

### Error: Agent Not Available
**Cause**: The agent specified in `reuse_agent` or `new_agent.name` is not available for invocation.
**Solution**: Verify the agent exists in `agents/INDEX.json`. If the agent was just created by the scaffolder, it may need to be in the current session's context. Classify affected subdomains as FAIL with reason `agent_unavailable`.

### Error: Validation Script Not Found
**Cause**: A subdomain's `scripts_needed` references a script that doesn't exist at `scripts/{filename}`.
**Solution**: Skip domain-specific validation for this subdomain. Note the missing script in the failure trace. The subdomain can still PASS on structural validation alone -- the missing script is a separate issue for the scaffolder to fix.

### Error: All Subdomains Timeout
**Cause**: Every skill run exceeded the 5-minute timeout.
**Solution**: This usually means the generated skills have overly complex research phases or the agent is overloaded. Report all as TIMEOUT. In recommendations, suggest reducing `params.agents` count in research steps or simplifying chains. Consider enabling the Extended Timeout optional behavior for retry.

---

## Anti-Patterns

### Anti-Pattern 1: Skip Testing Because Chain Validates
**What it looks like**: "Chain validation passed, so the skills must work."
**Why wrong**: Chain validation checks TYPE compatibility (step A produces research-artifact, step B consumes research-artifact). Execution testing checks RUNTIME behavior (does the research phase actually find anything? does the generation phase produce non-empty content? does the validation script exist and pass?). Type-safe code can still crash at runtime.
**Do instead**: Always run the test phase. Chain validation and execution testing catch different failure classes.

### Anti-Pattern 2: Same Target for All Subdomains
**What it looks like**: Using one generic file as the test target for every subdomain skill.
**Why wrong**: Each subdomain has a different task type and expects different input. A PromQL query file is meaningless to an alerting-rules skill. A generic target produces false negatives (skill fails because the input is wrong, not because the skill is broken) or false positives (skill "succeeds" by ignoring the irrelevant input).
**Do instead**: Follow the priority-ordered target discovery per subdomain. Each gets domain-appropriate input.

### Anti-Pattern 3: Fail the Entire Run on One Subdomain Failure
**What it looks like**: "prometheus-metrics failed, so the whole test run is FAIL."
**Why wrong**: Per-subdomain results are essential for `pipeline-retro`. If 4 of 5 subdomains pass and 1 fails, the retro needs to fix only the one failing generator component. Blanket failure hides which parts work.
**Do instead**: Classify each subdomain independently. Compute overall verdict by majority, but always report per-subdomain results.

### Anti-Pattern 4: Test Against External Systems
**What it looks like**: Running the Prometheus operations skill against a live Prometheus cluster.
**Why wrong**: Test runs happen during pipeline generation. They must be safe (no side effects), repeatable (same result every time), and fast (under 5 minutes). Live systems introduce network latency, authentication, and the risk of actual changes.
**Do instead**: Use repo files, fixtures, or synthetic targets exclusively.

### Anti-Pattern 5: Retry Failed Skills Indefinitely
**What it looks like**: A skill fails, so the test runner re-runs it 3 times hoping for a different result.
**Why wrong**: Structural failures (missing manifest, empty content, template markers) are deterministic -- they will fail the same way every time. Retrying wastes time and context. The fix belongs in the generator (Layer 2), not in re-execution.
**Do instead**: Classify the failure, record the trace, and move on. The `pipeline-retro` skill handles fixing.

---

## Anti-Rationalization

| Rationalization Attempt | Why It's Wrong | Required Action |
|------------------------|----------------|-----------------|
| "The scaffolder validated everything, testing is redundant" | Scaffolder validates structure (YAML frontmatter, naming). Test runner validates execution (does it run and produce output?) | Run tests regardless of scaffolder results |
| "Synthetic targets are unrealistic, skip subdomains without fixtures" | Synthetic targets catch structural failures (missing manifest, empty content, template markers). They don't test domain quality, but they DO test pipeline mechanics. | Generate synthetic targets for subdomains without real targets |
| "One subdomain timed out, so all will timeout" | Timeouts depend on chain complexity, target size, and research scope. Each subdomain is independent. | Test all subdomains; don't extrapolate from one |
| "This failure is obviously a target issue, not a skill issue" | The test runner REPORTS the likely cause; it doesn't DECIDE. `pipeline-retro` decides what to fix. | Classify honestly, include recommendation, let retro decide |
| "We can skip the manifest validation script and just check JSON manually" | `artifact-utils.py validate-manifest` implements canonical rules from the ADR. Manual checks drift from the spec. | Always use the script |

---

## Blocker Criteria

STOP and ask the user (do NOT proceed autonomously) when:

| Situation | Why Stop | Ask This |
|-----------|----------|----------|
| Pipeline Spec not provided or not found | Can't determine what to test | "Where is the Pipeline Spec JSON? Provide a path or inline content." |
| No skill files exist for any subdomain | Scaffolder may not have run | "No generated skills found. Has pipeline-scaffolder completed? Should I run it first?" |
| All subdomains FAIL on first batch | Systemic issue, not per-subdomain | "All 5 subdomains failed. This suggests a systemic issue (agent problem, template bug). Investigate before testing remaining batches?" |

### Never Guess On
- Whether a failure is a target issue vs a skill issue (report both possibilities, let retro decide)
- Whether to increase timeout (ask, don't assume)
- Whether to skip a subdomain (test everything the spec defines)

---

## References

- **Artifact Utilities**: [../../scripts/artifact-utils.py](../../scripts/artifact-utils.py) -- manifest creation and validation
- **Pipeline Orchestrator**: [../../agents/pipeline-orchestrator-engineer.md](../../agents/pipeline-orchestrator-engineer.md) -- the parent orchestrator (this skill is Phase 5)
- **Pipeline Retro**: pipeline-retro skill (Phase 6) -- consumes this skill's report
