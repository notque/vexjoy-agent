---
name: pipeline-test-runner
description: "Test generated pipeline skills against real targets."
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

## Overview

This skill validates that generated pipeline skills actually work by running them against real targets. It is Phase 5 of the pipeline orchestrator's 7-phase flow, consuming the scaffolding output from `pipeline-scaffolder` and producing a report for `pipeline-retro`.

**Why this skill exists**: Chain validation (done by `chain-composer`) checks type compatibility between steps. This skill checks **execution** -- does the pipeline produce valid artifacts when given real input? Type-safe chains can still fail at runtime: research phases may find nothing, generation may produce empty content, validation scripts may reject output, or timeout may occur from overly complex research.

**Key distinction**: You will always test against repo files, fixtures, or synthetic inputs only—never against live systems. Structural validation tests artifact validity (manifest exists, content non-empty, status complete), not content quality (is the generated PromQL correct?). Per-subdomain results are essential: if 4 of 5 subdomains pass and 1 fails, `pipeline-retro` needs to fix only that one component.

---

## Instructions

### Input

This skill requires:
- **Pipeline Spec JSON**: The validated spec from `chain-composer` / `pipeline-scaffolder` (path or inline). Provides `spec.subdomains[*].skill_name`, `spec.subdomains[*].routing_triggers`, `spec.subdomains[*].scripts_needed`, `spec.subdomains[*].references_needed`, `spec.domain`, and executing agent.
- **Scaffolding Report** (optional): Confirmation that all components exist.

### Phase 1: DISCOVER TARGETS

**Goal**: For each subdomain skill, identify a suitable test target.

**Why**: A skill that passes chain validation can still fail when given real input.

**Step 1: Load the Pipeline Spec**

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
Search the repo for files matching the subdomain's domain. The search strategy depends on task type:

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

Use Glob and Grep to search.

**Priority 3 -- Synthetic targets**:
If no real targets exist, create a minimal synthetic target. Synthetic targets must be:
- Small enough to process quickly (under 50 lines)
- Representative of the subdomain's input type
- Valid input that the chain can actually consume

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

**Gate**: Every subdomain has a test target (fixture, codebase file, or synthetic). Target metadata recorded.

### Phase 2: EXECUTE (Parallel Skill Runs)

**Goal**: Run each subdomain skill against its test target and capture output artifacts.

**Why parallel**: Subdomain skills are independent. Sequential execution wastes time proportional to the number of subdomains. Parallel execution produces equivalent quality (the test runner cares about structural validity, not content quality).

**Constraint**: Never run more than 10 subdomain tests per batch. Fan out up to 5 in parallel; batch larger sets into groups of 5.

**Step 1: Create run directory**

```bash
mkdir -p /tmp/pipeline-test-{run-id}/runs/
```

Use a timestamp-based run-id: `$(date +%Y%m%d-%H%M%S)`.

**Step 2: Prepare invocation prompts**

For each subdomain, construct the prompt:

```
Run the {skill_name} skill against this test target:

Target: {target_path}
Target content: [include content for synthetic targets, path for real targets]

Produce output as dual-layer artifacts in:
  /tmp/pipeline-test-{run-id}/runs/{subdomain.name}/

Requirements:
- manifest.json must conform to the artifact envelope format
- content.md must contain the skill's output
- Follow the full pipeline chain -- execute every phase in order
```

**Step 3: Fan-out execution**

Dispatch skill runs in parallel batches:
- If N ≤ 5 subdomains: run all in parallel using the Agent tool
- If N > 5: batch into groups of 5, run each batch sequentially (each batch's skills run in parallel)

For each skill run:
1. Invoke using the Agent tool with the subdomain's bound agent
2. Pass the invocation prompt
3. Set timeout: 5 minutes (300,000ms). Constraint: Never increase timeout without user confirmation
4. On completion, record: exit status, execution time, output path
5. On timeout: record TIMEOUT status, note which phase was running when timeout hit (if determinable)

**Step 4: Collect results**

After all runs complete (or timeout):
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

**Gate**: All skill runs completed (success, timeout, or error). Results collected for every subdomain.

### Phase 3: VALIDATE OUTPUTS

**Goal**: Classify each skill's output as PASS, PARTIAL, FAIL, or TIMEOUT based on structural validity.

**Why structural validation, not semantic**: This tests "did the pipeline produce valid artifacts?" not "is the content correct?" Content quality requires domain expertise and is subjective. Structural validation is deterministic and catches failures that matter for generator improvement.

**Step 1: For each completed run, validate the manifest**

Always use `scripts/artifact-utils.py validate-manifest` for manifest validation. Never use manual JSON inspection. Constraint: The script implements canonical validation rules from the ADR; manual checks will drift from the spec over time.

```bash
python3 ~/.claude/scripts/artifact-utils.py validate-manifest \
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
- No unsubstituted `{{variable}}` markers

```bash
grep -c '{{' /tmp/pipeline-test-{run-id}/runs/{subdomain.name}/content.md
```

**Step 3: Check manifest status**

If the manifest exists and is valid, read the `status` field:
- `"complete"`: skill finished successfully
- `"partial"`: skill incomplete (some phases ran, some didn't)
- `"failed"`: skill reports explicit failure
- `"blocked"`: skill was blocked by a gate

**Step 4: Run domain-specific validation (if applicable)**

If the subdomain's `scripts_needed` includes a validation script, run it against the output:

```bash
python3 ~/.claude/scripts/{domain-validator}.py validate \
  /tmp/pipeline-test-{run-id}/runs/{subdomain.name}/content.md
```

Domain scripts provide deeper validation than manifest checks (e.g., `promql-validator.py` checks PromQL syntax). This step is optional if the script doesn't exist.

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
| Manifest valid, content exists, but domain validation has warnings | **PARTIAL** |
| Manifest valid, content non-empty, status `"complete"`, domain validation passes | **PASS** |

For each FAIL or PARTIAL classification, record the failure trace:
```json
{
  "subdomain": "{name}",
  "classification": "FAIL|PARTIAL",
  "reason": "manifest_invalid|content_empty|status_failed|timeout|domain_validation_failed|template_markers",
  "detail": "Specific error message or validation output",
  "chain_step_hint": "Best guess at which chain step failed"
}
```

**Gate**: All outputs classified. Failure traces recorded for every non-PASS result.

### Phase 4: REPORT

**Goal**: Produce the test run report as a dual-layer artifact for `pipeline-retro`.

**Why dual-layer**: The manifest enables `pipeline-retro` to programmatically determine the verdict and iterate over per-subdomain results. The content.md provides human-readable detail for debugging. Both are needed.

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

The "Recommended Fix Layer" column tells pipeline-retro WHERE to apply the fix. This skill ONLY reports the likely cause; it does not decide or apply fixes. `pipeline-retro` decides what to fix.
```

**Step 4: Display summary**

Output the results table and overall verdict to the user. Include the report path for `pipeline-retro` to consume. Report facts without self-congratulation. Show per-subdomain results table, not narrative descriptions.

**Step 5: Cleanup**

Remove `/tmp/pipeline-test-*` directories after the report is produced. Keep only the final report artifacts.

**Gate**: Report artifacts exist at `/tmp/pipeline-test-{run-id}/report/`. Pipeline test run complete.

---

## Error Handling

### Error: Pipeline Spec Not Found
**Cause**: The spec path provided doesn't exist or the spec wasn't passed as input.
**Solution**: Check the ADR for the spec path (usually saved by `chain-composer`). If the spec was consumed by `pipeline-scaffolder` but not saved, re-run chain composition or read the spec from the scaffolder's input artifacts. This is a blocker—ask the user for the spec path.

### Error: Skill File Not Found
**Cause**: A subdomain's `skill_name` in the spec references a skill that doesn't exist at `skills/{skill_name}/SKILL.md`.
**Solution**: The scaffolder didn't create this skill. Check the scaffolding report for errors. Classify this subdomain as FAIL with reason `skill_not_found`.

### Error: Agent Not Available
**Cause**: The agent specified in `reuse_agent` or `new_agent.name` is not available for invocation.
**Solution**: Verify the agent exists in `agents/INDEX.json`. If the agent was just created by the scaffolder, it may need to be in the current session's context. Classify affected subdomains as FAIL with reason `agent_unavailable`.

### Error: Validation Script Not Found
**Cause**: A subdomain's `scripts_needed` references a script that doesn't exist at `scripts/{filename}`.
**Solution**: Skip domain-specific validation for this subdomain. Note the missing script in the failure trace. The subdomain can still PASS on structural validation alone.

### Error: All Subdomains Timeout
**Cause**: Every skill run exceeded the 5-minute timeout.
**Solution**: Report all as TIMEOUT. In recommendations, suggest reducing `params.agents` count in research steps or simplifying chains. Ask the user before enabling Extended Timeout optional behavior for retry.

### Blocker Criteria

STOP and ask the user (wait for explicit confirmation) when:

| Situation | Why Stop | Ask This |
|-----------|----------|----------|
| Pipeline Spec not provided or not found | Can't determine what to test | "Where is the Pipeline Spec JSON? Provide a path or inline content." |
| No skill files exist for any subdomain | Scaffolder may not have run | "No generated skills found. Has pipeline-scaffolder completed? Should I run it first?" |
| All subdomains FAIL on first batch | Systemic issue, not per-subdomain | "All 5 subdomains failed. This suggests a systemic issue (agent problem, template bug). Investigate before testing remaining batches?" |

### Never Guess On
- Whether a failure is a target issue vs a skill issue (report both possibilities, let retro decide)
- Whether to increase timeout (ask the user first)
- Whether to skip a subdomain (test everything the spec defines)

---

## References

- **Artifact Utilities**: [../../scripts/artifact-utils.py](../../scripts/artifact-utils.py) -- manifest creation and validation
- **Pipeline Orchestrator**: [../../agents/pipeline-orchestrator-engineer.md](../../agents/pipeline-orchestrator-engineer.md) -- the parent orchestrator (this skill is Phase 5)
- **Pipeline Retro**: pipeline-retro skill (Phase 6) -- consumes this skill's report
