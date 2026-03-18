---
name: learn
description: |
  Manually teach Claude Code an error pattern and its solution, storing it in
  the learning database with high confidence. Use when user provides an
  explicit "error -> solution" pair, wants to pre-load fix knowledge, or
  corrects a previous bad fix. Use for "/learn", "teach pattern", "remember
  this fix". Do NOT use for automatic error learning (that is the error-learner
  hook), debugging live issues, or querying existing patterns.
version: 2.0.0
user-invocable: true
allowed-tools:
  - Read
  - Bash
---

# Learn Error Pattern Skill

## Operator Context

This skill operates as an operator for manual knowledge ingestion, configuring Claude to parse user-provided error-solution pairs and store them in the cross-session learning database. It implements a **Parse-Classify-Store-Confirm** workflow with deterministic Python scripts performing all database operations.

### Hardcoded Behaviors (Always Apply)
- **Input Validation**: Never store empty error patterns or empty solutions
- **Environment Variable Injection Prevention**: Always pass values via environment variables to the Python script, never inline user strings into code
- **High Confidence**: Manually taught patterns always receive confidence 0.9
- **Single Pattern Per Invocation**: Store exactly one pattern per `/learn` call

### Default Behaviors (ON unless disabled)
- **Auto-Classification**: Determine error type and fix type from solution text
- **Confirmation Output**: Display stored pattern details back to user
- **Duplicate Handling**: If pattern already exists, update its confidence to 0.9

### Optional Behaviors (OFF unless enabled)
- **Batch Mode**: Accept multiple patterns from a file (one per line, `error -> solution` format)
- **Dry Run**: Parse and classify without storing, showing what would be saved

## What This Skill CAN Do
- Parse "error -> solution" input into structured pattern data
- Classify fix types (auto, skill, agent, manual) from solution text
- Store patterns in SQLite learning database at 0.9 confidence
- Update confidence on existing patterns for the same error signature

## What This Skill CANNOT Do
- Debug live issues (use systematic-debugging instead)
- Automatically learn from tool errors (that is the error-learner hook)
- Query or list existing patterns (use `sqlite3 ~/.claude/learning/patterns.db "SELECT * FROM patterns"`)
- Delete or reset the database (remove `~/.claude/learning/patterns.db`)
- Store patterns without user-provided error AND solution text

---

## Instructions

### Phase 1: PARSE

**Goal**: Extract error pattern and solution from user input.

**Step 1: Identify input format**

Accepted formats:
- `/learn "error pattern" -> "solution"`
- `/learn "error pattern" => "solution"`
- Freeform: "teach that X means Y" or "remember: when X, do Y"

**Step 2: Extract fields**

- `error_pattern`: The error message or symptom text
- `solution`: The fix or resolution text

**Gate**: Both error_pattern and solution are non-empty strings. If either is missing, ask the user for the missing part. Do not proceed with empty fields.

### Phase 2: CLASSIFY

**Goal**: Determine fix type and action from the solution text.

Apply these rules in order:
1. Solution contains install command (pip install, npm install, apt install) -> `fix_type=auto`, `fix_action=install_dependency`
2. Solution contains `replace_all` -> `fix_type=auto`, `fix_action=use_replace_all`
3. Solution references a skill name -> `fix_type=skill`, `fix_action=<skill-name>`
4. Solution references an agent name -> `fix_type=agent`, `fix_action=<agent-name>`
5. Otherwise -> `fix_type=manual`, `fix_action=apply_suggestion`

**Gate**: fix_type and fix_action are determined. Proceed.

### Phase 3: STORE

**Goal**: Persist the pattern to the learning database.

Execute the storage script using environment variables for all user-provided values:

```bash
ERROR_MSG="<error>" SOLUTION="<solution>" FIX_TYPE="<type>" FIX_ACTION="<action>" python3 << 'PYEOF'
import os, sys
sys.path.insert(0, 'hooks/lib')
from learning_db import record_error, get_connection, generate_signature, classify_error

error_msg = os.environ['ERROR_MSG']
solution = os.environ['SOLUTION']
fix_type = os.environ['FIX_TYPE']
fix_action = os.environ['FIX_ACTION']

record_error(
    error_message=error_msg,
    solution=solution,
    success=True,
    fix_type=fix_type,
    fix_action=fix_action
)
sig = generate_signature(error_msg, classify_error(error_msg))
with get_connection() as conn:
    conn.execute('UPDATE patterns SET confidence = 0.9 WHERE signature = ?', (sig,))
    conn.commit()
print(f'Stored: [{fix_type}] {error_msg[:60]}')
PYEOF
```

**Gate**: Script exits 0 and prints confirmation. If script fails, see Error Handling.

### Phase 4: CONFIRM

**Goal**: Report stored pattern back to the user.

Display:
```
Learned pattern:
  Error: "<error_pattern>"
  Solution: "<solution>"
  Type: <fix_type> (<fix_action>)
  Confidence: 0.9
```

**Gate**: User sees confirmation. Skill complete.

---

## Error Handling

### Error: "Script fails with ImportError"
Cause: hooks/lib/learning_db.py not found or path incorrect
Solution: Verify working directory is the repo root. Run from the ai-overkill directory.

### Error: "Database locked"
Cause: Another process holds the SQLite lock
Solution: Retry after 2 seconds. If persistent, check for hung processes with `lsof ~/.claude/learning/patterns.db`.

### Error: "User provides only error, no solution"
Cause: Incomplete input
Solution: Ask the user explicitly for the solution text. Do not guess or fabricate solutions.

---

## Anti-Patterns

### Anti-Pattern 1: Storing Vague Patterns
**What it looks like**: `/learn "it broke" -> "fix it"`
**Why wrong**: Pattern too vague to match future errors. Solution provides no actionable guidance.
**Do instead**: Ask user to provide the specific error message and concrete fix steps.

### Anti-Pattern 2: Inlining User Strings Into Python Code
**What it looks like**: Building Python code with f-strings containing user input
**Why wrong**: Injection risk. Quotes or special characters in error text break the script.
**Do instead**: Always pass via environment variables as shown in Phase 3.

### Anti-Pattern 3: Storing Without Confirming Back
**What it looks like**: Running the script and saying "done" without showing what was stored
**Why wrong**: User cannot verify correctness. Typos go unnoticed.
**Do instead**: Always complete Phase 4 with the full confirmation output.

---

## References

- `hooks/lib/learning_db.py`: Core database module (record_error, generate_signature, classify_error)
- `sqlite3 ~/.claude/learning/patterns.db`: Direct SQLite queries for inspecting patterns
- `hooks/error-learner.py`: Automatic error learning hook (complementary system)
