---
name: agent-evaluation
description: |
  Evaluate agents and skills for quality, completeness, and standards
  compliance using a 6-step rubric: Identify, Structural, Content, Code,
  Integration, Report. Use when auditing agents/skills, checking quality
  after creation or update, or reviewing collection health. Triggers:
  "evaluate", "audit", "check quality", "review agent", "score skill".
  Do NOT use for creating or modifying agents/skills — only for
  read-only assessment and scoring.
version: 2.0.0
user-invocable: false
context: fork
allowed-tools:
  - Read
  - Grep
  - Glob
  - Bash
---

# Agent Evaluation Skill

## Operator Context

This skill operates as an operator for agent/skill quality assurance, configuring Claude's behavior for objective, evidence-based evaluation. It implements the **Iterative Assessment** pattern — identify targets, validate structure, measure depth, score, report — with **Domain Intelligence** embedded in the scoring rubric.

### Hardcoded Behaviors (Always Apply)
- **CLAUDE.md Compliance**: Read and follow repository CLAUDE.md before evaluation
- **Over-Engineering Prevention**: Evaluate only what is requested. Do not speculatively analyze additional agents/skills or invent metrics that were not asked for
- **Read-Only Evaluation**: NEVER modify agents or skills during evaluation — only report findings
- **Evidence-Based Findings**: Every issue MUST include file path and line reference
- **Objective Scoring**: Use the rubric consistently across all evaluations — no subjective "looks good" assessments
- **Complete Output**: Show all test results with scores; never summarize as "all tests pass"

### Default Behaviors (ON unless disabled)
- **Full Test Suite**: Run all evaluation categories (structural, content, code, integration)
- **Priority Ranking**: Sort findings by impact (HIGH / MEDIUM / LOW)
- **Score Calculation**: Generate numeric quality scores using the standard rubric
- **Improvement Suggestions**: Provide specific, actionable recommendations with file paths
- **Temporary File Cleanup**: Remove any intermediate analysis files at task completion
- **Comparative Analysis**: Show how evaluated items compare to collection averages

### Optional Behaviors (OFF unless enabled)
- **Historical Comparison**: Compare current scores to previous evaluations (requires baseline)
- **Cross-Reference Validation**: Check all internal links and references resolve
- **Code Example Execution**: Actually run code examples to verify they work

## What This Skill CAN Do
- Score agents and skills against a consistent 100-point rubric
- Detect missing sections, broken references, and structural gaps
- Measure content depth and compare to collection averages
- Generate structured reports with prioritized findings
- Batch-evaluate entire collections with summary statistics

## What This Skill CANNOT Do
- Modify or fix agents/skills (use skill-creator-engineer instead)
- Evaluate external repositories or non-agent/skill files
- Replace human judgment on content accuracy or domain correctness
- Skip rubric categories — all must be scored

---

## Instructions

### Step 1: Identify Evaluation Targets

**Goal**: Determine what to evaluate and confirm targets exist.

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

### Step 2: Structural Validation

**Goal**: Check that required components exist and are well-formed.

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

### Step 3: Content Depth Analysis

**Goal**: Measure content quality and volume.

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

### Step 4: Code Quality Checks

**Goal**: Validate that code examples and scripts are functional.

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

### Step 5: Integration Verification

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

### Step 6: Generate Quality Report

**Goal**: Compile all findings into the standard report format.

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

## Anti-Patterns

### Anti-Pattern 1: Superficial Evaluation Without Evidence
**What it looks like**: "Structure: Looks good. Content: Seems adequate. Overall: PASS"
**Why wrong**: No file paths, no line references, no specific scores. Cannot verify or reproduce.
**Do instead**: Score every rubric category. Cite file:line for every finding.

### Anti-Pattern 2: Skipping Validation Script Execution
**What it looks like**: "The skill has a validation script present."
**Why wrong**: Presence is not correctness. Script may have syntax errors or do nothing.
**Do instead**: Run `python3 -m py_compile` at minimum. Execute the script and capture output.

### Anti-Pattern 3: Accepting Placeholder Content as Complete
**What it looks like**: "Agent has comprehensive examples section. PASS"
**Why wrong**: Did not check if examples contain [TODO] or [PLACEHOLDER] text.
**Do instead**: Search for placeholder patterns. Score content on substance, not section headers.

### Anti-Pattern 4: Batch Evaluation Without Summary Statistics
**What it looks like**: "Evaluated all 38 agents. Most are good quality."
**Why wrong**: No quantitative data. Cannot track improvements or identify problem areas.
**Do instead**: Generate score distribution table, top/bottom performers, common issues count. See `references/batch-evaluation.md` for the collection summary template.

### Anti-Pattern 5: Ignoring Repository-Specific Standards
**What it looks like**: "This agent follows standard practices and is well-structured."
**Why wrong**: Did not check CLAUDE.md requirements. May miss v2 standards (YAML list format, pipe description, item count ranges, gates, anti-rationalization table).
**Do instead**: Check CLAUDE.md first. Verify all v2-specific criteria. A generic "well-structured" verdict is meaningless without rubric scores.

---

## References

This skill uses these shared patterns:
- [Anti-Rationalization](../shared-patterns/anti-rationalization-core.md) - Prevents shortcut rationalizations
- [Verification Checklist](../shared-patterns/verification-checklist.md) - Pre-completion checks

### Domain-Specific Anti-Rationalization

| Rationalization | Why It's Wrong | Required Action |
|-----------------|----------------|-----------------|
| "YAML looks fine, no need to parse it" | Looking is not parsing; fields may be missing | Check each required field explicitly |
| "Content is long enough, skip counting" | Impressions are not measurements | Count lines, calculate score |
| "Script exists, must work" | Existence is not correctness | Run `python3 -m py_compile` |
| "One failing check, rest are probably fine" | Partial evaluation is not evaluation | Complete all 6 steps |

### Reference Files
- `${CLAUDE_SKILL_DIR}/references/scoring-rubric.md` - Full/partial/no credit breakdowns per rubric category
- `${CLAUDE_SKILL_DIR}/references/report-templates.md` - Standard report format templates (single, batch, comparison)
- `${CLAUDE_SKILL_DIR}/references/common-issues.md` - Frequently found issues with fix templates
- `${CLAUDE_SKILL_DIR}/references/batch-evaluation.md` - Batch evaluation procedures and collection summary format
