# Report self-review

One revision pass over a synthesized final report. It removes or corrects claims the agents' evidence does not support, so the user reads only supported claims.

## When to run

Run it when a report is synthesized from the outputs of two or more dispatched agents:

- `/do` Complex fan-in: several agents feed one report to the user.
- `research` and `assessment` final reports built from dispatched agents' findings.

Skip it for Trivial, Simple, and Medium routes, for one agent's own output, and for reports with no checkable claims.

## How to run

1. Write the draft report.
2. Dispatch one separate agent with `model: opus` and read-only tools (Read, Grep, Glob). Use a fresh dispatch: the author of the draft does not review it.
3. Give it the prompt below, with the request verbatim, the evidence, and the draft. Evidence is each agent's full output and the paths of the files those outputs cite.
4. Deliver the revised report it returns. Run the pass once.
5. If the reply is empty or under 30% of the draft's length, retry once, then deliver the draft.

The pass adds no new claims, so it adds no new sources. Content the reviewer finds correct stays as written.

## Prompt

```
You are the orchestrator of a multi-agent task. You sent subagents to work on the user's request and you ran
tools yourself. Their complete outputs and the files they cite are the EVIDENCE below, in the order you
received them. You wrote the DRAFT REPORT below for the user.

TASK
Check every claim in the draft against the evidence. Fix each claim that the evidence contradicts or does not
support: correct it to what the evidence says, or remove it. Read cited files when an output refers to them.
Add no new claims. Leave correct content, structure, and tone as they are.

Output only the full revised report text, with no notes about what you changed.

REQUEST:
<request verbatim>

EVIDENCE:
<each agent's output and cited file paths>

DRAFT REPORT:
<draft>
```
