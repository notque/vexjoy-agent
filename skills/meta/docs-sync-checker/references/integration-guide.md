# Integration Guide

How the docs-sync-checker pipeline runs, its output, and which CI checks already cover the same ground.

## Pipeline

```bash
python3 skills/meta/docs-sync-checker/scripts/scan_tools.py --repo-root . --output /tmp/scan.json
python3 skills/meta/docs-sync-checker/scripts/parse_docs.py --repo-root . --scan-results /tmp/scan.json --output /tmp/issues.json
python3 skills/meta/docs-sync-checker/scripts/generate_report.py --issues /tmp/issues.json --scan-results /tmp/scan.json --output /tmp/sync-report.md
```

| Script | Exit 0 | Exit 1 | Exit 2 |
|--------|--------|--------|--------|
| `scan_tools.py` | Scan done | Repo root missing, or YAML and name errors | Unexpected error |
| `parse_docs.py` | No issues | Missing or stale entries | Error, including a missing primary doc |
| `generate_report.py` | Report written | `--strict` and issues found | Error |

`hooks/posttool-docs-drift-alert.py` runs `scan_tools.py` after edits; keep its exit-code contract stable.

## Filter by tool type

```bash
python3 skills/meta/docs-sync-checker/scripts/scan_tools.py --repo-root . --types skills
python3 skills/meta/docs-sync-checker/scripts/scan_tools.py --repo-root . --types agents,commands
```

## JSON output

```bash
python3 skills/meta/docs-sync-checker/scripts/generate_report.py --issues /tmp/issues.json --format json --output report.json
```

```json
{
  "generated_at": "2026-01-01T00:00:00Z",
  "summary": {"missing_entries": 0, "stale_entries": 0, "total_issues": 0},
  "issues": {"missing_entries": [], "stale_entries": [], "incomplete_entries": []},
  "report_version": "1.0.0",
  "scan_summary": {}
}
```

Each issue carries `suggested_fix`: a generator command for `docs/skills.md` and `docs/routing-map.md`, or the exact row to add or remove in `docs/REFERENCE.md`.

## CI coverage

CI (`.github/workflows/test.yml`) does not run this skill. It runs the authoritative checks directly:

| Check | Catches |
|-------|---------|
| `python3 scripts/generate-skills-doc.py --check` | `docs/skills.md` out of date |
| `python3 scripts/generate-routing-map.py --check` | `docs/routing-map.md` out of date |
| `python3 scripts/validate-index-integrity.py` | Index entries pointing at missing files |
| `python3 scripts/validate-doc-links.py` | Broken doc links |
| `python3 scripts/validate-doc-counts.py` | Wrong count claims in docs |
| `python3 scripts/validate-doc-commands.py` | Scripts named in docs that do not exist |
| `python3 scripts/docs-catalog.py --check` | `docs/*.md` missing `summary` or `read_when` |

The commands-to-`docs/REFERENCE.md` comparison is the one check only this skill makes.

## Pull request checklist

```markdown
- [ ] Ran docs-sync-checker; 0 missing, 0 stale
- [ ] Regenerated docs/skills.md and docs/routing-map.md after component changes
- [ ] Added or removed the docs/REFERENCE.md row for any new or deleted command
```
