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
  triggers:
    - "evaluate agent"
    - "audit agent"
    - "score skill"
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

Objective, evidence-based quality assessment for agents and skills. 6-phase rubric: Identify, Structural, Content, Code, Integration, Report. Every finding must cite file path and line number -- no subjective verdicts.

## Reference Loading Table

| Signal | Load These Files | Why |
|---|---|---|
| tasks related to this reference | `batch-evaluation.md` | Loads detailed guidance from `batch-evaluation.md`. |
| tasks related to this reference | `common-issues.md` | Loads detailed guidance from `common-issues.md`. |
| tasks related to this reference | `report-templates.md` | Loads detailed guidance from `report-templates.md`. |
| tasks related to this reference | `scoring-rubric.md` | Loads detailed guidance from `scoring-rubric.md`. |

## Instructions

### Phase 1: Identify Evaluation Targets

**Goal**: Determine what to evaluate and confirm targets exist.

Read the repository CLAUDE.md first. Only evaluate what was explicitly requested.

```bash
ls agents/*.md | wc -l
ls -d skills/*/ | wc -l
ls agents/{name}.md
ls -la skills/{name}/
```

**Gate**: All targets confirmed on disk.

### Phase 2: Structural Validation

**Goal**: Check required components exist and are well-formed.

Score every rubric category -- never skip one. Parse each field explicitly rather than eyeballing YAML. Record PASS/FAIL with line number.

Run `score-component.py` for deterministic PASS/FAIL on all structural checks. Do not re-implement checks the script covers.

```bash
python3 scripts/score-component.py agents/{name}.md --json
python3 scripts/score-component.py skills/{name}/SKILL.md --json
```

JSON output includes `results[0].checks` (per-check status, earned_points, max_points, detail) and `results[0].total`.

**Script covers** (do not duplicate): YAML frontmatter fields, Operator Context presence, Error Handling presence, Anti-Patterns presence, referenced file existence, inline constraint presence.

**Requires LLM judgment in Phase 3+** (not script-covered):
- Operator Context item counts (Hardcoded 5-8, Default 5-8, Optional 3-5)
- `allowed-tools` list format vs comma-separated string
- `description` pipe format with WHAT + WHEN + negative constraint
- `version` set to `2.0.0`
- Gate presence in Instructions
- CAN/CANNOT boundaries
- Anti-rationalization table in References

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

**Gate**: All structural checks scored with evidence.

### Phase 3: Content Depth Analysis

**Goal**: Measure content quality and volume.

Count lines explicitly -- "content is long enough" is not a measurement.

```bash
skill_lines=$(wc -l < skills/{name}/SKILL.md)
ref_lines=$(cat skills/{name}/references/*.md 2>/dev/null | wc -l)
total=$((skill_lines + ref_lines))
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

**Gate**: Depth score calculated.

### Phase 4: Code Quality Checks

**Goal**: Validate code examples and scripts are functional.

A script on disk does not mean it works -- run `python3 -m py_compile` on every `.py` file. Search for placeholders in every file.

1. **Script syntax**: `python3 -m py_compile` on all `.py` files
2. **Placeholder detection**: Search for `[TODO]`, `[TBD]`, `[PLACEHOLDER]`, `[INSERT]`
3. **Code block tagging**: Count untagged (bare ` ``` `) vs tagged (` ```language `) blocks

```bash
python3 -m py_compile scripts/*.py 2>/dev/null
grep -nE '\[TODO\]|\[TBD\]|\[PLACEHOLDER\]|\[INSERT\]' {file}
grep -c '```$' {file}
```

**Gate**: All code checks complete.

### Phase 5: Integration Verification

**Goal**: Confirm cross-references and tool declarations are consistent.

**Reference Resolution**:
1. Extract all referenced files from SKILL.md (grep for `references/`)
2. Verify each exists on disk
3. Check shared pattern links resolve (`../shared-patterns/`)

**Tool Consistency**:
1. Parse `allowed-tools` from YAML
2. Scan instructions for tool usage (Read, Write, Edit, Bash, Grep, Glob, Task, WebSearch)
3. Flag tools used but not declared
4. Flag tools declared but never used

**Anti-Rationalization Table**:
1. Check References section links to `anti-rationalization-core.md`
2. Verify domain-specific anti-rationalization table present (3-5 rows)

```bash
grep -oE 'references/[a-z-]+\.md' skills/{name}/SKILL.md | while read ref; do
  ls "skills/{name}/$ref" 2>/dev/null || echo "MISSING: $ref"
done

grep "allowed-tools:" skills/{name}/SKILL.md
grep -oE '(Read|Write|Edit|Bash|Grep|Glob|Task|WebSearch)' skills/{name}/SKILL.md | sort -u

grep -c "anti-rationalization-core" skills/{name}/SKILL.md
```

**Gate**: All integration checks complete.

### Phase 6: Generate Quality Report

**Goal**: Compile findings into standard report format.

Show all test results with individual scores -- never summarize as "all tests pass." Sort findings by impact (HIGH / MEDIUM / LOW). Include actionable recommendations with file paths and line numbers. For batch evaluations, show per-item comparison to collection averages.

This phase is read-only: report findings, never modify agents or skills. Use skill-creator for fixes. Clean up intermediate analysis files.

Use `references/report-templates.md`. Report MUST include:

1. **Header**: Name, type, date, overall score and grade
2. **Structural Validation**: Table with check, status, score, evidence (line numbers)
3. **Content Depth**: Line counts, grade, depth score
4. **Code Quality**: Script syntax results, placeholder count, untagged block count
5. **Issues Found**: Grouped HIGH / MEDIUM / LOW
6. **Recommendations**: Specific improvements with file paths and line numbers
7. **Comparison**: Score vs collection average (if batch)

**Issue Priority**:

| Priority | Criteria | Examples |
|----------|----------|---------|
| HIGH | Missing required section or broken functionality | No Operator Context, script syntax errors |
| MEDIUM | Present but incomplete or non-compliant | Wrong item counts, old allowed-tools format |
| LOW | Cosmetic or minor quality | Untagged code blocks, missing changelog |

**Grade Boundaries**:

| Score | Grade | Interpretation |
|-------|-------|----------------|
| 90-100 | A | Production ready, exemplary |
| 80-89 | B | Good, minor improvements needed |
| 70-79 | C | Adequate, some gaps |
| 60-69 | D | Below standard, significant work needed |
| <60 | F | Major overhaul required |

**Gate**: Report generated with all sections populated and evidence cited.

---

## Examples

### Example 1: Single Skill Evaluation
User says: "Evaluate the test-driven-development skill"
1. Confirm `skills/test-driven-development/` exists (IDENTIFY)
2. Check YAML, Operator Context, Error Handling (STRUCTURAL)
3. Count lines in SKILL.md + references (CONTENT)
4. Syntax-check scripts, find placeholders (CODE)
5. Verify referenced files exist (INTEGRATION)
6. Generate scored report (REPORT)

### Example 2: Collection Batch Evaluation
User says: "Audit all agents and skills"
1. List all agents/*.md and skills/*/SKILL.md (IDENTIFY)
2. Run Steps 2-5 for each target (EVALUATE)
3. Generate individual reports + collection summary (REPORT)

### Example 3: V2 Migration Compliance Check
User says: "Check if systematic-refactoring skill meets v2 standards"
1. Confirm skill exists (IDENTIFY)
2. Check YAML uses list `allowed-tools`, pipe description, version 2.0.0 (STRUCTURAL)
3. Verify Operator Context counts: Hardcoded 5-8, Default 5-8, Optional 3-5 (STRUCTURAL)
4. Confirm CAN/CANNOT, gates, anti-rationalization table (STRUCTURAL)
5. Count lines, run code checks (CONTENT + CODE)
6. Generate report highlighting v2 gaps (REPORT)

---

## Error Handling

### Error: "File Not Found"
Cause: Incorrect path or deleted item
Solution: Verify with `ls`. If missing, exclude from batch and note in report.

### Error: "Cannot Parse YAML Front Matter"
Cause: Malformed YAML -- missing delimiters, bad indentation, invalid syntax
Solution: Flag as HIGH priority. Score YAML as 0/10. Include parse error in report.

### Error: "Python Syntax Error in Script"
Cause: Validation script has syntax issues
Solution: Run `python3 -m py_compile`, capture error. Score as 0/10. Include error in report.

### Error: "Operator Context Item Counts Out of Range"
Cause: v2 requires Hardcoded 5-8, Default 5-8, Optional 3-5
Solution: Count actual items per type (`- **` prefix). Too few = MEDIUM priority; too many = LOW priority. Score at partial credit (10/20).

---

## References

### Reference Files
- `${CLAUDE_SKILL_DIR}/references/scoring-rubric.md` - Full/partial/no credit breakdowns per category
- `${CLAUDE_SKILL_DIR}/references/report-templates.md` - Standard report format templates
- `${CLAUDE_SKILL_DIR}/references/common-issues.md` - Frequently found issues with fix templates
- `${CLAUDE_SKILL_DIR}/references/batch-evaluation.md` - Batch evaluation procedures and collection summary format
