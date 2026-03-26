# Playwright Patterns Reference

Detailed patterns for the `e2e-testing` skill. These are progressive-disclosure
supplements — the main SKILL.md covers the core workflow; this file covers
patterns you reach for once the basics are in place.

---

## Full POM Class Example

```typescript
// pages/CheckoutPage.ts
import { type Page, type Locator } from '@playwright/test';

export class CheckoutPage {
  readonly page: Page;
  readonly cartSummary: Locator;
  readonly promoCodeInput: Locator;
  readonly applyPromoButton: Locator;
  readonly promoSuccessMsg: Locator;
  readonly promoErrorMsg: Locator;
  readonly placeOrderButton: Locator;
  readonly orderConfirmation: Locator;

  constructor(page: Page) {
    this.page             = page;
    this.cartSummary      = page.getByTestId('checkout-cart-summary');
    this.promoCodeInput   = page.getByTestId('checkout-promo-input');
    this.applyPromoButton = page.getByTestId('checkout-promo-apply');
    this.promoSuccessMsg  = page.getByTestId('checkout-promo-success');
    this.promoErrorMsg    = page.getByTestId('checkout-promo-error');
    this.placeOrderButton = page.getByTestId('checkout-place-order');
    this.orderConfirmation = page.getByTestId('checkout-order-confirmation');
  }

  async goto() {
    await this.page.goto('/checkout');
    await this.page.waitForLoadState('networkidle');
  }

  async applyPromoCode(code: string) {
    await this.promoCodeInput.fill(code);
    await this.applyPromoButton.click();
  }

  async placeOrder() {
    await this.placeOrderButton.click();
    // Wait for confirmation element, not arbitrary timeout
    await this.orderConfirmation.waitFor({ state: 'visible' });
  }
}
```

```typescript
// tests/e2e/features/checkout.spec.ts
import { test, expect } from '@playwright/test';
import { CheckoutPage } from '../../../pages/CheckoutPage';
import { LoginPage } from '../../../pages/LoginPage';

test.describe('Checkout Flow', () => {
  test.beforeEach(async ({ page }) => {
    const login = new LoginPage(page);
    await login.goto();
    await login.login('test@example.com', 'password');
  });

  test('valid promo code applies discount', async ({ page }) => {
    const checkout = new CheckoutPage(page);
    await checkout.goto();
    await checkout.applyPromoCode('SAVE10');
    await expect(checkout.promoSuccessMsg).toBeVisible();
    await expect(checkout.promoSuccessMsg).toContainText('10% off');
  });

  test('invalid promo code shows error', async ({ page }) => {
    const checkout = new CheckoutPage(page);
    await checkout.goto();
    await checkout.applyPromoCode('BADCODE');
    await expect(checkout.promoErrorMsg).toBeVisible();
  });

  test('order completes and shows confirmation', async ({ page }) => {
    const checkout = new CheckoutPage(page);
    await checkout.goto();
    await checkout.placeOrder();
    await expect(checkout.orderConfirmation).toBeVisible();
  });
});
```

---

## Condition-Based Waiting Patterns

### Wait for network response

Use when an action triggers an API call and you need to assert on the result:

```typescript
// Wait for a specific API response before asserting
const [response] = await Promise.all([
  page.waitForResponse(resp =>
    resp.url().includes('/api/orders') && resp.status() === 200
  ),
  checkout.placeOrderButton.click(),
]);
const data = await response.json();
expect(data.orderId).toBeDefined();
```

### Wait for element state

```typescript
// Wait for element to appear
await page.getByTestId('loading-spinner').waitFor({ state: 'hidden' });
await page.getByTestId('results-list').waitFor({ state: 'visible' });

// Wait for element to contain text
await expect(page.getByTestId('status-badge')).toContainText('Complete');

// Wait for URL change
await expect(page).toHaveURL(/\/dashboard/);
```

### Wait for load state

```typescript
// After navigation or form submit
await page.waitForLoadState('networkidle');   // No pending XHR/fetch
await page.waitForLoadState('domcontentloaded'); // DOM parsed
await page.waitForLoadState('load');          // All resources loaded
```

### Wait for element count

```typescript
// Wait until a list has items
await expect(page.getByTestId('product-card')).toHaveCount(5);
// Wait until empty
await expect(page.getByTestId('cart-item')).toHaveCount(0);
```

---

## Multi-Browser Configuration

### Full matrix (default)

```typescript
// playwright.config.ts
projects: [
  { name: 'chromium', use: { ...devices['Desktop Chrome'] } },
  { name: 'firefox',  use: { ...devices['Desktop Firefox'] } },
  { name: 'webkit',   use: { ...devices['Desktop Safari'] } },
  { name: 'Mobile Chrome', use: { ...devices['Pixel 5'] } },
  { name: 'Mobile Safari', use: { ...devices['iPhone 12'] } },
],
```

### CI-only subset (cost/time trade-off)

```typescript
// playwright.config.ts
projects: process.env.CI
  ? [
      { name: 'chromium', use: { ...devices['Desktop Chrome'] } },
      { name: 'Mobile Chrome', use: { ...devices['Pixel 5'] } },
    ]
  : [
      { name: 'chromium', use: { ...devices['Desktop Chrome'] } },
      { name: 'firefox',  use: { ...devices['Desktop Firefox'] } },
      { name: 'webkit',   use: { ...devices['Desktop Safari'] } },
    ],
```

### Browser-specific test

```typescript
import { test, expect } from '@playwright/test';

// Run only on webkit — use sparingly, prefer cross-browser tests
test('safari-specific rendering', async ({ page, browserName }) => {
  test.skip(browserName !== 'webkit', 'WebKit only');
  // ...
});
```

---

## Financial / Production Skip Guards

Protect against running destructive financial flows in production or shared staging:

```typescript
// Skip entire describe block in production
test.describe('Payment Flow', () => {
  test.skip(
    process.env.NODE_ENV === 'production',
    'Payment tests skipped in production environment'
  );

  test('credit card charge succeeds', async ({ page }) => {
    // ...
  });
});
```

```typescript
// Skip based on BASE_URL to protect staging shared with real users
test.beforeEach(async () => {
  test.skip(
    !process.env.BASE_URL?.includes('localhost') &&
    !process.env.BASE_URL?.includes('e2e.'),
    'Skipping destructive test: not on local or dedicated E2E environment'
  );
});
```

```typescript
// Guard for blockchain/async confirmation waits
// Do NOT use waitForTimeout — poll for confirmation state instead
async function waitForTransactionConfirmed(page: Page, txId: string) {
  await expect(async () => {
    const status = await page.getByTestId(`tx-status-${txId}`).textContent();
    expect(status).toBe('Confirmed');
  }).toPass({ timeout: 30_000, intervals: [1000, 2000, 5000] });
}
```

---

## Shared Authentication State

Avoid logging in for every test — use `storageState` to reuse sessions:

```typescript
// tests/e2e/auth/setup.ts (global setup)
import { chromium, type FullConfig } from '@playwright/test';

async function globalSetup(config: FullConfig) {
  const browser = await chromium.launch();
  const page = await browser.newPage();
  await page.goto('http://localhost:3000/login');
  await page.getByTestId('login-email').fill('test@example.com');
  await page.getByTestId('login-password').fill('password');
  await page.getByTestId('login-submit').click();
  await page.waitForURL('/dashboard');
  // Save storage state (cookies, localStorage)
  await page.context().storageState({ path: 'playwright/.auth/user.json' });
  await browser.close();
}

export default globalSetup;
```

```typescript
// playwright.config.ts
import { defineConfig } from '@playwright/test';

export default defineConfig({
  globalSetup: require.resolve('./tests/e2e/auth/setup'),
  projects: [
    {
      name: 'authenticated',
      use: {
        storageState: 'playwright/.auth/user.json',
      },
    },
    {
      name: 'unauthenticated',
      // No storageState — tests run without session
    },
  ],
});
```

---

## Viewport and Responsive Testing

```typescript
test('mobile navigation menu opens', async ({ page }) => {
  await page.setViewportSize({ width: 375, height: 667 }); // iPhone SE
  await page.goto('/');
  await page.getByTestId('mobile-menu-toggle').click();
  await expect(page.getByTestId('mobile-nav')).toBeVisible();
});
```

---

## Accessibility Assertions

```typescript
import { test, expect } from '@playwright/test';
import AxeBuilder from '@axe-core/playwright';

test('checkout page has no accessibility violations', async ({ page }) => {
  await page.goto('/checkout');
  const results = await new AxeBuilder({ page })
    .withTags(['wcag2a', 'wcag2aa'])
    .analyze();
  expect(results.violations).toEqual([]);
});
```
