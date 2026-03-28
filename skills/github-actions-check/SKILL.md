---
name: github-actions-check
description: |
  Check GitHub Actions workflow status after git push using gh CLI. Reports
  CI status, identifies failing jobs, and suggests local reproduction
  commands. Use after "git push", when user asks about CI status, workflow
  failures, or build results. Use for "check CI", "workflow status",
  "actions failing", or "build broken". Route to other skills for local linting
  (use code-linting), debugging test failures locally (use
  systematic-debugging), or setting up new workflows.
version: 2.0.0
user-invocable: false
allowed-tools:
  - Read
  - Bash
  - Grep
routing:
  force_route: true
  triggers:
    - "check CI"
    - "CI status"
    - "actions status"
    - "did CI pass"
  category: git-workflow
---

# GitHub Actions Check Skill

Check GitHub Actions workflow status after a git push, identify failures, and suggest local reproduction commands. This skill observes and reports -- it modifies workflow files or auto-fixes code only with explicit permission.

## Instructions

### Step 1: Identify Repository and Branch

Read and follow any repository CLAUDE.md before proceeding -- it may contain CI-specific instructions or branch naming conventions.

Determine which repository and branch to check:

```bash
# Get repository from git remote
git remote get-url origin

# Get the branch that was pushed
git branch --show-current
```

Always use the branch that was actually pushed, always the branch that was actually pushed. Checking without `--branch` can show runs from other branches and give misleading status for the user's actual push.

**Gate**: Repository and branch both identified. Confirm both values before proceeding.

### Step 2: Wait and Check Workflow Status

GitHub needs 5-10 seconds after a push to register the workflow run. Checking immediately returns stale results from previous runs, not the current push.

```bash
# Wait for GitHub to register the workflow run
sleep 10

# Check workflow runs for the pushed branch
BRANCH=$(git branch --show-current)
gh run list --branch "$BRANCH" --limit 5
```

Always use the `gh` CLI rather than raw GitHub API calls -- `gh` handles authentication, pagination, and formatting automatically. Writing custom scripts with `curl` or `requests` adds unnecessary complexity when `gh` already does the job.

Show the complete `gh` output verbatim. Show complete output rather than summarizing as "build passed" or "tests failed" -- that hides which jobs ran, their timing, and any warnings. Claiming "build passed" without showing output is unverifiable. The user needs to see the actual data.

**Gate**: Workflow status retrieved and complete output displayed to user. Wait for the gate to pass before proceeding.

### Step 3: Investigate Failures

Only execute this step if Step 2 shows a failed or failing run. Compare against previous runs before classifying failures as pre-existing without comparing against previous runs -- that is speculation, not evidence.

```bash
# Get details of the failed run
gh run view <run-id>

# For deeper investigation (only if user explicitly requests it,
# since full logs can be very verbose)
gh run view <run-id> --log-failed
```

For each failing job, identify:
1. Which job failed (build, test, lint, deploy)
2. The specific error message
3. A local reproduction command

```markdown
## Failure Report
Job: [job name]
Error: [specific error from logs]
Local reproduction: [command to reproduce locally]
Suggested fix: [exact commands to fix, if applicable]
```

For common failures like linting or formatting, provide exact fix commands but present them for user approval. Wait for explicit user permission before auto-fixing and re-pushing -- making code changes and git commits without review may introduce unintended changes. Only use `gh run watch` for interactive monitoring if the user specifically asks for it.

**Gate**: All failures identified with reproduction commands. Wait for the gate to pass before proceeding.

### Step 4: Report and Suggest

If all checks passed:
- Show the complete `gh run list` output (not a summary)
- Confirm which workflows ran and their status

If checks failed:
- Show the failure report from Step 3
- Suggest local reproduction commands
- Suggest fix commands but wait for confirmation before executing without permission
- Ask the user if they want you to apply fixes

Report facts without self-congratulation. Show command output rather than describing it. Be concise but informative.

Clean up any temporary scripts or cache files created during the check before finishing.

This skill only checks CI status. For local debugging of test failures, hand off to systematic-debugging. For local linting, hand off to code-linting. Keep workflow YAML files and CI configuration out of scope for this skill.

**Gate**: Complete status report delivered to user.

---

## Error Handling

### Error: "gh CLI not found"
**Cause**: GitHub CLI not installed on the system
**Solution**:
1. Check if `gh` is available: `which gh`
2. If missing, suggest installation: `brew install gh` or `sudo apt install gh`
3. As last resort, use `curl` with GitHub API (but prefer installing gh)

### Error: "gh auth required"
**Cause**: GitHub CLI not authenticated
**Solution**:
1. Run `gh auth status` to check current auth
2. If not authenticated, suggest `gh auth login`
3. Check if GITHUB_TOKEN environment variable is set as alternative

### Error: "No workflow runs found"
**Cause**: Workflow not triggered, branch has no workflows, or checked too early
**Solution**:
1. Wait longer (up to 30 seconds) and retry
2. Verify `.github/workflows/` directory exists in the repository
3. Check if workflow is configured to trigger on the pushed branch
4. Verify push event matches workflow trigger conditions
