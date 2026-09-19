# Bash to Zsh Migration Reference

> **Scope**: Bash→Zsh syntax translation for shell config migration. Covers variables, arrays, conditionals, loops, functions, traps, process substitution, heredocs, and parameter expansion.
> **Version range**: Zsh 5.8+
> **Generated**: 2026-05-26

---

## Syntax Translation Table

| Bash | Zsh | Notes |
|------|-----|-------|
| `VAR=value` | `VAR=value` | Both work — Zsh is POSIX-compatible |
| `export VAR=value` | `export VAR=value` or `typeset -x VAR=value` | Both work; `typeset -x` is Zsh-native |
| `unset VAR` | `unset VAR` | Same syntax |
| `$?` | `$?` | Exit status — identical |
| `$@` or `$*` | `$@` or `$*` | Function arguments — identical |
| `$#` | `$#` | Argument count — identical |
| `${var:-default}` | `${var:-default}` | Default value — identical |
| `$(command)` | `$(command)` | Command substitution — identical |
| `[[ condition ]]` | `[[ condition ]]` | Both work — `[[ ]]` is native in Zsh |
| `[ condition ]` | `[ condition ]` or `[[ ]]` | Both work; prefer `[[ ]]` in Zsh |
| `&&` / `\|\|` | `&&` / `\|\|` | Identical |
| `function name() { }` | `function name { }` or `name() { }` | Both work in Zsh |
| `source file` | `source file` or `. file` | Identical |
| `declare -a arr` | `typeset -a arr` | `declare` works but `typeset` is canonical |
| `declare -A assoc` | `typeset -A assoc` | Associative arrays — same semantics |
| `declare -i int` | `typeset -i int` | Integer — same semantics |
| `declare -r CONST` | `typeset -r CONST` | Read-only — same semantics |
| `local var` | `local var` | Both work inside functions |
| `array=(one two three)` | `array=(one two three)` | Same syntax |
| `${array[0]}` | `${array[1]}` | **Zsh arrays are 1-indexed** |
| `${#array[@]}` | `${#array[@]}` or `$#array` | Count — `$#array` is Zsh shorthand |
| `export PATH="$PATH:/new"` | `path+=/new` or `path=(/new $path)` | Use `path` array — Zsh-native |
| `trap 'cmd' SIGTERM` | `trap 'cmd' TERM` | Zsh omits `SIG` prefix |
| `diff <(sort f1) <(sort f2)` | `diff <(sort f1) <(sort f2)` | Process substitution — identical |
| `heredoc <<EOF` | `heredoc <<EOF` | Identical |
| `=()` temp file | `=()` temp file | Zsh-only: `=(cmd)` creates temp file |

---

## Common Migration Patterns

### Variable Assignment

```bash
# Bash
VAR=value command        # Inline env for command
```

```zsh
# Zsh — inline env works the same
VAR=value command

# Or with typeset for function-scoped
typeset -x VAR=value; command
```

### PATH Manipulation

```bash
# Bash
export PATH="$PATH:/new/path"
```

```zsh
# Zsh — preferred: use path array
path+=(/new/path)           # Append
path=(/new/path $path)      # Prepend
typeset -U path             # Deduplicate

# Compatible: still works in zsh
export PATH="$PATH:/new/path"
```

### Conditionals

```bash
# Bash
if [[ -z "$var" ]]; then
    echo "empty"
fi
```

```zsh
# Zsh — identical syntax (both [[ ]] and [ ] work)
if [[ -z "$var" ]]; then
    echo "empty"
fi

# Zsh also accepts: if [[ -z $var ]]; (no quotes needed for single words)
```

### Arrays

```bash
# Bash — 0-indexed
array=(one two three)
echo "${array[0]}"    # one
echo "${#array[@]}"   # 3
for item in "${array[@]}"; do echo "$item"; done
```

```zsh
# Zsh — 1-indexed
array=(one two three)
echo "$array[1]"      # one  (note: no braces needed for simple index)
echo "$array[-1]"     # three (negative indexing)
echo "$array[2,3]"    # two three (range slice)
echo "${#array}"      # 3  (or $#array)
for item in $array; do echo "$item"; done
```

### Associative Arrays

```bash
# Bash
declare -A map
map[key]="value"
echo "${map[key]}"
for k in "${!map[@]}"; do echo "$k=${map[$k]}"; done
```

```zsh
# Zsh
typeset -A map
map[key]="value"
echo "$map[key]"
for k in "${(k)map}"; do echo "$k=$map[$k]"; done
# Keys: ${(k)map}  Values: ${(v)map}  Key+value pairs: ${(kv)map}
```

### Heredocs

```bash
# Bash
cat <<EOF
line 1
line 2
EOF
```

```zsh
# Zsh — identical syntax
cat <<EOF
line 1
line 2
EOF

# Zsh-only: strip leading tabs with <<-EOF
cat <<-EOF
    line 1
    line 2
EOF
```

### Process Substitution

```bash
# Bash
diff <(sort file1) <(sort file2)
```

```zsh
# Zsh — identical syntax
diff <(sort file1) <(sort file2)

# Zsh-only: =(cmd) creates a named temp file (not a pipe)
# Useful for commands that require seekable input
diff =(sort file1) =(sort file2)
```

### Traps

```bash
# Bash
trap 'cleanup' SIGTERM SIGINT EXIT
```

```zsh
# Zsh — omit SIG prefix; EXIT uses zshexit
trap 'cleanup' TERM INT EXIT
# Or use zsh hooks:
zshexit() { cleanup; }
```

### Parameter Expansion

```bash
# Bash
${var#prefix}       # Remove shortest prefix
${var##prefix}      # Remove longest prefix
${var%suffix}       # Remove shortest suffix
${var%%suffix}      # Remove longest suffix
${var/old/new}      # Replace first
${var//old/new}     # Replace all
${var^}             # Uppercase first char (Bash 4+)
${var^^}            # Uppercase all (Bash 4+)
${var,}             # Lowercase first (Bash 4+)
${var,,}            # Lowercase all (Bash 4+)
```

```zsh
# Zsh — all Bash forms work, plus expansion flags
${var#prefix}       # Same
${var##prefix}      # Same
${var%suffix}       # Same
${var%%suffix}      # Same
${var/old/new}      # Same
${var//old/new}     # Same

# Zsh-native (via parameter expansion flags — load zsh-quick-reference.md for full list)
${(U)var}           # Uppercase all (replaces ${var^^})
${(L)var}           # Lowercase all (replaces ${var,,})
${(C)var}           # Capitalize first letter of each word
${(f)var}           # Split on newlines → array
${(s:,:)var}        # Split on comma → array
${(j: :)array}      # Join array with spaces → string
${(u)array}         # Unique elements
```

---

## Key Differences to Remember

1. **Arrays are 1-indexed**: `$array[1]` is the first element. `$array[0]` is empty in Zsh, not the first element.

2. **`[[ ]]` works in Zsh**: Unlike fish, `[[ ]]` is native Zsh syntax. Bash scripts using `[[ ]]` run in Zsh without modification.

3. **`typeset` vs `declare`**: `declare` is a Bash synonym that works in Zsh for compatibility. `typeset` is the Zsh-canonical form. Use `typeset` in new Zsh code.

4. **`=()` temp files**: Zsh-only feature. `diff =(sort f1) =(sort f2)` creates actual temp files (not pipes), enabling random access. Bash has no equivalent.

5. **`path` array**: Zsh maintains `$path` (array) and `$PATH` (colon string) in sync. Manipulating `$path` directly is cleaner than string concatenation.

6. **`typeset -U`**: Zsh-only. `typeset -U path` automatically deduplicates the `path` array on every assignment. No Bash equivalent.

7. **Glob qualifiers**: `*.txt(N)` (null glob), `**/*.go(.)` (regular files only), `*(m-7)` (modified in last 7 days). Bash has no equivalent — requires `find`.

8. **`autoload`**: Zsh lazy-loads functions from `fpath`. A function file is not sourced until the function is first called. Bash has no equivalent mechanism.

---

## See Also

- `zsh-quick-reference.md` — Parameter expansion flags, special variables, control flow
- `zsh-preferred-patterns.md` — Failure modes and detection commands
- `tool-integrations.md` — Tool integration patterns (Go, Rust, Node, Python, shell enhancers)
