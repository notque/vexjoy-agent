---
name: testing
description: "Testing contracts: evidence, agent evaluation, Playwright edge domains, and completion verification."
user-invocable: false
allowed-tools: [Read, Write, Bash, Grep, Glob, Edit, Task, Skill, Agent]
agent: testing-automation-engineer
routing:
  not_for: "code review (use review), linting (use code-quality)"
  triggers: ["TDD", "test first", "flaky test", "test agents", "agent testing", "vitest", "playwright", "E2E test", "verify completion", "run tests"]
  category: testing
  pairs_with: [review, code-quality, workflow]
---

# Testing

Use repository test commands and conventions. A check-only request does not
authorize changing tests, dependencies, configuration, or product code.

## Contracts

- A RED result must fail for the missing behavior, not import, syntax, fixture,
  or environment setup. Record the command and observed failure before coding.
- After the smallest implementation passes its focused test, run the affected
  suite. Shared behavior requires the broader repository gate.
- Do not weaken, delete, skip, quarantine, or rewrite a failing assertion merely
  to obtain green. If the assertion is wrong, establish intended behavior from
  source evidence before changing it.
- Flakiness requires repeated runs with retries disabled. Preserve the failing
  seed, trace, or timing evidence; a retry-assisted pass is not a fix.
- Use the project-installed runner. For Vitest use `vitest run`; bare `vitest`
  enters watch mode. Capture the exit code—partial output is not a pass.
- Playwright failures retain trace/screenshot/video when configured. Prefer
  accessible or test-id locators; fixed sleeps are valid only when timing itself
  is the behavior under test.

## Agent evaluations

Test agent behavior in fresh contexts, not prompt wording. Freeze inputs and
expected action-changing claims, and rerun the entire case set after each prompt
or routing change. Include positive, negative, malformed,
ambiguous, and boundary cases. A consistency run checks whether structure and
key findings survive repetition; it does not require identical prose.

Load `references/agents-examples-and-errors.md` for this toolkit's dispatch and
capture failure cases.

## Narrow E2E domains

Load only when applicable:

- `references/e2e-wallet-testing.md` — extension wallets, popup/page switching,
  signing, chain/account state.
- `references/e2e-financial-flows.md` — monetary invariants, webhook/idempotency,
  and sandbox-vs-production safeguards.

## Completion evidence

Before a success claim:

1. Inspect the actual diff and affected call paths.
2. Run the repository-required focused checks, then the required broader gate.
3. For new integrations establish **exists → substantive → wired → data flows**.
4. Rerun after fixes; inherited or pre-edit results do not cover changed code.
5. Report commands, exit codes, scope, counts, and anything not run.

A failed required check blocks a success claim. Missing tools, credentials, or
environment make a check **unrun**, never passed. Load
`references/verify-checklist.md` only for migrations, compatibility surfaces,
or cross-component wiring.

When a test fails, classify product defect, test defect, environment,
fixture/setup, or nondeterminism from the evidence. Fix only within authorized
scope and rerun the same command. Preserve diagnostics when blocked.
