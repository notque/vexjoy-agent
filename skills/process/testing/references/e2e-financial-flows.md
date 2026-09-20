# Financial E2E safeguards

- Refuse destructive payment/refund tests unless the target is positively
  identified as local/test and the provider as sandbox. Absence of production
  markers is not sufficient evidence.
- Assert money as integer minor units and verify currency, fees, rounding, and
  total invariants—not merely success text.
- Use provider-generated sandbox fixtures; never copy live tokens or customer
  identifiers into test state.
- Treat redirects, webhooks, and settlement as asynchronous. Poll an observable
  backend/UI state with a deadline and diagnostic receipt; fixed sleeps conceal
  races.
- Exercise duplicate webhook/request delivery and assert idempotency: one ledger
  mutation, stable external identifier, and replay-safe response.
- For decline, authentication, cancellation, and refund cases, verify both user
  state and ledger/order state. A UI error alone does not prove rollback.
