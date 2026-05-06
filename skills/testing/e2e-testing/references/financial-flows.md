# Financial Flow Patterns

Production skip guards and async confirmation wait patterns for financial E2E tests.

---

## Production Skip Guards

Always guard destructive financial tests with environment checks:

```typescript
// At describe level — skips entire suite
test.describe('Payment Processing', () => {
  test.skip(
    process.env.NODE_ENV === 'production',
    'Payment tests must not run in production'
  );

  test.skip(
    !['localhost', 'e2e.', 'test.'].some(h =>
      process.env.BASE_URL?.includes(h)
    ),
    'Payment tests only run on local, e2e, or test environments'
  );

  // ... tests
});
```

```typescript
// At individual test level
test('refund processes correctly', async ({ page }) => {
  test.skip(
    process.env.PAYMENT_PROVIDER !== 'sandbox',
    'Refund test requires sandbox payment provider'
  );
  // ...
});
```

---

## Polling for Async Confirmation

Financial operations often involve async backend confirmation. Use `toPass` to poll:

```typescript
import { expect } from '@playwright/test';

async function waitForPaymentConfirmed(page: Page, orderId: string) {
  await expect(async () => {
    const statusEl = page.getByTestId(`order-status-${orderId}`);
    await expect(statusEl).toHaveText('Payment confirmed');
  }).toPass({
    timeout: 30_000,
    intervals: [1000, 2000, 5000, 10000],
  });
}
```

---

## Stripe Test Cards

Use Stripe test card numbers in sandbox environments:

| Scenario | Card Number |
|----------|-------------|
| Success | 4242 4242 4242 4242 |
| Insufficient funds | 4000 0000 0000 9995 |
| 3D Secure required | 4000 0025 0000 3155 |
| Generic decline | 4000 0000 0000 0002 |

Always use expiry `12/34`, CVC `123`, ZIP `00000` for test cards.
