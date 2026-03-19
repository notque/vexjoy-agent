---
name: git-commit-flow
description: |
  Phase-gated git commit workflow with validation, staging, and CLAUDE.md
  compliance enforcement. Use when creating commits, staging changes, or
  when PR workflows need standardized commits. Triggers: "commit changes",
  "save work", "create commit", or internal skill invocation from PR
  workflows. Do NOT use for merge commits, rebases, amends, cherry-picks,
  or emergency rollbacks requiring raw git speed.
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
---

# Git Commit Flow Skill

## Operator Context

This skill operates as an operator for git commit workflows, configuring Claude's behavior for standardized commit creation with quality enforcement. It implements a **4-phase gate** pattern: VALIDATE, STAGE, COMMIT, VERIFY.

### Hardcoded Behaviors (Always Apply)
- **CLAUDE.md Compliance**: Read and follow repository CLAUDE.md before execution. Enforce banned patterns ("Generated with Claude Code", "Co-Authored-By: Claude") in all commit messages
- **Sensitive File Blocking**: NEVER commit `.env`, `*credentials*`, `*secret*`, `*.pem`, `*.key`, `.npmrc`, `.pypirc`. Hard fail if detected in staging area
- **Over-Engineering Prevention**: Only implement the requested commit workflow. No speculative features, no "while I'm here" improvements
- **Atomic Operations**: Each phase gate must pass before proceeding. No partial commits
- **Branch Protection**: Warn and require confirmation before committing to main/master
- **No Skipped Phases**: Execute all 4 phases sequentially. Never skip validation

### Default Behaviors (ON unless disabled)
- **Interactive Confirmation**: Show staging plan and commit message for user approval before executing
- **Conventional Commit Enforcement**: Validate message follows `<type>[scope]: <description>` format
- **Working Tree Validation**: Check for clean state (no merge/rebase in progress) before starting
- **Smart File Staging**: Group files by type (docs, code, config, tests, CI) for logical commits
- **Post-Commit Verification**: Confirm commit exists in log and working tree is clean after commit
- **Temporary File Cleanup**: Remove validation artifacts created during workflow

### Optional Behaviors (OFF unless enabled)
- **Auto-Stage All**: Stage all modified files without confirmation (`--auto-stage`)
- **Skip Validation**: Bypass conventional commit format checks (`--skip-validation`)
- **Dry Run Mode**: Show what would be committed without executing (`--dry-run`)
- **Push After Commit**: Automatically push to remote after success (`--push`)

## What This Skill CAN Do
- Detect sensitive files before they are committed (regex pattern matching)
- Validate commit messages against conventional commit format and CLAUDE.md banned patterns
- Smart-group files by type for logical, atomic commits
- Generate compliant commit messages from staged changes
- Verify commits succeeded and working tree is clean post-commit

## What This Skill CANNOT Do
- Resolve merge conflicts (requires contextual code judgment)
- Perform interactive rebases (incompatible with deterministic workflow)
- Amend previous commits (use `git commit --amend` directly)
- Judge code quality (use systematic-code-review skill instead)
- Auto-resolve conflicting CLAUDE.md rules (requires human judgment)

---

## Instructions

### Phase 1: VALIDATE

**Goal**: Confirm environment is safe for committing.

**Step 1: Check working tree state**

```bash
git status --porcelain
git rev-parse --abbrev-ref HEAD
```

Verify:
- Not in merge or rebase state (check for `.git/MERGE_HEAD` or `.git/rebase-merge/`)
- Not in detached HEAD (if so, warn user to create branch first)
- Identify current branch name

**Step 2: Scan for sensitive files**

Check all changed files against sensitive patterns. See `references/banned-patterns.md` for the full pattern list.

```bash
# TODO: scripts/validate_state.py not yet implemented
# Manual alternative: check for sensitive files in staged changes
git diff --cached --name-only | grep -iE '\.(env|pem|key)$|credentials|secret|\.npmrc|\.pypirc'
```

If sensitive files detected: display them, suggest `.gitignore` additions, and HARD STOP until resolved.

**Step 3: Load CLAUDE.md rules**

Read repository CLAUDE.md to extract:
- Banned commit message patterns
- Conventional commit requirements
- Custom commit rules

If no CLAUDE.md exists, use defaults: ban "Generated with Claude Code" and "Co-Authored-By: Claude".

**Step 4: Check branch state**

If on `main` or `master`: warn user and require explicit confirmation before proceeding.

**Gate**: All checks pass. No sensitive files, no merge/rebase state, CLAUDE.md loaded.

### Phase 2: STAGE

**Goal**: Stage files in logical groups for atomic commits.

**Step 1: Analyze changes**

```bash
git status --porcelain
```

Parse file statuses: Modified (`M`), Added (`A`), Deleted (`D`), Untracked (`??`).

**Step 2: Group files by type**

Apply staging rules (see `references/staging-rules.md` for full rules):

| Category | Patterns | Commit Prefix |
|----------|----------|---------------|
| Documentation | `*.md`, `docs/*` | `docs:` |
| Source code | `*.py`, `*.go`, `*.js`, `*.ts` | `feat:`, `fix:`, `refactor:` |
| Configuration | `*.yaml`, `*.json`, `Makefile` | `chore:`, `build:` |
| Tests | `*_test.*`, `tests/*` | `test:` (or combined with code) |
| CI/Build | `.github/*`, `Dockerfile` | `ci:`, `build:` |

**Step 3: Present staging plan and get confirmation**

Show the user which files will be staged and in how many commits. Wait for approval.

**Step 4: Execute staging**

```bash
git add <files>
```

Re-validate that no sensitive files ended up in the staging area.

**Gate**: Files staged, no sensitive files in staging area, user confirmed plan.

### Phase 3: COMMIT

**Goal**: Create a validated commit with a compliant message.

**Step 1: Get commit message**

Either accept user-provided message or generate one from staged changes.

**Step 2: Validate message**

```bash
# TODO: scripts/validate_message.py not yet implemented
# Manual alternative: validate commit message format
# Check: type prefix exists, no banned patterns, subject line <= 72 chars
```

Check:
- Conventional commit format: `<type>[scope]: <description>` (see `references/conventional-commits.md`)
- No banned patterns (see `references/banned-patterns.md`)
- Subject line: lowercase after type, no trailing period, max 72 chars, imperative mood
- Body: separated by blank line, wrapped at 72 chars

If validation fails with CRITICAL (banned pattern): block commit, show suggested revision.
If validation fails with WARNING (line length): show warning, allow user to proceed or revise.

**Step 3: Execute commit**

Use heredoc format to preserve multi-line messages:

```bash
git commit -m "$(cat <<'EOF'
<type>: <subject>

<body>
EOF
)"
```

Capture commit hash from output for verification.

**Gate**: Commit message validated and commit executed successfully.

### Phase 4: VERIFY

**Goal**: Confirm commit succeeded and repository is in expected state.

**Step 1: Verify commit exists**

```bash
git log -1 --format="%H %s"
```

Confirm commit hash and subject match expectations.

**Step 2: Verify clean working tree**

```bash
git status --porcelain
```

No staged files should remain (unless user had additional unstaged changes).

**Step 3: Verify message persisted**

```bash
git log -1 --format="%B"
```

Confirm no banned patterns and format preserved (hooks may modify messages).

**Step 4: Display summary**

Report: commit hash, branch, files changed, validation results, and suggested next steps (push, create PR).

**Gate**: All verification passes. Workflow complete.

---

## Examples

### Example 1: Standard Feature Commit
User says: "Commit my changes"
Actions:
1. Validate working tree, scan for sensitive files, load CLAUDE.md (VALIDATE)
2. Group files by type, present staging plan, user confirms (STAGE)
3. Generate message like `feat: add user authentication`, validate format (COMMIT)
4. Verify commit in log, confirm clean tree (VERIFY)

### Example 2: PR Fix Workflow
Internal invocation with explicit message:
```bash
skill: git-commit-flow --message "fix: apply PR review feedback"
```
Runs all 4 phases with the provided message, skipping message generation.

### Example 3: Dry Run
User says: "Show me what would be committed"
```bash
skill: git-commit-flow --dry-run
```
Runs VALIDATE and STAGE phases, shows commit message preview, but does not execute.

---

## Error Handling

### Error: Sensitive Files Detected
**Cause**: Files matching sensitive patterns (`.env`, `*credentials*`, `*.key`) found in changes.
**Solution**:
1. Add to `.gitignore`: `echo ".env" >> .gitignore`
2. Unstage if already staged: `git reset HEAD .env`
3. If already tracked: `git rm --cached .env`
4. Re-run validation

### Error: Banned Pattern in Commit Message
**Cause**: Message contains prohibited phrases like "Generated with Claude Code" or "Co-Authored-By: Claude".
**Solution**: Remove the banned pattern. Write clean, professional message focused on WHAT changed and WHY. See `references/banned-patterns.md` for the full list and alternatives.

### Error: Pre-Commit Hook Failure
**Cause**: Repository pre-commit hook (formatter, linter, tests) rejected the commit.
**Solution**:
1. Read hook output to identify the issue
2. Fix the issue (run formatter, fix lint errors)
3. Re-stage fixed files: `git add -u`
4. Create a NEW commit (do not amend - the previous commit did not happen)

### Error: Merge/Rebase in Progress
**Cause**: Working tree is in an incomplete merge or rebase state.
**Solution**: Complete or abort the merge/rebase (`git merge --abort` or `git rebase --abort`) before using this skill.

---

## Anti-Patterns

### Anti-Pattern 1: Committing Without Validation
**What it looks like**: `git add . && git commit -m "update files"`
**Why wrong**: Skips sensitive file detection, CLAUDE.md compliance, conventional format checks. Risk of leaking credentials or creating inconsistent history.
**Do instead**: Use this skill to validate all changes before manual commits.

### Anti-Pattern 2: Using Banned Commit Patterns
**What it looks like**: Adding "Generated with Claude Code" or "Co-Authored-By: Claude" to messages.
**Why wrong**: Violates CLAUDE.md standards, adds noise instead of meaningful context.
**Do instead**: Focus on WHAT changed and WHY. No attribution, no emoji unless repo style requires it.

### Anti-Pattern 3: Massive Commits with Unrelated Changes
**What it looks like**: Staging 15 files across 5 features with `git add .` and message "update".
**Why wrong**: Makes review overwhelming, breaks `git bisect`, unclear purpose, difficult to revert.
**Do instead**: Use staging groups. One logical change per commit. Each commit independently reviewable.

### Anti-Pattern 4: Committing Directly to Main/Master
**What it looks like**: Making changes on `main` and pushing directly.
**Why wrong**: Bypasses code review, risks breaking production, makes rollback difficult.
**Do instead**: Create feature branch, commit there, push, create PR.

### Anti-Pattern 5: Ignoring Sensitive File Warnings
**What it looks like**: Dismissing warnings about `.env` or credential files and committing anyway.
**Why wrong**: Credentials in git history are permanent. Requires history rewrite and credential rotation to fix.
**Do instead**: IMMEDIATELY add to `.gitignore`, unstage, and rotate any exposed credentials.

### Anti-Pattern 6: Stash/Pop Across Branch Merges
**What it looks like**: Running `git stash`, switching branches to merge or rebase, then `git stash pop` back on the original branch.
**Why wrong**: Stashed changes were based on the pre-merge state. Popping after a merge can silently apply changes to the wrong base, causing branch drift.
**Do instead**: Commit changes before switching branches. If stash is unavoidable, verify the working tree diff after pop with `git diff` to confirm changes still make sense against the new base.
*Graduated from learning.db — multi-agent-coordination/stash-pop-branch-drift*

---

## References

This skill uses these shared patterns:
- [Anti-Rationalization](../shared-patterns/anti-rationalization-core.md) - Prevents shortcut rationalizations
- [Verification Checklist](../shared-patterns/verification-checklist.md) - Pre-completion checks

### Domain-Specific Anti-Rationalization

| Rationalization | Why It's Wrong | Required Action |
|-----------------|----------------|-----------------|
| "Quick commit, no need to validate" | Quick commits leak credentials | Run all 4 phases |
| "It's just docs, skip sensitive scan" | Docs commits can include `.env` files | Validate every commit |
| "I'll fix the message later" | Later never comes; history is permanent | Validate message now |
| "Main branch is fine for this small change" | Small changes cause big problems | Create feature branch |

### Reference Files
- `${CLAUDE_SKILL_DIR}/references/conventional-commits.md`: Type definitions, format rules, examples, flowchart
- `${CLAUDE_SKILL_DIR}/references/banned-patterns.md`: Prohibited phrases, detection rules, alternatives
- `${CLAUDE_SKILL_DIR}/references/staging-rules.md`: File type categories, grouping strategies, auto-stage conditions
- `${CLAUDE_SKILL_DIR}/references/commit-workflow-examples.md`: Integration examples, advanced patterns, CI/CD usage
