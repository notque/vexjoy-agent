# Reference Enrichment — Headless Prompt

You are running as an autonomous hourly process to improve the toolkit's domain knowledge depth. This is ADR-173: Reference Enrichment.

## Context

- **Date:** ${ENRICH_DATE}
- **Repository:** ${ENRICH_REPO_DIR}
- **Targets:** ${ENRICH_TARGETS}
- **Max targets:** ${ENRICH_MAX_TARGETS}
- **Dry-run mode:** ${ENRICH_DRY_RUN_MODE}

These targets were identified by `scripts/audit-reference-depth.py` as having Level 0-2 reference depth (missing, thin, or incomplete domain knowledge). Your job is to enrich them to Level 3+ by generating concrete, domain-specific reference files.

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

### Phase 2.5: Validate Enrichment Quality (Keep-or-Revert Gate)

For each enriched target, run a quick validation before committing:

1. **Generate 3 domain-specific test queries** for the agent/skill. Examples:
   - For threejs-builder: "Create a holographic shader effect", "Optimize a scene with 10,000 instances", "Set up morph target animation"
   - For phaser-gamedev: "Add screen shake on enemy hit", "Set up Matter.js collision categories"
   - Queries should specifically exercise the domains covered by the NEW reference files

2. **Score the agent's knowledge** by checking if the agent would produce output that uses patterns from the new references:
   - Read each new reference file and identify 3-5 key patterns it teaches (specific function calls, specific parameter values, specific anti-patterns to avoid)
   - For each test query, check: would the reference loading table's signal detection correctly trigger loading this reference?
   - Verify the loading table entry exists and has correct file path

3. **Keep-or-revert decision:**
   - If the loading table correctly maps signals to the new references AND the references contain concrete, actionable patterns (not generic advice): **KEEP**
   - If the loading table is missing entries for the new references: **FIX the loading table, then KEEP**
   - If the reference file contains only generic patterns that don't add domain-specific value beyond what the agent already knows: **REVERT** (delete the file, remove loading table entry)

4. **Log the decision** for each target: `[KEEP] {name}: {reason}` or `[REVERT] {name}: {reason}`

This gate prevents reference bloat — only references that add concrete, signal-matched domain knowledge survive. The enrichment system should get better, not just bigger.

### Phase 3: Commit and PR

1. Stage only the files you created/modified (reference files, agent/skill body updates)
2. Commit with: `feat(refs): {agent-name} — {brief description of what was added} (Level {before}→{after})`
   - Example: `feat(refs): prometheus-grafana-engineer — PromQL patterns, alerting rules, cardinality management (Level 0→3)`
3. Push: `git push -u origin enrich/refs-${ENRICH_DATE}`
4. Create PR and auto-merge: `gh pr create --title "feat(refs): {agent-name} (Level {before}→{after})" --body "..."` then `gh pr merge --squash --auto --delete-branch`
   - PR title should describe WHAT was enriched, not just the date
   - PR body should include: targets processed, level before/after for each, list of new reference files
   - The `--auto` flag merges once CI passes — no human review needed for reference-only changes
5. Switch back to main: `git checkout main`

## Safety Constraints

- **Never modify existing code** — only create/modify files in `references/` directories and loading tables in agent/skill bodies
- **Never modify agent/skill logic** — only add knowledge, not change behavior
- **Maximum 500 lines per reference file** — progressive disclosure principle
- **If a target already has Level 3+ references** when you actually check (audit data may be stale), skip it
- **No force-push, no commits to main** — everything goes through a PR
- **If anything fails, continue with the next target** — don't abort the whole run
- **Validation gate is mandatory** — never skip Phase 2.5, even if the references "look good"

## Output

End your session with a summary:

```
=== Reference Enrichment Summary ===
Date: {date}
Targets processed: N/M
  - {name}: Level {before} → Level {after} ({new_files} new reference files)
  - {name}: SKIPPED (already Level 3+)
  - ...
PR: {url or "none (dry-run)"}
===
```
