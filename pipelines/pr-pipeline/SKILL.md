---
name: pr-pipeline
description: "End-to-end pull request pipeline with review-fix loop."
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
  force_route: true
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
  category: devops
---

# PR Pipeline

A structured pipeline for creating high-quality pull requests with proper staging, meaningful commits, parallel review, and CI verification.

---

## Instructions

### Phase 0: CLASSIFY REPO

**Goal**: Determine repo type to apply the correct review and merge policy.

```bash
# Detect repo type using the classification script
REPO_TYPE=$(python3 ~/.claude/scripts/classify-repo.py --type-only)
```

| Repo Type | Review Policy | Merge Policy | Step Execution |
|-----------|--------------|--------------|----------------|
| `protected-org` | Phase 2 parallel review only (their reviewers handle comprehensive review) | **Create PR, report URL, stop** — merge is handled by org reviewers. | **Human-gated**: confirm commit message, push, and PR creation with user before each step |
| `personal` | Phase 2 parallel review + Phase 4b review-fix loop (max 3 iterations of `/pr-review` -> fix) | Create PR after review passes | Auto-execute steps normally |

Protected-org repos require user confirmation before EACH step (commit message approval, push approval, PR creation approval) because unauthorized actions in shared org repos can trigger CI storms, notify entire teams, or violate org policies. Never auto-execute any of these steps -- present the proposed action and wait for user approval.

**Gate**: Repo type classified. Policy determined.

### Phase 0.5: PREFLIGHT CHECKLIST

**Goal**: Fail fast on environment issues before attempting PR creation. Every check produces a specific, actionable error message -- not a generic "preflight failed."

PR creation can fail mid-way because the working tree is dirty, the branch is main, or `gh` isn't authenticated -- all discoverable before starting the pipeline. Catching these upfront avoids partial state (e.g., a commit pushed but no PR created).

Run 5 checks sequentially (verification status, clean working tree, correct branch, remote configured, `gh` authenticated). Abort on the first failure with a specific error message.

See `references/preflight-checklist.md` for the full check table, bash script, and note on Check 1 (verification status).

**Gate**: All preflight checks pass. Environment is ready for PR creation. Proceed to Phase 1.

### Phase 1: STAGE

**Goal**: Analyze working tree and stage appropriate changes.

**Step 1: Read and follow CLAUDE.md**

Before staging, read the repository's CLAUDE.md for commit and branch rules. These rules override defaults because each repo has its own conventions for branch naming, commit format, and file organization.

**Step 2: Inspect changes**

```bash
# See what's changed
git status --porcelain

# Review diff for context
git diff
git diff --cached
```

**Step 3: Block sensitive files**

Check every changed file against the blocklist. Sensitive files must be blocked here, before staging, because once committed they enter git history permanently -- removing them later requires history rewriting which is disruptive for all collaborators.

Blocklist:
- `.env`, `.env.*`
- `credentials.json`, `secrets.*`
- `*.pem`, `*.key`, `*.p12`
- Any file matching patterns in `.gitignore`

If sensitive files are detected, STOP and report to user. Do not stage them.

**Step 4: Stage changes**

Stage specific files by name -- never run `git add -A` or `git add .` because blind staging captures unrelated changes, build artifacts, and debug logs that obscure review and pollute history.

```bash
# Stage specific files (never git add -A blindly)
git add [files]
```

If the changeset spans 30+ files or multiple unrelated features, suggest the user split into focused PRs. Monolithic PRs are impossible to review effectively, carry high regression risk, and block other work.

**Gate**: Changes staged. No sensitive files included. Staged diff makes sense as a cohesive unit.

### Phase 2: REVIEW (Comprehensive Multi-Agent Review)

**Goal**: Catch ALL issues before they reach the commit. Run the review loop before creating the commit because post-merge fixes cost 2 PRs instead of 1.

**Skip condition**: Only if user explicitly passes `--skip-review`. One-line changes can still introduce security vulnerabilities or break business logic, so the default is always to review.

**Invoke the comprehensive-review skill:**

```
Invoke: /comprehensive-review
Scope: git diff --cached (staged changes)
Mode: review + fix (default)
```

This dispatches:
- **Wave 1**: 11 foundation agents in parallel (security, business logic, architecture, silent failures, test coverage, type design, code quality, comments, language specialist, docs validator, ADR compliance)
- **Wave 2**: 10 deep-dive agents with Wave 1 context (performance, concurrency, API contracts, dependencies, error messages, dead code, naming, observability, config safety, migration safety)

All findings are auto-fixed. The fix commit is applied to the staged changes before proceeding to Phase 3.

**If comprehensive-review finds CRITICAL issues that cannot be auto-fixed**: STOP and report to user. Do not proceed to commit.

**Gate**: Comprehensive review complete. All findings fixed or explained. No unresolved CRITICAL issues.

### Phase 2b: CROSS-MODEL REVIEW (optional)

**Goal**: Get an independent second opinion from OpenAI Codex CLI to catch issues that same-model review might miss.

**Skip condition**: Skip if `codex` CLI is not installed (`which codex` fails), or if user passes `--skip-codex`. This phase is additive -- it never blocks the pipeline, only adds signal.

**Invoke the codex-code-review skill:**

```
Invoke: /codex-code-review
Scope: git diff --cached (staged changes)
```

Codex runs in read-only sandbox mode with GPT-5.4 xhigh reasoning. It produces structured findings (CRITICAL / IMPROVEMENTS / POSITIVE / SUMMARY). Claude assesses each finding before incorporating -- Codex feedback is a second opinion, not authoritative.

**If Codex finds CRITICAL issues that Claude agrees with**: Fix them and re-stage before proceeding.
**If Codex is unavailable or errors**: Log the skip reason and proceed. This phase must never block the pipeline.

**Gate**: Cross-model review complete (or skipped). Any agreed-upon findings fixed.

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

Write the commit message now with full context -- "I'll fix the commit message later" never happens, and git history is permanent.

```bash
git commit -m "$(cat <<'EOF'
type(scope): concise description of WHAT changed

- Detail about WHY this change was made
- Additional context if multiple files changed
EOF
)"
```

Follow CLAUDE.md rules for commit messages. Never add "Generated with Claude Code", "Co-Authored-By: Claude", or similar attribution lines because they add noise and violate most project commit conventions.

**Protected-org repos**: Before executing the commit, present the proposed commit message to the user and wait for explicit approval. Show the full message and list of files that will be committed.

**Gate**: Commit created successfully. Message follows conventional format. (protected-org: user confirmed.)

### Phase 4: PUSH

**Goal**: Push changes to remote with proper branch setup.

**Step 1: Ensure correct branch**

Never push directly to main/master without explicit authorization -- this bypasses all review gates and can break the build for everyone.

```bash
# Check current branch
git branch --show-current

# If on main/master, create feature branch first
git checkout -b type/descriptive-branch-name
```

Use branch-naming skill if available for compliant names.

**Step 2: Push with tracking**

Push with `-u` flag for new branches so subsequent pushes and PR creation can find the upstream automatically.

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

**Skip condition**: If `REPO_TYPE == "protected-org"`, skip this phase entirely. Protected-org repos have their own PR gates. This phase cannot be skipped for personal repos -- even with `--skip-review` (which only skips Phase 2), this loop always runs because it is the final quality gate before PR creation.

**Loop**: Up to 3 iterations of `/pr-review` -> fix -> amend commit -> push. After iteration 3, exit and document remaining issues in the PR body.

See `references/review-fix-loop.md` for the full loop logic, steps 1-5 with code blocks, result table, and iteration report format.

**Gate**: Review-fix loop complete. Either clean (0 issues) or max 3 iterations reached with remaining issues documented.

### Phase 4c: RETRO (toolkit repo only)

**Goal**: Record review findings as retro learnings, graduate them, and embed patterns in the responsible agents/skills to prevent recurrence.

**Skip condition**: If the repo is NOT the claude-code-toolkit repo, skip this phase entirely. Detection: check if both `agents/` and `skills/` directories exist at the project root. If either is missing, skip directly to Phase 5.

Five steps: collect findings from Phases 2 and 4b, record per-component learnings, boost to 1.0 and graduate immediately, embed graduated patterns in the responsible agent/skill files, and stage the updated files.

See `references/retro-adr-phases.md` for full steps, bash commands, and the finding-target table.

**Gate**: All review findings recorded in learning.db, graduated to 1.0, and embedded in the responsible agent/skill files. Updated files staged for commit.

### Phase 4d: ADR VALIDATION (toolkit repo only)

**Goal**: Verify that all ADRs in the `adr/` directory have consistent format and valid status fields before the PR is created.

**Skip condition**: Same as Phase 4c -- only runs in the toolkit repo (both `agents/` and `skills/` directories exist at root).

Run `python3 ~/.claude/scripts/adr-status.py check`; fix any warnings and stage changes. Run `python3 ~/.claude/scripts/adr-status.py status` and include the summary in the PR body if the PR touches `adr/*.md` files.

See `references/retro-adr-phases.md` for full ADR commands and fix workflow.

**Gate**: `python3 ~/.claude/scripts/adr-status.py check` exits 0. All ADRs have valid format.

### Phase 5: CREATE PR

**Goal**: Create the pull request with meaningful title and body.

**Step 1: Generate PR content**

Analyze the full diff against the base branch and all commit messages to draft:
- Title: Short (under 70 chars), descriptive of the change
- Body: Summary bullets, test plan, review findings from Phase 2

**Step 1.5: Artifact-Driven PR Body Generation**

When planning artifacts exist (`task_plan.md`, verification reports, review summaries, deviation logs), generate the PR body from them rather than writing freeform. Artifacts capture *intent*, which is more valuable to reviewers than a mechanical diff summary. Fall back to diff-based generation when no artifacts exist.

See `references/pr-templates.md` for the full artifact table, PR body template, and fallback guidance.

**Step 2: Create PR**

This pipeline cannot create PRs without staged changes -- if nothing is staged, the earlier phases would have caught this.

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

Add `--draft` flag if draft mode was requested via `--draft`.

**Protected-org repos**: Before creating the PR, present the title, body, and target branch to the user. Wait for explicit approval before executing `gh pr create`.

**Step 3: Capture PR URL**

Record and report the PR URL to the user.

**Gate**: PR created successfully. URL available. (protected-org: user confirmed.)

**Protected-org repos**: After creating the PR, report the URL and **STOP the pipeline**. Do not wait for CI or attempt any merge operations. Output:
```
PR PIPELINE COMPLETE (protected-org repo)

Protected-org repo detected -- PR created for human review.
PR: https://github.com/your-org/your-repo/pull/123

Next steps are handled by org CI gates and human reviewers.
This pipeline will NOT auto-merge protected-org PRs.
```

### Phase 6: VERIFY (personal repos only)

**Goal**: Wait for CI and report final status. Always check CI status before marking the pipeline complete because merging without CI confirmation risks shipping broken code.

```bash
# Get the latest workflow run for this branch
gh run list --branch $(git branch --show-current) --limit 1

# Wait for completion (timeout 10 minutes)
gh run watch [run-id] --exit-status
```

If CI fails, report which checks failed and the PR URL. Do NOT merge. Do NOT proceed to cleanup. This pipeline reports CI failures but does not fix them -- diagnosing CI requires different context than PR creation.

If CI passes and user requested merge:
```bash
CLAUDE_GATE_BYPASS=1 gh pr merge --merge --delete-branch
```

**HARD RULE**: Never merge a PR with failing or pending CI. CI must pass first. The `ci-merge-gate.py` hook enforces this mechanically -- it blocks `gh pr merge` when checks are failing or pending. Do NOT use `--admin` or any bypass to circumvent this. If CI fails on an "unrelated" test, investigate the root cause (date-dependent fixtures, flaky tests) rather than force-merging -- assuming CI is "probably flaky" masks real failures and normalizes broken builds.

*Graduated from learning.db -- skill:pr-sync/17fed1ab26c7 (PR #55 merged with failing CI, led to broken main)*

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

**ADR status update (ADR-095)**: If `.adr-session.json` exists and the PR was merged:
1. Read the active ADR path from `.adr-session.json`
2. Update status from "Proposed" to "Accepted" in the ADR file
3. Move the ADR file to `adr/completed/`
4. Clear `.adr-session.json`
5. Report: `ADR updated: {name} -> Accepted, moved to completed/`

ADRs are gitignored (local-only), so this is a local file operation, not a git operation.

**Gate**: Branch cleaned up (or skipped if PR is still open). Pipeline complete.

### Worktree Agent Awareness

When this pipeline runs inside a worktree agent (dispatched with `isolation: "worktree"`), the worktree creates a local branch that persists after the agent completes. This branch blocks `gh pr merge --delete-branch` and `git branch -d`. The dispatching agent or cleanup skill must run `git worktree remove <path>` before merging the PR or deleting the branch. If you are creating a PR from a worktree, note this in the PR body so the caller knows cleanup is required.

### Options Reference and Examples

See `references/pr-templates.md` for the full options reference table and all 4 usage examples (Standard PR, Draft PR, Trivial Change, Protected-Org).

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
1. STOP immediately -- exclude the sensitive file from staging
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
