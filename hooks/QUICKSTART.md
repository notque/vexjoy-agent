# Claude Code Learning System - Quick Start Guide

## What is this?

A self-improving hook ecosystem that learns from errors across Claude Code sessions and provides intelligent suggestions based on accumulated knowledge.

## How it works

1. **You encounter an error** (e.g., "Found 3 matches, use replace_all")
2. **System learns the pattern** (stores in SQLite database with initial confidence 0.4)
3. **You fix it and it works** (automatic feedback: confidence increases by +0.12 to 0.52)
4. **After multiple successful fixes** (confidence reaches 0.7 threshold - typically 3-4 successes)
5. **System auto-suggests solution** next time you encounter similar error
6. **Automatic feedback continues** (success +0.12, failure -0.18)

## Quick Commands

### View Statistics
```bash
sqlite3 ~/.claude/learning/patterns.db "SELECT COUNT(*) as total, SUM(CASE WHEN confidence >= 0.7 THEN 1 ELSE 0 END) as high_confidence FROM patterns"
```

### List All Patterns
```bash
sqlite3 ~/.claude/learning/patterns.db "SELECT error_type, solution, confidence FROM patterns ORDER BY confidence DESC"
```

### View High-Confidence Patterns (Ready to Use)
```bash
sqlite3 ~/.claude/learning/patterns.db "SELECT error_type, solution, confidence FROM patterns WHERE confidence >= 0.7"
```

### Run Tests
```bash
cd tests
python3 test_learning_system.py
```

## File Locations

| File | Purpose |
|------|---------|
| `~/.claude/learning/patterns.db` | Main SQLite learning database (NOT JSON) |
| `~/.claude/learning/patterns.db-shm` | SQLite shared memory file |
| `~/.claude/learning/patterns.db-wal` | SQLite write-ahead log |
| `~/.claude/learning/pending_feedback.json` | Automatic feedback state (60s expiry) |
| `/tmp/claude_error_learner_debug.log` | Debug logs (if enabled) |

**Note**: The database format is SQLite, not JSON. Use `sqlite3` to query.

## What Gets Learned?

The system automatically learns from these error types:

- **missing_file** - File not found errors
- **missing_command** - Command not found errors
- **permissions** - Permission denied errors
- **multiple_matches** - Edit tool ambiguous matches
- **syntax_error** - Code syntax errors
- **type_error** - Python type errors
- **import_error** - Module import errors
- **timeout** - Timeout errors

## Confidence Levels

| Confidence | Meaning | Action |
|------------|---------|--------|
| 0.0 - 0.3 | Low | Pattern tracked, not applied |
| 0.3 - 0.7 | Developing | Building confidence through feedback |
| 0.7 - 1.0 | High-Confidence | Auto-suggested on errors |

**Confidence Adjustments**:
- Success: +0.12 (capped at 1.0)
- Failure: -0.18 (floored at 0.0)
- Initial: 0.4 (failure) or 0.6 (success)

## Example Session

```
Session Start:
[learned-context] Loaded 12 high-confidence patterns from previous sessions
[learned-context]   Edit: multiple_matches(3), missing_file(2)
[learned-context] Overall success rate: 84.2%

... work happens ...

Error Occurs:
[learned-solution] Use replace_all or provide unique context
[learned-solution] → Add replace_all=true to Edit parameters

Session End:
[session-summary] Session completed
[session-summary]   Tool uses: 47
[session-summary]   Files modified: 8
[session-summary]   Success rate: 93.6%
[session-summary] Learning database: 45 patterns, 28 high-confidence
```

## Debugging

Enable debug logging in any hook:

```python
# In error-learner.py, session-context.py, etc.
DEBUG = True
```

Then view logs:
```bash
tail -f /tmp/claude_error_learner_debug.log
```

## Database Schema (SQLite)

Each pattern contains:
- **id**: Auto-incrementing primary key
- **signature**: MD5 hash of normalized error (16 chars, unique index)
- **error_type**: Classified error category (8 types)
- **error_message**: First 500 chars of error (for reference)
- **solution**: Human-readable solution description
- **confidence**: Success probability (0.0 - 1.0, default 0.5)
- **success_count**: Times this solution worked
- **failure_count**: Times this solution failed
- **last_seen**: ISO timestamp of last occurrence
- **project_path**: Where this pattern applies (NULL = global)
- **created_at**: ISO timestamp of pattern creation
- **fix_type**: Type of fix (manual, auto, skill, agent)
- **fix_action**: Specific action/command/skill/agent name

## Confidence Evolution Example

```
Error: "Found 5 matches of the string to replace"

First encounter: Recorded with confidence = 0.4 (no success yet)
Attempt 1: Fix it → Success (+0.12) → confidence = 0.52
Attempt 2: Fix it → Success (+0.12) → confidence = 0.64
Attempt 3: Fix it → Failure (-0.18) → confidence = 0.46
Attempt 4: Fix it → Success (+0.12) → confidence = 0.58
Attempt 5: Fix it → Success (+0.12) → confidence = 0.70 ✓ HIGH-CONFIDENCE

Next error → System auto-suggests: "Use replace_all=true or provide more unique context"
           → Automatic feedback tracks if fix works
```

**Automatic Feedback Loop**:
1. Error occurs, system suggests fix
2. Pending feedback set (`~/.claude/learning/pending_feedback.json`)
3. Next PostToolUse checks: error gone? (success) or persists? (failure)
4. Confidence updated automatically
5. Feedback state cleared

## Reset Database

If you want to start fresh:

```bash
# Backup first
sqlite3 ~/.claude/learning/patterns.db .dump > patterns_backup.sql

# Delete to start fresh
rm ~/.claude/learning/patterns.db
```

## Tips

1. **Let it learn gradually** - New patterns start at 0.4 or 0.6 confidence
2. **3-4 successes** typically needed to reach 0.7 auto-suggestion threshold
3. **Failures count more** (-0.18) than successes (+0.12) - conservative learning
4. **Global patterns** (NULL project_path) work everywhere
5. **Project patterns** only suggest in relevant directories
6. **Automatic feedback** tracks fix outcomes - no manual intervention needed
7. **60-second window** - feedback must occur within 60s of fix suggestion

## Architecture

```
SessionStart → Load learned patterns
     ↓
PostToolUse → Detect errors, update patterns
     ↓
PreCompact → Archive before context compression
     ↓
Stop → Save session summary and metrics
```

## Performance

- **Target**: Sub-50ms execution per hook
- **Storage**: ~1KB per pattern
- **Database**: Atomic writes, file locking
- **Non-blocking**: Always exits 0, never blocks Claude

## Advanced Usage

### Manual Pattern Creation

```python
import sys
from pathlib import Path
sys.path.insert(0, str(Path.cwd() / "hooks" / "lib"))

from learning_db import record_error, get_connection, generate_signature, classify_error

# Record a new error pattern
error_msg = "My custom error message"
solution = "How to fix it"
fix_type = "manual"  # or "auto", "skill", "agent"
fix_action = "specific_command"  # or skill name, agent name, etc.

record_error(
    error_message=error_msg,
    solution=solution,
    success=True,  # True = start with confidence 0.6, False = 0.4
    fix_type=fix_type,
    fix_action=fix_action,
    project_path=None  # None = global pattern
)

# Optionally boost confidence for manually-added patterns
sig = generate_signature(error_msg, classify_error(error_msg))
with get_connection() as conn:
    conn.execute('UPDATE patterns SET confidence = 0.9 WHERE signature = ?', (sig,))
    conn.commit()

print(f"Pattern created with signature: {sig}")
```

### Querying Patterns

```python
import sys
from pathlib import Path
sys.path.insert(0, str(Path.cwd() / "hooks" / "lib"))

from learning_db import (
    get_connection,
    get_high_confidence_patterns,
    lookup_solution,
    classify_error,
    generate_signature
)

# Find solution for specific error
error_msg = "Found 3 matches"
solution = lookup_solution(error_msg)
if solution:
    print(f"Solution: {solution['solution']}")
    print(f"Fix type: {solution['fix_type']}")
    print(f"Confidence: {solution['confidence']}")

# Get all high-confidence patterns
high_conf = get_high_confidence_patterns(min_confidence=0.7, limit=10)
for pattern in high_conf:
    print(f"{pattern['error_type']}: {pattern['solution']} ({pattern['confidence']:.2f})")

# Get project-specific patterns
project_patterns = get_high_confidence_patterns(
    min_confidence=0.7,
    project_path="/home/user/myproject",
    limit=10
)

# Manual confidence update (use feedback_tracker instead for automatic)
sig = generate_signature(error_msg, classify_error(error_msg))
with get_connection() as conn:
    row = conn.execute(
        'SELECT confidence, success_count FROM patterns WHERE signature = ?',
        (sig,)
    ).fetchone()
    if row:
        new_conf = min(1.0, row['confidence'] + 0.12)  # Success
        conn.execute(
            'UPDATE patterns SET confidence = ?, success_count = ? WHERE signature = ?',
            (new_conf, row['success_count'] + 1, sig)
        )
        conn.commit()
```

## Troubleshooting

**Q: Hooks not running?**
- Check `.claude/settings.json` has hooks registered
- Verify Python files are executable: `chmod +x *.py`
- Check Claude Code supports hook events

**Q: No patterns being learned?**
- Enable DEBUG mode
- Check `/tmp/claude_error_learner_debug.log`
- Verify errors are being detected in tool output

**Q: Database corrupted?**
- SQLite has automatic recovery via write-ahead log
- Manual backup: `sqlite3 ~/.claude/learning/patterns.db .dump > backup.sql`
- Restore: `sqlite3 ~/.claude/learning/patterns.db < backup.sql`
- Or reset by removing the database file: `rm ~/.claude/learning/patterns.db`

**Q: Hooks too slow?**
- Check debug logs for execution times
- Consider reducing pattern count
- Verify database isn't too large (>1MB)

## Next Steps

1. Let it learn from your normal workflow
2. Watch high-confidence patterns appear
3. Enjoy auto-suggestions on future errors!

---

For detailed documentation, see [README.md](README.md)
