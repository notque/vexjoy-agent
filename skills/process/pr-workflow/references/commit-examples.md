# Commit Intent — Detail Tables, Examples, and Error Handling

## Phase 1: Full Validate Steps

### Step 1: Check working tree state

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

### Step 2: Scan for sensitive files

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

### Step 3: Load CLAUDE.md rules

Read repository CLAUDE.md to extract:
- Banned commit message patterns
- Conventional commit requirements
- Custom commit rules

If no CLAUDE.md exists, use defaults: ban "Generated with Claude Code" and "Co-Authored-By: Claude".

These banned patterns are enforced because they add noise instead of meaningful context and violate repository standards. They will be checked again in Phase 3 during message validation.

### Step 4: Check branch state

If on `main` or `master`: warn user and require explicit confirmation before proceeding, because direct commits to main bypass code review and CI, risk breaking production, and make rollback difficult. Even small changes belong on a feature branch.

---

## Phase 4: Full Verify Steps

### Step 1: Verify commit exists

```bash
git log -1 --format="%H %s"
```

Confirm commit hash and subject match expectations.

### Step 2: Verify clean working tree

```bash
git status --porcelain
```

No staged files should remain (unless user had additional unstaged changes).

### Step 3: Verify message persisted

```bash
git log -1 --format="%B"
```

Confirm no banned patterns and format preserved. Pre-commit hooks may modify messages, so re-check the persisted version rather than trusting the input.

### Step 4: Clean up and display summary

Remove any validation artifacts created during the workflow.

Report: commit hash, branch, files changed, validation results, and suggested next steps (push, create PR).

If `--push` flag is set, push to remote after displaying the summary.

---

## Phase 2: Staging Category Table

Group files into logical categories because massive commits with unrelated changes make review overwhelming, break `git bisect`, and are difficult to revert. Each commit should represent one logical change that is independently reviewable.

Apply staging rules (see `references/commit-staging-rules.md` for full rules):

| Category | Patterns | Commit Prefix |
|----------|----------|---------------|
| Documentation | `*.md`, `docs/*` | `docs:` |
| Source code | `*.py`, `*.go`, `*.js`, `*.ts` | `feat:`, `fix:`, `refactor:` |
| Configuration | `*.yaml`, `*.json`, `Makefile` | `chore:`, `build:` |
| Tests | `*_test.*`, `tests/*` | `test:` (or combined with code) |
| CI/Build | `.github/*`, `Dockerfile` | `ci:`, `build:` |

## Phase 2.5: ADR Decision Coverage Verdicts

| Verdict | Action |
|---------|--------|
| PASS (100%) | Proceed to Phase 3. Display coverage summary. |
| PARTIAL (>0%) | Display uncovered decision points. Ask: "N decision points not covered. Proceed anyway, or address them first?" |
| FAIL (0%) | Display warning. Ask: "No ADR decision points found in staged changes. This may mean the wrong files are staged, or implementation is incomplete." |

This is advisory -- the implementer can acknowledge uncovered points as intentionally deferred (e.g., "will be covered in a follow-up PR").

## Phase 3: Commit Message Validation Rules

Check:
- Conventional commit format: `<type>[scope]: <description>` (see `references/commit-conventional.md`). Skip this check if `--skip-validation` flag is set.
- No banned patterns from CLAUDE.md (see `references/commit-banned-patterns.md`). Always enforce banned patterns -- this check applies even with `--skip-validation` because these patterns violate repository-level standards, not just formatting preferences.
- Subject line: lowercase after type, no trailing period, max 72 chars, imperative mood
- Body: separated by blank line, wrapped at 72 chars
- Focus on WHAT changed and WHY -- no attribution, no emoji unless repo style requires it

If validation fails with CRITICAL (banned pattern): block commit, show suggested revision.
If validation fails with WARNING (line length): show warning, allow user to proceed or revise.

## Phase 3: Commit Heredoc Template

Use heredoc format to preserve multi-line messages:

```bash
git commit -m "$(cat <<'EOF'
<type>: <subject>

<body>
EOF
)"
```

Capture commit hash from output for verification.

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
skill: pr-workflow commit --message "fix: apply PR review feedback"
```
Runs all 4 phases with the provided message, skipping message generation.

### Example 3: Dry Run
User says: "Show me what would be committed"
```bash
skill: pr-workflow commit --dry-run
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
**Solution**: Remove the banned pattern. Write clean, professional message focused on WHAT changed and WHY. See `references/commit-banned-patterns.md` for the full list and alternatives.

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
