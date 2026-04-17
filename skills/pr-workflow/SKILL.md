---
name: pr-workflow
description: |
  Pull request lifecycle: commit, codex review, sync, review, fix, status,
  cleanup, and PR mining. Use when user wants to commit changes, get a
  second-opinion code review from Codex, push changes, create a PR, check PR
  status, fix review comments, clean up branches after merge, or mine tribal
  knowledge from PR reviews. Use for "commit my changes", "codex review",
  "push my changes", "create a PR", "pr status", "fix PR comments",
  "clean up branches", "mine PRs", or "address feedback".
user-invocable: true
allowed-tools:
  - Bash
  - Read
  - Write
  - Edit
  - Grep
  - Glob
  - Task
  - Skill
  - AskUserQuestion
routing:
  force_route: true
  triggers:
    - "push changes"
    - "push my changes"
    - "push to GitHub"
    - "push to remote"
    - "create PR"
    - "sync to GitHub"
    - "PR status"
    - "branch status"
    - "merge readiness"
    - "fix PR comments"
    - "resolve PR feedback"
    - "pr-fix"
    - "cleanup branches"
    - "clean up branches"
    - "merged branches"
    - "delete merged branch"
    - "prune branches"
    - "mine PRs"
    - "extract review comments"
    - "tribal knowledge"
    - "process PR feedback"
    - "address review comments"
    - "submit PR"
    - "create pull request"
    - "send for review"
    - "open PR"
    - "generate branch name"
    - "validate branch name"
    - "name branch"
    - "branch convention"
    - "git branch name"
    - "check CI"
    - "CI status"
    - "actions status"
    - "did CI pass"
    - "build status"
    - "CI passed"
    - "stage and commit"
    - "commit changes"
    - "commit these"
    - "commit my changes"
    - "commit my files"
    - "codex review"
    - "second opinion"
    - "code review codex"
    - "gpt review"
    - "cross-model review"
  category: git-workflow
---

# PR Workflow Skill

Umbrella skill for the entire pull request lifecycle. Routes to the correct reference based on the PR task requested.

## Routing

Detect the user's intent and load the appropriate reference file:

| Intent | Trigger phrases | Reference |
|--------|----------------|-----------|
| **Sync** (default) | "push", "create PR", "sync", "ship this" | `${CLAUDE_SKILL_DIR}/references/sync.md` |
| **Pipeline** | "submit PR", "full PR", "end-to-end PR", "open PR" | `${CLAUDE_SKILL_DIR}/references/pipeline.md` |
| **Fix** | "fix PR comments", "address review", "pr-fix", "resolve feedback" | `${CLAUDE_SKILL_DIR}/references/fix.md` |
| **Status** | "pr status", "branch status", "is my PR ready", "check CI" | `${CLAUDE_SKILL_DIR}/references/status.md` |
| **Cleanup** | "clean up branches", "delete merged branch", "prune" | `${CLAUDE_SKILL_DIR}/references/cleanup.md` |
| **Feedback** | "process PR feedback", "address reviews", "what did reviewers say" | `${CLAUDE_SKILL_DIR}/references/feedback.md` |
| **Miner** | "mine PRs", "extract review comments", "tribal knowledge", "reviewer patterns" | `${CLAUDE_SKILL_DIR}/references/miner.md` |
| **Branch name** | "generate branch name", "validate branch name", "name branch", "branch convention", "git branch name" | `${CLAUDE_SKILL_DIR}/references/branch-name.md` |
| **CI check** | "check CI", "CI status", "actions status", "did CI pass", "build status", "CI passed" | `${CLAUDE_SKILL_DIR}/references/ci-check.md` |
| **Commit** | "commit changes", "stage and commit", "commit my changes", "commit my files", "commit these" | `${CLAUDE_SKILL_DIR}/references/commit.md` |
| **Codex review** | "codex review", "second opinion", "code review codex", "gpt review", "cross-model review" | `${CLAUDE_SKILL_DIR}/references/codex-review.md` |

**Default action**: When invoked with no arguments or ambiguous intent, load `sync.md` (the most common PR use case).

## Instructions

1. Identify the user's PR task from their message
2. Load the matching reference file from the table above
3. Follow the instructions in that reference file exactly
