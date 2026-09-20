# Objective state schema

Path: `.objective/<lowercase-hyphen-slug>/state.md`.

```markdown
# Objective: <frozen outcome>
Status: ACTIVE | DONE | NOT-DONE
Iteration: <current>/<budget>
## Done criteria
- command: `<command>`; expect: <exit/output>
- rubric: <verbatim frozen rubric>; grader: fresh context
## Guardrails
- <forbidden shortcut>
## Iteration log
### <n> — <ISO-8601>
- action/receipt:
- criterion results:
- remaining gap:
## Next planned step
<smallest action>
```

Wakeups read this file, not chat memory. Append observed results; never rewrite
earlier receipts or silently alter frozen criteria.
