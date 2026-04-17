# Codex CLI Patterns

> **Scope**: `codex exec` command variants, flags, and error recovery for code review invocations.
> **Version range**: @openai/codex >=0.1.0, gpt-5.4 / gpt-4o / o4-mini models
> **Generated**: 2026-04-16

---

## Overview

The Codex CLI runs GPT models in a sandboxed environment with direct filesystem access.
For code review, the key pattern is `codex exec review` (built-in review subcommand) or
`codex exec` with a custom prompt. The CLI manages its own git context — embedding diffs
wastes tokens and hits prompt-length limits.

---

## Command Pattern Table

| Use Case | Command Variant | Key Flags |
|----------|----------------|-----------|
| Branch review vs main | `codex exec review --base main` | `--base <branch>` |
| Single commit review | `codex exec review --commit <SHA>` | `--commit <SHA>` |
| Unstaged changes only | `codex exec review --uncommitted` | `--uncommitted` |
| Custom focus areas | `codex exec "YOUR PROMPT"` | no `--base/--commit` |
| High-quality analysis | add to any | `-m gpt-5.4 -c 'model_reasoning_effort="xhigh"'` |
| Capture output | add to any | `-o "$TMPFILE"` |
| One-shot (no persist) | add to any | `--ephemeral` |
| Container/VM bypass | add to any | `--dangerously-bypass-approvals-and-sandbox` |

---

## Correct Patterns

### Branch review with output capture

```bash
TMPFILE=$(mktemp /tmp/codex-review.XXXXXXXX)

codex exec review \
  --base main \
  -m gpt-5.4 \
  -c 'model_reasoning_effort="xhigh"' \
  --ephemeral \
  --dangerously-bypass-approvals-and-sandbox \
  -o "$TMPFILE"
```

**Why**: `mktemp` template must end in Xs — appending an extension (`.md`) after the Xs
breaks macOS `mktemp`. `--base` and a custom prompt are mutually exclusive — `review`
handles diff internally.

### Custom prompt with heredoc

```bash
TMPFILE=$(mktemp /tmp/codex-review.XXXXXXXX)

codex exec \
  -m gpt-5.4 \
  -c 'model_reasoning_effort="xhigh"' \
  --ephemeral \
  --dangerously-bypass-approvals-and-sandbox \
  -o "$TMPFILE" \
  "$(cat <<'PROMPT'
Review the changes in git diff HEAD~1 focusing on error handling and security.
Run: git diff HEAD~1
PROMPT
)"
```

**Why**: Let Codex run `git diff` itself rather than embedding the diff — Codex has repo
access and embedding large diffs wastes tokens and loses formatting.

### Check exit code before reading output

```bash
if ! codex exec review --base main -m gpt-5.4 -o "$TMPFILE"; then
  echo "Codex failed — check stderr for API/auth errors"
  rm -f "$TMPFILE"
  exit 1
fi

if [ ! -s "$TMPFILE" ]; then
  echo "Codex produced empty output"
  rm -f "$TMPFILE"
  exit 1
fi
```

---

## Anti-Pattern Catalog

### Embedding the diff in the prompt

**Detection**:
```bash
# In constructed prompt strings — look for variable expansion with git diff output
grep -n 'DIFF=\$(git diff' . -r
```

**What it looks like**:
```bash
DIFF=$(git diff main...HEAD)
codex exec "Review this code: $DIFF"
```

**Why wrong**: Large diffs (>50 files) hit prompt-length limits. Formatting collapses.
Codex already has filesystem access — it can run `git diff` directly.

**Fix**: Tell Codex which command to run, not what the output is:
```bash
codex exec "Run \`git diff main...HEAD\` and review the changes for security issues."
```

---

### Using `--base` and a custom prompt together with `codex exec review`

**What it looks like**:
```bash
codex exec review --base main "Focus on error handling"
```

**Why wrong**: `--base`, `--commit`, and `--uncommitted` are mutually exclusive with a
custom `[PROMPT]` argument in the `review` subcommand. The CLI errors.

**Fix**: Use `codex exec` (not `codex exec review`) with a custom prompt:
```bash
codex exec -m gpt-5.4 -o "$TMPFILE" \
  "Run \`git diff main...HEAD\` and focus on error handling patterns."
```

---

### Appending extension to mktemp template

**What it looks like**:
```bash
TMPFILE=$(mktemp /tmp/codex-review.XXXXXXXX.md)
```

**Why wrong**: macOS `mktemp` requires the template to end in Xs. Appending `.md` causes
`mktemp: /tmp/codex-review.XXXXXXXX.md: invalid suffix`.

**Fix**: No extension, Xs at the end:
```bash
TMPFILE=$(mktemp /tmp/codex-review.XXXXXXXX)
```

---

### Using `-s read-only` with `--dangerously-bypass-approvals-and-sandbox`

**What it looks like**:
```bash
codex exec review --dangerously-bypass-approvals-and-sandbox -s read-only ...
```

**Why wrong**: These flags are mutually exclusive. `-s read-only` configures the bwrap
sandbox; the bypass flag disables it entirely. Combining them errors.

**Fix**: Use one or the other. In containerized environments, use the bypass flag.

---

## Error-Fix Mappings

| Error Message | Root Cause | Fix |
|---------------|------------|-----|
| `codex: command not found` | CLI not installed or not in PATH | `npm install -g @openai/codex`; verify with `codex --version` |
| `loopback: Failed RTM_NEWADDR: Operation not permitted` | bwrap sandbox fails in VM/container | Add `--dangerously-bypass-approvals-and-sandbox` |
| `invalid suffix` from mktemp | Extension appended after Xs in template | Remove extension: `mktemp /tmp/codex-review.XXXXXXXX` |
| `Error: cannot use --base with PROMPT` | `codex exec review` with both `--base` and positional prompt | Remove `--base` or switch to `codex exec` without review subcommand |
| Empty output file | Timeout, model error, or prompt too long | Check stderr; do not retry automatically |
| `401 Unauthorized` | OPENAI_API_KEY not set or expired | `export OPENAI_API_KEY=...` or check key validity |
| `429 Too Many Requests` | Rate limit hit | Wait and report to user — do not retry in a loop |
| `model not found: gpt-5.4` | Model unavailable in account tier | Fall back to `gpt-4o` and note in report |

---

## Detection Commands Reference

```bash
# Verify codex is installed
codex --version

# Check temp file has content before processing
[ -s "$TMPFILE" ] && echo "has content" || echo "empty or missing"

# Find embedded diffs in any shell scripts (anti-pattern signal)
grep -rn 'DIFF=\$(git' . --include="*.sh" --include="*.bash"
```
