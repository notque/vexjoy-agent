# Retro Loop Pattern

Capture and graduate knowledge at phase checkpoints. Any skill can reference this pattern to add self-improving context management.

## Architecture

The learning system uses a single source of truth: **learning.db** (SQLite + FTS5).

```
CAPTURE (automatic)     → learning.db entries
  error-learner.py        PostToolUse: tool errors + solutions
  review-capture.py       PostToolUse: reviewer agent findings
  session-learning-recorder.py  Stop: gap detection

INJECTION (automatic)   → <retro-knowledge> blocks
  retro-knowledge-injector.py   UserPromptSubmit: FTS5 search → context injection
  session-context.py            SessionStart: high-confidence pattern loading

GRADUATION (manual)     → permanent agent/skill edits
  /retro graduate               LLM-driven: propose edits, user approves
  learning-db.py graduate       Mark entries as graduated (stop injection)
```

## How It Works

### Capture

Hooks automatically record learnings during normal work:

- **Error patterns**: `error-learner.py` captures tool errors and their solutions. Confidence adjusts based on whether the same fix works again.
- **Review findings**: `review-capture.py` extracts high-severity findings from reviewer agents.
- **Session gaps**: `session-learning-recorder.py` warns when substantive sessions produce zero learnings.
- **Manual recording**: For design decisions and gotchas that hooks can't detect:
  ```bash
  python3 scripts/learning-db.py record TOPIC KEY "VALUE" --category CATEGORY
  ```
  Categories: `error | pivot | review | design | debug | gotcha | effectiveness`

### Injection

The `retro-knowledge-injector` hook fires on every `UserPromptSubmit`:

1. Fast-path skip for trivial prompts (< 4 words, questions, reads)
2. Checks work intent (implement, build, design, plan, etc.)
3. Queries learning.db via FTS5 with prompt keywords
4. Injects relevant entries as `<retro-knowledge>` block (~2000 token budget)
5. Graduated entries are excluded (`graduated_to IS NULL` filter)

**Benchmark validation** (7 trials, blind grading):
- Win rate: 67% when knowledge is relevant
- Avg margin: +5.3 points on 8-dimension rubric
- Knowledge Transfer dimension: 5-0 win record
- Token efficiency: retro agents use 32% FEWER tokens (23.5K vs 34.5K)

### Graduation

When learnings are mature enough to become permanent agent/skill instructions:

1. Run `/retro graduate`
2. The LLM evaluates design/gotcha entries for actionability and specificity
3. Searches the repo for the target file
4. Proposes a specific edit (2-5 lines)
5. On user approval: edits target, marks entry graduated
6. Graduated entries stop being injected

## Integration with Feature Lifecycle

Each feature lifecycle skill (design, plan, implement, validate, release) has a CHECKPOINT phase that records learnings:

```bash
python3 scripts/learning-db.py record TOPIC KEY "VALUE" --category design
```

Focus on non-obvious, specific insights — not generic best practices.

## Integration with Existing System

| Component | Role |
|-----------|------|
| `scripts/learning-db.py` | CLI for all DB operations (record, query, search, graduate) |
| `hooks/retro-knowledge-injector.py` | Auto-inject relevant knowledge into agent context |
| `hooks/session-context.py` | Load high-confidence patterns at session start |
| `hooks/error-learner.py` | Auto-capture tool errors and solutions |
| `hooks/review-capture.py` | Capture review findings from subagents |
| `hooks/confidence-decay.py` | Prune stale low-confidence entries |
| `skills/retro/SKILL.md` | User-facing `/retro` commands (status, list, search, graduate) |

## Anti-Patterns

| Anti-Pattern | Why Wrong | Do Instead |
|--------------|-----------|------------|
| Skip recording because "nothing learned" | Every phase teaches something | Record specific insights; hooks catch errors automatically |
| Record generic findings | "Follow best practices" teaches nothing | Record specific: "sync.Mutex for multi-field state machines in this project" |
| Graduate without checking target | Creates duplication | Always grep target file for equivalent guidance |
| Graduate without user approval | Changes agent behavior permanently | Present proposals, wait for explicit approval |
| Maintain parallel file stores | Two sources of truth drift | learning.db is the single source; no L1/L2 markdown files |
