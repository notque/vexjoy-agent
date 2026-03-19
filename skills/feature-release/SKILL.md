---
name: feature-release
description: |
  Merge validated feature to main via PR, tag release, cleanup worktree.
  Use after /feature-validate passes. Use for "release feature", "merge
  feature", "ship it", or "/feature-release". Do NOT use without passing
  validation or for hotfixes that skip the pipeline.
version: 2.0.0
user-invocable: true
command: /feature-release
allowed-tools:
  - Read
  - Write
  - Bash
  - Grep
  - Glob
  - Edit
routing:
  triggers:
    - feature release
    - release feature
    - merge feature
    - ship it
    - feature-release
  pairs_with:
    - feature-validate
    - pr-pipeline
    - git-commit-flow
  complexity: Medium
  category: process
---

# Feature Release Skill

## Purpose

Merge the validated feature to main branch via PR, optionally tag a release, and clean up the feature worktree. Phase 5 of the feature lifecycle (design → plan → implement → validate → **release**).

## Operator Context

### Hardcoded Behaviors (Always Apply)
- **CLAUDE.md Compliance**: Read and follow repository CLAUDE.md
- **Validation Required**: CANNOT release without validation passing
- **State Management via Script**: All state operations through `python3 scripts/feature-state.py`
- **PR-Based Merge**: Always merge via pull request, never direct push to main
- **Conventional Commits**: Use conventional commit format
- **No Attribution Lines**: No "Co-Authored-By" or "Generated with Claude Code"

### Default Behaviors (ON unless disabled)
- **Context Loading**: Read all artifacts (design, plan, implement, validate)
- **Squash Merge**: Squash feature branch into single commit on main
- **Worktree Cleanup**: Remove worktree after successful merge
- **Feature State Archive**: Move feature state to completed

### Optional Behaviors (OFF unless enabled)
- **Version Bump**: Bump version number based on change type
- **Changelog Update**: Add entry to CHANGELOG.md
- **Tag Release**: Create git tag after merge

## What This Skill CAN Do
- Create pull requests from feature branches
- Generate PR descriptions from design/plan/validation artifacts
- Clean up worktrees and feature state after merge
- Archive completed feature state

## What This Skill CANNOT Do
- Release without passing validation
- Push directly to main
- Skip PR review process
- Delete feature branch before merge confirmation

## Instructions

### Phase 0: PRIME

1. Verify feature state is `release` and `validate` is completed.
2. Load all artifacts: design, plan, implementation summary, validation report.
3. Check gate: `python3 scripts/feature-state.py gate FEATURE release.merge-strategy`

**Gate**: All artifacts loaded. Validation passed. Proceed.

### Phase 1: EXECUTE (Release)

**Step 1: Generate PR Content**

From the accumulated artifacts, generate:

```markdown
## Summary
[From design document problem statement]

## Changes
[From implementation artifact — what was built]

## Testing
[From validation report — what was verified]

## Design Decision
[From design document — why this approach]
```

**Step 2: Create PR**

Use our existing pr-pipeline patterns:
1. Ensure feature branch is pushed
2. Create PR via `gh pr create`
3. Link to design decisions

**Step 3: Post-Merge Cleanup** (after PR is merged)

1. Clean up worktree:
   ```bash
   python3 scripts/feature-state.py worktree FEATURE cleanup
   ```

2. Archive feature state:
   ```bash
   python3 scripts/feature-state.py complete FEATURE
   ```

3. Update L0 (remove feature from active list).

**Gate**: PR created/merged. Cleanup complete.

### Phase 2: VALIDATE

- [ ] PR was created successfully
- [ ] Feature branch exists on remote
- [ ] PR description includes design context

### Phase 3: CHECKPOINT

1. Save release artifact:
   ```bash
   echo "RELEASE_NOTES" | python3 scripts/feature-state.py checkpoint FEATURE release
   ```

2. **Record learnings** — final pass, capture insights from the full lifecycle:
   ```bash
   python3 scripts/learning-db.py record TOPIC KEY "VALUE" --category design
   ```
   Focus on: architectural decisions, workflow improvements, agent performance, patterns to reuse.

3. Report completion:
   ```
   Feature [NAME] released successfully.
   - Design → Plan → Implement → Validate → Release: complete
   - PR: [URL]
   - Retro findings: [N] recorded, [M] promoted to context
   ```

## References

- [PR Pipeline](../pr-pipeline/SKILL.md)
- [Git Commit Flow](../git-commit-flow/SKILL.md)
- [Retro Loop](../shared-patterns/retro-loop.md)
- [State Conventions](../_feature-shared/state-conventions.md)
