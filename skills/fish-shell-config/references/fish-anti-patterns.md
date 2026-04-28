# Fish Shell Patterns to Fix

> **Scope**: Common fish shell configuration mistakes that cause silent failures, broken environments, or scripts that work interactively but fail in CI/cron. Does not cover fish scripting logic errors unrelated to configuration.
> **Version range**: Fish 3.0+ (Fish 4.0 Rust rewrite has identical syntax)
> **Generated**: 2026-04-17

---

## Overview

Fish configuration errors rarely throw loud errors — they silently produce wrong behavior: PATH entries that vanish after restart, abbreviations that expand in the terminal but break scripts, environment variables invisible to child processes. Detection requires grep-based auditing of `.fish` files rather than waiting for runtime failures.

---

## Pattern Catalog

### ❌ Bash-Style Variable Assignment

**Detection**:
```bash
grep -rn '^[A-Z_]*=[^=]' --include="*.fish" ~/.config/fish/
rg '^\s*[A-Z_a-z]+=[^=]' --type-add 'fish:*.fish' --type fish ~/.config/fish/
```

**What it looks like**:
```fish
# WRONG — syntax error in Fish
GOPATH=~/go
MY_VAR=hello
```

**Why wrong**: `VAR=value` is a syntax error in Fish (not silently ignored). Fish rejects it at parse time, causing the entire conf.d file to fail to load — all subsequent lines in that file are skipped.

**Fix**:
```fish
set -gx GOPATH ~/go
set -g MY_VAR hello
```

**Version note**: No version where this worked. Fish has never supported `VAR=value` assignment syntax.

---

### ❌ `export VAR=value` (Bash Export Syntax)

**Detection**:
```bash
grep -rn 'export ' --include="*.fish" ~/.config/fish/
rg 'export \w+=' --type-add 'fish:*.fish' --type fish ~/.config/fish/
```

**What it looks like**:
```fish
# WRONG — syntax error in Fish
export PATH="$PATH:~/.local/bin"
export EDITOR=nvim
```

**Why wrong**: `export` is not a Fish builtin for variable assignment. The syntax `export VAR=value` is a parse error. Even `export EDITOR nvim` (space-separated) calls the external `export` binary, sets nothing in Fish scope, and is immediately discarded.

**Fix**:
```fish
fish_add_path ~/.local/bin
set -gx EDITOR nvim
```

---

### ❌ Colon-Separated PATH Manipulation

**Detection**:
```bash
grep -rn 'PATH.*:.*PATH\|"\$PATH:' --include="*.fish" ~/.config/fish/
rg 'set.*PATH.*"\$PATH:' --type-add 'fish:*.fish' --type fish ~/.config/fish/
```

**What it looks like**:
```fish
# WRONG — creates a single malformed string element
set -gx PATH "$PATH:$HOME/.local/bin"
set -gx PATH "$HOME/.local/bin:$PATH"
```

**Why wrong**: Fish PATH is a list variable. Each element is a separate string. String-concatenating with colons creates a single element containing the literal colon — e.g., `"/home/user/.local/bin:/usr/bin"` becomes one list entry, not two PATH components. Commands in the new directory become unfindable.

**Fix**:
```fish
fish_add_path ~/.local/bin        # Prepend, deduplicates, persists
fish_add_path --append ~/bin      # Append to end
set -gx PATH ~/.local/bin $PATH   # Session-only prepend (list syntax, not string)
```

---

### ❌ Unguarded Abbreviations in conf.d/

**Detection**:
```bash
grep -rn '^abbr ' --include="*.fish" ~/.config/fish/conf.d/
rg '^abbr ' --type-add 'fish:*.fish' --type fish ~/.config/fish/conf.d/
```

**What it looks like**:
```fish
# ~/.config/fish/conf.d/20-abbreviations.fish — WRONG
abbr -a g git
abbr -a gst "git status"
```

**Why wrong**: Abbreviations are interactive-only. When Fish sources `conf.d/` in non-interactive mode (scripts, CI, cron, `fish -c "..."`), `abbr -a` emits a warning and is a no-op. More critically, they never expand in scripts regardless — so logic depending on abbreviation expansion in `.fish` scripts will silently fail.

**Fix**:
```fish
# ~/.config/fish/conf.d/20-abbreviations.fish — CORRECT
if status is-interactive
    abbr -a g git
    abbr -a gst "git status"
    abbr -a gc "git commit"
end
```

---

### ❌ Bash Double-Bracket Conditionals

**Detection**:
```bash
grep -rn '\[\[' --include="*.fish" ~/.config/fish/
grep -rn 'if \[' --include="*.fish" ~/.config/fish/
```

**What it looks like**:
```fish
# WRONG — syntax error in Fish
if [[ -f ~/.config/fish/local.fish ]]
    source ~/.config/fish/local.fish
end

if [ -z "$TMUX" ]
    echo "not in tmux"
end
```

**Why wrong**: `[[` is not recognized by Fish — it is a Bash/Zsh construct and causes a parse error. `[ ]` calls the external `/bin/[` binary which has slightly different behavior from the Fish `test` builtin and incurs a fork/exec overhead.

**Fix**:
```fish
if test -f ~/.config/fish/local.fish
    source ~/.config/fish/local.fish
end

if test -z "$TMUX"
    echo "not in tmux"
end
```

---

### ❌ Function/Filename Mismatch

**Detection**:
```bash
# Bash: find functions/ files where function name doesn't match filename
for f in ~/.config/fish/functions/*.fish; do
    name=$(basename "$f" .fish)
    grep -qL "function $name" "$f" && echo "MISMATCH: $f"
done
```

**What it looks like**:
```
# File: ~/.config/fish/functions/mkcd.fish
function make_directory_and_cd    # WRONG — name doesn't match file
    mkdir -p $argv[1]
    and cd $argv[1]
end
```

**Why wrong**: Fish autoloads functions by filename. When `mkcd` is called, Fish looks for `~/.config/fish/functions/mkcd.fish`. If that file exists but defines `function make_directory_and_cd`, calling `mkcd` fails with "Unknown command: mkcd". The file loads but the desired name never registers.

**Fix**:
```fish
# ~/.config/fish/functions/mkcd.fish — function name must match filename
function mkcd --description "Create directory and cd into it"
    mkdir -p $argv[1]
    and cd $argv[1]
end
```

---

### ❌ Tool Integration Without Availability Guard

**Detection**:
```bash
grep -rn 'init fish | source\|hook fish | source' --include="*.fish" ~/.config/fish/conf.d/
rg '(starship|direnv|fnm|zoxide|mise|pyenv) (init|hook)' --type-add 'fish:*.fish' --type fish ~/.config/fish/conf.d/
```

**What it looks like**:
```fish
# WRONG — breaks on machines where tool is not installed
starship init fish | source
direnv hook fish | source
fnm env --use-on-cd | source
```

**Why wrong**: If the tool is not installed, the command fails with "command not found: starship". This error may stop further `conf.d/` processing, producing error output for every new shell opened on machines without that tool.

**Fix**:
```fish
if type -q starship
    starship init fish | source
end

if type -q direnv
    direnv hook fish | source
end

if type -q fnm
    fnm env --use-on-cd | source
end
```

---

### ❌ Using `set -U` (Universal) in conf.d/ for Tool Paths

**Detection**:
```bash
grep -rn 'set -U\|set --universal' --include="*.fish" ~/.config/fish/conf.d/
rg 'set -U ' --type-add 'fish:*.fish' --type fish ~/.config/fish/conf.d/
```

**What it looks like**:
```fish
# ~/.config/fish/conf.d/10-env.fish — WRONG
set -U GOPATH ~/go
set -U EDITOR nvim
set -U JAVA_HOME /usr/lib/jvm/java-17-openjdk
```

**Why wrong**: Universal variables are stored in `fish_variables` and persist across all sessions. Setting them in `conf.d/` re-sets them on every shell start — harmless for idempotent values but causes subtle bugs when the value changes (e.g., different JAVA_HOME on different machines). Universal scope is for user preferences set interactively, not for environment configuration deployed via conf.d/.

**Fix**:
```fish
# Use -gx for environment variables in conf.d/ files
set -gx GOPATH ~/go
set -gx EDITOR nvim
set -gx JAVA_HOME /usr/lib/jvm/java-17-openjdk
```

---

## Error-Fix Mappings

| Error / Symptom | Root Cause | Fix |
|-----------------|------------|-----|
| `Unknown command: myfunction` | `functions/myfunction.fish` defines wrong function name | Rename function inside file to match filename exactly |
| PATH entry disappears after reboot | Used `set -gx PATH ...` (session-only) | Replace with `fish_add_path /path` |
| Abbreviation works in terminal, not in script | Abbreviations are interactive-only by design | Use a function in `functions/` instead |
| Parse error on shell start | `export VAR=value` or `VAR=value` in `.fish` file | Replace with `set -gx VAR value` |
| Garbled PATH with colons visible | `set PATH "$PATH:/new"` colon concatenation | Replace with `fish_add_path /new` |
| `[[: command not found` | Bash `[[` brackets used in Fish file | Replace with `test` builtin |
| Tool init error on every new shell | Init call without `type -q` guard | Wrap in `if type -q toolname; ... end` |
| Universal variable duplicated in PATH | `fish_user_paths` has duplicate entries | `set -U fish_user_paths (string split \n (printf "%s\n" $fish_user_paths \| sort -u))` |
| conf.d changes not taking effect | File has syntax error from Bash constructs | Run `fish -n ~/.config/fish/conf.d/myfile.fish` to check |

---

## Detection Commands Reference

```bash
# Bash-style assignment
grep -rn '^[A-Z_a-z]*=[^=]' --include="*.fish" ~/.config/fish/

# Bash export syntax
grep -rn 'export ' --include="*.fish" ~/.config/fish/

# Colon PATH manipulation
grep -rn '"\$PATH:' --include="*.fish" ~/.config/fish/

# Unguarded abbreviations
grep -rn '^abbr ' --include="*.fish" ~/.config/fish/conf.d/

# Bash bracket conditionals
grep -rn '\[\[' --include="*.fish" ~/.config/fish/

# Tool integrations without availability guard
grep -rn 'init fish | source\|hook fish | source' --include="*.fish" ~/.config/fish/conf.d/

# Universal variables set in conf.d (likely should be -gx)
grep -rn 'set -U ' --include="*.fish" ~/.config/fish/conf.d/

# Syntax check all conf.d files
for f in ~/.config/fish/conf.d/*.fish; do fish -n "$f" || echo "SYNTAX ERROR: $f"; done
```

---

## See Also

- `bash-migration.md` — Bash-to-Fish syntax translation table
- `fish-quick-reference.md` — Variable scoping, PATH management, control flow cheatsheet
- `tool-integrations.md` — Complete tool integration patterns (Go, Rust, Docker, Node.js, pyenv)
