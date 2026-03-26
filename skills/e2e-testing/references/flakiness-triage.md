# Flakiness Triage Guide

Decision tree and commands for identifying, reproducing, and quarantining flaky tests.

---

## Step 1: Reproduce

Before quarantining, confirm the test is actually flaky (not consistently failing):

```bash
# Run a single test 5 times
npx playwright test tests/e2e/features/checkout.spec.ts --repeat-each=5

# Run with verbose output to see timing
npx playwright test tests/e2e/features/checkout.spec.ts --repeat-each=5 --reporter=list

# Run with retries disabled (isolates the flakiness)
npx playwright test tests/e2e/features/checkout.spec.ts --retries=0 --repeat-each=10
```

If it fails at least once in 5 runs → flaky. If it fails every run → consistently broken.

---

## Step 2: Categorise

| Symptom | Likely Cause | Fix |
|---------|-------------|-----|
| `Timeout waiting for element` | Race between render and assertion | Use `waitFor({ state: 'visible' })` |
| `Element not found` with correct testid | Page navigated or re-rendered | Add `waitForLoadState('networkidle')` |
| `Expected X, received Y` intermittently | Async data race | Wait for API response before asserting |
| `Element intercepted by another element` | Overlay still visible | Wait for overlay to disappear first |
| Fails only in parallel | Shared state between tests | Ensure each test has isolated setup |
| Fails only on CI | Slower CI machines | Increase `timeout` in test config, not `waitForTimeout` |

---

## Step 3: Fix or Quarantine

**Fix first** — if the root cause is clear and fixable in under 30 minutes, fix it.

**Quarantine** if:
- Root cause is unclear and needs investigation
- Fix requires changes outside the test suite (backend, infra)
- The test is blocking CI on an otherwise-healthy branch

```typescript
// Quarantine pattern
test.fixme('checkout completes with slow network', async ({ page }) => {
  // FLAKY: Times out under CI load — suspect race in payment webhook
  // TODO: #789 — add explicit waitForResponse on /api/webhooks/payment
  ...
});
```

---

## Step 4: Verify Fix

Before removing `test.fixme`:

```bash
# Must pass 10 out of 10 with retries disabled
npx playwright test tests/e2e/features/checkout.spec.ts --repeat-each=10 --retries=0
```

If 10/10 clean, remove `test.fixme`. If not, leave quarantined and update the TODO.

---

## Playwright Retry Config vs. --repeat-each

| Flag | Purpose |
|------|---------|
| `--retries=N` | Automatically retry a failed test N times (masks flakiness in CI) |
| `--repeat-each=N` | Run every test N times regardless of result (exposes flakiness) |

Use `--retries` in CI to stabilise the pipeline. Use `--repeat-each` locally to diagnose.
Never use `--retries` as a substitute for fixing a flaky test.
