# Feature State Conventions

## Directory Structure

```
.feature/
├── FEATURE.md                        # L0: System overview (always loaded)
├── state/
│   ├── <feature-name>.json           # Active feature state
│   ├── design/
│   │   └── YYYY-MM-DD-<feature>.md   # Design doc artifact
│   ├── plan/
│   │   └── YYYY-MM-DD-<feature>.md   # Plan artifact
│   ├── implement/
│   │   └── YYYY-MM-DD-<feature>.md   # Implementation log
│   ├── validate/
│   │   └── YYYY-MM-DD-<feature>.md   # Validation report
│   ├── release/
│   │   └── YYYY-MM-DD-<feature>.md   # Release notes
│   ├── completed/                    # Archived feature states
│   └── abandoned/                    # Abandoned feature states
├── context/                          # L1/L2: What we know
│   ├── DESIGN.md                     # L1 design summary
│   ├── design/                       # L2 design details
│   │   ├── architecture.md
│   │   └── conventions.md
│   ├── PLAN.md                       # L1 plan summary
│   ├── plan/
│   ├── IMPLEMENT.md
│   ├── implement/
│   ├── VALIDATE.md
│   └── validate/
├── meta/                             # L1/L2: How we work
│   ├── design/
│   │   └── process.md                # L3 records (retro output)
│   ├── plan/
│   └── implement/
└── worktrees/                        # Git worktree directories
    └── <feature-name>/
```

## State Management Commands

All state operations go through the deterministic CLI:

```bash
# Initialize
python3 ~/.claude/scripts/feature-state.py init "my feature"

# Status
python3 ~/.claude/scripts/feature-state.py status
python3 ~/.claude/scripts/feature-state.py status my-feature

# Phase lifecycle
python3 ~/.claude/scripts/feature-state.py checkpoint my-feature design
python3 ~/.claude/scripts/feature-state.py advance my-feature

# Gates
python3 ~/.claude/scripts/feature-state.py gate my-feature design.approach-selection

# Retro
python3 ~/.claude/scripts/feature-state.py retro-record my-feature error-handling "always wrap with context" --confidence medium
python3 ~/.claude/scripts/feature-state.py retro-promote my-feature error-handling

# Context
python3 ~/.claude/scripts/feature-state.py context-read my-feature L0
python3 ~/.claude/scripts/feature-state.py context-read my-feature L1 --phase design

# Worktrees
python3 ~/.claude/scripts/feature-state.py worktree my-feature create
python3 ~/.claude/scripts/feature-state.py worktree my-feature path

# Lifecycle
python3 ~/.claude/scripts/feature-state.py complete my-feature
python3 ~/.claude/scripts/feature-state.py abandon my-feature --reason "superseded"
```

## Context Loading Rules

| Level | When Loaded | Content |
|-------|-------------|---------|
| L0 | Always (auto-loaded) | ~10 lines: feature list, phase map |
| L1 | At phase prime | ~100 lines per phase: summary + pointers |
| L2 | On-demand | Variable: full detail for specific topic |
| L3 | Rarely | Raw artifacts, retro records |

## Write Protection

| Phase Code | Can Write To | Cannot Write To |
|------------|-------------|-----------------|
| Design/Plan/Implement/Validate | `state/<phase>/` only | `context/`, `meta/` |
| Retro agents | `meta/<phase>/` (L3), promote to `context/` (L2/L1) | Direct L0 edits |
| Release | `state/release/`, L0 update | N/A |

## Feature Naming

- Input: "Add user authentication"
- Slug: `add-user-authentication`
- Branch: `feature/add-user-authentication`
- Worktree: `.feature/worktrees/add-user-authentication/`
