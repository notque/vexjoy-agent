# Interview and Ambiguity Triage

Phase 3 protocol for unresolved requirements, decisions, and multi-round interviews.

## Unresolved-State Triage

| Unresolved state | Action |
|---|---|
| Low impact, reversible, or covered by a safe convention | State the assumption and execute. |
| One high impact decision owned by the current user | Ask one question with a recommendation, then execute. |
| Two or more high impact decisions owned by the current user | Use `skills/process/workflow/references/pl-depth-first-interview.md`: batch the independent frontier, then traverse genuine dependencies. Apply the bounds below. |
| Facts, constraints, preferences, or approval exist with another person | Use `skills/process/workflow/references/pl-human-source-elicitation.md`; draft the artifact and obtain authorization before sending. |
| Evidence can settle the choice faster than discussion | Use `skills/process/workflow/references/pl-empirical-prototype.md`: Question → Evidence → Verdict → Next action. |

## Interview Scope and Continuation

- **Explicit interview requests**: "interview me" or "grill me" opts into exhaustive material coverage until shared understanding or a user stop, with no arbitrary question or round cap.
- **Implicit router-initiated interviews**: earn their interruption cost through likely avoided rework and stay bounded to at most five questions and three decision rounds, plus at most one concise confirmation response. Keep every question load-bearing and skip ceremonial questions.
- **Skip-questions directives**: "Just build it", "skip questions", and equivalents apply recommended defaults and continue immediately.
- **Non-terminal rule**: an interview that suspends an active delivery objective is never terminal. Compile the decisions and automatically resume the originating build, fix, deploy, validation, or other execution flow. Report the decision artifact alone only when the user explicitly asked for an interview artifact or excluded implementation.

## Frontier Batching and Confirmation

1. Ask the current independent frontier in one logical round.
2. In Markdown, present the full frontier with a recommendation for each question and wait once.
3. When a harness-native structured question UI limits questions per call, chunk the frontier at its per-call capacity and keep the pending questions stable unless an answer invalidates a later question.
4. Reserve single-question turns for true dependency branches where the next question depends on the previous answer.
5. After the user answers the last frontier, ask one concise shared-understanding confirmation before resuming execution. Skip that extra confirmation when the user's response explicitly authorizes execution ("proceed", "build it", "looks right, continue", or equivalent).
6. Resume nested execution only after explicit proceed or confirmation. Stop at the compiled artifact when the request asked only for an interview.
