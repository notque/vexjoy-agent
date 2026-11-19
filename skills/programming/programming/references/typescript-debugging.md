---
description: "TypeScript debugging: race conditions, async/await bugs, floating promises, waterfalls, type errors, memory leaks, production runtime exceptions. Hypothesis-driven phases and STOP blocks."
type: reference
---

# TypeScript Debugging

Diagnose TypeScript type errors, async races, floating promises, waterfall
requests, and production exceptions. Use reproduction tests, stack traces,
source maps, and evidence to find the cause. Validate external data with Zod and
preserve type safety. Parallelize independent waterfall requests. Use
appropriate log levels with structured context and correlation IDs.

Not for: building components, state management, or build configuration (use the
`frontend` skill, `typescript-frontend.md`); running `tsc` and clearing reported
errors mechanically (the TypeScript section of `SKILL.md`); React Native runtime
issues and Core Web Vitals or bundle performance (use the `frontend` skill).

## Hard rules

- **No over-engineering.** Add only the debugging infrastructure the issue
  needs. Limit logging, tracing, and monitoring to what solves the current
  issue.
- **Scientific method.** State a hypothesis before any fix. No "try this and
  see" without the expected outcome.
- **Reproduction first.** Verify a fix with a reproduction case that now passes
  before calling it fixed.
- **Stack trace focus.** Ignore `node_modules` noise; start at the first line of
  application code.
- **Preserve type safety.** Fixes keep or improve type safety. Use `unknown` or
  proper types, never `any`, to silence errors.

## Defaults (on unless disabled)

- Structured (JSON) logs with context, not string concatenation.
- Suggest error boundaries for React components with async operations.
- For regressions (used to work), suggest `git bisect` to find the commit.

## Off unless requested

- **Sentry:** only when production errors need tracking; set it up with source
  maps.
- **Performance profiling:** only once a performance issue is confirmed.
- **Memory profiling:** only when a leak is suspected; heap snapshot analysis.
- **Advanced tracing:** only for complex distributed systems; correlation IDs,
  distributed tracing.

## Diagnostic tools

For TS2322 and TS2345, compare the expected and actual type structures. For
races, inspect abort controllers and cleanup timing. For production exceptions,
use source maps and a reproduction from production data. Find leaked listeners
and timers with Chrome DevTools, then verify cleanup.

## Out of scope (hand off)

| Problem | Go to |
|---|---|
| Architectural redesign | `frontend` skill (`typescript-frontend.md`) or `data` skill for database design |
| Systematic performance tuning beyond debugging | `frontend` skill (performance optimization reference) |
| Security vulnerabilities | `review` skill (system/security review) or `security` skill |
| Deployment or config infrastructure | `kubernetes` skill |

## Output format (Analysis Schema)

Before debugging:

```
<analysis>
Symptoms: [What's broken]
Hypothesis: [What I think is causing it]
Evidence: [Stack traces, logs, error messages]
Test Plan: [How to reproduce]
</analysis>
```

During debugging: show stack traces (app code), log output, debugger state if
using breakpoints, and test results.

After the fix:

- **Root Cause:** what was actually broken
- **Fix Applied:** what changed
- **Verification:** the test case that now passes
- **Prevention:** how to avoid it in future

Schema details: [output-schemas.md](../../../shared-patterns/output-schemas.md).

## Reference loading table

| Signal | Load | Why |
|---|---|---|
| race conditions, abort controller, TS2322, TS2345, type mismatch, production errors, source maps, Sentry | [debugging-workflows.md](typescript-debugging/debugging-workflows.md) | Workflows 1-3: race conditions, type errors, production runtime errors |
| floating promises, waterfall requests, error swallowing, regression, git bisect, memory leak, heap snapshot, leaked listeners/timers, debugging checklist | [debugging-workflows-async-memory.md](typescript-debugging/debugging-workflows-async-memory.md) | Workflows 4-6: async/await, git bisect, memory leaks; systematic checklist |
| type errors, hard gates, `any`, type assertions, React 19 migration, non-obvious failure modes | [engineering-rules.md](../../../frontend/frontend/references/typescript-frontend/engineering-rules.md) | House gates and the failure-mode table (inline components, `React.cache` argument equality, RSC serialization, effect remounts, localStorage throws) |

## Common scenarios

### Race conditions in async code

**Cause:** multiple async operations update state without coordination, or
cleanup runs before async work completes.
**Fix:** add abort controllers to cleanup functions, use discriminated unions for
state, implement cancellation with `useEffect` cleanup.

### Type mismatch errors

**Cause:** structural differences between expected and actual types (missing
fields, wrong types, optional vs required).
**Fix:** compare type definitions field by field, use utility types (`Partial`,
`Omit`), validate external data with Zod, fix type definitions to match reality.

### Production runtime errors

**Cause:** null/undefined values, environment differences, browser-specific
issues, timing issues only visible in production.
**Fix:** Sentry with source maps, error boundaries, defensive checks, logging
that captures context, a reproduction case from production data.

## Patterns to replace

| Pattern | Looks like | Why wrong | Do instead |
|---|---|---|---|
| Guessing without a hypothesis | "Try changing X", "Maybe add this check" | No learning; may fix the symptom, not the cause; wastes time | State a hypothesis ("X causes Y because..."), design an experiment, analyze, iterate |
| Marking fixed without reproduction | "This should fix it", "Try it and let me know" | Can't verify; may recur; root cause unproven | Failing test, fix, test passes, no regressions |
| Suppressing errors | Empty `catch`, `\|\| {}` everywhere, `any` to silence types | Hides real bugs; errors still happen at runtime | Handle errors (show, log to Sentry, retry), fix the root cause, fail fast with a clear message |

## Rationalizations to reject

| Rationalization | Why it's wrong | Required action |
|---|---|---|
| "The error is intermittent so we can't debug it" | Intermittent = race or timing issue | Add delays to force timing; build a reproduction |
| "It works on my machine" | The environment difference is the clue | Document differences; test in a production-like environment |
| "The type error is TypeScript being wrong" | Types reflect runtime reality | Compare types to the actual data; fix the mismatch |
| "We lack time for root cause analysis" | Quick fixes cause future bugs | Invest in reproduction + test case |

## Blockers

Resolve routine issues from repository evidence and existing authorization. When
sure, decide, record the assumption in the report, and continue; ask Jev when
genuinely unsure. Ask only when these situations leave a material decision
uncovered. Rows marked **(owner)** guard production, destructive, credential,
public-exposure, or persistence actions: get explicit owner confirmation first.

| Situation | Why stop | Ask |
|---|---|---|
| Cannot reproduce the bug | Different environment/data needed | "Can you provide exact steps, environment, and data that trigger this?" |
| Multiple possible causes | Scope needs narrowing | "Does this happen in local dev, staging, or only production?" |
| Breaking changes needed | Coordination required | "Fix requires changing the API contract - proceed?" |
| Production access needed **(owner)** | Security/permissions | "Can you provide production logs/stack traces?" |
| Git history unclear | Need the last good commit | "When did this start? Which commit last worked?" |

Never assume without evidence: the root cause (stack trace, logs,
reproduction), environment differences (actual env vars, config), the user flow
(exact steps), or the data shape (example input).

## Debugging phases

1. **Reproduce:** understand symptoms; gather stack traces, logs, error
   messages; build a minimal reproduction; confirm it is reliable. Gate on a
   reliable reproduction.
2. **Hypothesize:** state "I believe X causes Y because Z"; name the evidence
   that would prove or disprove it; design the experiment.
3. **Experiment:** run it; collect logs, stack traces, state; compare to the
   prediction.
4. **Analyze and iterate:** if results match, implement the fix; if not, revise
   the hypothesis and return to step 2.
5. **Verify:** reproduction passes, no regressions, root cause understood,
   prevention added (test, better types, validation).

## Verification STOP blocks

- **After writing a fix:** STOP. Run the reproduction test and show the output.
  A fix without a passing test is a guess.
- **After claiming the root cause:** STOP. Explain WHY the bug happened, not just
  WHERE. If you can only point to a line, keep investigating.
- **After completing the debug:** STOP. Run `npx tsc --noEmit` and the full test
  suite before reporting. Show the actual output.
- **Before editing a file:** read it first. Blind edits cause new bugs that mask
  the original.
- **Before committing a fix:** do not commit to main. Create a feature branch.

## Related skills

- `workflow` for multi-phase tasks and planning.
- `frontend` for TypeScript frontend architecture (load
  `typescript-frontend.md`).
