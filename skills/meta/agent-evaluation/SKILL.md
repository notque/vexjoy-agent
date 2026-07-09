---
name: agent-evaluation
description: "Evaluate agents and skills for quality and standards compliance."
user-invocable: false
context: fork
allowed-tools:
  - Read
  - Grep
  - Glob
  - Bash
routing:
  not_for: "empirical/behavioral testing of a skill with test cases and benchmarks (use skill-eval). This skill is static structural/standards-compliance grading."
  triggers:
    - "evaluate agent"
    - "audit agent"
    - "agent standards check"
    - "check quality"
    - "grade agent"
    - "agent quality"
  category: meta-tooling
  pairs_with:
    - agent-comparison
    - skill-eval
    - skill-creator
---

# Agent Evaluation Skill

Evidence-based quality assessment for agents and skills. The deterministic scorer supplies a 90-point structural precheck; qualitative review covers usefulness and behavior without inventing extra points. Every qualitative finding must cite a file path and line number.

## Reference Loading Table

| Signal | Load These Files | Why |
|---|---|---|
| evaluating an entire agent/skill collection | `batch-evaluation.md` | Loads detailed guidance from `batch-evaluation.md`. |
| diagnosing recurring structural and content issues | `common-issues.md` | Loads detailed guidance from `common-issues.md`. |
| writing single-item or collection evaluation reports | `report-templates.md` | Loads detailed guidance from `report-templates.md`. |
| interpreting deterministic scores, JSON keys, or grade boundaries | `scoring-rubric.md` | Exact contract implemented by `score-component.py` |

## Instructions

### Phase 1: Identify Evaluation Targets

**Goal**: Determine what to evaluate and confirm targets exist.

Read the repository CLAUDE.md first to understand current standards before evaluating anything. Only evaluate what was explicitly requested — do not speculatively analyze additional agents or skills.

```bash
# List all agents
ls agents/*.md | wc -l

# List all skills
ls -d skills/*/ | wc -l

# Verify specific target
ls agents/{name}.md
ls -la skills/{name}/
```

**Gate**: All targets confirmed to exist on disk. Proceed only when gate passes.

### Phase 2: Structural Validation

**Goal**: Check that required components exist and are well-formed.

Score every rubric category — never skip a category even if it "looks fine." Parse each required field explicitly rather than eyeballing YAML. Record PASS/FAIL with the line number for each check.

Run `score-component.py` to get deterministic structural scores. It checks frontmatter, referenced paths, pattern and error headings, routing registration, reference-directory presence, workflow structure, and internal links. It does not emit line references or judge content depth, Operator Context, tool semantics, or behavioral quality.

```bash
# Deterministic structural checks via score-component.py
python3 scripts/score-component.py agents/{name}.md --json
# or for a skill:
python3 scripts/score-component.py skills/{name}/SKILL.md --json
```

The JSON output includes `results[0].checks` with `status`, `earned`, `max`, and `detail`, plus `results[0].total`, `max_total`, and `grade`. Record these exact keys. Do not refer to `earned_points` or `max_points`; those are internal Python attributes, not JSON fields.

See `references/scoring-rubric.md` for the exact eight checks, 90-point maximum, percentage grade boundaries, optional secret penalty, and JSON contract.

**Gate**: All structural checks scored with evidence. Proceed only when gate passes.

### Phase 3: Qualitative Content Analysis

**Goal**: Assess whether the component carries useful, accurate, proportionate guidance.

Line counts can describe size, but do not award points for length. More prose is not evidence of better behavior.

```bash
# Skill total lines (SKILL.md + references)
skill_lines=$(wc -l < skills/{name}/SKILL.md)
ref_lines=$(cat skills/{name}/references/*.md 2>/dev/null | wc -l)
total=$((skill_lines + ref_lines))

# Agent total lines
agent_lines=$(wc -l < agents/{name}.md)
```

Check for concrete domain knowledge, stale or contradictory claims, unnecessary bulk, and missing instructions needed to execute the advertised task. Keep these findings outside the deterministic score.

**Gate**: Qualitative findings cite evidence, or explicitly state that none were found.

### Phase 4: Code Quality Checks

**Goal**: Validate that code examples and scripts are functional.

A script existing on disk does not mean it works — run `python3 -m py_compile` on every `.py` file. Search for placeholder text in every file, not just files that "look incomplete."

1. **Script syntax**: Run `python3 -m py_compile` on all `.py` files
2. **Placeholder detection**: Search for `[TODO]`, `[TBD]`, `[PLACEHOLDER]`, `[INSERT]`
3. **Code block tagging**: Count untagged (bare ` ``` `) vs tagged (` ```language `) blocks

```bash
# Python syntax check
# Syntax-check any .py scripts found in the skill's scripts/ directory
python3 -m py_compile scripts/*.py 2>/dev/null

# Placeholder search
grep -nE '\[TODO\]|\[TBD\]|\[PLACEHOLDER\]|\[INSERT\]' {file}

# Untagged code blocks
grep -c '```$' {file}
```

**Gate**: All code checks complete. Proceed only when gate passes.

### Phase 5: Integration Verification

**Goal**: Confirm cross-references and tool declarations are consistent.

**Reference Resolution**:
1. Extract all referenced files from SKILL.md (grep for `references/`)
2. Verify each reference exists on disk
3. Check shared pattern links resolve (`../shared-patterns/`)

**Tool Consistency**:
1. Parse `allowed-tools` from YAML front matter
2. Scan instructions for tool usage (Read, Write, Edit, Bash, Grep, Glob, Task, WebSearch)
3. Flag any tool used in instructions but not declared in `allowed-tools`
4. Flag any tool declared but never used in instructions

**Anti-Rationalization Table**:
1. Check that References section links to `anti-rationalization-core.md`
2. Verify domain-specific anti-rationalization table is present
3. Table should have 3-5 rows specific to the skill's domain

```bash
# Check referenced files exist
grep -oE 'references/[a-z-]+\.md' skills/{name}/SKILL.md | while read ref; do
  ls "skills/{name}/$ref" 2>/dev/null || echo "MISSING: $ref"
done

# Check tool consistency
grep "allowed-tools:" skills/{name}/SKILL.md
grep -oE '(Read|Write|Edit|Bash|Grep|Glob|Task|WebSearch)' skills/{name}/SKILL.md | sort -u

# Check anti-rationalization reference
grep -c "anti-rationalization-core" skills/{name}/SKILL.md
```

**Gate**: All integration checks complete. Proceed only when gate passes.

### Phase 6: Generate Quality Report

**Goal**: Compile all findings into the standard report format.

Show all test results with individual scores — never summarize as "all tests pass." Sort findings by impact (HIGH / MEDIUM / LOW). Include specific, actionable recommendations with file paths and line numbers. When batch evaluating, show how each item compares to collection averages; do not report "most are good quality" without quantitative data.

This phase is read-only: report findings but never modify agents or skills. Use skill-creator for fixes. Clean up any intermediate analysis files created during evaluation.

Use the report template from `references/report-templates.md`. The report MUST include:

1. **Header**: Name, type, date, structural score, maximum, and grade
2. **Structural Validation**: Table with each scorer check, status, `earned/max`, and detail
3. **Qualitative Analysis**: Evidence-backed findings kept separate from the score
4. **Code Quality**: Script syntax results, placeholder count, untagged block count
5. **Issues Found**: Grouped by HIGH / MEDIUM / LOW priority
6. **Recommendations**: Specific, actionable improvements with file paths and line numbers
7. **Comparison**: Score vs collection average (if batch evaluating)

**Issue Priority Classification**:

| Priority | Criteria | Examples |
|----------|----------|---------|
| HIGH | Broken functionality or a severe structural failure | Syntax errors, invalid frontmatter, broken critical references |
| MEDIUM | Incomplete or misleading guidance | Stale instructions, weak recovery guidance, tool mismatch |
| LOW | Cosmetic or minor quality issues | Untagged code blocks, missing changelog |

**Grade Boundaries** (percentage of `total / max_total`):

| Score | Grade | Interpretation |
|-------|-------|----------------|
| 90-100 | A | Strong structural health |
| 75-89 | B | Good structural health |
| 60-74 | C | Structural gaps to address |
| 40-59 | D | Significant structural gaps |
| <40 | F | Major structural gaps |

**Gate**: Report generated with all sections populated and evidence cited. Evaluation complete.

---

## Examples

### Example 1: Single Skill Evaluation
User says: "Evaluate the test-driven-development skill"
Actions:
1. Confirm `skills/testing/test-driven-development/` exists (IDENTIFY)
2. Run `score-component.py` and record all eight checks (STRUCTURAL)
3. Inspect content for useful, accurate, proportionate guidance (CONTENT)
4. Syntax-check any scripts, find placeholders (CODE)
5. Verify all referenced files exist (INTEGRATION)
6. Generate scored report (REPORT)
Result: Structured report with score, grade, and prioritized findings

### Example 2: Collection Batch Evaluation
User says: "Audit all agents and skills"
Actions:
1. List all agents/*.md and skills/*/SKILL.md (IDENTIFY)
2. Run Steps 2-5 for each target (EVALUATE)
3. Generate individual reports + collection summary (REPORT)
Result: Per-item scores plus distribution, top performers, and improvement areas

### Example 3: Structural Compliance Check
User says: "Check the structural health of systematic-refactoring"
Actions:
1. Confirm `skills/systematic-refactoring/` exists (IDENTIFY)
2. Run the deterministic 90-point precheck (STRUCTURAL)
3. Inspect guidance and examples for accuracy and usefulness (CONTENT)
4. Run code checks where scripts or examples exist (CODE)
5. Generate a report that separates scored checks from qualitative findings (REPORT)
Result: Structural score plus evidence-backed qualitative findings

---

## Error Handling

### Error: "File Not Found"
Cause: Agent or skill path incorrect, or item was deleted
Solution: Verify path exists with `ls` before evaluation. If truly missing, exclude from batch and note in report.

### Error: "Cannot Parse YAML Front Matter"
Cause: Malformed YAML — missing `---` delimiters, bad indentation, or invalid syntax
Solution: Flag as HIGH priority structural failure. Score YAML section as 0/10. Include the specific parse error in the report.

### Error: "Python Syntax Error in Script"
Cause: Validation script has syntax issues
Solution: Run `python3 -m py_compile` and capture the specific error. Score validation script as 0/10. Include error output in report.

### Error: "Documented JSON Key Missing"
Cause: The evaluator read internal `earned_points` or `max_points` names instead of the JSON contract.
Solution: Read `checks[*].earned` and `checks[*].max`; confirm top-level `total`, `max_total`, and `grade` before reporting.

---

## References

### Reference Files
- `${CLAUDE_SKILL_DIR}/references/scoring-rubric.md` - Full/partial/no credit breakdowns per rubric category
- `${CLAUDE_SKILL_DIR}/references/report-templates.md` - Standard report format templates (single, batch, comparison)
- `${CLAUDE_SKILL_DIR}/references/common-issues.md` - Frequently found issues with fix templates
- `${CLAUDE_SKILL_DIR}/references/batch-evaluation.md` - Batch evaluation procedures and collection summary format
