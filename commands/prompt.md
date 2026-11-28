---
description: "One-turn prompt compiler: shape an underspecified request into a 5-line task contract before passing it to /do or /d"
allowed-tools: ["Read", "Bash", "Grep", "Glob", "Skill", "Agent"]
---

# /prompt - One-Turn Prompt Compiler

Usage: `/prompt [--strict-scope|--spike|--review-only|--ship|--local-only] <request>`

Turn a rough or underspecified request into a ratified 5-line task contract before making edits, then feed the ratified contract straight into `/do` or `/d`.

## Instructions

Read `skills/meta/do/references/prompt-compiler.md` and run the one-turn prompt compiler.

```
Base directory: $CLAUDE_PROJECT_DIR or the current working directory
Reference file: skills/meta/do/references/prompt-compiler.md
```

1. **Ground (read-only):** Inspect up to 5 relevant files or run read-only repository queries so paths and assumptions match the codebase. Make zero file edits or mutating commands.
2. **Extract presets:** When the request includes standalone preset flags (`--strict-scope`, `--spike`, `--review-only`, `--ship`, `--local-only`), write the raw request to a temp file and extract presets via `$SDIR` so shell quoting and leading flags stay safe:

```bash
SDIR="${HOME}/.claude/scripts"; [ -d "$SDIR" ] || SDIR="${HOME}/.gemini/scripts"; [ -d "$SDIR" ] || SDIR="${HOME}/.hermes/scripts"; [ -d "$SDIR" ] || SDIR="${HOME}/.factory/scripts"; [ -d "$SDIR" ] || SDIR="${HOME}/.codex/scripts"; [ -d "$SDIR" ] || SDIR="${HOME}/.reasonix/scripts"
REQUEST_FILE=$(mktemp)
cat <<'EOF' > "$REQUEST_FILE"
<request>
EOF
python3 "$SDIR/prompt_presets.py" --extract-file "$REQUEST_FILE" --json
rm -f "$REQUEST_FILE"
```

3. **Emit the 5-line ratification card:**
   1. **Outcome:** one sentence naming the exact deliverable.
   2. **Out of scope:** explicit exclusions and boundaries.
   3. **Verify with:** exact command or observable proof.
   4. **Owned paths / assumptions:** concrete repo paths and grounded assumptions.
   5. **Open question (only if needed):** at most 1 load-bearing question with a recommended default; omit line 5 if none.
4. **Hand off on ratification:** Once the user replies `go` or `proceed` (or adjusts a line), call the Skill tool with `do` (or `d` when requested) and pass the compiled contract as `task_spec` plus any `prompt_presets` without re-asking.

If the request already states concrete target, scope, and verification, skip the card and invoke `/do` or `/d` directly.

ARGUMENTS: $ARGUMENTS
