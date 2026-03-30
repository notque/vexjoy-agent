---
name: git-commit-flow
description: "Phase-gated git commit workflow with validation."
effort: low
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
routing:
  force_route: true
  triggers:
    - "commit"
    - "stage and commit"
    - "commit changes"
  category: git-workflow
---

# Git Commit Flow Skill

Create validated, compliant git commits through a 4-phase gate pattern: VALIDATE, STAGE, COMMIT, VERIFY. Every phase must pass its gate before the next phase begins -- no partial commits, no skipped phases. Only implement the requested commit workflow; implement only the requested commit workflow or "while I'm here" changes.

**Flags** (all OFF by default):
- `--auto-stage`: Stage all modified files without confirmation
- `--skip-validation`: Bypass conventional commit format checks
- `--dry-run`: Show what would be committed without executing
- `--push`: Automatically push to remote after success

---

## Instructions

### Phase 1: VALIDATE

**Goal**: Confirm the environment is safe for committing.

**Step 1: Check working tree state**

Verify clean state before starting because committing during a merge or rebase produces broken history that is painful to untangle.

```bash
git status --porcelain
git rev-parse --abbrev-ref HEAD
```

Verify:
- Not in merge or rebase state (check for `.git/MERGE_HEAD` or `.git/rebase-merge/`)
- Not in detached HEAD (if so, warn user to create branch first)
- Identify current branch name
- No stash/pop operations across branch merges are in progress, because stashed changes based on a pre-merge state can silently apply to the wrong base when popped after a merge, causing branch drift. If stash is detected, verify the working tree diff after pop with `git diff` to confirm changes still make sense against the new base.

**Step 2: Scan for sensitive files**

block `.env`, `*credentials*`, `*secret*`, `*.pem`, `*.key`, `.npmrc`, or `.pypirc` into a commit because credentials in git history are permanent -- removing them requires a full history rewrite and credential rotation. This is a hard fail, not a warning.

Check all changed files against sensitive patterns:

```bash
git diff --cached --name-only | grep -iE '\.(env|pem|key)$|credentials|secret|\.npmrc|\.pypirc'
```

If sensitive files detected:
1. Display them
2. Suggest `.gitignore` additions
3. HARD STOP until resolved -- resolve the issue before proceeding

This scan applies to every commit, including documentation-only changes, because doc commits can accidentally include `.env` files staged alongside them.

**Step 3: Load CLAUDE.md rules**

Read repository CLAUDE.md to extract:
- Banned commit message patterns
- Conventional commit requirements
- Custom commit rules

If no CLAUDE.md exists, use defaults: ban "Generated with Claude Code" and "Co-Authored-By: Claude".

These banned patterns are enforced because they add noise instead of meaningful context and violate repository standards. They will be checked again in Phase 3 during message validation.

**Step 4: Check branch state**

If on `main` or `master`: warn user and require explicit confirmation before proceeding, because direct commits to main bypass code review and CI, risk breaking production, and make rollback difficult. Even small changes belong on a feature branch.

**Gate**: All checks pass. No sensitive files, no merge/rebase state, CLAUDE.md loaded, branch confirmed.

### Phase 2: STAGE

**Goal**: Stage files in logical groups for atomic commits.

**Step 1: Analyze changes**

```bash
git status --porcelain
```

Parse file statuses: Modified (`M`), Added (`A`), Deleted (`D`), Untracked (`??`).

**Step 2: Group files by type**

Group files into logical categories because massive commits with unrelated changes make review overwhelming, break `git bisect`, and are difficult to revert. Each commit should represent one logical change that is independently reviewable.

Apply staging rules (see `references/staging-rules.md` for full rules):

| Category | Patterns | Commit Prefix |
|----------|----------|---------------|
| Documentation | `*.md`, `docs/*` | `docs:` |
| Source code | `*.py`, `*.go`, `*.js`, `*.ts` | `feat:`, `fix:`, `refactor:` |
| Configuration | `*.yaml`, `*.json`, `Makefile` | `chore:`, `build:` |
| Tests | `*_test.*`, `tests/*` | `test:` (or combined with code) |
| CI/Build | `.github/*`, `Dockerfile` | `ci:`, `build:` |

**Step 3: Present staging plan and get confirmation**

Show the user which files will be staged and in how many commits. Wait for approval before executing, because showing the plan first catches mistakes like accidentally staging generated files or mixing unrelated changes.

If `--auto-stage` flag is set, skip confirmation and stage all modified files.

**Step 4: Execute staging**

Stage files explicitly by name -- stage files explicitly by name because blind bulk staging bypasses sensitive file detection and groups unrelated changes together.

```bash
git add <files>
```

Re-validate that no sensitive files ended up in the staging area, because files can be added between the initial scan and staging.

**Gate**: Files staged, no sensitive files in staging area, user confirmed plan.

### Phase 2.5: ADR DECISION COVERAGE (conditional -- ADR-094)

**Goal**: Verify staged changes cover all ADR decision points.

**Skip if**: No `.adr-session.json` exists in the working directory (no active ADR session).

**Step 1: Run coverage check**

```bash
python3 scripts/adr-decision-coverage.py --adr <active-adr-path> --json
```

Read the active ADR path from `.adr-session.json` (`adr_file` field).

**Step 2: Interpret results**

| Verdict | Action |
|---------|--------|
| PASS (100%) | Proceed to Phase 3. Display coverage summary. |
| PARTIAL (>0%) | Display uncovered decision points. Ask: "N decision points not covered. Proceed anyway, or address them first?" |
| FAIL (0%) | Display warning. Ask: "No ADR decision points found in staged changes. This may mean the wrong files are staged, or implementation is incomplete." |

This is advisory -- the implementer can acknowledge uncovered points as intentionally deferred (e.g., "will be covered in a follow-up PR").

**Gate**: Coverage reported. User acknowledged any gaps.

### Phase 3: COMMIT

**Goal**: Create a validated commit with a compliant message.

**Step 1: Get commit message**

Either accept user-provided message or generate one from staged changes. Show the message to the user for approval before executing, because commit messages are permanent history and worth getting right the first time.

**Step 2: Validate message**

Validate now, not later, because git history is permanent and "I'll fix the message later" rarely happens in practice.

```bash
# TODO: scripts/validate_message.py not yet implemented
# Manual alternative: validate commit message format
# Check: type prefix exists, no banned patterns, subject line <= 72 chars
```

Check:
- Conventional commit format: `<type>[scope]: <description>` (see `references/conventional-commits.md`). Skip this check if `--skip-validation` flag is set.
- No banned patterns from CLAUDE.md (see `references/banned-patterns.md`). Always enforce banned patterns -- this check applies even with `--skip-validation` because these patterns violate repository-level standards, not just formatting preferences.
- Subject line: lowercase after type, no trailing period, max 72 chars, imperative mood
- Body: separated by blank line, wrapped at 72 chars
- Focus on WHAT changed and WHY -- no attribution, no emoji unless repo style requires it

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

If `--dry-run` flag is set, display the commit command and message without executing, then stop.

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

Confirm no banned patterns and format preserved. Pre-commit hooks may modify messages, so re-check the persisted version rather than trusting the input.

**Step 4: Clean up and display summary**

Remove any validation artifacts created during the workflow.

Report: commit hash, branch, files changed, validation results, and suggested next steps (push, create PR).

If `--push` flag is set, push to remote after displaying the summary.

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
4. Create a NEW commit (create a NEW commit -- the previous commit attempt did not complete)

### Error: Merge/Rebase in Progress
**Cause**: Working tree is in an incomplete merge or rebase state.
**Solution**: Complete or abort the merge/rebase (`git merge --abort` or `git rebase --abort`) before using this skill.

---

## References

### Reference Files
- `${CLAUDE_SKILL_DIR}/references/conventional-commits.md`: Type definitions, format rules, examples, flowchart
- `${CLAUDE_SKILL_DIR}/references/banned-patterns.md`: Prohibited phrases, detection rules, alternatives
- `${CLAUDE_SKILL_DIR}/references/staging-rules.md`: File type categories, grouping strategies, auto-stage conditions
- `${CLAUDE_SKILL_DIR}/references/commit-workflow-examples.md`: Integration examples, advanced patterns, CI/CD usage
