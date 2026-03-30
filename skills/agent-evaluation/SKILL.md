---
name: agent-evaluation
description: "Evaluate agents and skills for quality and standards compliance."
version: 2.0.0
user-invocable: false
context: fork
allowed-tools:
  - Read
  - Grep
  - Glob
  - Bash
routing:
  triggers:
    - "evaluate agent"
    - "audit agent"
    - "score skill"
    - "check quality"
  category: meta-tooling
---

# Agent Evaluation Skill

Objective, evidence-based quality assessment for agents and skills. Implements a 6-phase rubric: Identify, Structural, Content, Code, Integration, Report. Every finding must cite a file path and line number — no subjective "looks good" verdicts.

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

**For Agents** — check each item and record PASS/FAIL with line number:

1. YAML front matter: `name`, `description`, `color` fields present
2. Operator Context section with all 3 behavior types (Hardcoded, Default, Optional)
3. Hardcoded Behaviors: 5-8 items, MUST include CLAUDE.md Compliance and Over-Engineering Prevention
4. Default Behaviors: 5-8 items
5. Optional Behaviors: 3-5 items
6. Examples in description: 3+ `<example>` blocks with `<commentary>`
7. Error Handling section with 3+ documented errors
8. CAN/CANNOT boundaries section

```bash
# Agent structural checks
head -20 agents/{name}.md | grep -E "^(name|description|color):"
grep -c "## Operator Context" agents/{name}.md
grep -c "### Hardcoded Behaviors" agents/{name}.md
grep -c "### Default Behaviors" agents/{name}.md
grep -c "### Optional Behaviors" agents/{name}.md
grep -c "CLAUDE.md" agents/{name}.md
grep -c "Over-Engineering" agents/{name}.md
grep -c "<example>" agents/{name}.md
grep -c "## Error Handling" agents/{name}.md
grep -c "CAN Do" agents/{name}.md
grep -c "CANNOT Do" agents/{name}.md
```

**For Skills** — check each item and record PASS/FAIL with line number:

1. YAML front matter: `name`, `description`, `version`, `allowed-tools` present
2. `allowed-tools` uses YAML list format (not comma-separated string)
3. `description` uses pipe (`|`) format with WHAT + WHEN + negative constraint, under 1024 chars
4. `version` set to `2.0.0` for migrated skills
5. Operator Context section with all 3 behavior types
6. Hardcoded Behaviors: 5-8 items, MUST include CLAUDE.md Compliance and Over-Engineering Prevention
7. Default Behaviors: 5-8 items
8. Optional Behaviors: 3-5 items
9. Instructions section with gates between phases
10. Error Handling section with 2-4 documented errors
11. Anti-Patterns section with 3-5 patterns
12. `references/` directory with substantive content
13. CAN/CANNOT boundaries section
14. References section with shared patterns and domain-specific anti-rationalization table

```bash
# Skill structural checks
head -20 skills/{name}/SKILL.md | grep -E "^(name|description|version|allowed-tools):"
grep -n "allowed-tools:" skills/{name}/SKILL.md  # Check YAML list vs comma format
grep -c "## Operator Context" skills/{name}/SKILL.md
grep -c "CLAUDE.md" skills/{name}/SKILL.md
grep -c "Over-Engineering" skills/{name}/SKILL.md
grep -c "## Instructions" skills/{name}/SKILL.md
grep -c "Gate.*Proceed" skills/{name}/SKILL.md  # Count gates
grep -c "## Error Handling" skills/{name}/SKILL.md
grep -c "## Anti-Patterns" skills/{name}/SKILL.md
grep -c "CAN Do" skills/{name}/SKILL.md
grep -c "CANNOT Do" skills/{name}/SKILL.md
grep -c "anti-rationalization-core" skills/{name}/SKILL.md
ls skills/{name}/references/
```

**Structural Scoring** (60 points):

| Component | Points | Requirement |
|-----------|--------|-------------|
| YAML front matter | 10 | All required fields, list format, pipe description |
| Operator Context | 20 | All 3 behavior types with correct item counts |
| Error Handling | 10 | Section present with documented errors |
| Examples (agents) / References (skills) | 10 | 3+ examples or 2+ reference files |
| CAN/CANNOT | 5 | Both sections present with concrete items |
| Anti-Patterns | 5 | 3-5 domain-specific patterns with 3-part structure |

**Integration Scoring** (10 points):

| Component | Points | Requirement |
|-----------|--------|-------------|
| References and cross-references | 5 | Shared patterns linked, all refs resolve |
| Tool and link consistency | 5 | allowed-tools matches usage, anti-rationalization table present |

See `references/scoring-rubric.md` for full/partial/no credit breakdowns.

**Gate**: All structural checks scored with evidence. Proceed only when gate passes.

### Phase 3: Content Depth Analysis

**Goal**: Measure content quality and volume.

Do not estimate length by impression — count lines and calculate the score. "Content is long enough" is not a measurement.

```bash
# Skill total lines (SKILL.md + references)
skill_lines=$(wc -l < skills/{name}/SKILL.md)
ref_lines=$(cat skills/{name}/references/*.md 2>/dev/null | wc -l)
total=$((skill_lines + ref_lines))

# Agent total lines
agent_lines=$(wc -l < agents/{name}.md)
```

**Depth Scoring** (30 points max):

| Total Lines | Score | Grade |
|-------------|-------|-------|
| >1500 (skills) / >2000 (agents) | 30 | EXCELLENT |
| 500-1500 / 1000-2000 | 22 | GOOD |
| 300-500 / 500-1000 | 15 | ADEQUATE |
| 150-300 / 200-500 | 8 | THIN |
| <150 / <200 | 0 | INSUFFICIENT |

**Gate**: Depth score calculated. Proceed only when gate passes.

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

1. **Header**: Name, type, date, overall score and grade
2. **Structural Validation**: Table with check, status, score, and evidence (line numbers)
3. **Content Depth**: Line counts for main file and references, grade, depth score
4. **Code Quality**: Script syntax results, placeholder count, untagged block count
5. **Issues Found**: Grouped by HIGH / MEDIUM / LOW priority
6. **Recommendations**: Specific, actionable improvements with file paths and line numbers
7. **Comparison**: Score vs collection average (if batch evaluating)

**Issue Priority Classification**:

| Priority | Criteria | Examples |
|----------|----------|---------|
| HIGH | Missing required section or broken functionality | No Operator Context, syntax errors in scripts |
| MEDIUM | Section present but incomplete or non-compliant | Wrong item counts, old allowed-tools format |
| LOW | Cosmetic or minor quality issues | Untagged code blocks, missing changelog |

**Grade Boundaries**:

| Score | Grade | Interpretation |
|-------|-------|----------------|
| 90-100 | A | Production ready, exemplary |
| 80-89 | B | Good, minor improvements needed |
| 70-79 | C | Adequate, some gaps to address |
| 60-69 | D | Below standard, significant work needed |
| <60 | F | Major overhaul required |

**Gate**: Report generated with all sections populated and evidence cited. Evaluation complete.

---

## Examples

### Example 1: Single Skill Evaluation
User says: "Evaluate the test-driven-development skill"
Actions:
1. Confirm `skills/test-driven-development/` exists (IDENTIFY)
2. Check YAML, Operator Context, Error Handling sections (STRUCTURAL)
3. Count lines in SKILL.md + references (CONTENT)
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

### Example 3: V2 Migration Compliance Check
User says: "Check if systematic-refactoring skill meets v2 standards"
Actions:
1. Confirm `skills/systematic-refactoring/` exists (IDENTIFY)
2. Check YAML uses list `allowed-tools`, pipe description, version 2.0.0 (STRUCTURAL)
3. Verify Operator Context has correct item counts: Hardcoded 5-8, Default 5-8, Optional 3-5 (STRUCTURAL)
4. Confirm CAN/CANNOT sections, gates in Instructions, anti-rationalization table (STRUCTURAL)
5. Count total lines, run code checks (CONTENT + CODE)
6. Generate scored report highlighting v2 gaps (REPORT)
Result: Report with specific v2 compliance gaps and required actions

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

### Error: "Operator Context Item Counts Out of Range"
Cause: v2 standard requires Hardcoded 5-8, Default 5-8, Optional 3-5 items. Skill has too few or too many.
Solution:
1. Count actual items per behavior type (bold items starting with `- **`)
2. If too few: flag as MEDIUM priority — behaviors likely need to be split or added
3. If too many: flag as LOW priority — behaviors may need consolidation
4. Score Operator Context at partial credit (10/20) if counts are wrong

---

## References

### Reference Files
- `${CLAUDE_SKILL_DIR}/references/scoring-rubric.md` - Full/partial/no credit breakdowns per rubric category
- `${CLAUDE_SKILL_DIR}/references/report-templates.md` - Standard report format templates (single, batch, comparison)
- `${CLAUDE_SKILL_DIR}/references/common-issues.md` - Frequently found issues with fix templates
- `${CLAUDE_SKILL_DIR}/references/batch-evaluation.md` - Batch evaluation procedures and collection summary format
