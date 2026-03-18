# Agent Structural Quality Rubric

This rubric is designed for LLM-based assessment of agent and skill files.
Based on the agent-evaluation skill's 100-point scoring system.

## Scoring Summary

| Category | Max Points | Description |
|----------|------------|-------------|
| YAML Front Matter | 10 | Required metadata present |
| Operator Context | 20 | Complete behavior definitions |
| Examples | 10 | Realistic usage examples |
| Error Handling | 10 | Common errors documented |
| Reference Files | 10 | Supporting documentation (skills) |
| Validation Script | 10 | Automated validation (skills) |
| Content Depth | 30 | Total line count / documentation depth |

**Total: 100 points**

---

## Category Details

### 1. YAML Front Matter (10 points)

**Required Fields for Agents:**
- `name`: Agent identifier
- `description`: Clear purpose explanation

**Required Fields for Skills:**
- `name`: Skill identifier
- `description`: Clear purpose explanation
- `allowed-tools`: List of permitted tools

**Scoring:**
- 10 points: All required fields present with meaningful content
- 5 points: Some fields missing or empty
- 0 points: No YAML frontmatter or critically malformed

**Check for:**
```yaml
---
name: agent-name
description: |
  Multi-line description explaining purpose
allowed-tools: Read, Write, Bash  # Skills only
---
```

---

### 2. Operator Context Section (20 points)

**Required Subsections:**
1. `### Hardcoded Behaviors` - Always-on behaviors
2. `### Default Behaviors` - On by default, can be disabled
3. `### Optional Behaviors` - Off by default, can be enabled

**Scoring:**
- 20 points: All 3 subsections present with specific behaviors listed
- 13 points: 2 of 3 subsections present
- 7 points: 1 of 3 subsections present
- 0 points: No Operator Context section

**Quality Indicators:**
- Each behavior type has at least 3 specific items
- Behaviors are actionable, not vague
- Clear distinction between hardcoded/default/optional

---

### 3. Examples Section (10 points)

**For Agents - Look for `<example>` tags:**
```xml
<example>
Context: [Scenario description]
user: "[User prompt]"
assistant: "[Expected response]"
<commentary>
[Why this routing makes sense]
</commentary>
</example>
```

**For Skills - Look for code blocks and step-by-step instructions:**
```bash
# Step 1: Do this
command --flag

# Step 2: Then this
another_command
```

**Scoring:**
- 10 points: 3+ realistic examples covering different scenarios
- 6 points: 1-2 examples present
- 3 points: Examples present but incomplete or unrealistic
- 0 points: No examples

---

### 4. Error Handling Section (10 points)

**Expected Content:**
- `## Error Handling` or `## Common Errors` section
- Specific error scenarios listed
- Solutions provided for each error
- Root causes explained

**Scoring:**
- 10 points: Comprehensive error handling with 3+ scenarios
- 5 points: Basic error handling (1-2 scenarios)
- 0 points: No error handling documentation

**Example Format:**
```markdown
## Error Handling

### Error: "Connection refused"
**Cause**: Database not running
**Solution**: Start database with `docker-compose up -d db`

### Error: "Permission denied"
**Cause**: Missing write permissions
**Solution**: Check file ownership and permissions
```

---

### 5. Reference Files (10 points) - Skills Only

**Expected Structure:**
```
skills/skill-name/
  SKILL.md
  references/
    patterns.md
    examples.md
    troubleshooting.md
```

**Scoring:**
- 10 points: references/ directory with substantive .md files
- 5 points: references/ directory exists but sparse
- 0 points: No references/ directory

**Quality Indicators:**
- Reference files add value beyond main SKILL.md
- Cross-referenced from main skill file
- Well-organized by topic

---

### 6. Validation Script (10 points) - Skills Only

**Expected:**
- `scripts/validate.py` present
- Valid Python syntax
- Actually validates something meaningful

**Scoring:**
- 10 points: validate.py exists with valid syntax and meaningful checks
- 5 points: validate.py exists but has syntax errors or minimal checks
- 0 points: No validation script

---

### 7. Content Depth (30 points)

Based on total line count (skill + references for skills):

| Lines | Grade | Points |
|-------|-------|--------|
| >= 2000 | EXCELLENT | 30 |
| 1000-1999 | GOOD | 25 |
| 500-999 | ADEQUATE | 20 |
| 200-499 | THIN | 10 |
| < 200 | INSUFFICIENT | 0 |

**Note:** Quality matters more than quantity. A 500-line file with excellent content beats a 2000-line file with filler.

---

## Grade Thresholds

| Grade | Score Range | Description |
|-------|-------------|-------------|
| A | 90-100 | Production-ready, comprehensive |
| B | 80-89 | Good quality, minor improvements |
| C | 70-79 | Adequate, several areas need work |
| D | 60-69 | Below standard, significant gaps |
| F | < 60 | Incomplete, needs major revision |

---

## Red Flags (Automatic Deductions)

These issues indicate poor quality regardless of other scores:

| Issue | Deduction | Check |
|-------|-----------|-------|
| Placeholder text | -5 per | `[TODO]`, `[TBD]`, `[PLACEHOLDER]` |
| Copy-paste artifacts | -10 | Mismatched names, wrong examples |
| Contradictory instructions | -10 | Conflicting behavior definitions |
| Missing required fields | -20 | No name or description |
| Untagged code blocks | -2 per | Code blocks without language tag |

---

## Assessment Instructions

When assessing an agent or skill:

1. **Read the entire file** before scoring
2. **Check each category** systematically
3. **Note specific evidence** for scores (line numbers, quotes)
4. **Apply red flag deductions** after initial scoring
5. **Provide actionable recommendations** for improvement

**Output Format:**
```json
{
  "overall_pass": true/false,
  "score": 0.0-1.0,
  "assertions": [
    {"assertion": "YAML front matter complete", "passed": true, "reasoning": "..."},
    {"assertion": "Operator Context present", "passed": true, "reasoning": "..."},
    {"assertion": "Examples realistic", "passed": false, "reasoning": "..."}
  ],
  "summary": "Brief overall assessment with key strengths and weaknesses"
}
```
