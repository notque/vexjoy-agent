# Handoff plan template

Write every plan for an executor with no context: it has not seen the advisor
session, the audit, or the other plans. Assume it follows explicit instructions
well and is weak at filling gaps, recovering from ambiguity, and knowing when
to stop.

Three properties make a plan executable:

1. **Self-contained.** Paths, code excerpts, conventions, and commands are all
   in the file.
2. **Verification gates.** Every step ends with a command and its expected
   result. The executor never judges whether it succeeded.
3. **Boundaries and exits.** An explicit out-of-scope list, and STOP conditions
   in place of improvisation.

File name: `plans/NNN-short-slug.md`, numbered in execution order.

---

## Template

Replace every angle-bracket slot. Delete a section only where the template
marks it optional.

```markdown
# Plan NNN: <imperative title: what is true after this plan>

> **Executor instructions**: follow this plan step by step. Run every
> verification command and confirm the expected result before the next step.
> If a STOP condition occurs, stop and report. Do not improvise. Do not run
> any step marked OWNER-GATED. When done, update this plan's row in
> `plans/README.md`, unless a reviewer dispatched you and maintains the index.
>
> **Drift check (run first)**: `git diff --stat <planned-at SHA>..HEAD -- <in-scope paths>`
> If an in-scope file changed, compare the "Current state" excerpts with the
> live code. A mismatch is a STOP condition.

## Status

- **Priority**: P1 | P2 | P3
- **Effort**: S | M | L
- **Risk**: LOW | MED | HIGH
- **Depends on**: plans/NNN-*.md, or "none"
- **Category**: bug | security | perf | tests | tech-debt | deps | dx | docs | direction
- **Kind**: fix | investigate | spike
- **Planned at**: commit `<short SHA>`, <YYYY-MM-DD>
- **Issue**: <URL, only when published with --issues>

## Why this matters

2-5 sentences: the problem, its concrete cost, what improves. Intent lets the
executor make a correct call when a detail is off.

## Current state

- Each relevant file with its role:
  - `src/orders/api.ts`: order-list endpoint; holds the N+1 (lines 130-160)
- Short excerpts of today's code with `file:line` markers, enough for the
  executor to confirm it is in the right place.
- The conventions that apply, each with one exemplar: "Error handling uses the
  Result pattern; see `src/lib/result.ts` and `src/users/api.ts:40-60`. Match it."
- Lines quoted from any ADR, `CONTEXT.md`, or `DESIGN.md` this work must stay
  consistent with. The executor has not read them.

## Commands you will need

| Purpose | Command | Expected on success |
|---|---|---|
| Install | `pnpm install` | exit 0 |
| Type check | `pnpm typecheck` | exit 0, no errors |
| Tests | `pnpm test -- <filter>` | all pass |
| Lint | `pnpm lint` | exit 0 |

Use the repo's exact commands, verified in recon.

## Executor toolkit (optional)

Skills to load and what for ("load `testing` before step 3"), and docs to read
first, by path.

## Scope

**In scope** (the only files to modify):
- `src/orders/api.ts`
- `src/orders/api.test.ts` (create)

**Out of scope** (do not touch, though they look related):
- `src/orders/legacy-api.ts`: deprecated; v1 clients still pin it.
- The public response shape: clients depend on it.

## Git workflow

- Branch: `advisor/NNN-<slug>`, or the repo's convention when one is evident.
- Commit per step or logical unit. Message style: <the repo's style, with one
  example from `git log`>.
- Do not push, open a PR, merge, deploy, or tag.

## Steps

### Step 1: <imperative title>

What to do, with exact files and symbols. Include the target code shape when
it carries the design.

**Verify**: `<command>` → <expected result>

### Step 2: <imperative title>

Keep each step small enough to verify alone. Order steps so the code works
between them: add the new path, switch callers, then remove the old path.

### Step N (OWNER-GATED: <approval needed>): <title>

Describe the step for the owner. The executor skips it and reports it as
pending.

## Test plan

- New tests, their file, and the cases: the happy path, the regression this
  plan fixes, named edge cases.
- The existing test to copy the structure from: "model after
  `src/users/api.test.ts`".
- Verification: `<test command>` → all pass, including N new tests.

## Done criteria

All must hold. Each is a command and a result.

- [ ] `pnpm typecheck` exits 0
- [ ] `pnpm test` exits 0; the new tests for <X> exist and pass
- [ ] `grep -rn "<old pattern>" src/` returns no matches
- [ ] `git status --short` shows no file outside the in-scope list
- [ ] `plans/README.md` status row updated

## STOP conditions

Stop and report if:

- The code at the "Current state" locations does not match the excerpts.
- A step's verification fails twice after a reasonable fix attempt.
- The fix needs a file outside the in-scope list.
- The assumption "<this plan's key assumption>" proves false.
- A step would need a deploy, a credential, a public listener, a scheduled
  job, data deletion, or a request to a third party.

## Maintenance notes

- Future changes that interact with this ("if this endpoint gains pagination,
  revisit the batching in step 2").
- What a reviewer should check in the diff.
- Follow-ups deferred from this plan, and why.
```

---

## Index: `plans/README.md`

The advisor writes it after the plans. Executors and the advisor update it.

```markdown
# Implementation plans

Written by the improve skill on <date> at commit `<short SHA>`. Execute in the
order below unless dependencies say otherwise. Read a plan fully before
starting, honor its STOP conditions, and update your row when done.

Selection: <chosen by the owner | default top N by leverage, no user present>

## Execution order and status

| Plan | Title | Priority | Effort | Depends on | Status |
|---|---|---|---|---|---|
| 001 | <title> | P1 | S | none | TODO |
| 002 | <title> | P1 | M | 001 | TODO |

Status values: TODO, IN PROGRESS, DONE, BLOCKED (one-line reason), REJECTED
(one-line rationale), STALE (superseded by plan NNN).

## Dependency notes

- 002 needs 001 because <reason>.

## Findings considered and rejected

- <finding>: <one-line reason>. Recorded so nobody audits it again.

## Not audited

- <package or category>: <why>.
```

---

## Quality bar

Check each plan before you finish it:

| Check | Pass when |
|---|---|
| Self-contained | A model that has never seen the repo can execute it with only this file and the repo |
| Verification | Every step and done criterion is a command with an expected result |
| Exactness | Every step names files and symbols, never "the relevant module" |
| STOP conditions | At least one is specific to this plan's real risk |
| Reviewability | "Why this matters" plus "Done criteria" tell a reviewer what they approve |
| Secrets | No secret value anywhere; locations and types only |
| Drift check | "Planned at" is filled; drift-check paths equal the in-scope list |
| Excerpts | Each excerpt came from your own read of the file at the stamped commit |
| Authority | Every step that needs owner approval is marked OWNER-GATED |
