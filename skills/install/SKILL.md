---
name: install
description: "Verify VexJoy Agent installation, diagnose issues, and guide first-time setup."
user-invocable: true
allowed-tools:
  - Read
  - Bash
  - Glob
  - Grep
  - Write
  - Edit
  - Agent
routing:
  force_route: true
  triggers:
    - "install toolkit"
    - "verify installation"
    - "health check toolkit"
    - "setup toolkit"
    - "diagnose setup"
    - "toolkit health"
  category: meta-tooling
---

# /install — Setup & Health Check

Verify installation, diagnose issues, get oriented. Use after cloning + running `install.sh`, when something seems broken, for first-time orientation, or after `git pull`.

## Instructions

### Phase 1: DIAGNOSE

**Step 1: Run install-doctor.py**

```bash
python3 ~/.claude/scripts/install-doctor.py check
```

If not found at `scripts/install-doctor.py`, try `~/.claude/scripts/install-doctor.py`.

**Step 2: Interpret results**

| Result | Action |
|--------|--------|
| All checks pass | Skip to Phase 3 (Inventory) |
| `~/.claude` missing | Guide user to run `install.sh` — Phase 2 |
| Components missing | Guide user to run `install.sh` — Phase 2 |
| Hooks not configured | Guide user to run `install.sh` — Phase 2 |
| Broken symlinks | Re-run `install.sh --symlink --force` |
| Python deps missing | `pip install -r requirements.txt` from repo directory |
| Permissions wrong | `chmod 755` on affected files |

**Step 3: Display results** — show raw script output without paraphrasing (it already formats diagnostics for readability).

**Gate**: Health check complete. If issues, proceed to Phase 2. If clean, skip to Phase 3.

### Phase 2: FIX (only if issues found)

**Step 1: Guide install.sh if needed**

```
The toolkit hasn't been installed yet. Run this from the repo directory:

  ./install.sh --symlink     # recommended: updates with git pull
  ./install.sh --dry-run     # preview first
```

Wait for user confirmation, then re-run health check. Always show what needs fixing and let the user choose.

**Step 2: Fix individual issues** (only with user approval):

```bash
find ~/.claude/hooks -name "*.py" -exec chmod 755 {} \;
find ~/.claude/scripts -name "*.py" -exec chmod 755 {} \;
pip install -r requirements.txt
```

**Step 3: Re-check**
```bash
python3 ~/.claude/scripts/install-doctor.py check
```

**Gate**: All checks pass.

### Phase 3: INVENTORY

```bash
python3 ~/.claude/scripts/install-doctor.py inventory
```

Show actual counts from the script — never display hardcoded numbers:

```
Your toolkit is ready. Here's what's installed:

  Agents:   [N] specialized domain experts
  Skills:   [N] workflow methodologies ([N] user-invocable)
  Hooks:    [N] automation hooks
  Commands: [N] slash commands
  Scripts:  [N] utility scripts
```

**Gate**: User sees inventory.

### Phase 3.5: MCP INVENTORY

```bash
python3 ~/.claude/scripts/mcp-registry.py list
```

If not found at `scripts/mcp-registry.py`, try `~/.claude/scripts/mcp-registry.py`.

Show MCP status with checkmarks for connected, X for missing (with install commands):

```
MCP Servers:

  [✓] Chrome DevTools MCP  — Live browser debugging
      Paired skills: wordpress-live-validation
  [✓] Playwright MCP       — Automated browser testing
      Paired skills: wordpress-live-validation
  [✓] gopls MCP            — Go workspace intelligence
      Paired skills: go-patterns
  [✗] Context7 MCP         — Library documentation lookups
      Install: claude mcp add context7 -- npx @anthropic-ai/mcp-context7@latest
```

**Gate**: MCP inventory displayed.

### Phase 4: ORIENT

**Step 1: Essential commands**

```
Getting started:

  /do [describe what you want]    — routes to the right agent + skill
  /comprehensive-review           — 20+ reviewer agents in 3 waves
  /install                        — run this again anytime to check health
```

**Step 2: Practical examples**

```
Try these:

  /do debug this failing test
  /do review my Go code for quality
  /do write a blog post about [topic]
  /do create a voice profile from my writing samples
```

**Step 3: Docs**

```
Documentation:
  docs/QUICKSTART.md   — 30-second overview
  docs/REFERENCE.md    — quick reference card
```

**Gate**: User is oriented. Installation complete.

## Error Handling

### Error: install-doctor.py not found
Script not installed. Check if user is in the repo directory. If so, run from `scripts/`. If not, guide to clone and install.

### Error: Permission denied on install.sh
Run `chmod +x install.sh`.

### Error: Python not found
Toolkit requires Python 3.10+. Guide user to install for their platform.
