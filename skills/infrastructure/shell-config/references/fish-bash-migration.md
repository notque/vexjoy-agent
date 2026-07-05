# Bash to Fish Migration Reference

## Syntax Translation Table

| Bash | Fish | Notes |
|------|------|-------|
| `VAR=value` | `set VAR value` | Always use `set` |
| `export VAR=value` | `set -gx VAR value` | Global + Export |
| `unset VAR` | `set -e VAR` | Erase variable |
| `$?` | `$status` | Exit status of last command |
| `$@` or `$*` | `$argv` | Function/script arguments |
| `$#` | `(count $argv)` | Argument count |
| `${var:-default}` | `set -q var; or set var default` | Default value pattern |
| `$(command)` | `$(command)` or `(command)` | Both work in Fish 3.0+ |
| `[[ condition ]]` | `test condition` | Fish builtin |
| `[ condition ]` | `test condition` | Prefer Fish builtin |
| `&&` | `&&` or `; and` | Both work in Fish 3.0+ |
| `\|\|` | `\|\|` or `; or` | Both work in Fish 3.0+ |
| `function name() { }` | `function name ... end` | No braces in Fish |
| `source file` | `source file` | Same syntax |
| `heredoc <<EOF` | Use `echo` or `printf` | Fish has no heredocs |
| `array=(one two three)` | `set array one two three` | Fish variables are lists |
| `${array[0]}` | `$array[1]` | Fish is 1-indexed |
| `${#array[@]}` | `(count $array)` | Count list elements |
| `export PATH="$PATH:/new"` | `fish_add_path /new` | Fish PATH is a list |

## Common Migration Patterns

### Variable Assignment
```bash
# Bash
VAR=value command
```
```fish
# Fish — two approaches
env VAR=value command
# or
set -lx VAR value; command
```

### PATH Manipulation
```bash
# Bash
export PATH="$PATH:/new/path"
```
```fish
# Fish
fish_add_path /new/path
# or (session only)
set -gx PATH $PATH /new/path
```

### Conditionals
```bash
# Bash
if [[ -z "$var" ]]; then
    echo "empty"
fi
```
```fish
# Fish
if test -z "$var"
    echo "empty"
end
```

### String Comparison
```bash
# Bash
if [[ "$a" == "$b" ]]; then
    echo "equal"
fi
```
```fish
# Fish — note single = for equality
if test "$a" = "$b"
    echo "equal"
end
```

### Arrays
```bash
# Bash
array=(one two three)
echo ${array[0]}      # one (0-indexed)
echo ${#array[@]}     # 3
```
```fish
# Fish
set array one two three
echo $array[1]        # one (1-indexed!)
echo (count $array)   # 3
echo $array[-1]       # three (negative indexing)
echo $array[2..3]     # two three (range slicing)
```

### Heredocs
Fish has no heredocs. Use alternatives:

```fish
# Multi-line string variable
set content "line 1
line 2
line 3"

# Write multi-line to file
printf '%s\n' "line 1" "line 2" "line 3" > file.txt

# Echo with embedded newlines
echo "line 1
line 2
line 3" > file.txt
```

### Process Substitution
```bash
# Bash
diff <(sort file1) <(sort file2)
```
```fish
# Fish — use psub
diff (sort file1 | psub) (sort file2 | psub)
```

### Inline Environment for Commands
```bash
# Bash
LANG=C sort file.txt
```
```fish
# Fish
env LANG=C sort file.txt
```

## Key Differences to Remember

1. **No word splitting**: `$var` and `"$var"` behave identically in Fish. Quotes are not needed to prevent word splitting.

2. **1-indexed arrays**: Fish arrays start at 1, not 0. `$array[1]` is the first element.

3. **Variables are always lists**: Even a single-element variable is a one-element list. This is fundamental to Fish.

4. **No inline assignment**: `VAR=value command` does not work. Use `env VAR=value command` or `set -lx VAR value; command`.

5. **`test` not brackets**: Use `test -f file` not `[[ -f file ]]`. The `test` builtin is fast and native.

6. **`end` not braces/fi/done**: All blocks close with `end` — `if/end`, `for/end`, `while/end`, `function/end`, `switch/end`.

7. **No `$()` needed for arithmetic**: Fish has `math` builtin: `math "2 + 2"` returns `4`.
