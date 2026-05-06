# Local-Only Constraint

Injected by /do when the user signals local-only work. Prevents premature git operations.

## Rules

1. **No git push.** Work stays on the local machine.
2. **No PR creation.** No `gh pr create`, no PR URLs.
3. **No git commit** unless the user explicitly asks for one.
4. **No branch creation.** Stay on the current branch.
5. **No deploy, publish, or upload** to any remote service.

## What IS allowed

- All file reads, writes, and edits
- Running tests, linters, build tools
- `git status`, `git diff`, `git log` (read-only git)
- Creating local directories and files
- Running scripts and validation

## Detection signals

The router injects this pattern when the user says any of:
- "local only", "keep it local", "locally", "no push", "no PR"
- "don't push", "don't commit", "don't create a PR"
- "work locally", "stay local", "draft mode"

## Injection template

Prepend to agent prompts:
```
**LOCAL-ONLY MODE.** Do not push, commit, create PRs, or deploy. All work stays on disk. Read-only git is fine. The user will decide when to commit.
```
