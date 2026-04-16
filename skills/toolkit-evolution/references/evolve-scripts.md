# EVOLVE Phase Scripts

> **Scope**: PR creation templates, merge commands, branch cleanup scripts, and learning DB recording commands for Phase 6 EVOLVE. Load this reference before promoting winners or recording cycle outcomes. The SKILL.md contains the decision logic and gates; this file contains the exact commands to execute.

---

## Step 1: Create PR for Winning Proposal

```bash
git push -u origin feat/evolve-{proposal-slug}
gh pr create \
  --title "feat: {short description of improvement}" \
  --body "$(cat <<'EOF'
## Summary
- Evolution cycle proposal: {proposal description}
- Consensus score: {score} (Pragmatist: {rating}, Purist: {rating}, User Advocate: {rating})
- A/B result: {win rate}% improvement across {N} test cases

## Changes
{list of specific changes}

## Test Results
| Test Case | Baseline | Candidate | Delta |
|-----------|----------|-----------|-------|
| ... | ... | ... | ... |

## Evolution Cycle
This PR was generated and validated by the toolkit-evolution skill.
EOF
)"
```

## Step 1: Merge Winner

After creating the PR and verifying CI passes:

```bash
gh pr merge {pr-number} --squash --delete-branch
```

## Step 1b: Branch Cleanup Verification

After merge, verify the remote branch is gone:

```bash
BRANCH_NAME="feat/evolve-{proposal-slug}"
if git ls-remote --heads origin "$BRANCH_NAME" | grep -q "$BRANCH_NAME"; then
  git push origin --delete "$BRANCH_NAME" && echo "Remote branch deleted: $BRANCH_NAME" \
    || echo "WARNING: could not delete remote branch $BRANCH_NAME -- delete manually"
else
  echo "Remote branch already cleaned up: $BRANCH_NAME"
fi
```

## Step 1b: Stale Branch Cleanup

Clean up any stranded remote evolution branches from cycles where PRs were never created:

```bash
git fetch --prune origin 2>/dev/null
git branch -r --merged origin/main | grep "origin/feat/evolve-" | while read branch; do
  remote="${branch#origin/}"
  git push origin --delete "$remote" 2>/dev/null && echo "Cleaned up merged branch: $remote" || true
done
```

## Step 2: Record Failed Proposal

```bash
python3 ~/.claude/scripts/learning-db.py learn \
  --topic "evolution-result" \
  "Failed proposal: {description}. Hypothesis: {what we expected}. Result: {what happened}. Lesson: {what we learned}."
```

## Step 3: Record Full Cycle Summary

```bash
python3 ~/.claude/scripts/learning-db.py learn \
  --topic "evolution-cycle" \
  "toolkit-evolution cycle: {N} proposals evaluated, {M} built, {W} winners, {L} losses. Top win: {description}. Focus: {area or 'general'}."
```

## Step 4: Write Evolution Report

```bash
# Write to project-local evolution-reports directory (gitignored)
# Path: evolution-reports/evolution-report-{YYYY-MM-DD}.md
# Template: skills/toolkit-evolution/references/evolution-report-template.md
mkdir -p evolution-reports
```

Read `references/evolution-report-template.md`, fill in all sections with cycle data, write the dated report.
