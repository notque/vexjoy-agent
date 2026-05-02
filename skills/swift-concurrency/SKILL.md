---
name: swift-concurrency
description: "Swift concurrency: async/await, Actor, Task, Sendable patterns."
user-invocable: false
context: fork
agent: swift-general-engineer
routing:
  triggers:
    - "swift concurrency"
    - "swift async await"
    - "Swift Actor"
    - "Swift Task group"
  category: swift
  pairs_with:
    - swift-testing
---

# Swift Structured Concurrency

Pattern catalog for Swift's structured concurrency: async/await, Actors, TaskGroups, AsyncSequence, Sendable, cancellation. Load the reference matching the question.

## Reference Loading Table

| Signal | Reference File | Content |
|--------|---------------|---------|
| async/await, Task, Sendable | references/fundamentals.md | async/await, Task/Task.detached, Sendable/@Sendable |
| Actor, @MainActor, nonisolated | references/actor-isolation.md | Actor isolation, MainActor UI confinement, nonisolated opt-out |
| TaskGroup, AsyncSequence, AsyncStream, cancellation | references/task-patterns.md | Structured concurrency, rate-limited groups, streams, cancellation |
| Anti-patterns, common mistakes | references/preferred-patterns.md | Blocking MainActor, task leaking, actor reentrancy hazard |

## Key Conventions

- **Prefer structured concurrency** -- `TaskGroup` over loose `Task { }` for automatic cancellation/error propagation
- **Mark types Sendable** -- enable `-strict-concurrency=complete`, resolve warnings before Swift 6
- **Use actors for shared mutable state** -- compiler-verified safety, no manual locks
- **Cancel what you create** -- every stored `Task` needs a cancellation path
- **Minimize @MainActor surface** -- isolate UI layer only; business logic and networking off main actor

## References

- `references/fundamentals.md` -- async/await, Task, Sendable basics
- `references/actor-isolation.md` -- Actor, @MainActor, nonisolated
- `references/task-patterns.md` -- TaskGroup, AsyncSequence, AsyncStream, cancellation
- `references/preferred-patterns.md` -- blocking, leaking, reentrancy mistakes
