# Markdown Format Reference

This file provides expected markdown table and list formats for each README file in the repository.

## skills/README.md

### Expected Format

```markdown
# Skills

| Name | Description | Command | Hook |
|------|-------------|---------|------|
| skill-name-1 | Description of skill 1 | `skill: skill-name-1` | - |
| skill-name-2 | Description of skill 2 | `skill: skill-name-2` | hook-name |
```

### Column Specifications

1. **Name**: Skill name (lowercase-with-hyphens), matches directory name and YAML `name` field
2. **Description**: Brief description (1-2 sentences, <200 chars preferred), from YAML `description` field
3. **Command**: Invocation syntax, always format: `` `skill: skill-name` ``
4. **Hook**: Associated hook name if any, use `-` if no hook

### Parsing Rules

- **Header**: Case-insensitive match for "name", "description", "command", "hook"
- **Separator**: Must have `|---|---|---|---|` pattern
- **Data Rows**: Must have 4 cells matching header columns
- **Alignment**: Pipes must align with header (visual alignment optional)

### Example Valid Variations

All of these are valid and will parse correctly:

```markdown
| Name | Description | Command | Hook |
```

```markdown
| Skill | Desc | Usage | Associated Hook |
```

```markdown
| Skill Name | Description | Command | Hook |
```

## agents/README.md

### Expected Format (Table)

```markdown
# Agents

| Name | Description |
|------|-------------|
| agent-name-1 | Description of agent 1 |
| agent-name-2 | Description of agent 2 |
```

### Expected Format (List)

```markdown
# Agents

- agent-name-1 - Description of agent 1
- agent-name-2 - Description of agent 2
```

### Column/Field Specifications (Table)

1. **Name**: Agent name (lowercase-with-hyphens), matches filename (without .md) and YAML `name` field
2. **Description**: Brief description, from YAML `description` field

### Parsing Rules

- **Table Format**: 2-column table with "Name" and "Description" headers
- **List Format**: Markdown list items with pattern: `- agent-name - Description`
- **Fallback**: If table format fails, try list format

## commands/README.md

### Expected Format (Table)

```markdown
# Commands

| Command | Description |
|---------|-------------|
| /command-1 | Description of command 1 |
| /namespace/command-2 | Description of namespaced command |
```

### Expected Format (List)

```markdown
# Commands

- `/command-1` - Description of command 1
- `/namespace/command-2` - Description of namespaced command
```

### Field Specifications

1. **Command**: Command name with `/` prefix (e.g., `/do`, `/code cleanup`)
2. **Description**: Brief description of what command does

### Parsing Rules

- **Table Format**: 2-column table with "Command" and "Description" headers
- **List Format**: Markdown list items with pattern: `- /command - Description`
- **Slash Prefix**: Leading `/` is optional in parsing (stripped/normalized)
- **Namespaced Commands**: Use `/` separator for namespaces (e.g., `/code cleanup`)

## README.md (Root)

### Expected Format

README.md uses inline references within narrative text. No specific table/list format required.

### Parsing Rules

Tool references extracted via pattern matching:

1. **Skill References**: `` `skill: skill-name` ``
2. **Agent References**: `` `agent-name-engineer` `` or `` `agent-name-agent` ``
3. **Command References**: `` `/command-name` ``

### Example

```markdown
# Repository Overview

Use the `/do` command for complex requests. For code quality, try `skill: code-linting`.
The `golang-general-engineer` agent provides Go expertise.
```

**Parsed References**:
- Command: `do`
- Skill: `code-linting`
- Agent: `golang-general-engineer`

## docs/REFERENCE.md

### Expected Format

```markdown
# Reference Documentation

## Skills Reference

### skill-name-1

Description of skill-name-1. Detailed explanation of purpose and usage.

**Usage**: `skill: skill-name-1`
**Version**: 1.2.0

### skill-name-2

Description of skill-name-2.

**Usage**: `skill: skill-name-2`
**Version**: 2.0.0

## Agents Reference

### agent-name-1

Description of agent-name-1.

...
```

### Section Specifications

1. **Header Level**: `###` (three hashes) for tool name
2. **Tool Name**: Same as YAML `name` field
3. **Description**: First paragraph after header
4. **Usage**: Optional "Usage:" line showing invocation
5. **Version**: Optional "Version:" line showing current version

### Parsing Rules

- **Pattern**: `###\s+([a-z0-9\-]+)` to extract tool name
- **Description**: First non-empty, non-header line after tool header
- **Usage/Version**: Extract from bold "Usage:" or "Version:" lines if present

## Markdown Formatting Best Practices

### Table Alignment

**Preferred** (aligned):
```markdown
| Name              | Description                                    | Command                    |
|-------------------|------------------------------------------------|----------------------------|
| code-linting      | Combined Python and JavaScript linting         | `skill: code-linting`      |
| test-driven-dev   | RED-GREEN-REFACTOR cycle for all code changes  | `skill: test-driven-dev`   |
```

**Acceptable** (unaligned):
```markdown
| Name | Description | Command |
|---|---|---|
| code-linting | Combined Python and JavaScript linting | `skill: code-linting` |
| test-driven-dev | RED-GREEN-REFACTOR cycle | `skill: test-driven-dev` |
```

Both parse identically, but aligned tables are more readable.

### Code Formatting

- **Commands**: Always use backticks: `` `skill: name` ``, `` `/command` ``
- **Tool Names**: Use backticks when referencing in prose: `` `code-linting` ``
- **Consistency**: Use same format throughout all documentation

### Special Characters

- **Hyphens**: Use `-` in tool names, not underscores
- **Pipes**: Use `|` for table cells, escape if needed in content: `\|`
- **Backticks**: Use `` ` `` for inline code, ` ``` ` for code blocks

## Format Validation

The docs-sync-checker validates:

1. **Table Structure**: Header, separator, data rows properly formatted
2. **Column Count**: Data row cells match header column count
3. **Required Columns**: All required columns present (case-insensitive)
4. **List Format**: Items start with `-` or `*`, consistent pattern
5. **Code Blocks**: Backticks properly paired

## Common Formatting Errors

### Error: Misaligned Pipes

```markdown
# ❌ WRONG
| Name | Description |
|---|---
| skill-name | Description |
```

```markdown
# ✅ CORRECT
| Name | Description |
|------|-------------|
| skill-name | Description |
```

### Error: Missing Separator Row

```markdown
# ❌ WRONG
| Name | Description |
| skill-name | Description |
```

```markdown
# ✅ CORRECT
| Name | Description |
|------|-------------|
| skill-name | Description |
```

### Error: Inconsistent List Format

```markdown
# ❌ WRONG
- Command 1 - Description
* Command 2 - Description
- Command 3: Description
```

```markdown
# ✅ CORRECT
- Command 1 - Description
- Command 2 - Description
- Command 3 - Description
```

### Error: Missing Code Backticks

```markdown
# ❌ WRONG
| Name | Command |
|------|---------|
| skill-name | skill: skill-name |
```

```markdown
# ✅ CORRECT
| Name | Command |
|------|---------|
| skill-name | `skill: skill-name` |
```

## Automated Formatting

Future enhancement: docs-sync-checker could offer `--auto-format` flag to:
- Align table columns
- Add missing backticks
- Standardize list markers
- Fix separator rows

## Testing Format Parsing

Use `parse_docs.py --debug` to see detailed parsing output:

```bash
python3 skills/docs-sync-checker/scripts/parse_docs.py --repo-root . --debug
```

Output includes:
- Tables found and parsed
- Row counts
- Column names detected
- Parse errors/warnings
