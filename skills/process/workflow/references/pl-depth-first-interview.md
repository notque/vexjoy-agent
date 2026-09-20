# Decision-frontier interview

Prime from repository evidence before asking. Build a graph of unresolved
decisions; a question enters the current frontier only when its answer does not
depend on another unanswered question. Ask that frontier as one batch, each with
a recommendation and consequence. Use answers to expose the next frontier.

Stop when action-changing branches are resolved or the user defers them. Output:

```markdown
## Resolved decisions
- <decision>: <choice> — <source/reason>
## Carried forward
- <open choice>: <owner and consequence>
## Scope boundary
- <included / excluded>
```

For an implicit interview, cap questioning at the smallest set required to act;
return unresolved high-impact branches instead of silently assuming them.
