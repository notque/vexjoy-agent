# Zsh Quick Reference

> **Scope**: Variable scoping, parameter expansion flags, special variables, fpath management, and control flow. Covers Zsh-specific features not in POSIX sh or Bash.
> **Version range**: Zsh 5.8+
> **Generated**: 2026-05-26

---

## Variable Scoping

### Scope Modifiers

```zsh
local var="value"          # Local to current function (preferred for readability)
typeset var="value"        # Same as local inside functions; global at top level
typeset -g var="value"     # Force global even inside function
typeset -x var="value"     # Export (same as export)
typeset -r var="value"     # Read-only
typeset -i var=0           # Integer (arithmetic auto-applied)
typeset -l var="VALUE"     # Always stored lowercase
typeset -u var="value"     # Always stored uppercase
typeset -a arr             # Indexed array
typeset -A assoc           # Associative array
typeset -U arr             # Unique elements (dedup on assignment)
```

### Scope Guidelines

| Scope | Modifier | Use For |
|-------|----------|---------|
| Function-local | `local` / `typeset` | Loop variables, temporary values in functions |
| Global | `typeset -g` or top-level | Session-wide settings |
| Exported | `typeset -x` / `export` | Variables visible to child processes |
| Read-only | `typeset -r` | Constants |
| Unique array | `typeset -U` | PATH, fpath — auto-deduplicates |

### Scope Examples

```zsh
# Function-local variable
my_function() {
  local result=""
  typeset -i count=0
  # $result and $count are destroyed on function return
}

# Global exported variable
export EDITOR=nvim
# or equivalently:
typeset -x EDITOR=nvim

# PATH deduplication (set once at top of .zshenv)
typeset -U path
path=(~/bin ~/.local/bin $path)

# Integer arithmetic
typeset -i total=0
total+=5    # total is now 5 (not "05")
```

---

## Parameter Expansion Flags

Zsh parameter expansion flags go inside `${(flags)var}` — load them lazily; full list in `man zshexpn`.

### String Operations

```zsh
${(U)var}           # Uppercase all characters
${(L)var}           # Lowercase all characters
${(C)var}           # Capitalize first letter of each word
${(q)var}           # Shell-quote the value (safe for eval)
${(Q)var}           # Remove one level of quoting
${(l:N::c:)var}     # Left-pad to width N with char c
${(r:N::c:)var}     # Right-pad to width N with char c
${#var}             # Length of string (or array element count)
```

### Splitting and Joining

```zsh
${(f)var}           # Split on newlines → array
${(s:,:)var}        # Split on comma → array  (any delimiter in :delim:)
${(z)var}           # Split as shell words (respecting quotes)
${(j: :)array}      # Join array with space separator
${(j:\n:)array}     # Join array with newlines
${(F)array}         # Join array with newlines (shorthand for ${(j:\n:)})
```

### Array Operations

```zsh
${(u)array}         # Unique elements (deduplicated)
${(o)array}         # Sort ascending
${(O)array}         # Sort descending
${(i)array}         # Sort case-insensitively
${(n)array}         # Sort numerically
${(r)array}         # Reverse order
${(k)assoc}         # Keys of associative array
${(v)assoc}         # Values of associative array
${(kv)assoc}        # Interleaved key-value pairs
```

### Practical Examples

```zsh
# Split a colon-separated PATH into array
path_parts=("${(s.:.)PATH}")

# Split command output into lines array
lines=("${(f)$(cat file.txt)}")

# Join array back to string
joined="${(j:,:)myarray}"

# Get unique items from array
typeset -U myarray
# or without typeset:
unique=("${(u)myarray[@]}")

# Lowercase a string
lower="${(L)MY_UPPER_VAR}"

# Shell-safe quoting for dynamic eval
safe="${(q)user_input}"

# Split on newlines and iterate
while IFS= read -r line; do
  # ...
done <<< "${(F)myarray}"
```

---

## fpath Management

`fpath` is to functions what `PATH` is to executables. Zsh searches `fpath` for autoloaded functions and completion scripts.

```zsh
# ~/.zshrc — extend fpath before compinit

# Dedup fpath (same as path)
typeset -U fpath

# Add custom completion directory
fpath=(~/.zsh/completions $fpath)

# Add custom functions directory
fpath=(~/.zsh/functions $fpath)

# Homebrew completions (macOS)
if [[ -d /opt/homebrew/share/zsh/site-functions ]]; then
  fpath=(/opt/homebrew/share/zsh/site-functions $fpath)
fi

# Autoload a function from fpath (lazy — loads on first call)
autoload -Uz my_function

# Autoload all functions in a directory
for f in ~/.zsh/functions/*; do
  autoload -Uz "${f:t}"    # :t = tail (basename)
done
```

**Completion script naming**: Completion functions must be named `_command` (underscore prefix). Place `_mycommand` in a `fpath` directory, then `compinit` finds it automatically — no explicit `autoload` needed.

---

## Special Variables

```zsh
$?          # Exit status of last command
$!          # PID of last background process
$$          # PID of current shell
$0          # Name of current script or shell
$SHELL      # Path to current shell binary
$ZSH_VERSION # Zsh version string (e.g., "5.9")
$SHLVL      # Shell nesting level (increments per subshell)

# History
$HISTFILE   # Path to history file (default: ~/.zsh_history)
$HISTSIZE   # Max commands in memory
$SAVEHIST   # Max commands saved to HISTFILE

# Prompt
$PROMPT     # Primary prompt (same as $PS1)
$PS1        # Primary prompt (POSIX compatible)
$RPROMPT    # Right-side prompt (Zsh-only)
$PS2        # Continuation prompt (default: "> ")
$PS3        # Select menu prompt
$PS4        # Xtrace prefix (default: "+ ")

# Completion/match state
$REPLY      # Default variable for read builtin; also set by some builtins
$reply      # Array version of $REPLY (lowercase)
$MATCH      # String matched by last regex (with =~ or pcre_match)
$match      # Array of capture groups from last regex match
$MBEGIN     # Start position of last regex match
$MEND       # End position of last regex match
$compstate  # Associative array of completion state (in completion functions)

# Directory
$PWD        # Current directory
$OLDPWD     # Previous directory (used by cd -)
$CDPATH     # Colon-separated list of dirs to search for cd targets

# Zsh-specific
$ZSH_ARGZERO    # $0 equivalent but not modified by function calls
$LINENO         # Current line number in script
$COLUMNS        # Terminal width
$LINES          # Terminal height
```

---

## Control Flow Cheatsheet

```zsh
# If/elif/else
if [[ condition ]]; then
    action
elif [[ other ]]; then
    other_action
else
    fallback
fi

# Common conditions
[[ -f file ]]       # File exists and is regular file
[[ -d dir ]]        # Directory exists
[[ -e path ]]       # Path exists (any type)
[[ -r file ]]       # Readable
[[ -w file ]]       # Writable
[[ -x file ]]       # Executable
[[ -s file ]]       # Non-empty file
[[ -L link ]]       # Symbolic link
[[ -z "$var" ]]     # String is empty
[[ -n "$var" ]]     # String is not empty
[[ "$a" == "$b" ]]  # String equality (glob patterns on right side)
[[ "$a" =~ regex ]] # Regex match (POSIX ERE; match in $MATCH)
[[ $n -eq 5 ]]      # Numeric equal
[[ $n -lt 5 ]]      # Numeric less than
[[ $n -gt 5 ]]      # Numeric greater than

# Case
case "$var" in
  start|begin) action ;;
  stop|end)    other_action ;;
  *)           default_action ;;
esac

# For loop
for item in one two three; do
    echo "$item"
done

# For loop over array
for item in "${array[@]}"; do
    echo "$item"
done

# C-style for loop
for (( i=0; i<10; i++ )); do
    echo "$i"
done

# While loop
while [[ condition ]]; do
    action
done

# Read lines from file
while IFS= read -r line; do
    echo "$line"
done < file.txt

# Until loop
until [[ condition ]]; do
    action
done

# Select menu
select choice in option1 option2 quit; do
    case "$choice" in
        option1) handle1 ;;
        option2) handle2 ;;
        quit)    break ;;
    esac
done

# Arithmetic
(( total = a + b ))
(( i++ ))
result=$(( 2 ** 8 ))    # 256
```

---

## Debugging and Inspection

```zsh
# Syntax check without executing
zsh -n script.zsh

# Trace execution
set -x          # Enable xtrace (echoes each command)
set +x          # Disable xtrace

# Check variable value and type
typeset -p var         # Print variable with flags and value
print -l "${path[@]}"  # Print array one per line

# Check if variable is set
[[ -v var ]]           # True if var is set (any value including empty)
[[ -n "${var+x}" ]]    # POSIX-compatible set check

# Profile startup
zsh -i -c 'zmodload zsh/zprof; source ~/.zshrc; zprof'

# Check which file defines a function
which function_name     # or: whence -v function_name
type function_name      # Full type info
```

---

## See Also

- `bash-migration.md` — Bash→Zsh syntax translation table
- `zsh-preferred-patterns.md` — Failure modes with detection commands
- `tool-integrations.md` — Tool integration patterns
