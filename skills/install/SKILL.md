---
name: install
description: Verify Claude Code Toolkit installation, diagnose issues, and guide new users through first-time setup
version: 1.0.0
user-invocable: true
allowed-tools:
  - Read
  - Bash
  - Glob
  - Grep
  - Write
  - Edit
  - Agent
---

# /install — Setup & Health Check

Verify your Claude Code Toolkit installation, diagnose issues, and get oriented.

## When to Use

- After cloning the repo and running `install.sh`
- When something seems broken (hooks not firing, missing commands)
- First time using the toolkit — to see what's available
- After a `git pull` to verify nothing broke

## Instructions

### Phase 1: DIAGNOSE

**Goal**: Run deterministic health checks and report results.

**Step 1: Run install-doctor.py**

```bash
python3 scripts/install-doctor.py check
```

If the script is not found at `scripts/install-doctor.py`, try `~/.claude/scripts/install-doctor.py`.

**Step 2: Interpret results**

| Result | Action |
|--------|--------|
| All checks pass | Skip to Phase 3 (Inventory) |
| `~/.claude` missing | Guide user to run `install.sh` — go to Phase 2 |
| Components missing | Guide user to run `install.sh` — go to Phase 2 |
| Hooks not configured | Guide user to run `install.sh` — go to Phase 2 |
| Broken symlinks | Symlink targets moved. Re-run `install.sh --symlink --force` |
| Python deps missing | Run `pip install -r requirements.txt` |
| Permissions wrong | Run `chmod 755` on affected files |

**Step 3: Display results clearly**

Show the check output to the user with a clear pass/fail summary. Use the raw script output — do not paraphrase or reformat excessively.

**Gate**: Health check complete. If issues found, proceed to Phase 2. If clean, skip to Phase 3.

### Phase 2: FIX (only if issues found)

**Goal**: Guide the user through fixing detected issues.

**Important**: This phase is interactive. Show the user what needs fixing and let them choose.

**Step 1: Determine if install.sh needs to run**

If `~/.claude` is missing or components are not installed, the user needs to run install.sh. Tell them:

```
The toolkit hasn't been installed yet. Run this from the repo directory:

  ./install.sh --symlink     # recommended: updates with git pull
  ./install.sh --dry-run     # preview first
```

Wait for the user to confirm they've run it, then re-run the health check.

**Step 2: Fix individual issues**

For fixable issues (permissions, missing deps), offer to fix them:

```bash
# Fix permissions
find ~/.claude/hooks -name "*.py" -exec chmod 755 {} \;
find ~/.claude/scripts -name "*.py" -exec chmod 755 {} \;

# Install Python deps
pip install PyYAML
```

Only run fixes the user approves.

**Step 3: Re-check**

After fixes, re-run:
```bash
python3 scripts/install-doctor.py check
```

**Gate**: All checks pass. Proceed to Phase 3.

### Phase 3: INVENTORY

**Goal**: Show the user what they have installed.

**Step 1: Run inventory**

```bash
python3 scripts/install-doctor.py inventory
```

**Step 2: Display summary**

Show the component counts and highlight the key entry points:

```
Your toolkit is ready. Here's what's installed:

  Agents:   90 specialized domain experts
  Skills:   115 workflow methodologies (80 user-invocable)
  Hooks:    30 automation hooks
  Commands: 7 slash commands
  Scripts:  60 utility scripts
```

**Gate**: User sees their inventory. Proceed to Phase 4.

### Phase 4: ORIENT

**Goal**: Give the user their bearings — what to do first.

**Step 1: Show the three essential commands**

```
Getting started:

  /do [describe what you want]    — routes to the right agent + skill
  /comprehensive-review           — 20+ reviewer agents in 3 waves
  /install                        — run this again anytime to check health
```

**Step 2: Show a few practical examples**

```
Try these:

  /do debug this failing test
  /do review my Go code for quality
  /do write a blog post about [topic]
  /do create a voice profile from my writing samples
```

**Step 3: Mention the docs**

```
Documentation:
  docs/QUICKSTART.md   — 30-second overview
  docs/REFERENCE.md    — full command reference
```

**Gate**: User is oriented. Installation complete.

## Error Handling

### Error: install-doctor.py not found
The script hasn't been installed yet. Check if the user is in the repo directory. If so, run it directly from `scripts/`. If not, guide them to clone and install first.

### Error: Permission denied on install.sh
Run `chmod +x install.sh` first.

### Error: Python not found
The toolkit requires Python 3.10+. Guide the user to install Python for their platform.
