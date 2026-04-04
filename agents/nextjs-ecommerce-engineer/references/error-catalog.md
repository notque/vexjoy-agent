# Error Catalog Reference
<!-- Loaded by nextjs-ecommerce-engineer when task involves error handling, payment failures, webhook errors, or inventory conflicts -->

E-commerce errors fall into four categories: payment failures (user-recoverable), auth errors (session/permission), inventory conflicts (race conditions), and infrastructure errors (rate limits, webhooks).

## Payment Failures

### Card Declined
**Stripe code:** `card_declined`
**User message:** "Your card was declined. Please try a different payment method."
**Recovery:** Show alternative payment method options. Do not retry automatically.

```typescript
function mapStripeError(error: Stripe.StripeError): string {
  switch (error.code) {
    case 'card_declined':
      return error.decline_code === 'insufficient_funds'
        ? 'Your card has insufficient funds. Please try a different card.'
        : 'Your card was declined. Please try a different payment method.'
    case 'expired_card':
      return 'Your card has expired. Please update your payment method.'
    case 'incorrect_cvc':
      return 'Your security code is incorrect. Please check and try again.'
    case 'processing_error':
      return 'A processing error occurred. Please try again in a moment.'
    case 'authentication_required':
      return 'Your bank requires additional verification. Please complete authentication.'
    default:
      return 'Payment could not be processed. Please try a different method.'
  }
}
```

### Insufficient Funds
**Stripe decline_code:** `insufficient_funds`
**What happens:** Payment Intent created, confirmation fails.
**Recovery:** Show specific message about insufficient funds, suggest alternative card.

### Expired Card
**Stripe code:** `expired_card`
**What happens:** Stripe rejects the card before creating a Payment Intent.
**Recovery:** Prompt user to update card details.

### Authentication Required (3D Secure)
**Stripe code:** `authentication_required`
**What happens:** Bank requires 3DS challenge; `stripe.confirmPayment` triggers the flow automatically with Elements.
**Recovery:** Handled automatically by Stripe Elements — no special code needed unless using manual confirmation.

---

## Auth Errors

### Unauthenticated Access to Protected Route
**HTTP status:** 401
**Cause:** Session expired or user not logged in.

```typescript
// middleware.ts — redirect to login for protected routes
import { NextResponse } from 'next/server'
import type { NextRequest } from 'next/server'
import { getToken } from 'next-auth/jwt'

export async function middleware(request: NextRequest) {
  const PROTECTED = ['/account', '/orders', '/admin']
  const isProtected = PROTECTED.some(path => request.nextUrl.pathname.startsWith(path))

  if (!isProtected) return NextResponse.next()

  const token = await getToken({ req: request })
  if (!token) {
    const loginUrl = new URL('/login', request.url)
    loginUrl.searchParams.set('callbackUrl', request.nextUrl.pathname)
    return NextResponse.redirect(loginUrl)
  }

  return NextResponse.next()
}
```

### Insufficient Permissions (Admin Routes)
**HTTP status:** 403
**Cause:** Authenticated user accessing admin-only resource.

```typescript
// Verify admin role in Server Component
import { getServerSession } from 'next-auth'
import { authOptions } from '@/lib/auth'

export default async function AdminPage() {
  const session = await getServerSession(authOptions)

  if (session?.user?.role !== 'admin') {
    notFound() // Prefer notFound() over forbidden() to avoid revealing admin routes exist
  }

  return <AdminDashboard />
}
```

---

## Inventory Conflicts

### Out of Stock at Checkout
**When it happens:** Product was in stock when added to cart, sold out before payment confirmation.

```typescript
// actions/checkout.ts — validate stock before creating order
export async function validateCartStock(cartId: string): Promise<{
  valid: boolean
  outOfStock: Array<{ productId: string; name: string; available: number }>
}> {
  const cart = await db.cart.findUniqueOrThrow({
    where: { id: cartId },
    include: { items: { include: { product: true } } },
  })

  const outOfStock = cart.items
    .filter(item => item.product.stock < item.quantity)
    .map(item => ({
      productId: item.productId,
      name: item.product.name,
      available: item.product.stock,
    }))

  return { valid: outOfStock.length === 0, outOfStock }
}
```

Show the user which items are unavailable and offer to adjust quantities or remove items.

### Oversell Race Condition
**When it happens:** Two users purchase the last unit simultaneously.
**Solution:** Atomic transaction with pessimistic lock — see `shopping-cart-patterns.md`.

---

## Webhook Delivery Failures

### Signature Verification Failed
**Cause:** Raw body was parsed before signature check, or wrong webhook secret.

```typescript
// Correct: read raw body BEFORE any parsing
export async function POST(req: Request) {
  const body = await req.text()  // NOT req.json()
  const sig = headers().get('stripe-signature')!
  // ...
}
```

**Debugging:** Use `stripe listen` locally to see the exact body and signature Stripe sends.

### Webhook Timeout
**Cause:** Handler is doing too much work synchronously.
**Solution:** Acknowledge immediately, process asynchronously.

```typescript
export async function POST(req: Request) {
  const event = await verifyWebhook(req) // fast — just signature check

  // Queue for async processing
  await queue.add('stripe-event', { eventId: event.id, type: event.type })

  // Acknowledge to Stripe immediately — prevents retry
  return Response.json({ received: true })
}
```

Stripe retries with exponential backoff if it doesn't receive a 2xx within 30 seconds.

### Duplicate Webhook Events
**Cause:** Stripe guarantees at-least-once delivery.
**Solution:** Always check order/event status before processing. See `stripe-integration.md` webhook idempotency section.

---

## Rate Limits

### Stripe API Rate Limits
**Stripe limit:** 100 requests/second in test, 25 in live mode (per account).
**Symptoms:** `429 Too Many Requests` from Stripe SDK.

```typescript
// Implement retry with exponential backoff
async function stripeWithRetry<T>(
  fn: () => Promise<T>,
  maxRetries = 3
): Promise<T> {
  for (let attempt = 0; attempt <= maxRetries; attempt++) {
    try {
      return await fn()
    } catch (err) {
      if (err instanceof Stripe.errors.StripeRateLimitError && attempt < maxRetries) {
        const delay = Math.pow(2, attempt) * 1000 + Math.random() * 1000
        await new Promise(resolve => setTimeout(resolve, delay))
        continue
      }
      throw err
    }
  }
  throw new Error('Max retries exceeded')
}
```

### Database Connection Pool Exhausted
**Cause:** Too many concurrent requests, connection pool too small.
**Symptoms:** Prisma throws `P2024` (connection pool timeout).

```typescript
// prisma/schema.prisma
datasource db {
  provider  = "postgresql"
  url       = env("DATABASE_URL")
  // Increase pool size for high-traffic checkout flows
  // connection_limit and pool_timeout via URL params
}
```

Add `?connection_limit=20&pool_timeout=10` to `DATABASE_URL` for higher-traffic sites.

---

## Error Response Patterns

Consistent error shapes make client-side error handling predictable:

```typescript
// types/api.ts
interface ApiSuccess<T> {
  success: true
  data: T
}

interface ApiError {
  success: false
  error: string
  code?: string    // machine-readable code for programmatic handling
  field?: string   // which form field caused the error, if applicable
}

type ApiResponse<T> = ApiSuccess<T> | ApiError

// Usage in Server Action
export async function processCheckout(
  cartId: string
): Promise<ApiResponse<{ orderId: string }>> {
  try {
    const { valid, outOfStock } = await validateCartStock(cartId)
    if (!valid) {
      return {
        success: false,
        error: `${outOfStock[0].name} is out of stock`,
        code: 'OUT_OF_STOCK',
      }
    }
    const order = await createOrder(cartId)
    return { success: true, data: { orderId: order.id } }
  } catch (err) {
    console.error('Checkout error:', err)
    return { success: false, error: 'Checkout failed. Please try again.', code: 'INTERNAL' }
  }
}
```
