## Error Handling

| Symptom | Likely Cause | Fix |
|---------|-------------|-----|
| `npx tsc --noEmit` fails after Phase 1 | Bad config template or missing types | Check `@playwright/test` is in devDependencies, verify `tsconfig.json` includes the test directory |
| Tests pass locally, fail in CI | Missing browser deps or wrong `BASE_URL` | Use `npx playwright install --with-deps` in CI; verify `BASE_URL` env var matches the running app |
| `playwright-results.json` missing after run | Reporter not configured or test runner crashed | Verify `json` reporter is in `playwright.config.ts`; check for OOM or process kill signals |
| Locator timeout on element that exists | Element present but not actionable (hidden, disabled, covered) | Use `await expect(locator).toBeVisible()` before interaction; check for overlays or modals |
| `page.fill()` appends instead of replacing | Input field has existing value | Use `locator.clear()` then `locator.fill()` |
| Flaky test passes 4/5 runs | Race condition, network timing, or animation interference | Quarantine with `test.fixme()`, reproduce with `--repeat-each=10`, check for missing `waitFor` conditions |
| Locators depending on `nth(0)` break randomly | DOM order is not stable | Add a `data-testid` to the specific element instead of relying on position |
