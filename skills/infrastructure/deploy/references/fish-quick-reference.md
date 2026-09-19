# Fish Shell Quick Reference

## Variable Scoping

### Scope Flags
```fish
set -l VAR value    # Local — current block only
set -f VAR value    # Function — visible in entire function (not just current block)
set -g VAR value    # Global — current session
set -U VAR value    # Universal — persists across sessions (stored in fish_variables)
set -x VAR value    # Export — visible to child processes
```

### Common Combinations
```fish
set -gx VAR value   # Global + Export (typical for env vars in conf.d/)
set -Ux VAR value   # Universal + Export (persist + export)
set -lx VAR value   # Local + Export (temporary env for child process)
```

### Scope Guidelines

| Scope | Flag | Use For |
|-------|------|---------|
| Local | `-l` | Loop variables, temporary values in functions |
| Function | `-f` | Variables shared across blocks within one function |
| Global | `-g` | Session-specific settings that shouldn't persist |
| Universal | `-U` | User preferences that should survive restarts |
| Export | `-x` | Environment variables needed by child processes |

### Scope Examples
```fish
# Local: loop and temp variables
for file in *.txt
    set -l basename (basename $file .txt)
    echo $basename
end

# Global: session settings
set -g current_project "my-app"

# Universal: permanent preferences
set -U fish_greeting ""  # Disable greeting permanently

# Global + Export: env vars for tools
set -gx GOPATH ~/go
set -gx EDITOR nvim
```

## Special Variables

```fish
$argv       # Function/script arguments (list)
$status     # Exit status of last command
$pipestatus # Exit statuses of all pipe components (list)
$fish_pid   # PID of current Fish process
$USER       # Current user
$HOME       # Home directory
$PWD        # Current working directory
$_          # Last argument of previous command
$SHLVL      # Shell nesting level
$CMD_DURATION  # Duration of last command in milliseconds
```

## PATH Management

```fish
# Recommended: fish_add_path (handles deduplication)
fish_add_path ~/.local/bin              # Prepend, persists via fish_user_paths
fish_add_path --prepend ~/.cargo/bin    # Explicit prepend
fish_add_path --append ~/custom/bin     # Append instead
fish_add_path --move ~/go/bin           # Move existing entry to front
fish_add_path -P ~/.local/bin           # Session only (modifies PATH, not fish_user_paths)

# Manual: direct list manipulation (session only)
set -gx PATH ~/custom/bin $PATH         # Prepend
set -gx PATH $PATH ~/custom/bin         # Append

# WRONG: colon-separated (Fish PATH is a list)
# set PATH "$PATH:/new/path"            # Creates single malformed element
```

## Functions

```fish
# Define (or place in ~/.config/fish/functions/name.fish)
function name --description "what it does"
    # body
end

# Interactive editing
funced name      # Edit function in $EDITOR
funcsave name    # Save function to ~/.config/fish/functions/name.fish

# Inspection
functions              # List all functions
functions name         # Show function definition
type -q name           # Check if function/command exists (silent)
```

## Abbreviations

```fish
# Add (interactive only — always guard with status is-interactive)
abbr -a short "long command"

# Remove
abbr -e short

# List all
abbr

# Example setup in conf.d/
if status is-interactive
    abbr -a g git
    abbr -a ga "git add"
    abbr -a gc "git commit"
    abbr -a gp "git push"
    abbr -a gst "git status"
end
```

## Testing and Conditionals

```fish
# File tests
test -f file       # File exists and is regular file
test -d dir        # Directory exists
test -e path       # Path exists (any type)
test -r file       # Readable
test -w file       # Writable
test -x file       # Executable
test -s file       # Exists and non-empty

# String tests
test -z "$var"     # String is empty
test -n "$var"     # String is not empty
test "$a" = "$b"   # String equality (single =)
test "$a" != "$b"  # String inequality

# Numeric tests
test $n -eq 5      # Equal
test $n -ne 5      # Not equal
test $n -gt 5      # Greater than
test $n -ge 5      # Greater or equal
test $n -lt 5      # Less than
test $n -le 5      # Less or equal

# Combining
test -f file -a -r file   # AND
test -f file -o -d file   # OR
not test -f file           # NOT
```

## Control Flow

```fish
# If/else
if test -f config.json
    echo "exists"
else if test -d config
    echo "is directory"
else
    echo "not found"
end

# For loop
for file in *.fish
    echo "Processing $file"
end

# While loop
while read -l line
    echo "Line: $line"
end < file.txt

# Numeric loop
for i in (seq 1 10)
    echo "Number: $i"
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

# Command chaining (both styles, Fish 3.0+)
mkdir build && cd build && cmake ..
mkdir build; and cd build; and cmake ..
test -d build || mkdir build
test -d build; or mkdir build
```

## Debugging and Troubleshooting

```fish
# Syntax check without executing
fish -n script.fish

# Debug categories
fish --print-debug-categories
fish --debug='*config*' --debug-output=/tmp/fish-debug.log

# Clean environment test
fish --no-config

# Inspect variable scope and value
set --show VAR

# Check if interactive or login
status is-interactive; and echo "interactive"
status is-login; and echo "login"
```

## Common Troubleshooting

| Problem | Cause | Solution |
|---------|-------|---------|
| "Unknown command" for new function | Filename/function name mismatch | `functions/foo.fish` must contain `function foo` |
| PATH changes not persisting | Used `set -gx PATH` | Use `fish_add_path` (writes to `fish_user_paths`) |
| Abbreviations not working in scripts | Interactive-only by design | Use functions instead |
| Env var not visible to subprocess | Missing `-x` flag | Use `set -gx VAR value` |
| Universal variable stale | `fish_variables` file conflict | `set -e VAR` then `set -U VAR value` |
