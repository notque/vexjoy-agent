# Documentation Sync Rules

This file documents the synchronization rules for determining which files must document which tools.

## Primary Documentation Rules

### Skills
**Primary Location**: `skills/README.md`

**Rule**: EVERY skill with a `skills/*/SKILL.md` file MUST be documented in `skills/README.md`

**Format**: Markdown table with columns: Name, Description, Command, Hook

**Enforcement**: High priority - missing entries reported as HIGH severity

### Agents
**Primary Location**: `agents/README.md`

**Rule**: EVERY agent with an `agents/*.md` file MUST be documented in `agents/README.md`

**Format**: Markdown table or list with Name and Description

**Enforcement**: High priority - missing entries reported as HIGH severity

### Commands
**Primary Location**: `commands/README.md`

**Rule**: EVERY command with a `commands/**/*.md` file MUST be documented in `commands/README.md`

**Format**: Markdown list with Command and Description

**Enforcement**: High priority - missing entries reported as HIGH severity

## Secondary Documentation Rules

### docs/REFERENCE.md

**Inclusion Criteria**: Significant or commonly-used tools should be documented here

**Not Required For**:
- Experimental/WIP tools
- Internal/utility tools
- Rarely-used specialized tools

**Format**: Markdown sections with `### tool-name` headers

**Enforcement**: Medium priority - recommended but not required

### README.md (Root)

**Inclusion Criteria**: Highlighted/important tools mentioned in examples or overview

**Not Required For**: Most tools (this is narrative, not catalog)

**Format**: Inline references within text

**Enforcement**: Low priority - no enforcement

## Version Synchronization Rules

### Version Source of Truth

**Single Source**: YAML frontmatter `version:` field in SKILL.md or agent .md file

**Rule**: Documentation should reflect YAML version, NOT the other way around

**When to Update**:
1. Update YAML `version:` field
2. Run docs-sync-checker
3. Update all documentation to match YAML version

### Version Documentation Locations

**Required**: No location required to document version (optional everywhere)

**Recommended**:
- docs/REFERENCE.md: Include version in tool section
- skills/README.md: Could add Version column (not standard currently)

**Enforcement**: Low priority - version mismatches reported as LOW severity

## Deprecation Rules

### Marking Tools as Deprecated

**When to Mark**:
- Tool is being replaced by another tool
- Tool functionality merged elsewhere
- Tool no longer maintained

**How to Mark**:
1. Add `[DEPRECATED]` prefix to description in ALL documentation locations
2. Specify replacement tool if applicable
3. Include deprecation date
4. Include planned removal date (typically 3-6 months)

**Example**:
```markdown
| old-skill | [DEPRECATED] Use new-skill instead. Removal: 2025-03-01 | - | - |
```

### Removing Deprecated Tools

**Timeline**:
1. Mark as deprecated (Day 0)
2. Grace period: 3-6 months
3. Remove tool files (Day N)
4. Remove tool documentation (Day N)

**Rule**: Documentation removal and tool removal happen TOGETHER, not separately

**Enforcement**: Stale entries (documented but not in filesystem) reported as MEDIUM severity

## Sync Check Frequency

### Recommended Schedule

**Development**:
- Before every commit (pre-commit hook)
- After creating/removing tools

**CI/CD**:
- On every pull request (strict mode)
- Nightly on main branch

**Manual**:
- Weekly documentation audit
- Before releases

## Cross-Reference Consistency Rules

### Description Consistency

**Rule**: Same tool should have SAME description across all documentation locations

**Source**: YAML `description:` field is authoritative

**Enforcement**: Visual inspection (not automated currently)

**Example**:
```yaml
# SKILL.md
---
description: Combined Python (ruff) and JavaScript (Biome) linting
---
```

```markdown
# skills/README.md
| code-linting | Combined Python (ruff) and JavaScript (Biome) linting | ... |

# docs/REFERENCE.md
### code-linting
Combined Python (ruff) and JavaScript (Biome) linting skill.
```

All descriptions should match or be consistent variations.

### Command Syntax Consistency

**Rule**: All command references should use same format

**Skill Invocation**: `` `skill: skill-name` ``
**Command Invocation**: `` `/command-name` ``
**Agent Reference**: `` `agent-name` ``

**Enforcement**: Format validation (not automated currently)

## Namespace Handling Rules

### Namespaced Commands

**Format**: Commands in subdirectories use `/` separator

**Filesystem**: `commands/code/cleanup.md`
**Documentation**: `/code cleanup` or `code/cleanup`

**Rule**: Documentation must match the invocation path, not filesystem path

**Example**:
```markdown
# commands/README.md
- `/code cleanup` - Find and fix small neglected improvements
```

### Skill/Agent Namespaces

**Current State**: Skills and agents use flat, hyphenated names rather than namespaces

**Format**: Flat structure with hyphenated names (e.g., `code-linting`, not `code/linting`)

## Sync Score Calculation

### Formula

```
sync_score = (total_tools - total_issues) / total_tools * 100
```

**Where**:
- `total_tools` = count of all skills + agents + commands discovered
- `total_issues` = count of missing entries + stale entries + version mismatches

### Interpretation

- **95-100%**: Excellent - documentation up-to-date
- **85-94%**: Good - minor drift
- **70-84%**: Fair - noticeable drift, action needed
- **<70%**: Poor - significant drift, immediate action required

### Target

**Production**: Maintain >95% sync score at all times

**Development**: Accept 90%+ temporarily during active development

## Exception Handling Rules

### Tools to Ignore

**Scenario**: Some tools should exist in filesystem but NOT be documented

**Solution Options**:
1. Add `.docsignore` file (not implemented yet)
2. Mark as `[INTERNAL]` in documentation
3. Create stub documentation entry

**Current Behavior**: All tools in filesystem expected to be documented

### Work-in-Progress Tools

**Scenario**: Tool is being developed but not ready for users

**Solution**: Document with `[WIP]` or `[EXPERIMENTAL]` prefix

**Example**:
```markdown
| new-feature | [WIP] Experimental new feature, not ready for use | - | - |
```

**Rationale**: Prevents "missing entry" reports while clearly indicating status

## Enforcement Priority Levels

### HIGH Priority
- Missing entries (tool exists, not documented in primary location)
- **Action**: Must fix before merging PR (if in CI/CD strict mode)

### MEDIUM Priority
- Stale entries (documented but tool removed)
- **Action**: Should fix soon, acceptable temporarily

### LOW Priority
- Version mismatches (documented version ≠ YAML version)
- Incomplete entries (missing optional fields)
- **Action**: Fix when convenient

## Sync Workflow Integration

### Pre-Commit Hook

```bash
# Run sync check before commit
python3 skills/meta/docs-sync-checker/scripts/scan_tools.py --repo-root .
python3 skills/meta/docs-sync-checker/scripts/generate_report.py --strict

# If issues found, commit is blocked
# Developer must update documentation
```

### CI/CD Pipeline

```yaml
# GitHub Actions example
- name: Check docs sync
  run: |
    python3 skills/meta/docs-sync-checker/scripts/scan_tools.py --repo-root . --output /tmp/scan.json
    python3 skills/meta/docs-sync-checker/scripts/parse_docs.py --repo-root . --scan-results /tmp/scan.json --output /tmp/parse.json
    python3 skills/meta/docs-sync-checker/scripts/generate_report.py --issues /tmp/parse.json --scan-results /tmp/scan.json --strict
```

### Manual Workflow

```bash
# 1. Create/modify tool
mkdir skills/new-skill
echo "..." > skills/new-skill/SKILL.md

# 2. Run docs-sync-checker
python3 skills/meta/docs-sync-checker/scripts/scan_tools.py --repo-root . --output /tmp/scan.json
python3 skills/meta/docs-sync-checker/scripts/parse_docs.py --repo-root . --scan-results /tmp/scan.json --output /tmp/parse.json
python3 skills/meta/docs-sync-checker/scripts/generate_report.py --issues /tmp/parse.json --scan-results /tmp/scan.json

# 3. Review report and update documentation
vim skills/README.md

# 4. Verify sync
python3 skills/meta/docs-sync-checker/scripts/generate_report.py --issues /tmp/parse.json --scan-results /tmp/scan.json

# 5. Commit tool AND documentation together
git add skills/new-skill skills/README.md
git commit -m "Add new-skill with documentation"
```

## Rule Evolution

These rules may evolve as the repository grows:

**Potential Changes**:
- Add `.docsignore` for tools to exclude
- Add version column to skills/README.md table
- Introduce skill/agent namespaces
- Add automated description consistency checking
- Support alternative documentation formats (JSON, YAML)

**Change Process**:
1. Propose rule change
2. Update this file (sync-rules.md)
3. Update parsing scripts to match new rules
4. Update existing documentation to comply
5. Announce change to contributors
