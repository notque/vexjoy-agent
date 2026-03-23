# Retro Knowledge System

Interact with the accumulated retro knowledge store: view, audit, and fix.

## Usage

```
/retro              # Status overview (default)
/retro audit        # Check L2 files for hygiene issues
/retro list         # Display all accumulated knowledge
/retro fix          # Fix L2 hygiene issues (with confirmation)
/retro graduate     # Graduate mature knowledge into agents/skills
```

## What It Shows

```
RETRO KNOWLEDGE STATUS
======================

Knowledge Store:
  L1 summary: 19 lines
  L2 files:   1 topic files

Injection:
  Hook: installed
  Gating: language-aware (matches project file extensions)

Health:
  1 L2 files with issues (run /retro audit for details)
  0 cross-file duplicates
```

## Subcommands

### status (default)
Shows knowledge store size, injection hook health, and issue count.

### audit
Runs `python3 ~/.claude/scripts/feature-state.py retro-audit` and formats results by file with severity and hints.

### list
Displays L1 summary (always injected into agents) and L2 topic file inventory with tags, languages, and observation counts.

### fix
Runs audit, shows proposed changes (missing tags, missing languages), confirms with user, then applies fixes.

### graduate
AI-driven evaluation of mature L2 observations for embedding into specific agents/skills. Runs `retro-candidates` to identify HIGH confidence entries with 3+ observations, evaluates each for prescriptive readiness, drafts modifications to the target agent/skill, and applies after user approval.

## Instructions for Claude

When the user invokes `/retro`, load and follow the skill at `skills/retro/SKILL.md`.

Parse the argument to select the subcommand:
- No argument or "status" → run status subcommand
- "audit" → run audit subcommand
- "list" → run list subcommand
- "fix" → run fix subcommand
- "graduate" → run graduate subcommand

All retro state operations go through `python3 ~/.claude/scripts/feature-state.py` — never parse retro files manually.

## Related

- `scripts/feature-state.py retro-record` — Record observations during feature work
- `scripts/feature-state.py retro-promote` — Promote observations L3→L2
- `hooks/retro-knowledge-injector.py` — Auto-injects knowledge into agent context
- `skills/shared-patterns/retro-loop.md` — Full retro system documentation
