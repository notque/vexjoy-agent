---
name: fish-shell-config
description: |
  Fish shell configuration: config.fish, functions, abbreviations, variable
  scoping, conf.d modules, and PATH management. Use when user's $SHELL is fish,
  editing .fish files, working in ~/.config/fish/, or migrating from Bash. Use
  for "fish config", "fish function", "abbr", "conf.d", "fish_add_path", or
  "funcsave". Do NOT use for Bash/Zsh-only scripts, POSIX shell portability, or
  non-shell configuration tasks.
version: 2.0.0
user-invocable: false
allowed-tools:
  - Read
  - Write
  - Bash
  - Grep
  - Glob
  - Edit
routing:
  triggers:
    - fish
    - fish shell
    - config.fish
    - abbr
    - fish function
    - fish_config
    - fish_variables
    - funced
    - funcsave
    - ~/.config/fish
    - conf.d
    - fish abbreviation
    - .fish file
    - "#!/usr/bin/env fish"
  pairs_with: []
  force_routing: true
---

# Fish Shell Configuration Skill

## Operator Context

This skill operates as an operator for Fish shell configuration tasks, configuring Claude's behavior for correct Fish syntax and idioms. It implements **Domain Intelligence** — Fish-specific patterns that differ fundamentally from Bash/POSIX — ensuring generated shell code actually works in Fish.

### Hardcoded Behaviors (Always Apply)
- **Fish Syntax Only**: Never emit Bash syntax (`VAR=value`, `[[ ]]`, `export`, heredocs) in Fish contexts
- **Variables Are Lists**: Treat every Fish variable as a list; never use colon-separated PATH strings
- **No Word Splitting**: `$var` and `"$var"` are identical in Fish; do not add defensive quotes for word-splitting
- **`test` Over Brackets**: Use `test` builtin, never `[[ ]]` or `[ ]`
- **`set` Over Assignment**: Variable assignment is always `set VAR value`, never `VAR=value`
- **Filename = Function Name**: Autoloaded function files must match: `functions/foo.fish` contains `function foo`

### Default Behaviors (ON unless disabled)
- **Modular Config**: Place config in `conf.d/` files, keep `config.fish` minimal
- **`fish_add_path`**: Use for PATH manipulation instead of manual `set PATH`
- **Interactive Guards**: Wrap abbreviations and key bindings in `if status is-interactive`
- **`type -q` Checks**: Guard tool integrations with existence checks
- **Numeric Prefixes**: Use `00-`, `10-`, `20-` prefixes in `conf.d/` for ordering

### Optional Behaviors (OFF unless enabled)
- **Universal Variables**: Use `-U` flag for cross-session persistence
- **Bash Migration**: Convert Bash scripts to Fish syntax (see `references/bash-migration.md`)
- **Completion Authoring**: Write custom Fish completions

## What This Skill CAN Do
- Write syntactically correct Fish functions, config, and abbreviations
- Structure `~/.config/fish/` with proper modular layout
- Manage variable scoping (local, function, global, universal, export)
- Integrate tools (Starship, direnv, fzf, Homebrew, Nix) with Fish
- Migrate Bash patterns to Fish equivalents

## What This Skill CANNOT Do
- Write POSIX-compatible scripts (Fish is not POSIX)
- Fix Bash/Zsh configurations (use appropriate shell skill)
- Manage Fish plugin frameworks (Fisher, Oh My Fish) beyond basic guidance
- Debug Fish shell internals or C/Rust source code

---

## Instructions

### Phase 1: DETECT

**Goal**: Confirm Fish shell context before writing any shell code.

**Step 1: Check shell environment**
- `$SHELL` contains `fish`, or
- Target file has `.fish` extension, or
- Target directory is `~/.config/fish/`

**Step 2: Identify Fish version constraints**
- All patterns target Fish 3.0+ (supports `$()`, `&&`, `||`)
- Fish 4.0 (Rust rewrite) has no syntax changes

**Gate**: Confirmed Fish context. Proceed only when gate passes.

### Phase 2: STRUCTURE

**Goal**: Place configuration in the correct location.

**Directory layout**:
```
~/.config/fish/
├── config.fish              # Minimal — interactive-only init
├── fish_variables           # Auto-managed by Fish (never edit)
├── conf.d/                  # Auto-sourced in alphabetical order
│   ├── 00-path.fish
│   ├── 10-env.fish
│   └── 20-abbreviations.fish
├── functions/               # Autoloaded functions (one per file)
│   ├── fish_prompt.fish
│   └── mkcd.fish
└── completions/             # Custom completions
    └── mycommand.fish
```

**Decision tree**:
| What you're writing | Where it goes |
|---------------------|---------------|
| PATH additions | `conf.d/00-path.fish` |
| Environment variables | `conf.d/10-env.fish` |
| Abbreviations | `conf.d/20-abbreviations.fish` |
| Tool integrations | `conf.d/30-tools.fish` |
| Named function | `functions/<name>.fish` |
| Custom prompt | `functions/fish_prompt.fish` |
| Completions | `completions/<command>.fish` |
| One-time interactive init | `config.fish` (inside `status is-interactive`) |

**Gate**: Correct file location chosen. Proceed only when gate passes.

### Phase 3: WRITE

**Goal**: Generate syntactically correct Fish code.

**Step 1: Variables**

```fish
set -l VAR value    # Local — current block only
set -f VAR value    # Function — entire function scope
set -g VAR value    # Global — current session
set -U VAR value    # Universal — persists across sessions
set -x VAR value    # Export — visible to child processes
set -gx VAR value   # Global + Export (typical for env vars)
set -e VAR          # Erase variable
set -q VAR          # Test if set (silent, for conditionals)
```

**Step 2: PATH management**

```fish
# CORRECT: fish_add_path handles deduplication and persistence
fish_add_path ~/.local/bin
fish_add_path ~/.cargo/bin
fish_add_path -P ~/go/bin     # -P = session only, no persist

# CORRECT: Direct manipulation when needed (session only)
set -gx PATH ~/custom/bin $PATH

# WRONG: Colon-separated string — Fish PATH is a list
# set PATH "$PATH:/new/path"
```

**Step 3: Functions**

```fish
# ~/.config/fish/functions/mkcd.fish
function mkcd --description "Create directory and cd into it"
    mkdir -p $argv[1]
    and cd $argv[1]
end
```

Functions with argument parsing:
```fish
function backup --description "Create timestamped backup"
    argparse 'd/dest=' 'h/help' -- $argv
    or return

    if set -q _flag_help
        echo "Usage: backup [-d destination] file..."
        return 0
    end

    set -l dest (set -q _flag_dest; and echo $_flag_dest; or echo ".")
    for file in $argv
        set -l ts (date +%Y%m%d_%H%M%S)
        cp $file $dest/(basename $file).$ts.bak
    end
end
```

**Step 4: Abbreviations vs Functions vs Aliases**

| Use Case | Mechanism | Why |
|----------|-----------|-----|
| Simple shortcut | `abbr -a g git` | Expands in-place, visible in history |
| Needs arguments/logic | `function` in `functions/` | Full programming, works in scripts |
| Wrapping a command | `alias ll "ls -la"` | Convenience; creates function internally |

Abbreviations are **interactive-only** — they do not work in scripts.

```fish
# Always guard abbreviations
if status is-interactive
    abbr -a g git
    abbr -a ga "git add"
    abbr -a gc "git commit"
    abbr -a gst "git status"
    abbr -a dc "docker compose"
end
```

**Step 5: Conditionals and control flow**

```fish
# Conditionals — use 'test', not [[ ]]
if test -f config.json
    echo "exists"
else if test -d config
    echo "is directory"
end

# Command chaining (both styles work in Fish 3.0+)
mkdir build && cd build && cmake ..
mkdir build; and cd build; and cmake ..

# Loops
for file in *.fish
    echo "Processing $file"
end

# Switch
switch $argv[1]
    case start
        echo "Starting..."
    case stop
        echo "Stopping..."
    case "*"
        echo "Unknown: $argv[1]"
        return 1
end
```

**Step 6: Tool integrations**

Always guard with `type -q`:
```fish
# ~/.config/fish/conf.d/30-tools.fish
if type -q starship
    starship init fish | source
end

if type -q direnv
    direnv hook fish | source
end

if type -q fzf
    fzf --fish | source
end

# Homebrew (macOS)
if test -x /opt/homebrew/bin/brew
    eval (/opt/homebrew/bin/brew shellenv)
end

# Nix
if test -e /nix/var/nix/profiles/default/etc/profile.d/nix-daemon.fish
    source /nix/var/nix/profiles/default/etc/profile.d/nix-daemon.fish
end
```

**Gate**: Code uses correct Fish syntax. No Bash-isms present. Proceed only when gate passes.

### Phase 4: VERIFY

**Goal**: Confirm configuration works and is correctly structured.

**Step 1**: Syntax check — `fish -n <file>` (parse without executing)

**Step 2**: For functions — verify filename matches function name

**Step 3**: For conf.d — verify `status is-interactive` guards on interactive-only code

**Step 4**: Test in clean environment — `fish --no-config` then `source <file>`

**Gate**: All verification steps pass. Configuration is complete.

---

## Examples

### Example 1: Setting Up a New Fish Config
User says: "Set up my Fish shell config"
Actions:
1. Detect Fish context (DETECT)
2. Create modular structure in `~/.config/fish/` (STRUCTURE)
3. Write `conf.d/00-path.fish`, `conf.d/10-env.fish`, `conf.d/20-abbreviations.fish` (WRITE)
4. Syntax-check all files (VERIFY)
Result: Clean modular Fish configuration

### Example 2: Migrating a Bash Alias File
User says: "Convert my .bash_aliases to Fish"
Actions:
1. Read `.bash_aliases`, confirm Fish target (DETECT)
2. Determine which become abbreviations vs functions (STRUCTURE)
3. Write abbreviations to `conf.d/`, functions to `functions/` (WRITE)
4. Syntax-check, test in clean shell (VERIFY)
Result: Bash aliases converted to idiomatic Fish

---

## Error Handling

### Error: "Unknown command" for new function
Cause: Filename does not match function name
Solution: Ensure `functions/foo.fish` contains exactly `function foo`. Check for typos in both the filename and the function declaration.

### Error: PATH changes not persisting across sessions
Cause: Used `set -gx PATH` (session-only) instead of `fish_add_path` (writes to universal `fish_user_paths`)
Solution: Use `fish_add_path /new/path` which persists by default, or use `set -U fish_user_paths /path $fish_user_paths` explicitly.

### Error: Abbreviations not expanding in scripts
Cause: Abbreviations are interactive-only by design
Solution: Use a function instead. Move the logic from `abbr` to a file in `functions/`.

### Error: Variable not visible to child process
Cause: Missing `-x` (export) flag on `set`
Solution: Use `set -gx VAR value` to make variable visible to subprocesses. Check with `set --show VAR` to inspect current scope and export status.

---

## Anti-Patterns

### Anti-Pattern 1: Bash Assignment Syntax
**What it looks like**: `VAR=value` or `export VAR=value` in a `.fish` file
**Why wrong**: Syntax error in Fish. Fish has no inline assignment.
**Do instead**: `set VAR value` or `set -gx VAR value`

### Anti-Pattern 2: Colon-Separated PATH
**What it looks like**: `set PATH "$PATH:/new/path"`
**Why wrong**: Fish PATH is a list, not a colon-delimited string. Creates a single malformed element.
**Do instead**: `fish_add_path /new/path` or `set PATH $PATH /new/path`

### Anti-Pattern 3: Monolithic config.fish
**What it looks like**: Hundreds of lines in `config.fish` — PATH, env, aliases, functions, integrations
**Why wrong**: Slow to load, hard to maintain, impossible to selectively disable.
**Do instead**: Split into `conf.d/` modules and `functions/` autoload files.

### Anti-Pattern 4: Bracket Conditionals
**What it looks like**: `if [[ -f file ]]` or `if [ -f file ]`
**Why wrong**: `[[ ]]` is a syntax error. `[ ]` calls external `/bin/[`, slower than builtin.
**Do instead**: `if test -f file` — uses Fish's fast builtin.

### Anti-Pattern 5: Word-Split Defensive Quoting
**What it looks like**: Always quoting `"$var"` out of Bash habit
**Why wrong**: Not harmful, but misleading. Fish never word-splits; `$var` and `"$var"` are identical.
**Do instead**: Quote only when you need to prevent list expansion or preserve empty strings.

---

## References

This skill uses these shared patterns:
- [Anti-Rationalization](../shared-patterns/anti-rationalization-core.md) - Prevents shortcut rationalizations
- [Verification Checklist](../shared-patterns/verification-checklist.md) - Pre-completion checks

### Domain-Specific Anti-Rationalization

| Rationalization | Why It's Wrong | Required Action |
|-----------------|----------------|-----------------|
| "Quotes won't hurt in Fish" | Masks misunderstanding of Fish semantics | Learn Fish variable expansion rules |
| "Just put it all in config.fish" | Monolithic config is an anti-pattern | Use conf.d/ and functions/ |
| "Bash syntax is close enough" | Fish is not POSIX; Bash-isms cause errors | Use Fish-native syntax only |
| "I'll use [ ] since it works" | Calls external binary, slower than test | Use `test` builtin always |

### Reference Files
- `${CLAUDE_SKILL_DIR}/references/bash-migration.md`: Complete Bash-to-Fish syntax translation table
- `${CLAUDE_SKILL_DIR}/references/fish-quick-reference.md`: Variable scoping, special variables, and command cheatsheet
