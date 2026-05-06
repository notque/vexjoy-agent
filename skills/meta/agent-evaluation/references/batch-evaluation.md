# Batch Evaluation Procedures

Procedures for evaluating entire agent/skill collections and generating summary reports.

## Batch Evaluation Workflow

### Phase 1: Discovery

```bash
# Count collection size
echo "Agents: $(ls agents/*.md | wc -l)"
echo "Skills: $(ls -d skills/*/ | wc -l)"

# Quick health check
echo "With Operator Model: $(grep -l 'Operator Context' agents/*.md | wc -l)"
```

### Phase 2: Individual Evaluation

Run Steps 1-5 from SKILL.md for each target:

```bash
# Evaluate all agents
for agent in agents/*.md; do
  echo "=== $(basename $agent) ==="
  # Check YAML front matter
  head -20 "$agent" | grep -E "^(name|description|color):"
  # Check Operator Context
  grep -c "## Operator Context" "$agent"
  grep -c "### Hardcoded Behaviors" "$agent"
  grep -c "### Default Behaviors" "$agent"
  grep -c "### Optional Behaviors" "$agent"
done

# Evaluate all skills
for skill in skills/*/SKILL.md; do
  name=$(dirname "$skill" | xargs basename)
  echo "=== $name ==="
  # Check YAML front matter
  head -10 "$skill" | grep -E "^(name|description|version|allowed-tools):"
  # Check references
  ls "skills/$name/references/" 2>/dev/null || echo "NO REFERENCES"
  # Line count
  wc -l < "$skill"
done
```

### Phase 3: Aggregate

Calculate collection-level statistics:
- Score distribution (A/B/C/D/F counts)
- Mean and median scores
- Operator Model coverage percentage
- Average depth score

### Phase 4: Report

Use the Collection Summary template from `report-templates.md`.

## Find Common Issues

```bash
# Find agents missing Operator Model
for f in agents/*.md; do
  grep -q "Operator Context" "$f" || echo "MISSING: $f"
done

# Find thin skills (< 150 lines)
for skill in skills/*/SKILL.md; do
  lines=$(wc -l < "$skill")
  [ "$lines" -lt 150 ] && echo "THIN ($lines): $skill"
done

# Find skills with comma-separated allowed-tools (old format)
grep -l 'allowed-tools:.*,.*' skills/*/SKILL.md
```

## Collection Summary Template

```markdown
# Collection Evaluation Summary

**Date**: {YYYY-MM-DD}
**Agents**: X evaluated
**Skills**: X evaluated

## Score Distribution
| Grade | Agents | Skills |
|-------|--------|--------|
| A (90+) | X | X |
| B (80-89) | X | X |
| C (70-79) | X | X |
| D (60-69) | X | X |
| F (<60) | X | X |

## Top Performers
1. {name}: {score}/100
2. {name}: {score}/100
3. {name}: {score}/100

## Needs Improvement
1. {name}: {score}/100 - {primary issue}
2. {name}: {score}/100 - {primary issue}

## Collection Health
- Operator Model Coverage: X%
- Average Depth Score: X/30
- Reference Completeness: X%
```

## Agent Quality Rubric Summary

**A Grade (90-100)**: Complete Operator Model, 2000+ lines, 3+ examples, comprehensive error handling
**B Grade (80-89)**: Complete Operator Model, 1000-2000 lines, examples present, basic error handling
**C Grade (70-79)**: Partial Operator Model, 500-1000 lines, some examples, limited error handling
**D Grade (60-69)**: Missing components, 200-500 lines, few examples, minimal error handling
**F Grade (<60)**: No Operator Model, <200 lines, no examples, no error handling

## Skill Quality Rubric Summary

**A Grade (90-100)**: Complete YAML with list allowed-tools, full Operator Model, 500+ total lines, working scripts, comprehensive references
**B Grade (80-89)**: Complete YAML, full Operator Model, 300-500 lines, scripts present, basic references
**C Grade (70-79)**: Basic YAML, partial Operator Model, 150-300 lines, scripts present, minimal references
**D/F Grade (<70)**: Missing required components, no Operator Model, <150 lines, missing scripts/references
