# Agent/Skill Scoring Rubric

Detailed scoring criteria for evaluating Claude Code agents and skills against v2.0 standards.

## Point Allocation

### Total Points: 100

| Category | Max Points | Weight |
|----------|------------|--------|
| Structural Validation | 60 | 60% |
| Content Depth | 30 | 30% |
| Integration | 10 | 10% |

## Structural Validation (60 points)

### 1. YAML Front Matter (10 points)

**Full Credit (10 points)**:
- `name:` field present and matches filename
- `description:` field present with meaningful content
- For agents: `color:` field present
- For skills: `version:` set to `2.0.0`, `allowed-tools:` uses YAML list format
- For skills: `description:` uses pipe (`|`) format with WHAT + WHEN + negative constraint, under 1024 chars

**Partial Credit (5 points)**:
- Required fields present but incomplete
- Description too brief (<50 characters) or missing negative constraint
- `allowed-tools:` uses old comma-separated format instead of YAML list

**No Credit (0 points)**:
- Missing YAML front matter
- Missing required fields

### 2. Operator Context (20 points)

**Full Credit (20 points)**:
- `## Operator Context` section present
- `### Hardcoded Behaviors` with 5-8 items (MUST include CLAUDE.md Compliance + Over-Engineering Prevention)
- `### Default Behaviors` with 5-8 items
- `### Optional Behaviors` with 3-5 items
- Clear distinction between behavior types

**Partial Credit (10 points)**:
- Section present but incomplete
- Missing one behavior type
- Fewer than required items per type
- Missing CLAUDE.md Compliance or Over-Engineering Prevention hardcoded behaviors

**No Credit (0 points)**:
- No Operator Context section
- Missing 2+ behavior types

### 3. Error Handling Section (10 points)

**Full Credit (10 points)**:
- `## Error Handling` section present
- 3+ common errors documented
- Each error has cause, symptoms, and solution
- Practical recovery guidance

**Partial Credit (5 points)**:
- Section present with fewer errors
- Missing solutions or causes

**No Credit (0 points)**:
- No error handling section

### 4. Examples (Agents) or References (Skills) (10 points)

**Agents — Full Credit (10 points)**:
- 3+ `<example>` blocks in description
- Each example has Context, user message, assistant response
- Each example has `<commentary>` explaining why

**Agents — Partial Credit (5 points)**:
- 1-2 examples present, or missing context/commentary

**Skills — Full Credit (10 points)**:
- `references/` directory exists with 2+ substantive files
- Files are referenced in main SKILL.md
- Total reference content >200 lines

**Skills — Partial Credit (5 points)**:
- Directory exists with 1 file, or content is minimal

**No Credit (0 points)**:
- No examples (agents) or no references directory (skills)

### 5. CAN/CANNOT Boundaries (5 points)

**Full Credit (5 points)**:
- Both `## What This Skill CAN Do` and `## What This Skill CANNOT Do` sections present
- CAN lists 3-5 concrete capabilities
- CANNOT lists 3-5 explicit limitations with redirects to other skills/agents

**Partial Credit (2 points)**:
- Only one section present
- Items too vague or too few

**No Credit (0 points)**:
- No CAN/CANNOT sections

### 6. Anti-Patterns Section (5 points)

**Full Credit (5 points)**:
- `## Anti-Patterns` section present with 3-5 patterns
- Each pattern has "What it looks like", "Why wrong", "Do instead" structure
- Patterns are specific to the skill's domain

**Partial Credit (2 points)**:
- Section present with fewer than 3 patterns
- Patterns lack the required 3-part structure

**No Credit (0 points)**:
- No anti-patterns section

## Integration (10 points)

### 7. Reference Files and Cross-References (5 points)

**Full Credit (5 points)**:
- `references/` directory exists with 2+ substantive files
- Files are referenced in main SKILL.md
- Total reference content >200 lines
- Shared patterns referenced (anti-rationalization, verification checklist)

**Partial Credit (2 points)**:
- Directory exists with 1 file or minimal content
- Not properly referenced from SKILL.md

**No Credit (0 points)**:
- No references directory or empty directory

### 8. Tool and Link Consistency (5 points)

**Full Credit (5 points)**:
- `allowed-tools` declared in YAML
- Tools used in instructions match `allowed-tools` declaration
- All referenced files exist on disk
- Domain-specific anti-rationalization table present in References section

**Partial Credit (2 points)**:
- Tools declared but mismatch with instructions
- Some broken references

**No Credit (0 points)**:
- No `allowed-tools` declared
- Multiple broken references

## Content Depth (30 points)

### Line Count Thresholds

**For Agents** (main .md file):
| Lines | Score | Grade |
|-------|-------|-------|
| >2500 | 30 | EXCELLENT |
| 2000-2500 | 27 | EXCELLENT |
| 1500-2000 | 24 | GOOD |
| 1000-1500 | 20 | GOOD |
| 500-1000 | 15 | ADEQUATE |
| 300-500 | 10 | THIN |
| <300 | 5 | INSUFFICIENT |

**For Skills** (SKILL.md + references combined):
| Lines | Score | Grade |
|-------|-------|-------|
| >1500 | 30 | EXCELLENT |
| 1000-1500 | 27 | EXCELLENT |
| 500-1000 | 22 | GOOD |
| 300-500 | 17 | ADEQUATE |
| 150-300 | 12 | THIN |
| <150 | 5 | INSUFFICIENT |

## Grade Boundaries

| Score | Grade | Interpretation |
|-------|-------|----------------|
| 90-100 | A | Excellent - production ready |
| 80-89 | B | Good - minor improvements needed |
| 70-79 | C | Adequate - some gaps to address |
| 60-69 | D | Below standard - significant work needed |
| <60 | F | Insufficient - major overhaul required |

## Bonus Points (Up to +10)

May be awarded for exceptional quality:

- **+3**: Includes working code examples that can be executed
- **+2**: Has comprehensive cross-references to related agents/skills
- **+2**: Includes real-world case studies or usage examples
- **+2**: Has automated test coverage
- **+1**: Exceptionally clear writing and organization

## Penalty Points (Up to -10)

May be deducted for quality issues:

- **-3**: Contains placeholder text ([TODO], [TBD], etc.)
- **-2**: Code examples have syntax errors
- **-2**: Misleading or inaccurate information
- **-2**: Inconsistent formatting throughout
- **-1**: Untagged code blocks

## Example Scoring

### Agent Example: golang-general-engineer

| Check | Score | Notes |
|-------|-------|-------|
| YAML front matter | 10/10 | Complete with name, description, color |
| Operator Context | 20/20 | All 3 behavior types, 5+ items each |
| Examples | 10/10 | 3 examples with commentary |
| Error Handling | 10/10 | Comprehensive error section |
| Reference Files | N/A | Not applicable for agents |
| Validation Script | N/A | Not applicable for agents |
| **Structural Total** | **50/50** | |
| Content Depth | 30/30 | 3,343 lines (EXCELLENT) |
| **Total Score** | **80/80** | Adjusted: **100/100** |

### Skill Example: test-driven-development

| Check | Score | Notes |
|-------|-------|-------|
| YAML front matter | 10/10 | Complete with allowed-tools |
| Operator Context | 20/20 | Full Operator Model |
| Examples | N/A | Not applicable for skills |
| Error Handling | 10/10 | 4 common errors documented |
| Reference Files | 10/10 | examples.md with 874 lines |
| Validation Script | 10/10 | validate.py passes syntax |
| **Structural Total** | **60/60** | |
| Content Depth | 30/30 | 1,255 total lines (EXCELLENT) |
| **Total Score** | **90/90** | Adjusted: **100/100** |
