# Common Issues and Fixes

Frequently encountered issues during agent/skill evaluation with solutions.

## Structural Issues

### Issue: Missing Operator Context

**Symptoms**:
- No `## Operator Context` section
- Missing behavior type sections

**Impact**: HIGH - Core requirement for Operator Model compliance

**Fix Template**:
```markdown
## Operator Context

This [agent/skill] operates as an operator for [domain], configuring Claude's behavior for [purpose].

### Hardcoded Behaviors (Always Apply)
- **[Behavior 1]**: [Description - why this is non-negotiable]
- **[Behavior 2]**: [Description]
- **[Behavior 3]**: [Description]

### Default Behaviors (ON unless disabled)
- **[Behavior 1]**: [Description - why this is the sensible default]
- **[Behavior 2]**: [Description]
- **[Behavior 3]**: [Description]

### Optional Behaviors (OFF unless enabled)
- **[Behavior 1]**: [Description - when to enable]
- **[Behavior 2]**: [Description]
- **[Behavior 3]**: [Description]
```

### Issue: Missing allowed-tools Declaration

**Symptoms**:
- Skills without `allowed-tools:` in YAML front matter
- Mismatch between declared tools and instructions

**Impact**: MEDIUM - Affects skill execution capabilities

**Fix**:
```yaml
---
name: skill-name
description: ...
version: 1.0.0
allowed-tools: Read, Write, Bash, Grep, Glob
---
```

**Common Tool Sets**:
- Read-only skills: `Read, Grep, Glob, Bash`
- Editing skills: `Read, Write, Edit, Bash, Grep, Glob`
- Orchestration skills: `Read, Write, Bash, Grep, Glob, TodoWrite`
- Analysis skills: `Read, Bash, Grep, Glob, WebSearch` (if needed)
- Quality gate skills: `Read, Bash, Grep` (primarily execute commands)

### Issue: Missing Examples in Agent Description

**Symptoms**:
- No `<example>` blocks in description field
- Examples without `<commentary>`

**Impact**: MEDIUM - Reduces discoverability and understanding

**Fix Template**:
```markdown
description: Use this agent when... Examples:\n\n<example>\nContext: [Specific scenario]\nuser: "[User request]"\nassistant: "I'll use the [agent-name] agent to [action]."\n<commentary>\n[Why this agent is appropriate]\n</commentary>\n</example>
```

### Issue: No Error Handling Section

**Symptoms**:
- No `## Error Handling` section
- Errors mentioned but not structured

**Impact**: MEDIUM - Users don't know how to recover from problems

**Fix Template**:
```markdown
## Error Handling

### Error: "[Error name]"
**Symptoms**: [What user sees]
**Cause**: [Why this happens]
**Solution**: [How to fix]

### Error: "[Another error]"
**Symptoms**: [What user sees]
**Cause**: [Why this happens]
**Solution**: [How to fix]
```

## Content Issues

### Issue: Thin Content (<200 lines)

**Symptoms**:
- Main file under 200 lines
- No reference files
- Missing sections

**Impact**: HIGH - Insufficient guidance for practical use

**Fix Strategy**:
1. Add more detailed instructions
2. Include code examples with explanations
3. Add error handling section
4. Create reference files
5. Add workflow patterns

**Target Line Counts**:
- Agents: 1,500+ lines
- Skills: 500+ total lines (SKILL.md + references)

### Issue: Placeholder Text

**Symptoms**:
- `[TODO]`, `[TBD]`, `[PLACEHOLDER]`, `[INSERT]` in content
- Incomplete sections marked for later

**Impact**: HIGH - Indicates unfinished work

**Fix**:
1. Search: `grep -E '\[TODO\]|\[TBD\]|\[PLACEHOLDER\]|\[INSERT\]' file.md`
2. Complete or remove each placeholder
3. If genuinely needed, convert to proper TODO comment

### Issue: Untagged Code Blocks

**Symptoms**:
- Code blocks starting with just ` ``` ` instead of ` ```language `
- Syntax highlighting doesn't work

**Impact**: LOW - Affects readability

**Fix**:
```bash
# Find untagged blocks
grep -n '```$' file.md

# Should be:
```python
code here
```

## Integration Issues

### Issue: Broken Reference Links

**Symptoms**:
- References to files that don't exist
- `references/file.md` mentioned but missing

**Impact**: MEDIUM - Users can't find supporting materials

**Fix**:
1. List all references: `grep -oE 'references/[a-z-]+\.md' SKILL.md`
2. Check each exists: `ls references/`
3. Create missing files or remove references

### Issue: Tool Mismatch

**Symptoms**:
- Instructions mention tools not in `allowed-tools`
- Using TodoWrite but not declaring it
- Using WebSearch but not declaring it

**Impact**: MEDIUM - Skills may not work as documented

**Fix**:
1. Audit instructions for tool usage (grep for tool names)
2. Add missing tools to `allowed-tools`
3. Or remove instructions that use undeclared tools

**Example Audit**:
```bash
# Check for TodoWrite usage
grep -i "todowrite\|todo list" SKILL.md

# Check for WebSearch usage
grep -i "websearch\|web search" SKILL.md

# Check for undeclared tool usage
grep -E "Read|Write|Edit|Bash|Grep|Glob|TodoWrite|WebSearch" SKILL.md
```

## Quality Issues

### Issue: Inconsistent Formatting

**Symptoms**:
- Mixed heading levels
- Inconsistent list styles
- Varying code block usage

**Impact**: LOW - Affects professionalism

**Fix**:
- Use `##` for main sections
- Use `###` for subsections
- Use `-` for unordered lists
- Use `1.` for ordered lists
- Always tag code blocks with language

### Issue: Missing Changelog

**Symptoms**:
- No `## Changelog` section
- No version history

**Impact**: LOW - Affects maintainability

**Fix Template**:
```markdown
## Changelog

### Version 1.0.0 (YYYY-MM-DD)
- Initial release
- [Feature 1]
- [Feature 2]
```

## Validation Checklist

Use this checklist during evaluation:

### Structural (Required)
- [ ] YAML front matter complete
- [ ] Operator Context section present
- [ ] Hardcoded Behaviors (3+ items)
- [ ] Default Behaviors (3+ items)
- [ ] Optional Behaviors (3+ items)
- [ ] Error Handling section
- [ ] Reference files (skills)
- [ ] Validation script (skills)

### Content (Required)
- [ ] >200 lines minimum
- [ ] No placeholder text
- [ ] Code blocks tagged
- [ ] Working examples

### Quality (Recommended)
- [ ] Consistent formatting
- [ ] Clear writing
- [ ] Changelog present
- [ ] Cross-references work
