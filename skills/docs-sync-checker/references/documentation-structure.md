# Documentation Structure Reference

This file defines where each tool type should be documented and the required fields for each documentation location.

## Documentation File Matrix

| Tool Type | Primary Documentation | Secondary Documentation | Optional Documentation |
|-----------|----------------------|-------------------------|------------------------|
| Skills | skills/README.md (table) | docs/REFERENCE.md (sections) | README.md (references) |
| Agents | agents/README.md (table/list) | docs/REFERENCE.md (sections) | README.md (references) |
| Commands | commands/README.md (list) | docs/REFERENCE.md (sections) | README.md (references) |

## Required Fields Per Documentation Type

### skills/README.md

**Format**: Markdown table

**Required Columns**:
- Name: Skill name (matches YAML `name` field)
- Description: Brief description (from YAML `description` field)
- Command: Invocation syntax (e.g., `skill: skill-name`)
- Hook: Associated hook if any (or "-" if none)

**Example Row**:
```markdown
| code-linting | Combined Python (ruff) and JavaScript (Biome) linting | `skill: code-linting` | - |
```

### agents/README.md

**Format**: Markdown table or list (flexible)

**Required Fields**:
- Name: Agent name (matches YAML `name` field)
- Description: Brief description (from YAML `description` field)

**Table Example**:
```markdown
| Name | Description |
|------|-------------|
| golang-general-engineer | Deep expertise in Go development, architecture, debugging, concurrency |
```

**List Example**:
```markdown
- golang-general-engineer - Deep expertise in Go development, architecture, debugging, concurrency
```

### commands/README.md

**Format**: Markdown list

**Required Fields**:
- Command: Command name with slash prefix (e.g., `/do`, `/code cleanup`)
- Description: Brief description of what command does

**Example**:
```markdown
- `/do` - Smart router that automatically selects the right agents, skills, and commands
- `/code cleanup` - Find and fix small neglected improvements
```

### README.md (Root)

**Format**: References within narrative text

**Fields**: Tool name in code blocks (e.g., `skill: code-linting`, `/do`, `golang-general-engineer`)

**Purpose**: High-level overview showing examples, not comprehensive catalog

### docs/REFERENCE.md

**Format**: Markdown sections with headers

**Required Fields**:
- Section header: `### tool-name`
- Description: Detailed explanation of tool purpose
- Usage: How to invoke the tool
- Version: Current version number (optional but recommended)

**Example**:
```markdown
### code-linting

Combined Python (ruff) and JavaScript (Biome) linting skill. Use when user requests linting, formatting, code quality checks, or style fixes.

**Usage**: `skill: code-linting`
**Version**: 1.2.0
```

## Cross-Reference Requirements

### Skills
- **MUST** be documented in: skills/README.md
- **SHOULD** be documented in: docs/REFERENCE.md (if significant/commonly used)
- **MAY** be referenced in: README.md (if highlighted as important)

### Agents
- **MUST** be documented in: agents/README.md
- **SHOULD** be documented in: docs/REFERENCE.md (if complex/major agent)
- **MAY** be referenced in: README.md (if highlighted as important)

### Commands
- **MUST** be documented in: commands/README.md
- **SHOULD** be documented in: docs/REFERENCE.md (if significant command)
- **MAY** be referenced in: README.md (if highlighted as important)

## Version Synchronization Rules

1. **Single Source of Truth**: YAML frontmatter in SKILL.md or agent .md file is authoritative
2. **Documentation Follows YAML**: All documentation should reflect current YAML version
3. **Update Together**: When updating version in YAML, update all documentation locations
4. **Version Format**: Use semantic versioning (MAJOR.MINOR.PATCH)

## Deprecation Documentation Requirements

When deprecating a tool:

1. Add `[DEPRECATED]` prefix to description in all documentation
2. Specify replacement tool if applicable
3. Include deprecation date and removal timeline
4. Keep documentation present until removal (don't delete immediately)

**Example**:
```markdown
| old-skill | [DEPRECATED] Old skill, use new-skill instead. Removal: 2025-03-01 | - | - |
```

## Documentation Update Workflow

1. **Create Tool**: Add tool directory with SKILL.md/agent.md file
2. **Run docs-sync-checker**: Detect missing documentation
3. **Update Primary Documentation**: Add to skills/README.md, agents/README.md, or commands/README.md
4. **Update Secondary Documentation**: Add to docs/REFERENCE.md if significant tool
5. **Update Root README**: Add reference if highlighted tool
6. **Verify Sync**: Re-run docs-sync-checker to confirm all in sync

## Special Cases

### Namespaced Commands

Commands in subdirectories (e.g., `commands/code/cleanup.md`) should be documented as:
- Command name: `/code cleanup` (with namespace)
- Path reference: `commands/code/cleanup.md`

### Experimental/WIP Tools

Tools in development should be:
- Documented with `[EXPERIMENTAL]` or `[WIP]` prefix
- Included in documentation to prevent "missing entry" reports
- Marked clearly to set expectations

**Example**:
```markdown
| docs-sync-checker | [EXPERIMENTAL] Verify all skills, agents, and commands are documented | `skill: docs-sync-checker` | - |
```

### Private/Internal Tools

If tools should not be publicly documented:
- Add to `.docsignore` file (if implemented)
- Or document with `[INTERNAL]` prefix
- Include brief description for completeness

## Markdown Format Standards

### Table Format

```markdown
| Column 1 | Column 2 | Column 3 |
|----------|----------|----------|
| Value 1  | Value 2  | Value 3  |
```

**Requirements**:
- Header row with column names
- Separator row with `|---|---|` pattern
- Data rows aligned with header
- Consistent use of pipes `|`

### List Format

```markdown
- Item 1 - Description
- Item 2 - Description
```

**Requirements**:
- Use `-` or `*` consistently
- Format: `- /command-name - Description`
- One item per line
- No nested lists for tool catalogs

## Documentation Quality Standards

1. **Accuracy**: Descriptions must match actual tool behavior
2. **Completeness**: All required fields present
3. **Consistency**: Same tool described same way across all locations
4. **Clarity**: Descriptions clear and concise (prefer <200 chars)
5. **Currency**: Versions and descriptions reflect current state

## Validation Checks

The docs-sync-checker performs these validations:

1. **Existence**: Tool exists in filesystem
2. **Documentation**: Tool documented in required location(s)
3. **Name Match**: Documented name matches YAML `name` field
4. **Completeness**: All required fields present
5. **Format**: Markdown tables/lists properly formatted
6. **Staleness**: No documentation for non-existent tools
7. **Version Sync**: Documented version matches YAML version (if version documented)

## Reference Files

This documentation structure is enforced by:
- `skills/docs-sync-checker/scripts/scan_tools.py` - Tool discovery
- `skills/docs-sync-checker/scripts/parse_docs.py` - Documentation parsing
- `skills/docs-sync-checker/scripts/generate_report.py` - Sync reporting
