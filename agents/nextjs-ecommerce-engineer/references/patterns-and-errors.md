# Next.js E-commerce Patterns and Errors

Inline e-commerce implementation snippets, error catalog summary, anti-patterns, and domain-specific rationalizations. Loaded when implementing cart/Stripe/checkout features. Deeper patterns live in sibling references.

## Shopping Cart Implementation

See [shopping-cart-patterns.md](shopping-cart-patterns.md) for complete implementation.

**Server Component (cart display)**:
```typescript
// app/cart/page.tsx
import { getCart } from '@/lib/cart'

export default async function CartPage() {
  const cart = await getCart() // Server-side cart fetch
  return <CartDisplay items={cart.items} />
}
```

**Client Component (cart updates)**:
```typescript
// components/AddToCartButton.tsx
'use client'
import { addToCart } from '@/actions/cart'

export function AddToCartButton({ productId }: { productId: string }) {
  return (
    <button onClick={() => addToCart(productId)}>
      Add to Cart
    </button>
  )
}
```

**Server Action (cart mutation)**:
```typescript
// actions/cart.ts
'use server'
export async function addToCart(productId: string) {
  const cart = await getCart()
  await db.cartItem.create({
    data: { cartId: cart.id, productId, quantity: 1 }
  })
  revalidatePath('/cart')
}
```

## Stripe Integration

See [stripe-integration.md](stripe-integration.md) for complete implementation.

**Payment Intent Creation**:
```typescript
// app/api/checkout/route.ts
import Stripe from 'stripe'
const stripe = new Stripe(process.env.STRIPE_SECRET_KEY!)

export async function POST(req: Request) {
  const { amount } = await req.json()

  const paymentIntent = await stripe.paymentIntents.create({
    amount: amount * 100, // Convert to cents
    currency: 'usd',
    metadata: { orderId: '...' }
  })

  return Response.json({ clientSecret: paymentIntent.client_secret })
}
```

**Webhook Handler**:
```typescript
// app/api/webhooks/stripe/route.ts
import { headers } from 'next/headers'

export async function POST(req: Request) {
  const body = await req.text()
  const signature = headers().get('stripe-signature')!

  const event = stripe.webhooks.constructEvent(
    body,
    signature,
    process.env.STRIPE_WEBHOOK_SECRET!
  )

  if (event.type === 'payment_intent.succeeded') {
    const paymentIntent = event.data.object
    await fulfillOrder(paymentIntent.metadata.orderId)
  }

  return Response.json({ received: true })
}
```

## Error Handling

Common e-commerce errors. See [error-catalog.md](error-catalog.md) for comprehensive catalog.

### Stripe Webhook Signature Verification Failed
**Cause**: Webhook secret mismatch or invalid signature
**Solution**: Verify STRIPE_WEBHOOK_SECRET matches Stripe dashboard, use raw body (not parsed JSON)

### Inventory Oversold
**Cause**: No stock validation before order creation
**Solution**: Use Prisma transaction to check stock and decrement atomically

### Payment Intent Already Succeeded
**Cause**: Duplicate webhook events processed
**Solution**: Implement idempotency with order status checks

## Preferred Patterns

Common e-commerce mistakes and corrections. See [anti-patterns.md](anti-patterns.md) for full catalog.

### ❌ Storing Credit Card Data
**What it looks like**: Saving card numbers in database
**Why wrong**: PCI compliance violation, security risk
**✅ Do instead**: Use Stripe tokens exclusively for payment data

### ❌ Client-Side Price Calculation
**What it looks like**: Computing total in React component
**Why wrong**: Prices can be manipulated by client
**✅ Do instead**: Calculate prices server-side, validate in API route

### ❌ No Inventory Validation
**What it looks like**: Creating orders without checking stock
**Why wrong**: Overselling, disappointed customers
**✅ Do instead**: Validate stock in transaction before order creation

## Anti-Rationalization

See [shared-patterns/anti-rationalization-core.md](../../skills/shared-patterns/anti-rationalization-core.md) for universal patterns.

### Domain-Specific Rationalizations

| Rationalization Attempt | Why It's Wrong | Required Action |
|------------------------|----------------|-----------------|
| "Stripe test mode is enough for production" | Test mode keys won't process real payments | Use production keys for live site |
| "Client-side validation prevents invalid prices" | Client can be manipulated | Always validate prices server-side |
| "Checking stock once is sufficient" | Race conditions cause overselling | Use database transaction for atomic check+decrement |
| "Webhook might fire twice, that's rare" | Webhooks DO fire multiple times | Implement idempotency checks |
| "localhost webhook testing isn't needed" | Production issues are expensive | Use Stripe CLI for local webhook testing |

## Blocker Criteria

STOP and ask the user (get explicit confirmation) when:

| Situation | Why Stop | Ask This |
|-----------|----------|----------|
| Multiple payment providers requested | Different integration patterns | "Use Stripe, PayPal, or both? Different implementations needed." |
| Complex tax requirements | May need specialized service | "Manual tax calculation or integrate TaxJar/Avalara?" |
| Multi-currency needed | Affects pricing strategy | "Which currencies to support? Fixed rates or dynamic conversion?" |
| Subscription vs one-time unclear | Different Stripe products | "One-time purchases, subscriptions, or both?" |

### Always Confirm Before Acting On
- Payment provider selection (Stripe vs PayPal vs Square)
- Tax calculation strategy (manual vs service)
- Currency handling approach (single vs multi-currency)
- Subscription billing intervals (monthly vs annual vs custom)
