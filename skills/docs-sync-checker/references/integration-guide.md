# Integration Guide

This file covers CI/CD setup, pre-commit hooks, auto-fix mode, and workflow integration for docs-sync-checker.

## CI/CD Integration

### GitHub Actions (Strict Mode)

```yaml
name: Documentation Sync Check

on: [push, pull_request]

jobs:
  docs-sync:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      - name: Run docs-sync-checker
        run: |
          python3 skills/docs-sync-checker/scripts/scan_tools.py --repo-root .
          python3 skills/docs-sync-checker/scripts/parse_docs.py --repo-root .
          python3 skills/docs-sync-checker/scripts/generate_report.py --strict
```

Exit codes:
- `0` = no issues found
- `1` = issues found (fail build)

Do NOT use `continue-on-error: true` -- this defeats the purpose of the check.

## Pre-Commit Hook

Add to `.git/hooks/pre-commit`:

```bash
#!/bin/bash
echo "Running documentation sync check..."
python3 skills/docs-sync-checker/scripts/scan_tools.py --repo-root .
python3 skills/docs-sync-checker/scripts/generate_report.py --strict

if [ $? -ne 0 ]; then
  echo ""
  echo "Documentation sync issues found!"
  echo "Review the report above and update documentation files."
  echo "To bypass (NOT recommended): git commit --no-verify"
  exit 1
fi

echo "Documentation sync check passed"
```

## Auto-Fix Mode (Experimental)

```bash
python3 skills/docs-sync-checker/scripts/generate_report.py --issues /tmp/issues.json --auto-fix
```

**What auto-fix does**:
- Adds missing entries to appropriate README tables
- Uses YAML description field verbatim
- Preserves existing table formatting
- Creates backup files (*.backup) before modification

**What auto-fix does NOT do**:
- Remove stale entries (manual review required)
- Fix version mismatches (ambiguous which is correct)
- Improve description quality

Always review changes before committing.

## JSON Output

```bash
python3 skills/docs-sync-checker/scripts/generate_report.py --issues /tmp/issues.json --format json --output report.json
```

Schema:
```json
{
  "summary": {
    "total_tools": 25,
    "missing_entries": 3,
    "stale_entries": 2,
    "version_mismatches": 1,
    "sync_score": 0.88
  },
  "issues": {
    "missing_entries": [],
    "stale_entries": [],
    "version_mismatches": []
  },
  "recommendations": []
}
```

## Filter by Tool Type

```bash
# Skills only
python3 skills/docs-sync-checker/scripts/scan_tools.py --repo-root . --types skills

# Agents and commands
python3 skills/docs-sync-checker/scripts/scan_tools.py --repo-root . --types agents,commands
```

## Workflow Integration

### After Creating a Skill

```bash
mkdir skills/new-skill
# ... create SKILL.md with YAML frontmatter ...

# Run sync checker BEFORE committing
python3 skills/docs-sync-checker/scripts/scan_tools.py --repo-root .
python3 skills/docs-sync-checker/scripts/generate_report.py

# Update documentation per report suggestions
# Commit tool AND documentation together
git add skills/new-skill skills/README.md
git commit -m "Add new-skill with documentation"
```

### After Removing a Tool

```bash
rm -rf skills/old-skill

# Run sync checker to find stale entries
python3 skills/docs-sync-checker/scripts/generate_report.py

# Remove entries from skills/README.md, docs/REFERENCE.md
# Commit deletion AND documentation cleanup together
git add skills/ skills/README.md docs/REFERENCE.md
git commit -m "Remove old-skill and documentation references"
```

### Pull Request Checklist

```markdown
## Documentation Checklist
- [ ] Ran docs-sync-checker to verify documentation sync
- [ ] Added/updated documentation for new/modified tools
- [ ] Removed documentation for deleted tools
- [ ] Version numbers match between YAML and documentation
```

## Sync Score Interpretation

| Score | Rating | Action |
|-------|--------|--------|
| 95-100% | Excellent | Documentation up-to-date |
| 85-94% | Good | Minor drift, fix soon |
| 70-84% | Fair | Noticeable drift, action needed |
| <70% | Poor | Significant drift, immediate action required |

Target: Maintain >95% sync score at all times.
