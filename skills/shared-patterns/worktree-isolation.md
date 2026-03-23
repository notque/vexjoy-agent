# Worktree Isolation Pattern

Git worktrees provide physical branch isolation. Instead of `git checkout` (which swaps files in-place), worktrees create independent copies of the repo at separate filesystem paths.

## Why Worktrees Over Branches

| Approach | Risk | Isolation |
|----------|------|-----------|
| Branch + checkout | Uncommitted changes lost on switch, accidental main work | Weak — shared working directory |
| Worktree | Separate directory per feature, main untouched | Strong — physical isolation |

## When to Use

- **Feature lifecycle**: Every feature gets a worktree (via `feature-state.py`)
- **PR work**: Agent working on PR should use worktree isolation
- **Parallel development**: Multiple features in progress simultaneously
- **Any code modification**: Default to worktree when modifying code

## Integration with Our System

### Via Feature State Script
```bash
# Create worktree for a feature
python3 ~/.claude/scripts/feature-state.py worktree my-feature create
# Returns: .feature/worktrees/my-feature/ on branch feature/my-feature

# Get worktree path
python3 ~/.claude/scripts/feature-state.py worktree my-feature path

# Cleanup after merge
python3 ~/.claude/scripts/feature-state.py worktree my-feature cleanup
```

### Via Agent Tool (isolation parameter)
```
Agent(
  prompt="...",
  isolation="worktree"  # Built-in Claude Code worktree support
)
```

### Direct Git Commands
```bash
# Create
git worktree add .worktrees/feature-name feature/feature-name

# List
git worktree list

# Remove
git worktree remove .worktrees/feature-name
```

## Directory Convention

```
project-root/
├── .feature/worktrees/     # Feature lifecycle worktrees
│   ├── feature-a/
│   └── feature-b/
├── .worktrees/             # General-purpose worktrees
│   ├── pr-fix-123/
│   └── hotfix-456/
└── (main working tree)
```

## Rules

1. **NEVER modify main working tree for feature work** — use worktree
2. **One worktree per feature** — don't share worktrees between features
3. **Cleanup after merge** — remove worktree when PR is merged
4. **Archive branch tips** — tag `archive/feature/name` before deleting branch
5. **Worktree paths in .gitignore** — add `.feature/worktrees/` and `.worktrees/`

## Anti-Patterns

| Anti-Pattern | Why Wrong | Do Instead |
|--------------|-----------|------------|
| Checkout branch in main tree | Loses uncommitted work, no isolation | Use worktree |
| Keep worktrees after merge | Disk waste, stale state | Cleanup via script |
| Share worktree between features | Contamination | One worktree per feature |
| Skip worktree for "quick fix" | Quick fixes become big changes | Always isolate |
