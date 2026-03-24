# Don't Re-Ask Answered Questions

## Pattern

Before asking the user a question, check whether the answer exists in:

1. `task_plan.md` (current task context)
2. ADR files in the repository (architectural decisions)
3. Previous messages in the current conversation
4. `CLAUDE.md` or project configuration files

Only ask questions whose answers aren't already available.

## Why

Re-asking questions that have been answered erodes user trust and wastes interaction cycles. If the answer exists but is ambiguous, reference the existing answer and ask for clarification on the specific ambiguity.

## When to Apply

All investigation and implementation agents. This pattern applies whenever an agent is about to ask the user a question.

## Anti-Pattern

**What it looks like**: "What framework are you using?" when `package.json` lists React 19.
**Why wrong**: The answer is in the codebase. Reading a file is cheaper than an interaction cycle.
**Do instead**: Read the relevant config file, then state what you found and proceed.
