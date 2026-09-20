# Quick tracking contract

Load only when recording a standard quick task.

If absent, initialize root `STATE.md`:

```markdown
# Task State

## Quick Tasks

| Date | ID | Description | Commit | Branch | Tier | Status |
|---|---|---|---|---|---|---|
```

Append exactly one row:

```markdown
| YYYY-MM-DD | <task-id> | <description> | <short-hash or skipped (--no-commit)> | <branch> | <quick or trivial->quick> | done |
```

The commit shape is defined by the entrypoint; this reference owns only the persistent table schema.
