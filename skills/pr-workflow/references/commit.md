# Commit Intent

Create validated, compliant git commits through a 4-phase gate pattern: VALIDATE, STAGE, COMMIT, VERIFY. Every phase must pass its gate before the next phase begins. no partial commits, no skipped phases. Only implement the requested commit workflow or "while I'm here" changes.

**Flags** (all OFF by default):
- `--auto-stage`: Stage all modified files without confirmation
- `--skip-validation`: Bypass conventional commit format checks
- `--dry-run`: Show what would be committed without executing
- `--push`: Automatically push to remote after success

---

## Instructions

### Phase 1: VALIDATE

**Goal**: Confirm the environment is safe for committing.

Four steps cover working-tree state, sensitive-file scan, CLAUDE.md rule load, and branch-state check. See `${CLAUDE_SKILL_DIR}/references/commit-examples.md` (Phase 1: Full Validate Steps) for the complete commands, patterns, rationale, and failure behavior for each step.

**Gate**: All checks pass. No sensitive files, no merge/rebase state, CLAUDE.md loaded, branch confirmed.

### Phase 2: STAGE

**Goal**: Stage files in logical groups for atomic commits.

**Step 1: Analyze changes**

```bash
git status --porcelain
```

Parse file statuses: Modified (`M`), Added (`A`), Deleted (`D`), Untracked (`??`).

**Step 2: Group files by type**

Group files into logical categories because massive commits with unrelated changes make review overwhelming, break `git bisect`, and are difficult to revert. Each commit should represent one logical change that is independently reviewable. See `${CLAUDE_SKILL_DIR}/references/commit-examples.md` (Phase 2: Staging Category Table) and `${CLAUDE_SKILL_DIR}/references/commit-staging-rules.md` for full rules.

**Step 3: Present staging plan and get confirmation**

Show the user which files will be staged and in how many commits. Wait for approval before executing, because showing the plan first catches mistakes like accidentally staging generated files or mixing unrelated changes.

If `--auto-stage` flag is set, skip confirmation and stage all modified files.

**Step 4: Execute staging**

Stage files explicitly by name because blind bulk staging bypasses sensitive file detection and groups unrelated changes together.

```bash
git add <files>
```

Re-validate that no sensitive files ended up in the staging area, because files can be added between the initial scan and staging.

**Gate**: Files staged, no sensitive files in staging area, user confirmed plan.

### Phase 2.5: ADR DECISION COVERAGE (conditional, ADR-094)

**Goal**: Verify staged changes cover all ADR decision points.

**Skip if**: No `.adr-session.json` exists in the working directory (no active ADR session).

**Step 1: Run coverage check**

```bash
python3 scripts/adr-decision-coverage.py --adr <active-adr-path> --json
```

Read the active ADR path from `.adr-session.json` (`adr_file` field).

**Step 2: Interpret results**

See the ADR Decision Coverage Verdicts table in `${CLAUDE_SKILL_DIR}/references/commit-examples.md` (PASS / PARTIAL / FAIL actions). This is advisory. The implementer can acknowledge uncovered points as intentionally deferred.

**Gate**: Coverage reported. User acknowledged any gaps.

### Phase 3: COMMIT

**Goal**: Create a validated commit with a compliant message.

**Step 1: Get commit message**

Either accept user-provided message or generate one from staged changes. Show the message to the user for approval before executing, because commit messages are permanent history and worth getting right the first time.

**Step 2: Validate message**

Validate now, not later, because git history is permanent and "I'll fix the message later" rarely happens in practice.

```bash
python3 ${CLAUDE_SKILL_DIR}/scripts/validate_message.py "feat(scope): description"
```

See the Commit Message Validation Rules in `${CLAUDE_SKILL_DIR}/references/commit-examples.md` for the full checklist (format, banned patterns, subject/body rules, CRITICAL vs WARNING behavior).

**Step 3: Execute commit**

Use heredoc format to preserve multi-line messages. See the Commit Heredoc Template in `${CLAUDE_SKILL_DIR}/references/commit-examples.md`. Capture commit hash from output for verification.

If `--dry-run` flag is set, display the commit command and message without executing, then stop.

**Gate**: Commit message validated and commit executed successfully.

### Phase 4: VERIFY

**Goal**: Confirm commit succeeded and repository is in expected state.

Four steps verify commit existence, clean working tree, message persistence, and produce a summary report. See `${CLAUDE_SKILL_DIR}/references/commit-examples.md` (Phase 4: Full Verify Steps) for the complete commands and `--push` behavior.

**Gate**: All verification passes. Workflow complete.

---

## Examples and Error Handling

See `${CLAUDE_SKILL_DIR}/references/commit-examples.md` for:

- **Examples**: standard feature commit, PR fix workflow, dry run
- **Error Handling**: sensitive files detected, banned pattern, pre-commit hook failure, merge/rebase in progress

---

## References

- `${CLAUDE_SKILL_DIR}/references/commit-conventional.md`: Type definitions, format rules, examples, flowchart
- `${CLAUDE_SKILL_DIR}/references/commit-banned-patterns.md`: Prohibited phrases, detection rules, alternatives
- `${CLAUDE_SKILL_DIR}/references/commit-staging-rules.md`: File type categories, grouping strategies, auto-stage conditions
- `${CLAUDE_SKILL_DIR}/references/commit-workflow-examples.md`: Integration examples, advanced patterns, CI/CD usage
- `${CLAUDE_SKILL_DIR}/references/commit-examples.md`: Worked examples and error handling
