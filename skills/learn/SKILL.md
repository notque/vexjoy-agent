---
name: learn
description: "Manually teach error pattern and solution to learning database."
user-invocable: false
argument-hint: '"error" -> "solution"'
allowed-tools:
  - Read
  - Bash
routing:
  triggers:
    - "teach pattern"
    - "record learning"
    - "manual learning entry"
    - "teach error pattern"
    - "save learning"
  category: meta-tooling
  pairs_with:
    - retro
    - auto-dream
---

# Learn Error Pattern Skill

Parse a user-provided "error -> solution" pair, classify it, store it in the learning database at high confidence, and confirm. One pattern per invocation. All database operations go through `learning-db.py`.

## Instructions

### Step 1: Parse Input

Extract two fields:

- `error_pattern`: The error message or symptom
- `solution`: The fix or resolution

Accepted formats:
- `/learn "error pattern" -> "solution"`
- `/learn "error pattern" => "solution"`
- Freeform: "teach that X means Y" or "remember: when X, do Y"

Both fields must be non-empty. If either is missing, ask the user. If the error pattern is vague (e.g., "it broke") or the solution non-actionable (e.g., "fix it"), ask for specifics -- vague patterns fail to match future errors.

### Step 2: Classify Fix Type

Determine `fix_type` and `fix_action` by applying these rules in order:

1. Solution contains an install command (`pip install`, `npm install`, `apt install`) -> `fix_type=auto`, `fix_action=install_dependency`
2. Solution contains `replace_all` -> `fix_type=auto`, `fix_action=use_replace_all`
3. Solution references a skill name -> `fix_type=skill`, `fix_action=<skill-name>`
4. Solution references an agent name -> `fix_type=agent`, `fix_action=<agent-name>`
5. Otherwise -> `fix_type=manual`, `fix_action=apply_suggestion`

### Step 3: Store Pattern

Always pass user-provided strings as CLI arguments exactly as shown -- never inline them via f-strings or concatenation (injection risk).

```bash
python3 ~/.claude/scripts/learning-db.py record \
  "<error_type>" \
  "<error_signature>" \
  "<error_pattern> → <solution>" \
  --category error \
  --confidence 0.9
```

- `<error_type>`: Classified type (e.g., "missing_file", "multiple_matches")
- `<error_signature>`: Kebab-case key derived from the error pattern
- Confidence is always 0.9 for manually taught patterns

Example:
```bash
python3 ~/.claude/scripts/learning-db.py record \
  "multiple_matches" \
  "edit-tool-multiple-matches" \
  "Edit tool fails with 'found N matches' → Use replace_all=True parameter" \
  --category error \
  --confidence 0.9
```

Script must exit 0 and print confirmation. If it fails, see Error Handling.

### Step 4: Confirm to User

Display what was stored so the user can verify:

```
Learned pattern:
  Error: "<error_pattern>"
  Solution: "<solution>"
  Type: <fix_type> (<fix_action>)
  Confidence: 0.9
```

## Error Handling

### Error: "Script fails with ImportError or FileNotFoundError"
Cause: `scripts/learning-db.py` not found or not synced to `~/.claude/scripts/`
Solution: Verify working directory is repo root, or use `~/.claude/scripts/learning-db.py`.

### Error: "Database locked"
Cause: Another process holds the SQLite lock.
Solution: Retry after 2 seconds. If persistent, check `lsof ~/.claude/learning/learning.db`.

### Error: "User provides only error, no solution"
Cause: Incomplete input.
Solution: Ask the user explicitly. Do not guess or fabricate solutions.

## References

- `hooks/lib/learning_db_v2.py`: Unified learning database module
- `scripts/learning-db.py`: CLI for recording, querying, and managing learnings
- `hooks/error-learner.py`: Automatic error learning hook (complementary system)
