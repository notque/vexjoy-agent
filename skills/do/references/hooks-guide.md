# Hooks System

## Event Types

| Event | When Fires | Use Case |
|-------|------------|----------|
| `SessionStart` | Session begins | Load context, sync files |
| `UserPromptSubmit` | Before processing prompt | Inject skills, detect complexity |
| `PostToolUse` | After tool execution | Learn from errors, suggest fixes |
| `PreCompact` | Before context compression | Archive learnings |
| `Stop` | Session ends | Generate summary |

## Key Hook Features

| Feature | Description |
|---------|-------------|
| `once: true` | Hook runs only once per session |
| `timeout` | Maximum execution time in ms |
| Cascading output | Hooks can inject context into prompts |

## Error Learning

The error-learner hook automatically:
1. Detects errors in tool results
2. Looks up similar patterns in SQLite database
3. Suggests fixes if confidence ≥ 0.7
4. Adjusts confidence based on outcome
