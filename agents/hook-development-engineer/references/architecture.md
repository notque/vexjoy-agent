# Hook Architecture Reference

> Loaded by hook-development-engineer when reviewing the event-driven pipeline flow or explaining how hooks integrate with Claude Code.

## Event-Driven Pipeline

```
Claude Code Session
    ↓
Event Generation (PostToolUse, PreToolUse, SessionStart)
    ↓
Hook Registry (settings.json)
    ↓
┌─────────────────────────────────────────────────────────┐
│                Hook Execution Pipeline                   │
├─────────────────────────────────────────────────────────┤
│ 1. Event JSON Input                                     │
│    - Tool name and parameters                           │
│    - Execution results and errors                       │
│    - Context and session data                           │
├─────────────────────────────────────────────────────────┤
│ 2. Error Detection & Classification                     │
│    - Pattern matching against known errors              │
│    - Error signature generation (MD5)                   │
│    - Classification into predefined types               │
├─────────────────────────────────────────────────────────┤
│ 3. Learning Database Query                              │
│    - Lookup existing patterns by signature              │
│    - Check solution confidence scores (>0.7)            │
│    - Retrieve high-confidence solutions                 │
├─────────────────────────────────────────────────────────┤
│ 4. Solution Injection                                   │
│    - Format solutions for Claude Code context          │
│    - Call context_output(EVENT, text).print_and_exit() │
│    - hook_utils handles JSON encoding to stdout         │
├─────────────────────────────────────────────────────────┤
│ 5. Learning Updates                                     │
│    - Track solution application success/failure         │
│    - Update confidence scores (+0.1/-0.2)              │
│    - Store new patterns with initial confidence 0.0     │
└─────────────────────────────────────────────────────────┘
    ↓
Context Available to Claude Code Next Tool Use
```

## Learning Database Directory Structure

```
~/.claude/learnings/
├── error_patterns.json         # Main learning database
├── error_patterns.json.bak     # Backup for recovery
├── error_patterns.lock         # File lock for atomic operations
└── debug/
    ├── classification_log.json  # Error classification history
    ├── confidence_history.json  # Confidence score evolution
    └── pattern_evolution.json   # Pattern discovery timeline
```

See [learning-database.md](learning-database.md) for schema and operations.
