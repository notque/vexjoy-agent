# Nightly Reference Enrichment — Headless Prompt

You are running as a nightly autonomous process to improve the toolkit's domain knowledge depth. This is ADR-173: Nightly Reference Enrichment.

## Context

- **Date:** ${ENRICH_DATE}
- **Repository:** ${ENRICH_REPO_DIR}
- **Targets:** ${ENRICH_TARGETS}
- **Max targets:** ${ENRICH_MAX_TARGETS}
- **Dry-run mode:** ${ENRICH_DRY_RUN_MODE}

These targets were identified by `scripts/audit-reference-depth.py` as having Level 0-1 reference depth (thin or missing domain knowledge). Your job is to enrich them to Level 2+ by generating concrete, domain-specific reference files.

## If Dry-Run Mode is "yes"

Only perform the audit analysis. For each target:
1. Run `python3 scripts/audit-reference-depth.py --agent {name} --verbose` (or `--skill {name}`)
2. Run `python3 skills/reference-enrichment/scripts/gap-analyzer.py --agent {name}` (or `--skill {name}`)
3. Report what WOULD be enriched: domains, gaps, recommended reference files
4. Do NOT create any files, branches, or PRs

Print a summary and exit.

## If Dry-Run Mode is "no"

### Phase 1: Setup

1. Check for existing open enrichment PRs: `gh pr list --search "enrich/refs" --state open --json number | python3 -c "import json,sys; d=json.load(sys.stdin); print(len(d))"`
2. If 5 or more enrichment PRs are already open, log "Too many open enrichment PRs (>=5), skipping to avoid accumulation" and exit
3. Create a feature branch: `git checkout -b enrich/refs-${ENRICH_DATE}`

### Phase 2: Enrich Each Target

For each target name in the targets list:

1. **Audit before:** Run `python3 scripts/audit-reference-depth.py --agent {name} --verbose` to record the starting level
2. **Gap analysis:** Run `python3 skills/reference-enrichment/scripts/gap-analyzer.py --agent {name}` to identify specific knowledge gaps
3. **Read exemplars:** Read one high-quality reference file as a model (e.g., `~/.claude/agents/golang-general-engineer/references/go-anti-patterns.md`). This shows what Level 3 depth looks like.
4. **Read the quality rubric:** Read `skills/reference-enrichment/references/quality-rubric.md` for Level classification criteria
5. **Read the template:** Read `skills/reference-enrichment/references/reference-file-template.md` for the standard structure
6. **Generate reference files:** For the top 2-3 gaps identified, create reference files that include:
   - Concrete pattern tables with version ranges (e.g., "Python 3.10+: use match/case")
   - Anti-pattern catalog with detection commands (grep/rg patterns)
   - Code examples in fenced blocks
   - Error-fix mappings from common issues
   - Maximum 500 lines per file
7. **Update the agent/skill body:** Add a loading table that maps task types to the new reference files (or update existing table)
8. **Audit after:** Run `python3 scripts/audit-reference-depth.py --agent {name} --verbose` to verify improvement
9. **Lint:** Run `ruff check . --config pyproject.toml` and `ruff format --check . --config pyproject.toml` if any .py files were created

### Phase 3: Commit and PR

1. Stage only the files you created/modified (reference files, agent/skill body updates)
2. Commit with: `feat(refs): nightly enrichment — {names} (Level {before}→{after})`
3. Push: `git push -u origin enrich/refs-${ENRICH_DATE}`
4. Create PR and auto-merge: `gh pr create --title "feat(refs): nightly reference enrichment ${ENRICH_DATE}" --body "..."` then `gh pr merge --squash --auto --delete-branch`
   - PR body should include: targets processed, level before/after for each, list of new reference files
   - The `--auto` flag merges once CI passes — no human review needed for reference-only changes
5. Switch back to main: `git checkout main`

## Safety Constraints

- **Never modify existing code** — only create/modify files in `references/` directories and loading tables in agent/skill bodies
- **Never modify agent/skill logic** — only add knowledge, not change behavior
- **Maximum 500 lines per reference file** — progressive disclosure principle
- **If a target already has Level 2+ references** when you actually check (audit data may be stale), skip it
- **No force-push, no commits to main** — everything goes through a PR
- **If anything fails, continue with the next target** — don't abort the whole run

## Output

End your session with a summary:

```
=== Nightly Reference Enrichment Summary ===
Date: {date}
Targets processed: N/M
  - {name}: Level {before} → Level {after} ({new_files} new reference files)
  - {name}: SKIPPED (already Level 2+)
  - ...
PR: {url or "none (dry-run)"}
===
```
