# Testing Automation Anti-Patterns

Common testing mistakes to avoid with examples.

## ❌ Anti-Pattern 1: Testing Implementation Details

**What it looks like:**
```typescript
// BAD: Testing internal state and implementation
it('updates internal counter', () => {
  const component = render(<Counter />)
  expect(component.state.count).toBe(0)
  component.instance().incrementCounter()
  expect(component.state.count).toBe(1)
})
```

**Why it's wrong:**
- Tests break when refactoring internal implementation
- Not testing actual user-facing behavior
- Creates brittle, maintenance-heavy test suites
- Couples tests to component internals instead of public API

**✅ Do this instead:**
```typescript
// GOOD: Testing user-visible behavior
it('displays incremented count when button clicked', async () => {
  const user = userEvent.setup()
  render(<Counter />)

  expect(screen.getByText('Count: 0')).toBeInTheDocument()
  await user.click(screen.getByRole('button', { name: /increment/i }))
  expect(screen.getByText('Count: 1')).toBeInTheDocument()
})
```

---

## ❌ Anti-Pattern 2: Shared Test State and Dependencies

**What it looks like:**
```typescript
// BAD: Tests depend on execution order
describe('User workflow', () => {
  let userId: string

  it('creates user', async () => {
    const user = await createUser({ name: 'Test' })
    userId = user.id  // Shared state!
  })

  it('updates user', async () => {
    await updateUser(userId, { name: 'Updated' })  // Depends on previous test
  })
})
```

**Why it's wrong:**
- Tests fail when run in isolation or different order
- Debugging becomes nightmare when one test affects others
- Cannot parallelize test execution
- Violates fundamental test isolation principle

**✅ Do this instead:**
```typescript
// GOOD: Each test completely independent
describe('User workflow', () => {
  it('creates user', async () => {
    const user = await createUser({ name: 'Test' })
    expect(user.id).toBeDefined()
    expect(user.name).toBe('Test')
  })

  it('updates user', async () => {
    // Setup within test
    const user = await createUser({ name: 'Test' })
    const updated = await updateUser(user.id, { name: 'Updated' })
    expect(updated.name).toBe('Updated')
  })
})
```

---

## ❌ Anti-Pattern 3: Mocking Everything (Over-Mocking)

**What it looks like:**
```typescript
// BAD: Mocking dependencies that should be tested together
it('calculates total price', () => {
  const mockTaxCalculator = vi.fn(() => 10)
  const mockShippingCalculator = vi.fn(() => 5)
  const mockDiscountCalculator = vi.fn(() => 2)

  const total = calculateTotal(100, {
    tax: mockTaxCalculator,
    shipping: mockShippingCalculator,
    discount: mockDiscountCalculator
  })

  expect(total).toBe(113)  // Just testing mock return values!
})
```

**Why it's wrong:**
- Not testing actual integration between components
- Mocks can drift from real implementation behavior
- False confidence - tests pass but real code breaks
- Missing integration bugs that matter to users

**✅ Do this instead:**
```typescript
// GOOD: Mock only external dependencies (APIs, databases)
it('calculates total price with tax and shipping', () => {
  // Real calculators, mock only external API calls
  const total = calculateTotal(100, {
    taxRate: 0.10,
    shippingCost: 5,
    discountCode: 'SAVE2'
  })

  expect(total).toBe(113)  // Testing real calculation logic
})

// Mock only at boundaries
it('fetches user orders from API', async () => {
  server.use(
    http.get('/api/orders', () => {
      return HttpResponse.json({ orders: [mockOrder] })
    })
  )

  const orders = await getUserOrders('user-123')
  expect(orders).toHaveLength(1)
})
```

---

## ❌ Anti-Pattern 4: No Assertions or Weak Assertions

**What it looks like:**
```typescript
// BAD: Test passes but validates nothing
it('renders product page', async () => {
  render(<ProductPage slug="test-product" />)
  await waitFor(() => {
    screen.getByText(/product/i)  // No assertion!
  })
})

// BAD: Weak assertion that always passes
it('calculates discount', () => {
  const discount = calculateDiscount(100, 0.10)
  expect(discount).toBeDefined()  // Tells us nothing!
})
```

**Why it's wrong:**
- Tests give false confidence - they pass even when code broken
- Don't actually verify correct behavior
- Waste CI/CD time without providing value
- Can mask regressions and bugs

**✅ Do this instead:**
```typescript
// GOOD: Strong, specific assertions
it('renders product page with correct details', async () => {
  render(<ProductPage slug="test-product" />)

  await waitFor(() => {
    expect(screen.getByText('Test Product')).toBeInTheDocument()
  })

  expect(screen.getByText('$99.99')).toBeInTheDocument()
  expect(screen.getByRole('img', { name: /test product/i })).toHaveAttribute('src')
  expect(screen.getByRole('button', { name: /add to cart/i })).toBeEnabled()
})

// GOOD: Assert specific values
it('calculates 10% discount correctly', () => {
  expect(calculateDiscount(100, 0.10)).toBe(10)
  expect(calculateDiscount(50, 0.10)).toBe(5)
  expect(calculateDiscount(0, 0.10)).toBe(0)
})
```

---

## ❌ Anti-Pattern 5: Flaky Tests Without Root Cause Investigation

**What it looks like:**
```typescript
// BAD: Adding arbitrary waits and retries
it('displays notification', async () => {
  render(<App />)

  await user.click(screen.getByRole('button'))

  await new Promise(resolve => setTimeout(resolve, 2000))  // Random wait!

  // Sometimes works, sometimes doesn't
  expect(screen.getByText(/success/i)).toBeInTheDocument()
})
```

**Why it's wrong:**
- Masks real timing issues in application
- Slows down test suite with unnecessary waits
- Tests remain unreliable even with retries
- Indicates underlying architectural problems

**✅ Do this instead:**
```typescript
// GOOD: Use proper waiting strategies
it('displays notification after successful action', async () => {
  const user = userEvent.setup()
  render(<App />)

  await user.click(screen.getByRole('button', { name: /submit/i }))

  // Wait for specific condition
  await waitFor(() => {
    expect(screen.getByText(/success/i)).toBeInTheDocument()
  }, { timeout: 5000 })
})

// GOOD: Find and fix root cause
it('handles async state updates correctly', async () => {
  const user = userEvent.setup()
  render(<App />)

  // Mock async operation with controlled timing
  server.use(
    http.post('/api/submit', async () => {
      return HttpResponse.json({ success: true })
    })
  )

  await user.click(screen.getByRole('button'))

  // Properly wait for API response
  await waitFor(() => {
    expect(screen.queryByRole('status')).not.toBeInTheDocument()
  })

  expect(screen.getByText(/success/i)).toBeInTheDocument()
})
```

---

## ❌ Anti-Pattern 6: Ignoring Test Coverage Gaps

**What it looks like:**
```typescript
// BAD: Only testing happy path
it('processes payment successfully', async () => {
  const result = await processPayment(validCard, 100)
  expect(result.success).toBe(true)
})

// Missing: error cases, edge cases, validation
```

**Why it's wrong:**
- Bugs hide in untested error paths and edge cases
- Production failures from unhandled scenarios
- Coverage metrics misleading (high line coverage, low path coverage)
- False confidence in code reliability

**✅ Do this instead:**
```typescript
// GOOD: Test happy path, error cases, and edge cases
describe('Payment processing', () => {
  it('processes valid payment successfully', async () => {
    const result = await processPayment(validCard, 100)
    expect(result.success).toBe(true)
    expect(result.transactionId).toBeDefined()
  })

  it('rejects invalid card number', async () => {
    await expect(
      processPayment(invalidCard, 100)
    ).rejects.toThrow('Invalid card number')
  })

  it('rejects amount below minimum', async () => {
    await expect(
      processPayment(validCard, 0.50)
    ).rejects.toThrow('Minimum payment is $1.00')
  })

  it('handles network timeout', async () => {
    server.use(
      http.post('/api/payment', () => {
        return new Promise(() => {})  // Never resolves
      })
    )

    await expect(
      processPayment(validCard, 100, { timeout: 1000 })
    ).rejects.toThrow('Payment timeout')
  })

  it('handles maximum amount correctly', async () => {
    const result = await processPayment(validCard, 999999.99)
    expect(result.success).toBe(true)
  })
})
```

---

## Summary: Testing Automation Checklist

Before implementing tests, verify:

1. ✅ Testing user-visible behavior, not implementation details
2. ✅ Each test completely isolated and independent
3. ✅ Mocking only external dependencies (APIs, databases, third-party services)
4. ✅ Strong, specific assertions that validate actual behavior
5. ✅ Proper async waiting strategies (no arbitrary timeouts)
6. ✅ Coverage of happy path, error cases, and edge cases
7. ✅ Tests can run in any order and in parallel
8. ✅ Test names clearly describe what they verify
9. ✅ Setup/teardown in beforeEach/afterEach, not shared variables
10. ✅ Fast execution (<1s per test for unit tests)

## Common Test Smells

| Smell | Indicator | Fix |
|-------|-----------|-----|
| Long test | >50 lines | Break into multiple focused tests |
| Unclear name | "test1", "it works" | Describe behavior: "displays error when invalid input" |
| Multiple assertions | Testing 5+ things | One concept per test |
| Deep setup | 20+ lines of setup | Extract to factory function |
| setTimeout | Arbitrary waits | Use waitFor with condition |
| test.skip | Skipped tests | Fix or remove, don't skip |
| Intermittent failure | Passes 80% of time | Find root cause, don't retry |
