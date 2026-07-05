# Fish Shell Configuration Patterns

> **Scope**: Fish-native patterns for variable assignment, PATH management, conditionals, and tool integration. Covers the correct way to configure Fish 3.0+ (including Fish 4.0 Rust rewrite, which has identical syntax).
> **Version range**: Fish 3.0+
> **Generated**: 2026-04-17

---

## Overview

Fish configuration errors rarely throw loud errors — they silently produce wrong behavior: PATH entries that vanish after restart, abbreviations that expand in the terminal but break scripts, environment variables invisible to child processes. The patterns below show the Fish-native approach for each common task, with detection commands to find violations in existing configs.

---

## Pattern Catalog

### Use Fish-Native Variable Assignment

Assign variables with `set` and the appropriate scope flag. Use `-gx` for environment variables (global + exported) and `-g` for shell-internal variables.

```fish
set -gx GOPATH ~/go
set -g MY_VAR hello
```

**Why this matters**: Fish has never supported `VAR=value` syntax. That form is a parse error that causes the entire conf.d file to fail to load — all subsequent lines in that file are skipped.

**Detection**:
```bash
grep -rn '^[A-Z_a-z]*=[^=]' --include="*.fish" ~/.config/fish/
```

---

### Use `set -gx` Instead of `export`

Set environment variables with `set -gx VAR value`. For PATH additions, use `fish_add_path`.

```fish
fish_add_path ~/.local/bin
set -gx EDITOR nvim
```

**Why this matters**: `export` is not a Fish builtin for variable assignment. The syntax `export VAR=value` is a parse error. Even `export EDITOR nvim` (space-separated) calls the external `export` binary, sets nothing in Fish scope, and is immediately discarded.

**Detection**:
```bash
grep -rn 'export ' --include="*.fish" ~/.config/fish/
```

---

### Use List Syntax for PATH Management

Add PATH entries with `fish_add_path` (preferred) or list-style `set`. Never concatenate with colons — Fish PATH is a list, not a colon-separated string.

```fish
fish_add_path ~/.local/bin        # Prepend, deduplicates, persists
fish_add_path --append ~/bin      # Append to end
set -gx PATH ~/.local/bin $PATH   # Session-only prepend (list syntax, not string)
```

**Why this matters**: String-concatenating with colons creates a single element containing the literal colon — e.g., `"/home/user/.local/bin:/usr/bin"` becomes one list entry, not two PATH components. Commands in the new directory become unfindable.

**Detection**:
```bash
grep -rn 'PATH.*:.*PATH\|"\$PATH:' --include="*.fish" ~/.config/fish/
```

---

### Guard Abbreviations With `status is-interactive`

Wrap `abbr` calls in an interactive check. Abbreviations are interactive-only — they never expand in scripts, CI, or `fish -c "..."` invocations.

```fish
# ~/.config/fish/conf.d/20-abbreviations.fish
if status is-interactive
    abbr -a g git
    abbr -a gst "git status"
    abbr -a gc "git commit"
end
```

**Why this matters**: When Fish sources conf.d/ in non-interactive mode (scripts, CI, cron), `abbr -a` emits a warning and is a no-op. Logic depending on abbreviation expansion in .fish scripts will silently fail.

**Detection**:
```bash
grep -rn '^abbr ' --include="*.fish" ~/.config/fish/conf.d/
```

---

### Use the `test` Builtin for Conditionals

Write conditionals with `test` or its equivalent forms. Fish does not support `[[` (Bash/Zsh construct) and `[ ]` calls an external binary with different behavior.

```fish
if test -f ~/.config/fish/local.fish
    source ~/.config/fish/local.fish
end

if test -z "$TMUX"
    echo "not in tmux"
end
```

**Why this matters**: `[[` is not recognized by Fish and causes a parse error. `[ ]` calls the external `/bin/[` binary which has slightly different behavior from the Fish `test` builtin and incurs a fork/exec overhead.

**Detection**:
```bash
grep -rn '\[\[' --include="*.fish" ~/.config/fish/
grep -rn 'if \[' --include="*.fish" ~/.config/fish/
```

---

### Match Function Names to Filenames

When defining autoloaded functions, the function name inside the file must exactly match the filename (without `.fish` extension). Fish autoloads functions by filename lookup.

```fish
# ~/.config/fish/functions/mkcd.fish — function name must match filename
function mkcd --description "Create directory and cd into it"
    mkdir -p $argv[1]
    and cd $argv[1]
end
```

**Why this matters**: When `mkcd` is called, Fish looks for `functions/mkcd.fish`. If that file defines `function make_directory_and_cd` instead, calling `mkcd` fails with "Unknown command: mkcd". The file loads but the desired name never registers.

**Detection**:
```bash
for f in ~/.config/fish/functions/*.fish; do
    name=$(basename "$f" .fish)
    grep -qL "function $name" "$f" && echo "MISMATCH: $f"
done
```

---

### Guard Tool Integrations With `type -q`

Wrap every external tool initialization in a `type -q` check. This prevents "command not found" errors on machines where the tool is not installed.

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

**Why this matters**: If the tool is not installed, the bare init command fails with "command not found: starship". This error may stop further conf.d/ processing and produces error output for every new shell opened on machines without that tool.

**Detection**:
```bash
grep -rn 'init fish | source\|hook fish | source' --include="*.fish" ~/.config/fish/conf.d/
rg '(starship|direnv|fnm|zoxide|mise|pyenv) (init|hook)' --type-add 'fish:*.fish' --type fish ~/.config/fish/conf.d/
```

---

### Use `-gx` Instead of `-U` for Environment Variables in conf.d/

Set environment variables in conf.d/ files with `set -gx` (global exported), not `set -U` (universal). Universal variables are for interactive user preferences set from the command line, not for deployed configuration.

```fish
# Use -gx for environment variables in conf.d/ files
set -gx GOPATH ~/go
set -gx EDITOR nvim
set -gx JAVA_HOME /usr/lib/jvm/java-17-openjdk
```

**Why this matters**: Universal variables persist in `fish_variables` across all sessions. Setting them in conf.d/ re-sets them on every shell start — harmless for idempotent values but causes subtle bugs when the value changes (e.g., different JAVA_HOME on different machines sharing dotfiles).

**Detection**:
```bash
grep -rn 'set -U\|set --universal' --include="*.fish" ~/.config/fish/conf.d/
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
