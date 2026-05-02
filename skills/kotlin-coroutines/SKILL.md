---
name: kotlin-coroutines
description: "Kotlin structured concurrency, Flow, and Channel patterns."
user-invocable: false
context: fork
agent: kotlin-general-engineer
routing:
  triggers:
    - "kotlin coroutines"
    - "kotlin structured concurrency"
    - "kotlin Flow"
    - "kotlin Channel"
    - "suspend function"
    - "structured concurrency kotlin"
  category: kotlin
  pairs_with:
    - kotlin-testing
---

# Kotlin Coroutines Patterns

Umbrella skill for Kotlin coroutine development: structured concurrency, cancellation, Flow, StateFlow/SharedFlow, Channels, exception handling, and dispatchers.

## Reference Loading Table

| Signal | Load These Files | Why |
|---|---|---|
| Concurrency | `concurrency-patterns.md` | Scopes, cancellation, dispatchers, exception handling |
| Flow | `flow-patterns.md` | Flow builders, StateFlow, SharedFlow, operators |
| Channels | `channel-patterns.md` | Producer-consumer, fan-in/fan-out patterns |
| Anti-patterns | `preferred-patterns.md` | GlobalScope, unstructured launch, CancellationException |

## Instructions

### Step 1: Identify the Domain

Classify the task, then load corresponding references. Only load what is needed.

| Domain | Load Reference | When |
|--------|---------------|------|
| Concurrency | `references/concurrency-patterns.md` | Scopes, cancellation, dispatchers, exception handling |
| Flow | `references/flow-patterns.md` | Flow builders, StateFlow, SharedFlow, operators |
| Channels | `references/channel-patterns.md` | Producer-consumer, fan-in/fan-out patterns |
| Anti-patterns | `references/preferred-patterns.md` | GlobalScope, unstructured launch, CancellationException |

Multiple domains may apply. Load all matching references.

### Step 2: Load and Follow the Reference

Read selected reference(s) using `${CLAUDE_SKILL_DIR}/references/<name>.md`. Follow the instructions in each reference as this skill's instructions.

### Step 3: Execute

Apply loaded reference patterns to the task. Use code examples as implementation templates.

## Key Principles

1. **Structured concurrency is non-negotiable** -- every coroutine must have a parent scope defining its lifetime.
2. **Inject dispatchers** -- accept `CoroutineDispatcher` as a parameter so callers and tests can control threading.
3. **Always rethrow CancellationException** -- rethrow immediately or catch specific exception types instead of `Exception`.
4. **Prefer Flow over Channel** -- Flow is cold, composable, and handles backpressure. Use Channels only when Flow cannot express the pattern.
5. **Use supervisorScope for partial failure tolerance** -- when independent tasks should not cancel each other.
6. **Never use GlobalScope** -- it has no lifecycle, no cancellation, no structured concurrency. Pass a scope from your application framework.
