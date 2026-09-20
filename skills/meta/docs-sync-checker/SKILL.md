---
name: docs-sync-checker
description: "Detect documentation drift against filesystem state using the repository's deterministic scanner, parser, and report generator."
user-invocable: false
allowed-tools: [Read, Write, Bash, Grep, Glob, Edit, Task]
routing:
  triggers: ["check doc drift", "sync documentation", "stale docs", "documentation drift", "README outdated"]
  category: documentation
  pairs_with: [toolkit, assessment]
---

# Documentation sync checker

This skill checks whether repository tools are present in or absent from the
expected documentation. It does not judge prose quality or infer when drift
began. Run the bundled programs rather than recreating their parsing rules.

## Run

Use the actual repository root, never a hard-coded home path:

```bash
python3 skills/meta/docs-sync-checker/scripts/scan_tools.py --repo-root "$PWD"
python3 scripts/docs-catalog.py --check
python3 skills/meta/docs-sync-checker/scripts/parse_docs.py --repo-root "$PWD" --scan-results /tmp/scan_results.json
python3 skills/meta/docs-sync-checker/scripts/generate_report.py --issues /tmp/issues.json --output /tmp/sync-report.md
python3 skills/meta/docs-sync-checker/scripts/validate.py --repo-root "$PWD"
```

The scripts own discovery, accepted Markdown shapes, issue severity, and score
calculation. Preserve their JSON contracts when composing them.
`docs-catalog.py --check` is a separate gate: every non-archive/non-image
`docs/*.md` needs `summary` and `read_when` frontmatter.

Supported execution flags include `--strict`, `--format json`, and experimental
`--auto-fix`; never enable mutation without explicit user authorization.

## Report contract

Report the checked files, discovered counts, parse failures, missing entries,
stale entries, incomplete entries, and the script-computed sync score. Every
issue must identify the tool, affected documentation file, severity, and a
concrete edit. Suggested entry text must use the tool's source metadata rather
than generated marketing prose.

Malformed source frontmatter or documentation is an input error, not drift;
surface the exact file and parser error. A missing expected documentation file
is also an input error. Do not create placeholder documentation unless the user
asks for a fix.

## Maintainer references

Load only when changing the checker itself:

- `references/documentation-structure.md` — exact source/document mapping.
- `references/markdown-formats.md` — parser-recognized formats.
- `references/sync-rules.md` — classifications and exclusions.
