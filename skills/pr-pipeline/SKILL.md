---
name: pr-pipeline
description: |
  End-to-end pipeline for creating pull requests: Classify Repo, Stage,
  Review, Commit, Push, Review-Fix Loop (max 3), Create, Verify. For personal repos,
  runs iterative /pr-review + fix cycles before PR creation. For protected-org
  repos, human-gated workflow with user confirmation at every step.
  Use when user says "submit PR", "create pull request", "push and PR",
  "send for review", or "open PR". Do NOT use for commits without PR
  creation, branch management alone, or code review without submission intent.
version: 2.0.0
user-invocable: false
allowed-tools:
  - Read
  - Write
  - Bash
  - Grep
  - Glob
  - Edit
  - Task
  - Skill
context: fork
command: /pr
routing:
  triggers:
    - submit PR
    - create pull request
    - send for review
    - push and PR
    - submit changes
    - open PR
  pairs_with:
    - git-commit-flow
    - branch-naming
    - github-actions-check
    - parallel-code-review
  complexity: medium
  category: git-workflow
---

# PR Pipeline

A structured pipeline for creating high-quality pull requests with proper staging, meaningful commits, parallel review, and CI verification.

**Core Principle**: Quality gates at every phase. Never submit a PR that hasn't been reviewed and verified.

---

## Operator Context

This skill operates as an operator for the PR submission workflow, configuring Claude's behavior for structured, gate-enforced pull request creation. It implements the **Pipeline Architecture** pattern -- Classify Repo, Stage, Review, Commit, Push, Review-Fix Loop, Create, Verify -- with repo-aware gating and parallel review as dedicated gate-enforced phases.

### Hardcoded Behaviors (Always Apply)
- **CLAUDE.md Compliance**: Read and follow repository CLAUDE.md commit and branch rules
- **No Attribution**: Never add "Generated with Claude Code", "Co-Authored-By: Claude", or similar
- **Sensitive File Blocking**: Block staging of .env, credentials.json, secrets.*, *.pem, *.key files
- **Verify CI**: Always check CI status before marking pipeline complete
- **Review Before Commit**: Run parallel code review before creating the commit
- **Branch Protection**: Never push directly to main/master without explicit authorization
- **Repo-Aware Review Gate**: Classify repo in Phase 0 using `scripts/classify-repo.py`. For personal repos, run up to 3 iterations of `/pr-review` → fix before creating the PR. For protected-org repos, create the PR but NEVER auto-merge — their CI gates and human reviewers handle quality.
- **Organization-Gated Workflow**: Repos under protected organizations (configured in `scripts/classify-repo.py`) require user confirmation before EACH step: commit message approval, push approval, and PR creation approval. Never auto-execute any of these steps in protected-org repos. Present the proposed action and wait for user approval. After PR creation, STOP — no CI waiting, no merge attempts.

### Default Behaviors (ON unless disabled)
- **Parallel Review**: Launch 3 reviewers (security, business logic, code quality) via Task calls
- **Branch Naming**: Use branch-naming skill for compliant branch names
- **CI Wait**: Wait for CI to complete and report status (timeout 10 minutes)
- **Conventional Commits**: Use conventional commit format focusing on WHAT and WHY
- **Upstream Tracking**: Push with -u flag for new branches

### Optional Behaviors (OFF unless enabled)
- **Skip Parallel Review**: Use `--skip-review` to skip Phase 2 (parallel subagent review) for trivial changes (typos, formatting). Phase 4b (comprehensive `/pr-review` loop) still runs — it cannot be skipped.
- **Draft PR**: Use `--draft` to create draft instead of ready PR
- **No CI Wait**: Use `--no-wait` to skip CI verification phase
- **Custom Title**: Use `--title "..."` to override generated PR title
- **File Filter**: Use `--files "pattern"` to stage only matching files

## What This Skill CAN Do
- Stage, commit, push, and create PRs in a single pipeline execution
- Run parallel code review with 3 independent reviewers before submission
- Block sensitive files from being staged or committed
- Generate meaningful PR titles and bodies from commit history and diff
- Wait for and report CI status after PR creation

## What This Skill CANNOT Do
- Push to main/master without explicit user authorization
- Skip Phase 2 (parallel subagent review) unless `--skip-review` is explicitly passed. Phase 4b review-fix loop always runs for personal repos.
- Create PRs without any staged changes
- Fix CI failures (report them, then stop)
- Merge PRs (creation and verification only)

### Worktree Agent Awareness

When this pipeline runs inside a worktree agent (dispatched with `isolation: "worktree"`), the worktree creates a local branch that persists after the agent completes. This branch blocks `gh pr merge --delete-branch` and `git branch -d`. The dispatching agent or cleanup skill must run `git worktree remove <path>` before merging the PR or deleting the branch. If you are creating a PR from a worktree, note this in the PR body so the caller knows cleanup is required.

---

## Instructions

### Phase 0: CLASSIFY REPO

**Goal**: Determine repo type to apply the correct review and merge policy.

```bash
# Detect repo type using the classification script
REPO_TYPE=$(python3 scripts/classify-repo.py --type-only)
```

| Repo Type | Review Policy | Merge Policy | Step Execution |
|-----------|--------------|--------------|----------------|
| `protected-org` | Phase 2 parallel review only (their reviewers handle comprehensive review) | **NEVER auto-merge**. Create PR, report URL, stop. | **Human-gated**: confirm commit message, push, and PR creation with user before each step |
| `personal` | Phase 2 parallel review + Phase 4b review-fix loop (max 3 iterations of `/pr-review` → fix) | Create PR after review passes | Auto-execute steps normally |

**Gate**: Repo type classified. Policy determined.

### Phase 1: STAGE

**Goal**: Analyze working tree and stage appropriate changes.

**Step 1: Inspect changes**

```bash
# See what's changed
git status --porcelain

# Review diff for context
git diff
git diff --cached
```

**Step 2: Block sensitive files**

Check every changed file against the blocklist:
- `.env`, `.env.*`
- `credentials.json`, `secrets.*`
- `*.pem`, `*.key`, `*.p12`
- Any file matching patterns in `.gitignore`

If sensitive files are detected, STOP and report to user. Do not stage them.

**Step 3: Stage changes**

```bash
# Stage specific files (never git add -A blindly)
git add [files]
```

**Gate**: Changes staged. No sensitive files included. Staged diff makes sense as a cohesive unit.

### Phase 2: REVIEW (Parallel Subagents)

**Goal**: Catch issues before they reach the PR.

Launch 3 reviewers in a single message with 3 Task calls:

**Security Reviewer:**
```
Review these changes for security issues:
[git diff --cached output]

Check for: hardcoded secrets, SQL injection, XSS, command injection, insecure dependencies.
Return: PASS/FAIL with specific findings.
Do NOT suggest changes -- only report issues.
```

**Business Logic Reviewer:**
```
Review these changes for correctness:
[git diff --cached output]

Check for: requirements coverage, edge case handling, state correctness, data validation.
Return: PASS/FAIL with specific findings.
Do NOT suggest changes -- only report issues.
```

**Code Quality Reviewer:**
```
Review these changes for quality:
[git diff --cached output]

Check for: style consistency, error handling, test coverage gaps, naming clarity.
Return: PASS/FAIL with specific findings.
Do NOT suggest changes -- only report issues.
```

**Aggregate results:**
```
Security: PASS/FAIL
Business Logic: PASS/FAIL (warnings if any)
Code Quality: PASS/FAIL (warnings if any)
```

**Gate**: No FAIL from any reviewer. Warnings are acceptable. If any reviewer returns FAIL with critical findings, STOP and report to user.

### Phase 3: COMMIT

**Goal**: Create a meaningful commit with conventional format.

**Step 1: Analyze staged changes**

```bash
git diff --cached --stat
git diff --cached
```

**Step 2: Determine commit type and scope**

Map changes to conventional commit type: feat, fix, refactor, docs, test, chore, ci, style, perf.

**Step 3: Create commit**

```bash
git commit -m "$(cat <<'EOF'
type(scope): concise description of WHAT changed

- Detail about WHY this change was made
- Additional context if multiple files changed
EOF
)"
```

Follow CLAUDE.md rules for commit messages. No attribution lines.

**Protected-org repos**: Before executing the commit, present the proposed commit message to the user and wait for explicit approval. Show the full message and list of files that will be committed.

**Gate**: Commit created successfully. Message follows conventional format. (protected-org: user confirmed.)

### Phase 4: PUSH

**Goal**: Push changes to remote with proper branch setup.

**Step 1: Ensure correct branch**

```bash
# Check current branch
git branch --show-current

# If on main/master, create feature branch first
git checkout -b type/descriptive-branch-name
```

Use branch-naming skill if available for compliant names.

**Step 2: Push with tracking**

```bash
# CLAUDE_GATE_BYPASS=1 bypasses the git-submission-gate hook (this skill IS the gate)
CLAUDE_GATE_BYPASS=1 git push -u origin $(git branch --show-current)
```

**Step 3: Verify push**

Confirm push succeeded by checking output. If push fails (e.g., rejected), report error and stop.

**Protected-org repos**: Before executing the push, present the branch name, remote, and list of commits that will be pushed. Wait for user to confirm before executing `CLAUDE_GATE_BYPASS=1 git push`.

**Gate**: Changes pushed to remote. Branch tracks upstream. (protected-org: user confirmed.)

### Phase 4b: REVIEW-FIX LOOP (personal repos only)

**Goal**: Iteratively review and fix issues until clean or max 3 iterations reached.

**Skip condition**: If `REPO_TYPE == "protected-org"`, skip this phase entirely. Protected-org repos have their own PR gates.

**Loop**: Up to 3 iterations of `/pr-review` → fix → amend commit → push.

```
ITERATION = 0
MAX_ITERATIONS = 3

while ITERATION < MAX_ITERATIONS:
    ITERATION += 1

    Step 1: Run /pr-review
    Step 2: If no issues found → EXIT LOOP (proceed to Phase 5)
    Step 3: Fix all reported issues
    Step 4: Stage fixes, amend commit, force push to branch
    Step 5: Report iteration results
```

**Step 1: Run `/pr-review`**

Invoke the `/pr-review` command, which launches specialized review agents (code-reviewer, silent-failure-hunter, comment-analyzer, etc.) and captures retro learnings.

**Step 2: Evaluate results**

| Result | Action |
|--------|--------|
| No issues found | **Exit loop**. Proceed to Phase 5 (CREATE PR). |
| Issues found (iteration < 3) | Fix issues in Step 3, then re-review. |
| Issues remaining after iteration 3 | **Exit loop**. Include remaining issues in PR body as known items. Proceed to Phase 5. |

**Step 3: Fix reported issues**

Address each issue found by the review. This includes:
- Code quality fixes (naming, style, error handling)
- Documentation updates (stale references, missing README entries)
- Test gaps (if flagged)

**Step 4: Amend and push**

```bash
git add [fixed files]
git commit --amend --no-edit
CLAUDE_GATE_BYPASS=1 git push --force-with-lease
```

**Step 5: Report iteration**

```
REVIEW-FIX ITERATION [N/3]
  Found: [X issues]
  Fixed: [Y issues]
  Remaining: [Z issues]
  Status: [CLEAN | FIXING | MAX ITERATIONS REACHED]
```

**Gate**: Review-fix loop complete. Either clean (0 issues) or max 3 iterations reached with remaining issues documented.

### Phase 5: CREATE PR

**Goal**: Create the pull request with meaningful title and body.

**Step 1: Generate PR content**

Analyze the full diff against the base branch and all commit messages to draft:
- Title: Short (under 70 chars), descriptive of the change
- Body: Summary bullets, test plan, review findings from Phase 2

**Step 2: Create PR**

```bash
CLAUDE_GATE_BYPASS=1 gh pr create --title "type(scope): description" --body "$(cat <<'EOF'
## Summary
- [Key change 1]
- [Key change 2]

## Test Plan
- [ ] Tests pass
- [ ] Manual verification of [specific behavior]

## Review Findings
Security: PASS
Business Logic: PASS
Code Quality: PASS
EOF
)"
```

Add `--draft` flag if draft mode was requested.

**Protected-org repos**: Before creating the PR, present the title, body, and target branch to the user. Wait for explicit approval before executing `gh pr create`.

**Step 3: Capture PR URL**

Record and report the PR URL to the user.

**Gate**: PR created successfully. URL available. (protected-org: user confirmed.)

**Protected-org repos**: After creating the PR, report the URL and **STOP the pipeline**. Do not wait for CI or attempt any merge operations. Output:
```
PR PIPELINE COMPLETE (protected-org repo)

Protected-org repo detected — PR created for human review.
PR: https://github.com/your-org/your-repo/pull/123

Next steps are handled by org CI gates and human reviewers.
This pipeline will NOT auto-merge protected-org PRs.
```

### Phase 6: VERIFY (personal repos only)

**Goal**: Wait for CI and report final status.

```bash
# Get the latest workflow run for this branch
gh run list --branch $(git branch --show-current) --limit 1

# Wait for completion (timeout 10 minutes)
gh run watch [run-id] --exit-status
```

If CI fails, report which checks failed and the PR URL. Do NOT merge. Do NOT proceed to cleanup.

If CI passes and user requested merge:
```bash
CLAUDE_GATE_BYPASS=1 gh pr merge --merge --delete-branch
```

**HARD RULE**: Never merge a PR with failing or pending CI. CI must pass first.

If `--no-wait` was passed, skip this phase and report the PR URL immediately.

**Gate**: CI green + merged (if requested). Proceed to Phase 7.

### Phase 7: CLEANUP

**Goal**: Delete the feature branch after successful merge or PR creation.

For personal repos where CI passed and PR was merged:
```bash
# Switch to main and pull
git checkout main
git pull origin main

# Delete local branch
git branch -d <branch-name>

# Delete remote branch
CLAUDE_GATE_BYPASS=1 git push origin --delete <branch-name>

# Prune stale tracking refs
git fetch --prune
```

For personal repos where PR was created but not yet merged: skip cleanup (branch is still active).

For protected-org repos: skip cleanup (their processes handle branch lifecycle).

**Gate**: Branch cleaned up (or skipped if PR is still open). Pipeline complete.

---

## Examples

### Example 1: Standard PR Submission (personal repo)
User says: "Submit a PR for these changes"
Actions:
1. Classify repo from remote URL (CLASSIFY REPO)
2. `git status`, review changes, stage files (STAGE)
3. Launch 3 parallel reviewers on staged diff (REVIEW)
4. Create conventional commit from staged changes (COMMIT)
5. Push branch to remote with tracking (PUSH)
6. Run review-fix loop: `/pr-review` → fix → re-review, up to 3 iterations (REVIEW-FIX LOOP)
7. Create PR with summary and review findings (CREATE PR)
8. Wait for CI, report status (VERIFY)
Result: PR URL with CI status and review-fix iteration count

### Example 2: Draft PR for Work in Progress (personal repo)
User says: "Open a draft PR for what I have so far"
Actions:
1. Classify repo (CLASSIFY REPO)
2. Stage current changes, skip incomplete files if noted (STAGE)
3. Run parallel review (REVIEW)
4. Commit with `wip:` or appropriate prefix (COMMIT)
5. Push to feature branch (PUSH)
6. Run review-fix loop (REVIEW-FIX LOOP)
7. Create PR with `--draft` flag (CREATE PR)
8. Report PR URL, skip CI wait if `--no-wait` (VERIFY)
Result: Draft PR URL

### Example 3: Trivial Change with Skip Parallel Review (personal repo)
User says: "Quick PR for this typo fix, skip review"
Actions:
1. Classify repo (CLASSIFY REPO)
2. Stage the single file change (STAGE)
3. Skip Phase 2 parallel review (--skip-review)
4. Commit: `fix(docs): correct typo in README` (COMMIT)
5. Push to branch (PUSH)
6. Run review-fix loop — Phase 4b still runs even with --skip-review (REVIEW-FIX LOOP)
7. Create PR with minimal body (CREATE PR)
8. Wait for CI (VERIFY)
Result: PR URL for typo fix

### Example 4: Protected-Org Repo (human-gated workflow)
User says: "Submit a PR for these changes" (in a protected-org repo)
Actions:
1. Classify repo → protected-org detected (CLASSIFY REPO)
2. Stage files (STAGE)
3. Run parallel review (REVIEW)
4. Present commit message → user confirms → create commit (COMMIT, human-gated)
5. Present push details → user confirms → push to remote (PUSH, human-gated)
6. Skip Phase 4b (protected-org repos use their own review gates)
7. Present PR title/body → user confirms → create PR (CREATE PR, human-gated)
8. **STOP**. No CI wait, no merge. Report PR URL.
Result: PR URL. Next steps handled by org CI gates and human reviewers.

---

## Error Handling

### Error: "Push Rejected by Remote"
Cause: Branch is behind remote, or branch protection rules block the push
Solution:
1. Check if branch needs rebase: `git log --oneline origin/main..HEAD`
2. If behind, rebase onto latest main: `git pull --rebase origin main`
3. If protection rules, verify branch name is not main/master
4. Retry push after resolving

### Error: "gh pr create Fails"
Cause: No upstream tracking, gh not authenticated, or PR already exists for branch
Solution:
1. Verify gh auth: `gh auth status`
2. Check if PR exists: `gh pr list --head $(git branch --show-current)`
3. If PR exists, report URL instead of creating duplicate
4. If auth issue, instruct user to run `gh auth login`

### Error: "Sensitive File Detected in Staging"
Cause: User's changes include .env, credentials, keys, or other secrets
Solution:
1. STOP immediately -- do not stage the sensitive file
2. Report which file(s) were blocked and why
3. Ask user to confirm exclusion or add to .gitignore
4. Resume pipeline with sensitive files excluded

### Error: "CI Timeout Exceeded"
Cause: CI workflow takes longer than 10 minutes or is stuck
Solution:
1. Report current CI status (pending/running)
2. Provide the PR URL so user can monitor manually
3. Suggest: `gh run watch [run-id]` for manual monitoring
4. Mark pipeline as complete with "CI pending" status

---

## Anti-Patterns

### Anti-Pattern 1: Staging Everything Blindly
**What it looks like**: Running `git add -A` or `git add .` without reviewing changes
**Why wrong**: Captures sensitive files, unrelated changes, build artifacts, and debug logs
**Do instead**: Review `git status`, stage specific files by name

### Anti-Pattern 2: Skipping Review for "Simple" Changes
**What it looks like**: "This is just a one-line fix, no need for review"
**Why wrong**: One-line changes can introduce security vulnerabilities or break business logic
**Do instead**: Run review unless user explicitly passes `--skip-review`

### Anti-Pattern 3: Vague Commit Messages
**What it looks like**: `git commit -m "updates"` or `git commit -m "fix stuff"`
**Why wrong**: Provides no context for reviewers, breaks blame history, makes rollback decisions harder
**Do instead**: Conventional format with WHAT and WHY: `fix(auth): prevent token expiry race condition`

### Anti-Pattern 4: Giant Monolithic PRs
**What it looks like**: 30+ files changed, multiple unrelated features in one PR
**Why wrong**: Impossible to review effectively, high regression risk, blocks other work
**Do instead**: Split into focused PRs. If changes are entangled, suggest user restructure first.

### Anti-Pattern 5: Ignoring CI Failures
**What it looks like**: "CI failed but it's probably flaky, let's merge anyway"
**Why wrong**: Flaky tests mask real failures. Merging broken CI normalizes broken builds.
**Do instead**: Report failure details. Let user decide whether to investigate or retry.

---

## References

This skill uses these shared patterns:
- [Pipeline Architecture](../shared-patterns/pipeline-architecture.md) - Phase sequencing and artifact flow
- [Gate Enforcement](../shared-patterns/gate-enforcement.md) - Phase transition rules
- [Anti-Rationalization](../shared-patterns/anti-rationalization-core.md) - Prevents shortcut rationalizations
- [Verification Checklist](../shared-patterns/verification-checklist.md) - Pre-completion checks

### Domain-Specific Anti-Rationalization

| Rationalization | Why It's Wrong | Required Action |
|-----------------|----------------|-----------------|
| "Just a small change, skip review" | Small changes cause big bugs | Run review unless --skip-review |
| "CI is probably flaky" | Flaky assumption masks real failures | Report failure, let user decide |
| "I'll fix the commit message later" | Later never comes, history is permanent | Write proper message now |
| "These files belong together" | Unrelated changes obscure review | Split into separate PRs |
