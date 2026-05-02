# Next.js E-commerce Patterns and Errors

Inline cart/Stripe/checkout snippets, error summary, anti-patterns, and rationalizations. Deeper patterns in sibling references.

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

See [error-catalog.md](error-catalog.md) for full catalog.

| Error | Cause | Fix |
|-------|-------|-----|
| Webhook signature verification failed | Secret mismatch or invalid sig | Verify STRIPE_WEBHOOK_SECRET, use raw body (not parsed JSON) |
| Inventory oversold | No stock validation before order | Prisma transaction: check stock and decrement atomically |
| Payment Intent already succeeded | Duplicate webhook events | Implement idempotency with order status checks |

## Preferred Patterns

See [preferred-patterns.md](preferred-patterns.md) for full catalog.

| Signal | Risk | Fix |
|--------|------|-----|
| Saving card numbers in DB | PCI violation | Use Stripe tokens exclusively |
| Computing total in React component | Client can manipulate prices | Calculate prices server-side |
| Creating orders without checking stock | Overselling | Validate stock in transaction before order creation |

## Anti-Rationalization

See [shared-patterns/anti-rationalization-core.md](../../skills/shared-patterns/anti-rationalization-core.md) for universal patterns.

| Rationalization | Why Wrong | Required Action |
|----------------|-----------|-----------------|
| "Stripe test mode is enough for production" | Test keys won't process real payments | Use production keys for live site |
| "Client-side validation prevents invalid prices" | Client can be manipulated | Validate prices server-side |
| "Checking stock once is sufficient" | Race conditions cause overselling | Atomic transaction for check+decrement |
| "Webhook might fire twice, that's rare" | Webhooks DO fire multiple times | Implement idempotency checks |
| "localhost webhook testing isn't needed" | Production issues are expensive | Use Stripe CLI for local testing |

## Blocker Criteria

STOP and ask the user when:

| Situation | Ask This |
|-----------|----------|
| Multiple payment providers requested | "Use Stripe, PayPal, or both?" |
| Complex tax requirements | "Manual tax calculation or integrate TaxJar/Avalara?" |
| Multi-currency needed | "Which currencies? Fixed rates or dynamic conversion?" |
| Subscription vs one-time unclear | "One-time purchases, subscriptions, or both?" |
